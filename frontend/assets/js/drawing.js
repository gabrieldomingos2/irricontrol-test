// assets/js/drawing.js

// --- Definições de Ícones ---
const TORRE_ICON_PATH = '/assets/images/cloudrf.png';
const BOMBA_ICON_AZUL_PATH = '/assets/images/homegardenbusiness.png';
const BOMBA_ICON_VERMELHO_PATH = '/assets/images/homegardenbusiness-red.png';
const ATTENTION_ICON_PATH = '/assets/images/attention-icon-original.svg';
const CHECK_ICON_PATH = '/assets/images/circle-check-big.svg';
const MOUNTAIN_ICON_PATH = '/assets/images/attention-icon-original.svg';
const CAPTIONS_ON_ICON_PATH = '/assets/images/captions.svg';
const CAPTIONS_OFF_ICON_PATH = '/assets/images/captions-off.svg';


const antenaIcon = L.icon({
  iconUrl: TORRE_ICON_PATH,
  iconSize: [28, 28],
  iconAnchor: [14, 28],
});

const bombaIconAzul = L.icon({
  iconUrl: BOMBA_ICON_AZUL_PATH,
  iconSize: [28, 28],
  iconAnchor: [14, 28],
});

const bombaIconVermelho = L.icon({
  iconUrl: BOMBA_ICON_VERMELHO_PATH,
  iconSize: [28, 28],
  iconAnchor: [14, 28],
});

const posicionamentoIcon = L.icon({
  iconUrl: TORRE_ICON_PATH,
  iconSize: [28, 28],
  iconAnchor: [14, 28],
  popupAnchor: [0, -30]
});

// As camadas agora são gerenciadas pelo AppState, mas a declaração da variável pode permanecer se for mais conveniente
let antenaCandidatesLayerGroup = L.layerGroup();
let tempSectorShape = null;


// --- FUNÇÃO AUXILIAR PARA MEDIÇÃO DINÂMICA ---
function findClosestSignalSource(targetLatLng) {
    let closestSource = null;
    let minDistance = Infinity;

    const antenaVisBtn = document.querySelector("#antena-item button[data-visible]");
    const isAntenaVisible = !antenaVisBtn || antenaVisBtn.getAttribute('data-visible') === 'true';

    if (AppState.antenaGlobal && isAntenaVisible) {
        const antenaLatLng = L.latLng(AppState.antenaGlobal.lat, AppState.antenaGlobal.lon);
        const distance = targetLatLng.distanceTo(antenaLatLng);
        if (distance < minDistance) {
            minDistance = distance;
            closestSource = {
                name: AppState.antenaGlobal.nome || 'Torre Principal',
                distance: distance
            };
        }
    }

    AppState.repetidoras.forEach(rep => {
        const repVisBtn = document.querySelector(`#rep-item-${rep.id} button[data-visible]`);
        const isRepVisible = !repVisBtn || repVisBtn.getAttribute('data-visible') === 'true';

        if (rep.marker && isRepVisible) {
            const repLatLng = rep.marker.getLatLng();
            const distance = targetLatLng.distanceTo(repLatLng);
            if (distance < minDistance) {
                minDistance = distance;
                closestSource = {
                    name: rep.label.options.icon.options.html,
                    distance: distance
                };
            }
        }
    });

    return closestSource;
}


// --- Funções de Desenho ---

function drawAntenaCandidates(antenasList) {
    if (!map) return;
    antenaCandidatesLayerGroup.clearLayers();
    if (!map.hasLayer(antenaCandidatesLayerGroup)) {
        antenaCandidatesLayerGroup.addTo(map);
    }
    antenasList.forEach(antenaData => {
        const uniqueId = `candidate-${antenaData.nome}-${antenaData.lat}`;
        const marker = L.marker([antenaData.lat, antenaData.lon], { icon: antenaIcon, customData: antenaData, customId: uniqueId }).addTo(antenaCandidatesLayerGroup);
        const nomeAntena = antenaData.nome;
        const label = L.marker([antenaData.lat, antenaData.lon], {
            icon: L.divIcon({ className: 'label-pivo', html: nomeAntena, iconSize: [(nomeAntena.length * 7) + 10, 20], iconAnchor: [((nomeAntena.length * 7) + 10) / 2, 45] }),
            interactive: false, customId: uniqueId
        }).addTo(antenaCandidatesLayerGroup);
        
        marker.on('click', (e) => {
            L.DomEvent.stopPropagation(e);
            const data = e.target.options.customData;
            AppState.coordenadaClicada = e.latlng;
            window.clickedCandidateData = data; // Manter como window temporariamente por ser um dado de clique transitório
            const painelRepetidora = document.getElementById("painel-repetidora");
            const inputAltura = document.getElementById("altura-antena-rep");
            if (painelRepetidora && inputAltura) {
                inputAltura.value = data.altura;
                painelRepetidora.classList.remove("hidden");
                mostrarMensagem(t('messages.success.tower_selected_for_simulation', { name: data.nome }), "sucesso");
            }
        });
    });
}

function drawPivos(pivosData, useEdited = false) {
    if (!map || !pivosData) return;

    AppState.marcadoresPivos.forEach(m => map.removeLayer(m));
    AppState.marcadoresPivos = [];
    AppState.pivotsMap = {};
    const legendasRestantes = AppState.marcadoresLegenda.filter(l => l.options.labelType !== 'pivot');
    AppState.marcadoresLegenda.filter(l => l.options.labelType === 'pivot').forEach(l => map.removeLayer(l));
    AppState.marcadoresLegenda = legendasRestantes;

    pivosData.forEach(pivo => {
        const cor = pivo.fora ? 'red' : 'green';
        const pos = useEdited && AppState.posicoesEditadas[pivo.nome] ? L.latLng(AppState.posicoesEditadas[pivo.nome].lat, AppState.posicoesEditadas[pivo.nome].lng) : L.latLng(pivo.lat, pivo.lon);
        const marker = L.circleMarker(pos, { radius: 8, color: cor, fillColor: cor, fillOpacity: 0.7, weight: 2 }).addTo(map);

        let finalHtml = pivo.nome;
        let hasDistancia = false;
        let labelWidth = (pivo.nome.length * 6.5) + 15;

        if (AppState.distanciasPivosVisiveis) {
            const closest = findClosestSignalSource(pos);
            if (closest) {
                const distanciaFormatada = closest.distance > 999 ? (closest.distance / 1000).toFixed(1) + ' km' : Math.round(closest.distance) + ' m';
                finalHtml = `${pivo.nome}<br><span class="source-name-pivo">${closest.name}</span><br><span class="distancia-pivo">${distanciaFormatada}</span>`;
                hasDistancia = true;
                labelWidth = Math.max(labelWidth, (closest.name.length * 6.5) + 15);
            }
        }

        const labelHeight = hasDistancia ? 55 : 20;
        const label = L.marker(pos, {
            icon: L.divIcon({ className: 'label-pivo', html: finalHtml, iconSize: [labelWidth, labelHeight], iconAnchor: [labelWidth / 2, -15] }),
            labelType: 'pivot'
        }).addTo(map);
        AppState.marcadoresLegenda.push(label);
        
        const statusTexto = pivo.fora ? `<span style="color:#ff4d4d; font-weight:bold;">${t('tooltips.out_of_signal')}</span>` : `<span style="color:#22c55e; font-weight:bold;">${t('tooltips.in_signal')}</span>`;
        marker.bindTooltip(`<div style="text-align:center;">${statusTexto}</div>`, { permanent: false, direction: 'top', offset: [0, -15], className: 'tooltip-sinal' });

        marker.on('click', (e) => {
            L.DomEvent.stopPropagation(e);
            if (AppState.modoEdicaoPivos) {
                 marker.bindPopup(`<div class="popup-glass">✏️ ${pivo.fora ? t('tooltips.out_of_signal') : t('tooltips.in_signal')}</div>`).openPopup();
            } else if (AppState.modoLoSPivotAPivot) {
                if (typeof handleLoSPivotClick === 'function') handleLoSPivotClick(pivo, marker);
            } else if (AppState.modoBuscaLocalRepetidora) {
                if (typeof handlePivotSelectionForRepeaterSite === 'function') handlePivotSelectionForRepeaterSite(pivo, marker);
            } else {
                window.ultimoCliqueFoiSobrePivo = true; // Dado transitório
                AppState.coordenadaClicada = e.latlng;
                removePositioningMarker();
                document.getElementById("painel-repetidora")?.classList.remove("hidden");
            }
        });
        
        AppState.marcadoresPivos.push(marker);
        AppState.pivotsMap[pivo.nome] = marker;

        marker.on('contextmenu', (e) => {
            L.DomEvent.stop(e);
            if (AppState.modoEdicaoPivos) return;

            if (confirm(t('messages.confirm.remove_pivot', { name: pivo.nome }))) {
                const nomeCicloParaRemover = `Ciclo ${pivo.nome}`;
                AppState.lastPivosDataDrawn = AppState.lastPivosDataDrawn.filter(p => p.nome !== pivo.nome);
                AppState.ciclosGlobais = AppState.ciclosGlobais.filter(c => c.nome_original_circulo !== nomeCicloParaRemover);
                if (AppState.currentProcessedKmzData?.pivos) AppState.currentProcessedKmzData.pivos = AppState.currentProcessedKmzData.pivos.filter(p => p.nome !== pivo.nome);
                if (AppState.currentProcessedKmzData?.ciclos) AppState.currentProcessedKmzData.ciclos = AppState.currentProcessedKmzData.ciclos.filter(c => c.nome_original_circulo !== nomeCicloParaRemover);
                drawPivos(AppState.lastPivosDataDrawn, false);
                drawCirculos(AppState.ciclosGlobais);
                atualizarPainelDados();
                mostrarMensagem(t('messages.success.pivot_removed', { name: pivo.nome }), 'sucesso');
            }
        });
    });
    toggleLegendas(AppState.legendasAtivas);
}


function drawBombas(bombasData) {
    if (!map || !bombasData) return;

    AppState.marcadoresBombas.forEach(b => map.removeLayer(b));
    AppState.marcadoresBombas = [];
    const legendasRestantes = AppState.marcadoresLegenda.filter(m => m.options.labelType !== 'bomba');
    AppState.marcadoresLegenda.filter(l => l.options.labelType === 'bomba').forEach(l => map.removeLayer(l));
    AppState.marcadoresLegenda = legendasRestantes;

    bombasData.forEach((bomba, i) => {
        const icone = bomba.fora === false ? bombaIconAzul : bombaIconVermelho;
        const marcadorBomba = L.marker([bomba.lat, bomba.lon], { icon: icone }).addTo(map);
        AppState.marcadoresBombas.push(marcadorBomba);

        const statusTexto = bomba.fora === false ? `<span style="color:#22c55e;">${t('tooltips.in_signal')}</span>` : `<span style="color:#ff4d4d;">${t('tooltips.out_of_signal')}</span>`;
        marcadorBomba.bindTooltip(`<div style="text-align: center;">${statusTexto}</div>`, { permanent: false, direction: 'top', offset: [0, -28], className: 'tooltip-sinal' });

        const nomeBomba = `Irripump ${String(i + 1).padStart(2, '0')}`;
        let finalHtml = nomeBomba;
        let hasDistancia = false;
        let labelWidth = (nomeBomba.length * 6.5) + 15;

        if (AppState.distanciasPivosVisiveis) {
            const closest = findClosestSignalSource(L.latLng(bomba.lat, bomba.lon));
            if (closest) {
                const distanciaFormatada = closest.distance > 999 ? (closest.distance / 1000).toFixed(1) + ' km' : Math.round(closest.distance) + ' m';
                finalHtml = `${nomeBomba}<br><span class="source-name-pivo">${closest.name}</span><br><span class="distancia-pivo">${distanciaFormatada}</span>`;
                hasDistancia = true;
                labelWidth = Math.max(labelWidth, (closest.name.length * 6.5) + 15);
            }
        }
        
        const labelHeight = hasDistancia ? 55 : 20;
        const labelBomba = L.marker([bomba.lat, bomba.lon], {
            icon: L.divIcon({ className: 'label-pivo', html: finalHtml, iconSize: [labelWidth, labelHeight], iconAnchor: [labelWidth / 2, -5] }),
            labelType: 'bomba', interactive: false
        }).addTo(map);
        AppState.marcadoresLegenda.push(labelBomba);
    });
    toggleLegendas(AppState.legendasAtivas);
}


function drawCirculos(ciclosData) {
    if (!map) return;
    AppState.circulosPivos.forEach(c => map.removeLayer(c));
    AppState.circulosPivos = [];

    AppState.lastPivosDataDrawn.forEach(pivo => {
        if (pivo.tipo === 'setorial') {
            const sectorCoords = generateSectorCoords(L.latLng(pivo.lat, pivo.lon), pivo.raio, pivo.angulo_central, pivo.abertura_arco);
            const sectorPolygon = L.polygon(sectorCoords, { color: '#cc0000', weight: 2, opacity: 0.9, fillOpacity: 0, className: 'circulo-pivo-setorial' }).addTo(map);
            AppState.circulosPivos.push(sectorPolygon);
        }
    });

    const ciclosCirculares = ciclosData.filter(ciclo => {
        const nomePivo = ciclo.nome_original_circulo.replace('Ciclo ', '');
        const pivoCorrespondente = AppState.lastPivosDataDrawn.find(p => p.nome === nomePivo);
        return !pivoCorrespondente || pivoCorrespondente.tipo !== 'setorial';
    });

    AppState.circulosPivos.push(...ciclosCirculares.map(circulo =>
        L.polygon(circulo.coordenadas, { color: '#cc0000', weight: 2, opacity: 0.9, fillOpacity: 0, className: 'circulo-vermelho-pulsante' }).addTo(map)
    ));
}

function drawImageOverlay(url, bounds, opacity = 1.0) {
    if (!map || !url || !bounds) return null;
    const imageBounds = [[bounds[0], bounds[1]], [bounds[2], bounds[3]]];
    const overlay = L.imageOverlay(url, imageBounds, { opacity, interactive: false }).addTo(map);
    AppState.overlaysVisiveis.push(overlay);
    return overlay;
}


function addRepetidoraNoPainel(repetidora) {
    const container = document.getElementById("lista-repetidoras");
    const item = document.createElement("div");
    item.className = "flex justify-between items-center bg-gray-800/60 px-3 py-2 rounded-lg border border-white/10";
    item.id = `rep-item-${repetidora.id}`;
    item.innerHTML = `
        <span class="text-white/80 text-sm">${repetidora.label.options.icon.options.html}</span>
        <div class="flex gap-3 items-center">
            <button class="text-white/60 hover:text-sky-300 transition relative top-px" title="${t('tooltips.run_diagnostic_from_source')}" data-id="${repetidora.id}" data-action="diagnostico">
                <i data-lucide="activity" class="w-4 h-4"></i>
            </button>
            <button class="text-white/60 hover:text-sky-300 transition" title="${t('tooltips.show_hide_coverage')}" data-id="${repetidora.id}" data-action="toggle-visibility" data-visible="true">
                <i data-lucide="eye" class="w-4 h-4 text-green-500"></i>
            </button>
            <button class="text-red-500 hover:text-red-400 text-xs font-bold transition" title="Remover Repetidora" data-id="${repetidora.id}" data-action="remover">
                ❌
            </button>
        </div>`;
    
    container.appendChild(item);
    lucide.createIcons();

    // Adiciona os event listeners de forma delegada ou direta
    item.querySelector('[data-action="diagnostico"]').addEventListener('click', () => runTargetedDiagnostic(repetidora));
    item.querySelector('[data-action="remover"]').addEventListener('click', () => {
        map.removeLayer(repetidora.marker);
        if (repetidora.overlay) map.removeLayer(repetidora.overlay);
        if (repetidora.label) map.removeLayer(repetidora.label);
        container.removeChild(item);
        AppState.idsDisponiveis.push(repetidora.id);
        AppState.idsDisponiveis.sort((a, b) => a - b);
        AppState.repetidoras = AppState.repetidoras.filter(r => r.id !== repetidora.id);
        AppState.overlaysVisiveis = AppState.overlaysVisiveis.filter(o => o !== repetidora.overlay);
        AppState.marcadoresLegenda = AppState.marcadoresLegenda.filter(l => l !== repetidora.label);
        atualizarPainelDados();
        setTimeout(reavaliarPivosViaAPI, 100);
    });

    const visibilityBtn = item.querySelector('[data-action="toggle-visibility"]');
    visibilityBtn.addEventListener('click', () => {
        const isVisible = visibilityBtn.getAttribute('data-visible') === 'true';
        const newState = !isVisible;
        visibilityBtn.setAttribute('data-visible', String(newState));
        const opacityValue = parseFloat(document.getElementById("range-opacidade").value);
        
        if (repetidora.marker) repetidora.marker.setOpacity(newState ? 1 : 0);
        if (repetidora.label?.getElement()) repetidora.label.getElement().style.display = (newState && AppState.legendasAtivas) ? '' : 'none';
        if (repetidora.overlay) repetidora.overlay.setOpacity(newState ? opacityValue : 0);
        
        visibilityBtn.innerHTML = newState ? `<i data-lucide="eye" class="w-4 h-4 text-green-500"></i>` : `<i data-lucide="eye-off" class="w-4 h-4 text-gray-500"></i>`;
        lucide.createIcons();
        setTimeout(reavaliarPivosViaAPI, 100);
    });
}

function addAntenaAoPainel(antena) {
    document.getElementById("antena-item")?.remove();
    const container = document.getElementById("lista-repetidoras");
    const item = document.createElement("div");
    item.className = "flex justify-between items-center bg-gray-700/60 px-3 py-2 rounded-lg border border-white/10";
    item.id = `antena-item`;
    item.innerHTML = `
        <span class="text-white/90 font-semibold text-sm">${antena.nome || t('ui.labels.main_antenna_default')}</span>
        <div class="flex gap-3 items-center">
            <button class="text-white/60 hover:text-sky-300 transition relative top-px" title="${t('tooltips.run_diagnostic_from_source')}" data-action="diagnostico">
                 <i data-lucide="activity" class="w-4 h-4"></i>
            </button>
            <button class="text-white/60 hover:text-sky-300 transition" title="${t('tooltips.show_hide_coverage')}" data-action="toggle-visibility" data-visible="true">
                <i data-lucide="eye" class="w-4 h-4 text-green-500"></i>
            </button>
        </div>`;
    
    container.firstChild ? container.insertBefore(item, container.firstChild) : container.appendChild(item);
    lucide.createIcons();

    item.querySelector('[data-action="diagnostico"]').addEventListener('click', () => runTargetedDiagnostic(antena));
    const visibilityBtn = item.querySelector('[data-action="toggle-visibility"]');
    visibilityBtn.addEventListener('click', () => {
        const isVisible = visibilityBtn.getAttribute('data-visible') === 'true';
        const newState = !isVisible;
        visibilityBtn.setAttribute('data-visible', String(newState));
        
        const opacityValue = parseFloat(rangeOpacidade.value);
        if (antena?.overlay) antena.overlay.setOpacity(newState ? opacityValue : 0);
        if (AppState.marcadorAntena) AppState.marcadorAntena.setOpacity(newState ? 1 : 0);
        
        visibilityBtn.innerHTML = newState ? `<i data-lucide="eye" class="w-4 h-4 text-green-500"></i>` : `<i data-lucide="eye-off" class="w-4 h-4 text-gray-500"></i>`;
        lucide.createIcons();
        setTimeout(reavaliarPivosViaAPI, 100);
    });
}

function drawDiagnostico(latlonOrigem, latlonDestino, dadosBloqueioAPI, dadosPontoMaisAlto, nomeDiagnostico, distanciaFormatada = null) {
    if (!map || !AppState.visadaLayerGroup) return;
    const linha = drawVisadaComGradiente(latlonOrigem, latlonDestino);
    let pontoParaMarcador = null;
    let mensagemTooltip = `<strong>${nomeDiagnostico}</strong>`;
    let iconUrl = CHECK_ICON_PATH, iconSize = [22, 22];

    if (distanciaFormatada) mensagemTooltip += `<br>${t('ui.labels.pivo_distance_label')} ${distanciaFormatada}`;

    if (dadosBloqueioAPI?.lat && typeof dadosBloqueioAPI.diff === 'number') {
        pontoParaMarcador = dadosBloqueioAPI;
        mensagemTooltip += `<br>${t('tooltips.blockage_point', { elevation: pontoParaMarcador.elev.toFixed(1) })}`;
        if (dadosBloqueioAPI.diff > 0.1) {
            iconUrl = ATTENTION_ICON_PATH; iconSize = [24, 24];
            mensagemTooltip += `<br><span style="color: #FF9800;">${t('tooltips.blockage_present', { diff: dadosBloqueioAPI.diff.toFixed(1) })}</span>`;
        } else if (distanciaFormatada) {
            mensagemTooltip += `<br><span style="color: #4CAF50;">${t('tooltips.los_clear_at_critical_point', { diff: dadosBloqueioAPI.diff.toFixed(1) })}</span>`;
        }
    } else if (dadosPontoMaisAlto?.lat) {
        pontoParaMarcador = dadosPontoMaisAlto;
        iconUrl = MOUNTAIN_ICON_PATH; iconSize = [20, 20];
        mensagemTooltip += `<br>${t('tooltips.highest_point', { elevation: pontoParaMarcador.elev.toFixed(1) })}`;
    }

    if (pontoParaMarcador && (distanciaFormatada ? !!dadosBloqueioAPI : true)) {
        const markerIcon = L.divIcon({
            className: 'label-bloqueio-dinamico',
            html: `<img src="${iconUrl}" style="width:${iconSize[0]}px; height:${iconSize[1]}px;">`,
            iconSize: iconSize, iconAnchor: [iconSize[0]/2, iconSize[1]/2]
        });
        const marker = L.marker([pontoParaMarcador.lat, pontoParaMarcador.lon], { icon: markerIcon })
            .addTo(AppState.visadaLayerGroup)
            .bindTooltip(mensagemTooltip, { permanent: false, direction: 'top', className: 'tooltip-sinal tooltip-visada-diagnostico', offset: [0, -(iconSize[1]/2 + 5)] });
        AppState.marcadoresBloqueio.push(marker);
    }
    AppState.linhasDiagnostico.push(linha);
}

function clearMapLayers() {
    if (!map) return;
    
    // Lista de todas as camadas a serem limpas/removidas
    const layersAndGroups = [
        AppState.marcadorAntena, 
        antenaCandidatesLayerGroup, 
        AppState.marcadorPosicionamento,
        AppState.visadaLayerGroup,
        window.candidateRepeaterSitesLayerGroup, // Assumindo que este será migrado também
        ...(AppState.marcadoresPivos || []),
        ...(AppState.circulosPivos || []),
        ...(AppState.marcadoresBombas || []),
        ...(AppState.marcadoresLegenda || []),
        ...Object.values(AppState.pivotsMap || {})
    ];

    layersAndGroups.forEach(layer => {
        if (!layer) return;
        if (typeof layer.clearLayers === 'function') {
            layer.clearLayers();
        } else if (map.hasLayer(layer)) {
            map.removeLayer(layer);
        }
    });

    AppState.repetidoras.forEach(r => {
        if (r.marker) map.removeLayer(r.marker);
        if (r.overlay) map.removeLayer(r.overlay);
        if (r.label) map.removeLayer(r.label);
    });
    if (AppState.antenaGlobal?.overlay) map.removeLayer(AppState.antenaGlobal.overlay);

    // O reset do estado já limpa os arrays, então não precisamos fazer aqui.
}


function toggleLegendas(show) {
    AppState.legendasAtivas = show;
    const toggleBtn = document.getElementById("toggle-legenda");
    if (!toggleBtn) return;

    toggleBtn.classList.toggle("glass-button-active", !show);
    toggleBtn.title = show ? t('tooltips.hide_legends') : t('tooltips.show_legends');
    const iconSpan = toggleBtn.querySelector('.sidebar-icon');
    if (iconSpan) {
        const iconPath = show ? CAPTIONS_ON_ICON_PATH : CAPTIONS_OFF_ICON_PATH;
        iconSpan.style.webkitMaskImage = `url(${iconPath})`;
        iconSpan.style.maskImage = `url(${iconPath})`;
    }

    AppState.marcadoresLegenda.forEach(m => {
        const el = m.getElement?.();
        if (el) el.style.display = show ? '' : 'none';
    });
}

function updateOverlaysOpacity(opacityValue) {
    const isPanelItemVisible = (overlay) => {
        let visibilityBtn = null;
        if (AppState.antenaGlobal?.overlay === overlay) {
            visibilityBtn = document.querySelector("#antena-item button[data-visible]");
        } else {
            const rep = AppState.repetidoras.find(r => r.overlay === overlay);
            if (rep) visibilityBtn = document.querySelector(`#rep-item-${rep.id} button[data-visible]`);
        }
        return !visibilityBtn || visibilityBtn.getAttribute('data-visible') === 'true';
    };

    AppState.overlaysVisiveis.forEach(overlay => {
        if (map.hasLayer(overlay)) {
            overlay.setOpacity(isPanelItemVisible(overlay) ? opacityValue : 0);
        }
    });
}

function criarGradienteVisada(id = 'gradient-visada') {
    const svgPane = map.getPane('overlayPane');
    let svg = svgPane.querySelector('svg');
    if (!svg) {
        // Truque para forçar a criação do SVG do Leaflet
        const tempLayer = L.polyline([[0,0],[0,0]]).addTo(map);
        svg = svgPane.querySelector('svg');
        map.removeLayer(tempLayer);
        if(!svg) return;
    }
    if (svg.querySelector(`#${id}`)) return;
    
    let defs = svg.querySelector('defs') || document.createElementNS("http://www.w3.org/2000/svg", "defs");
    const gradient = document.createElementNS("http://www.w3.org/2000/svg", "linearGradient");
    gradient.setAttribute("id", id);
    gradient.innerHTML = `<stop offset="0%" stop-color="green"/><stop offset="50%" stop-color="yellow"/><stop offset="100%" stop-color="red"/>`;
    defs.appendChild(gradient);
    svg.insertBefore(defs, svg.firstChild);
}

function drawVisadaComGradiente(pontoA, pontoB) {
    criarGradienteVisada();
    return L.polyline([pontoA, pontoB], {
        renderer: L.svg(),
        color: `url(#gradient-visada)`,
        weight: 2,
        opacity: AppState.visadaVisivel ? 1 : 0.5,
        dashArray: '8 8'
    }).addTo(AppState.visadaLayerGroup);
}

function drawCandidateRepeaterSites(sites, targetPivotData) {
    if (!map || !window.candidateRepeaterSitesLayerGroup) return;
    
    window.candidateRepeaterSitesLayerGroup.clearLayers();
    if (!sites || sites.length === 0) return;

    sites.forEach((site, index) => {
        if (typeof site.lat === 'undefined') return;
        const siteLatLng = [site.lat, site.lon];
        const uniqueMarkerId = `candidate-${index}-${site.lat.toFixed(5)}`;
        const iconHtml = `
            <div class="candidate-icon-wrapper">
                ⛰️ ${(site.elevation || 0).toFixed(1)}m
                ${site.has_los ? `<span class="los-ok">${t('tooltips.los_ok')}</span>` : `<span class="los-no">${t('tooltips.los_no')}</span>`}
                <br><span class="distancia-info">${t('ui.labels.pivo_distance_label')} ${site.distance_to_target ? site.distance_to_target.toFixed(0) + 'm' : 'N/A'}</span>
            </div>`;
        const candidateIcon = L.divIcon({
            className: 'custom-div-icon-ponto-alto',
            html: iconHtml,
            iconSize: [95, 48], iconAnchor: [47.5, 24]
        });
        const marker = L.marker(siteLatLng, { icon: candidateIcon, customId: uniqueMarkerId, interactive: false });
        marker.addTo(window.candidateRepeaterSitesLayerGroup);

        if (targetPivotData?.lat) {
            const targetLatLng = [targetPivotData.lat, targetPivotData.lon];
            const lineColor = site.has_los ? 'rgba(76, 175, 80, 0.7)' : 'rgba(255, 152, 0, 0.7)';
            const line = L.polyline([siteLatLng, targetLatLng], { color: lineColor, weight: 2, dashArray: '5, 5', opacity: 0.75, customId: uniqueMarkerId });
            line.addTo(window.candidateRepeaterSitesLayerGroup);
        }
    });
}

function togglePivoDistances(show) {
    if (AppState.lastPivosDataDrawn?.length > 0) {
        drawPivos(AppState.lastPivosDataDrawn, false); 
    }
    if (AppState.lastBombasDataDrawn?.length > 0) {
        drawBombas(AppState.lastBombasDataDrawn);
    }
    mostrarMensagem(t('messages.success.pivot_distances_toggled', { status: show ? t('labels.shown') : t('labels.hidden') }), 'sucesso');
}

let tempCircle = null;

function drawTempCircle(center, radiusPoint) {
    const radius = center.distanceTo(radiusPoint);
    if (tempCircle) {
        tempCircle.setLatLng(center).setRadius(radius);
    } else {
        tempCircle = L.circle(center, {
            radius: radius, color: '#3B82F6', weight: 2, dashArray: '5, 5',
            fillColor: '#3B82F6', fillOpacity: 0.1, interactive: false
        }).addTo(map);
    }
}

function removeTempCircle() {
    if (tempCircle) {
        map.removeLayer(tempCircle);
        tempCircle = null;
    }
}

function generateCircleCoords(center, radius, points = 60) {
    const coords = [];
    const earthRadius = 6378137;
    const lat = center.lat * (Math.PI / 180);
    const lon = center.lng * (Math.PI / 180);
    for (let i = 0; i < points; i++) {
        const bearing = (i / points) * 360 * (Math.PI / 180);
        const newLat = Math.asin(Math.sin(lat) * Math.cos(radius / earthRadius) + Math.cos(lat) * Math.sin(radius / earthRadius) * Math.cos(bearing));
        const newLon = lon + Math.atan2(Math.sin(bearing) * Math.sin(radius / earthRadius) * Math.cos(lat), Math.cos(radius / earthRadius) - Math.sin(lat) * Math.sin(newLat));
        coords.push([newLat * (180 / Math.PI), newLon * (180 / Math.PI)]);
    }
    coords.push(coords[0]);
    return coords;
}

function drawTempSector(center, currentPoint) {
    const radius = center.distanceTo(currentPoint);
    if (radius < 5) return;
    const bearing = calculateBearing(center, currentPoint);
    const coords = generateSectorCoords(center, radius, bearing, 180);
    if (tempSectorShape) {
        tempSectorShape.setLatLngs(coords);
    } else {
        tempSectorShape = L.polygon(coords, {
            color: '#3B82F6', weight: 2, dashArray: '8, 8',
            fillColor: '#3B82F6', fillOpacity: 0.2, interactive: false
        }).addTo(map);
    }
}

function removeTempSector() {
    if (tempSectorShape) {
        map.removeLayer(tempSectorShape);
        tempSectorShape = null;
    }
}

function calculateBearing(p1, p2) {
    const toRad = (deg) => deg * Math.PI / 180;
    const lat1 = toRad(p1.lat), lon1 = toRad(p1.lng);
    const lat2 = toRad(p2.lat), lon2 = toRad(p2.lng);
    const y = Math.sin(lon2 - lon1) * Math.cos(lat2);
    const x = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(lon2 - lon1);
    return (Math.atan2(y, x) * 180 / Math.PI + 360) % 360;
}

function generateSectorCoords(center, radius, mainAngle, arcAngle = 180) {
    const vertices = [[center.lat, center.lng]];
    const startAngle = mainAngle - (arcAngle / 2);
    const points = 40;
    for (let i = 0; i <= points; i++) {
        const angle = startAngle + (i * arcAngle / points);
        const point = L.latLng(center).destination(radius, angle);
        vertices.push([point.lat, point.lng]);
    }
    return vertices;
}

if (!L.LatLng.prototype.destination) {
    L.LatLng.prototype.destination = function(distance, bearing) {
        const R = 6378137;
        const toRad = (deg) => deg * Math.PI / 180;
        const toDeg = (rad) => rad * 180 / Math.PI;
        const brng = toRad(bearing);
        const lat1 = toRad(this.lat), lon1 = toRad(this.lng);
        const lat2 = Math.asin(Math.sin(lat1) * Math.cos(distance / R) + Math.cos(lat1) * Math.sin(distance / R) * Math.cos(brng));
        const lon2 = lon1 + Math.atan2(Math.sin(brng) * Math.sin(distance / R) * Math.cos(lat1), Math.cos(distance / R) - Math.sin(lat1) * Math.sin(lat2));
        return L.latLng(toDeg(lat2), toDeg(lon2));
    };
}