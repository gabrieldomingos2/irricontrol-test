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
  iconUrl: TORRE_ICON_PATH, // Usando o mesmo ícone da torre
  iconSize: [28, 28],
  iconAnchor: [14, 28],
  popupAnchor: [0, -30]
});

window.candidateRepeaterSitesLayerGroup = null; // Será inicializado no initMap (map.js)
let antenaCandidatesLayerGroup = L.layerGroup();
let tempSectorShape = null;


// --- NOVA FUNÇÃO AUXILIAR PARA MEDIÇÃO DINÂMICA ---

/**
 * Encontra a fonte de sinal ATIVA (antena principal ou repetidora) mais próxima de um dado ponto.
 * @param {L.LatLng} targetLatLng - As coordenadas do pivô ou bomba.
 * @returns {object|null} - Um objeto com { name, distance } da fonte mais próxima, ou null se nenhuma fonte estiver ativa.
 */
function findClosestSignalSource(targetLatLng) {
    let closestSource = null;
    let minDistance = Infinity;

    // 1. Verificar a Antena Principal
    const antenaCheckbox = document.querySelector("#antena-item input[type='checkbox']");
    if (window.antenaGlobal && (!antenaCheckbox || antenaCheckbox.checked)) {
        const antenaLatLng = L.latLng(window.antenaGlobal.lat, window.antenaGlobal.lon);
        const distance = targetLatLng.distanceTo(antenaLatLng);
        if (distance < minDistance) {
            minDistance = distance;
            closestSource = {
                name: window.antenaGlobal.nome || 'Torre Principal',
                distance: distance
            };
        }
    }

    // 2. Verificar TODAS as Repetidoras ativas
    repetidoras.forEach(rep => {
        const repCheckbox = document.querySelector(`#rep-item-${rep.id} input[type='checkbox']`);
        if (rep.marker && (!repCheckbox || repCheckbox.checked)) {
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
        const labelWidth = (nomeAntena.length * 7) + 10;
        const labelHeight = 20;
        const label = L.marker([antenaData.lat, antenaData.lon], {
            icon: L.divIcon({ className: 'label-pivo', html: nomeAntena, iconSize: [labelWidth, labelHeight], iconAnchor: [labelWidth / 2, 45] }),
            interactive: false, customId: uniqueId
        }).addTo(antenaCandidatesLayerGroup);
        marker.on('click', (e) => {
            L.DomEvent.stopPropagation(e);
            const data = e.target.options.customData;
            window.coordenadaClicada = e.latlng;
            window.clickedCandidateData = data;
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

    marcadoresPivos.forEach(m => map.removeLayer(m));
    marcadoresPivos = [];
    pivotsMap = {};
    const legendasRestantes = marcadoresLegenda.filter(l => l.options.labelType !== 'pivot');
    marcadoresLegenda.filter(l => l.options.labelType === 'pivot').forEach(l => map.removeLayer(l));
    marcadoresLegenda = legendasRestantes;

    pivosData.forEach(pivo => {
        const cor = pivo.fora ? 'red' : 'green';
        const pos = useEdited && posicoesEditadas[pivo.nome] ? L.latLng(posicoesEditadas[pivo.nome].lat, posicoesEditadas[pivo.nome].lng) : L.latLng(pivo.lat, pivo.lon);
        const marker = L.circleMarker(pos, { radius: 8, color: cor, fillColor: cor, fillOpacity: 0.7, weight: 2 }).addTo(map);

        const nomePivo = pivo.nome;
        let finalHtml = nomePivo;
        let hasDistancia = false;
        let labelWidth = (nomePivo.length * 6.5) + 15;

        if (window.distanciasPivosVisiveis) {
            const closest = findClosestSignalSource(pos);
            if (closest) {
                const nomeFonte = closest.name;
                const distanciaFormatada = closest.distance > 999 ? (closest.distance / 1000).toFixed(1) + ' km' : Math.round(closest.distance) + ' m';
                finalHtml = `${nomePivo}<br><span class="source-name-pivo">${nomeFonte}</span><br><span class="distancia-pivo">${distanciaFormatada}</span>`;
                hasDistancia = true;
                const sourceNameWidth = (nomeFonte.length * 6.5) + 15;
                labelWidth = Math.max(labelWidth, sourceNameWidth);
            }
        }

        const labelHeight = hasDistancia ? 55 : 20;
        const label = L.marker(pos, {
            icon: L.divIcon({ className: 'label-pivo', html: finalHtml, iconSize: [labelWidth, labelHeight], iconAnchor: [labelWidth / 2, -15] }),
            labelType: 'pivot'
        }).addTo(map);
        marcadoresLegenda.push(label);
        
        const statusTexto = pivo.fora ? `<span style="color:#ff4d4d; font-weight:bold;">${t('tooltips.out_of_signal')}</span>` : `<span style="color:#22c55e; font-weight:bold;">${t('tooltips.in_signal')}</span>`;
        marker.bindTooltip(`<div style="text-align:center;">${statusTexto}</div>`, { permanent: false, direction: 'top', offset: [0, -15], className: 'tooltip-sinal' });

        marker.on('click', (e) => {
            L.DomEvent.stopPropagation(e);
            if (window.modoEdicaoPivos) {
                marker.bindPopup(`<div class="popup-glass">✏️ ${pivo.fora ? t('tooltips.out_of_signal') : t('tooltips.in_signal')}</div>`).openPopup();
            } else if (window.modoLoSPivotAPivot) {
                if (typeof handleLoSPivotClick === 'function') handleLoSPivotClick(pivo, marker);
            } else if (window.modoBuscaLocalRepetidora) {
                if (typeof handlePivotSelectionForRepeaterSite === 'function') handlePivotSelectionForRepeaterSite(pivo, marker);
            } else {
                window.ultimoCliqueFoiSobrePivo = true;
                window.coordenadaClicada = e.latlng;
                if (typeof window.removePositioningMarker === 'function') window.removePositioningMarker();
                document.getElementById("painel-repetidora")?.classList.remove("hidden");
            }
        });
        marcadoresPivos.push(marker);
        pivotsMap[pivo.nome] = marker;

        marker.on('contextmenu', (e) => {
            L.DomEvent.stopPropagation(e);
            L.DomEvent.preventDefault(e);
            
            if (window.modoEdicaoPivos) return;

            if (confirm(t('messages.confirm.remove_pivot', { name: pivo.nome }))) {
                
                const nomeCicloParaRemover = `Ciclo ${pivo.nome}`;
                
                window.lastPivosDataDrawn = window.lastPivosDataDrawn.filter(p => p.nome !== pivo.nome);
                window.ciclosGlobais = window.ciclosGlobais.filter(c => c.nome_original_circulo !== nomeCicloParaRemover);
 
                if (window.currentProcessedKmzData?.pivos) {
                    window.currentProcessedKmzData.pivos = window.currentProcessedKmzData.pivos.filter(p => p.nome !== pivo.nome);
                }
                if (window.currentProcessedKmzData?.ciclos) {
                    window.currentProcessedKmzData.ciclos = window.currentProcessedKmzData.ciclos.filter(c => c.nome_original_circulo !== nomeCicloParaRemover);
                }

                drawPivos(window.lastPivosDataDrawn, false);
                drawCirculos(window.ciclosGlobais);

                atualizarPainelDados();
                mostrarMensagem(t('messages.success.pivot_removed', { name: pivo.nome }), 'sucesso');
            }
        });


    });
    toggleLegendas(legendasAtivas);
}


function drawBombas(bombasData) {
    if (!map || !bombasData) return;

    // Limpeza de camadas (código existente, sem alteração)
    marcadoresBombas.forEach(b => map.removeLayer(b));
    marcadoresBombas = [];
    const legendasRestantes = marcadoresLegenda.filter(m => m.options.labelType !== 'bomba');
    marcadoresLegenda.filter(l => l.options.labelType === 'bomba').forEach(l => map.removeLayer(l));
    marcadoresLegenda = legendasRestantes;

    bombasData.forEach(bomba => {
        const iconeASerUsado = bomba.fora === false ? bombaIconAzul : bombaIconVermelho;
        const marcadorBomba = L.marker([bomba.lat, bomba.lon], { icon: iconeASerUsado }).addTo(map);
        marcadoresBombas.push(marcadorBomba);

        const statusTexto = bomba.fora === false ? `<span style="color:#22c55e; font-weight:bold;">${t('tooltips.in_signal')}</span>` : `<span style="color:#ff4d4d; font-weight:bold;">${t('tooltips.out_of_signal')}</span>`;
        marcadorBomba.bindTooltip(`<div style="text-align: center;">${statusTexto}</div>`, { permanent: false, direction: 'top', offset: [0, -28], className: 'tooltip-sinal' });

        const nomeBomba = bomba.nome;
        let finalHtml = nomeBomba;
        let hasDistancia = false;
        let labelWidth = (nomeBomba.length * 6.5) + 15;

        if (window.distanciasPivosVisiveis) {
            const bombaLatLng = L.latLng(bomba.lat, bomba.lon);
            const closest = findClosestSignalSource(bombaLatLng);
            if (closest) {
                const nomeFonte = closest.name;
                const distanciaFormatada = closest.distance > 999 ? (closest.distance / 1000).toFixed(1) + ' km' : Math.round(closest.distance) + ' m';
                
                finalHtml = `${nomeBomba}<br><span class="source-name-pivo">${nomeFonte}</span><br><span class="distancia-pivo">${distanciaFormatada}</span>`;
                hasDistancia = true;
                
                const sourceNameWidth = (nomeFonte.length * 6.5) + 15;
                labelWidth = Math.max(labelWidth, sourceNameWidth);
            }
        }
        
        const labelHeight = hasDistancia ? 55 : 20;

        const labelBomba = L.marker([bomba.lat, bomba.lon], {
            icon: L.divIcon({ 
                className: 'label-pivo', 
                html: finalHtml, 
                iconSize: [labelWidth, labelHeight], 
                iconAnchor: [labelWidth / 2, -5] 
            }),
            labelType: 'bomba', 
            interactive: false
        }).addTo(map);
        marcadoresLegenda.push(labelBomba);
    });
    toggleLegendas(legendasAtivas);
}


function drawCirculos(ciclosData) {
    if (!map) return;
    circulosPivos.forEach(c => map.removeLayer(c));
    circulosPivos = [];

    window.lastPivosDataDrawn.forEach(pivo => {
        if (pivo.tipo === 'setorial') {
            const center = L.latLng(pivo.lat, pivo.lon);
            const sectorCoords = generateSectorCoords(center, pivo.raio, pivo.angulo_central, pivo.abertura_arco);
            const sectorPolygon = L.polygon(sectorCoords, {
                color: '#cc0000',
                weight: 2,
                opacity: 0.9,
                fillOpacity: 0.1,
                className: 'circulo-pivo-setorial'
            }).addTo(map);
            circulosPivos.push(sectorPolygon);
        }
    });

    const ciclosCirculares = ciclosData.filter(ciclo => {
        const nomePivo = ciclo.nome_original_circulo.replace('Ciclo ', '');
        const pivoCorrespondente = window.lastPivosDataDrawn.find(p => p.nome === nomePivo);
        return !pivoCorrespondente || pivoCorrespondente.tipo !== 'setorial';
    });

    const poligonosCirculares = ciclosCirculares.map(circulo =>
        L.polygon(circulo.coordenadas, {
            color: '#cc0000',
            weight: 2,
            opacity: 0.9,
            fillOpacity: 0,
            className: 'circulo-vermelho-pulsante'
        }).addTo(map)
    );
    circulosPivos.push(...poligonosCirculares);
}

function drawImageOverlay(url, bounds, opacity = 1.0) {
    if (!map || !url || !bounds) return null;
    const imageBounds = [[bounds[0], bounds[1]], [bounds[2], bounds[3]]];
    const overlay = L.imageOverlay(url, imageBounds, {
        opacity: opacity,
        interactive: false
    }).addTo(map);
    overlaysVisiveis.push(overlay);
    return overlay;
}


function addRepetidoraNoPainel(repetidora) {
    const container = document.getElementById("lista-repetidoras");
    const item = document.createElement("div");
    item.className = "flex justify-between items-center bg-gray-800/60 px-3 py-2 rounded-lg border border-white/10";
    item.id = `rep-item-${repetidora.id}`;
    const label = document.createElement("span");
    label.textContent = `${repetidora.label.options.icon.options.html}`;
    label.className = "text-white/80 text-sm";
    const controls = document.createElement("div");
    controls.className = "flex gap-3 items-center";

    const diagBtn = document.createElement("button");
    diagBtn.innerHTML = `<span class="sidebar-icon w-4 h-4" style="-webkit-mask-image: url(assets/images/mountain.svg); mask-image: url(assets/images/mountain.svg);"></span>`;
    diagBtn.className = "text-white/60 hover:text-sky-300 transition relative top-px";
    diagBtn.title = t('tooltips.run_diagnostic_from_source');
    diagBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        if (typeof runTargetedDiagnostic === 'function') {
            runTargetedDiagnostic(repetidora);
        }
    });

    const visibilityBtn = document.createElement("button");
    visibilityBtn.className = "text-white/60 hover:text-sky-300 transition";
    visibilityBtn.title = t('tooltips.show_hide_coverage');
    visibilityBtn.setAttribute('data-visible', 'true');
    visibilityBtn.innerHTML = `<i data-lucide="check" class="w-4 h-4 text-green-500"></i>`;
    
    visibilityBtn.addEventListener("click", () => {
        const isCurrentlyVisible = visibilityBtn.getAttribute('data-visible') === 'true';
        const newVisibilityState = !isCurrentlyVisible;
        visibilityBtn.setAttribute('data-visible', newVisibilityState);

        const opacityValue = parseFloat(document.getElementById("range-opacidade").value);
        if (repetidora.marker) repetidora.marker.setOpacity(newVisibilityState ? 1 : 0);
        if (repetidora.label) {
            const labelEl = repetidora.label.getElement();
            if(labelEl) labelEl.style.display = (newVisibilityState && legendasAtivas) ? '' : 'none';
        }
        if (repetidora.overlay) repetidora.overlay.setOpacity(newVisibilityState ? opacityValue : 0);
        
    
        visibilityBtn.innerHTML = newVisibilityState
            ? `<i data-lucide="check" class="w-4 h-4 text-green-500"></i>`
            : `<i data-lucide="eye-off" class="w-4 h-4 text-gray-500"></i>`;
        lucide.createIcons();

        setTimeout(reavaliarPivosViaAPI, 100);
    });

    
    const removerBtn = document.createElement("button");
    removerBtn.innerHTML = "❌";
    removerBtn.className = "text-red-500 hover:text-red-400 text-xs font-bold transition";
    removerBtn.title = "Remover Repetidora";
    removerBtn.addEventListener("click", () => {
        map.removeLayer(repetidora.marker);
        if (repetidora.overlay) map.removeLayer(repetidora.overlay);
        if (repetidora.label) map.removeLayer(repetidora.label);
        container.removeChild(item);
        idsDisponiveis.push(repetidora.id);
        idsDisponiveis.sort((a, b) => a - b);
        repetidoras = repetidoras.filter(r => r.id !== repetidora.id);
        overlaysVisiveis = overlaysVisiveis.filter(o => o !== repetidora.overlay);
        marcadoresLegenda = marcadoresLegenda.filter(l => l !== repetidora.label);
        atualizarPainelDados();
        setTimeout(reavaliarPivosViaAPI, 100);
    });
    
    controls.appendChild(diagBtn);
    controls.appendChild(visibilityBtn);
    controls.appendChild(removerBtn);
    item.appendChild(label);
    item.appendChild(controls);
    container.appendChild(item);
    lucide.createIcons();
}

function addAntenaAoPainel(antena) {
    const itemExistente = document.getElementById("antena-item");
    if (itemExistente) {
        itemExistente.remove();
    }
    const container = document.getElementById("lista-repetidoras");
    const item = document.createElement("div");
    item.className = "flex justify-between items-center bg-gray-700/60 px-3 py-2 rounded-lg border border-white/10";
    item.id = `antena-item`;
    const label = document.createElement("span");
    label.textContent = `${antena.nome || t('ui.labels.main_antenna_default')}`;
    label.className = "text-white/90 font-semibold text-sm";
    const controls = document.createElement("div");
    controls.className = "flex gap-3 items-center";

    const diagBtn = document.createElement("button");
    diagBtn.innerHTML = `<span class="sidebar-icon w-4 h-4" style="-webkit-mask-image: url(assets/images/mountain.svg); mask-image: url(assets/images/mountain.svg);"></span>`;
    diagBtn.className = "text-white/60 hover:text-sky-300 transition relative top-px";
    diagBtn.title = t('tooltips.run_diagnostic_from_source');
    diagBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        if (typeof runTargetedDiagnostic === 'function') {
            runTargetedDiagnostic(antena);
        }
    });

    const visibilityBtn = document.createElement("button");
    visibilityBtn.className = "text-white/60 hover:text-sky-300 transition";
    visibilityBtn.title = t('tooltips.show_hide_coverage');
    visibilityBtn.setAttribute('data-visible', 'true');
    visibilityBtn.innerHTML = `<i data-lucide="check" class="w-4 h-4 text-green-500"></i>`;
    visibilityBtn.addEventListener("click", () => {
        const isCurrentlyVisible = visibilityBtn.getAttribute('data-visible') === 'true';
        const newVisibilityState = !isCurrentlyVisible;
        visibilityBtn.setAttribute('data-visible', String(newVisibilityState));

        const opacityValue = parseFloat(rangeOpacidade.value);

        if (antena?.overlay) {
            antena.overlay.setOpacity(newVisibilityState ? opacityValue : 0);
        }
        if (marcadorAntena) {
            marcadorAntena.setOpacity(newVisibilityState ? 1 : 0);
        }

        visibilityBtn.innerHTML = newVisibilityState
            ? `<i data-lucide="check" class="w-4 h-4 text-green-500"></i>`
            : `<i data-lucide="eye-off" class="w-4 h-4 text-gray-500"></i>`;
        lucide.createIcons();

        setTimeout(reavaliarPivosViaAPI, 100);
    });

    controls.appendChild(diagBtn);
    controls.appendChild(visibilityBtn);
    item.appendChild(label);
    item.appendChild(controls);

    if (container.firstChild) {
        container.insertBefore(item, container.firstChild);
    } else {
        container.appendChild(item);
    }
    lucide.createIcons();
}

function drawDiagnostico(latlonOrigem, latlonDestino, dadosBloqueioAPI, dadosPontoMaisAlto, nomeDiagnostico, distanciaTotalPivosFormatada = null) {
    if (!map) return;
    const linha = drawVisadaComGradiente(latlonOrigem, latlonDestino);
    let pontoParaMarcador = null;
    let mensagemTooltip = `<strong>${nomeDiagnostico}</strong>`;
    let usarIconeAtencaoReal = false;
    let localIconUrl = ATTENTION_ICON_PATH;
    let localIconSize = [20, 20];
    if (distanciaTotalPivosFormatada) {
        mensagemTooltip += `<br>${t('ui.labels.pivo_distance_label')} ${distanciaTotalPivosFormatada}`;
    }
    if (dadosBloqueioAPI && typeof dadosBloqueioAPI.lat === 'number' && typeof dadosBloqueioAPI.elev === 'number' && typeof dadosBloqueioAPI.diff === 'number') {
        pontoParaMarcador = dadosBloqueioAPI;
        usarIconeAtencaoReal = dadosBloqueioAPI.diff > 0.1;
        mensagemTooltip += `<br>${t('tooltips.blockage_point', { elevation: pontoParaMarcador.elev.toFixed(1) })}`;
        if (usarIconeAtencaoReal) {
            localIconUrl = ATTENTION_ICON_PATH;
            localIconSize = [24, 24];
            mensagemTooltip += `<br><span style="color: #FF9800;">${t('tooltips.blockage_present', { diff: dadosBloqueioAPI.diff.toFixed(1) })}</span>`;
        } else {
            localIconUrl = CHECK_ICON_PATH;
            localIconSize = [22, 22];
            if (distanciaTotalPivosFormatada) {
                 mensagemTooltip += `<br><span style="color: #4CAF50;">${t('tooltips.los_clear_at_critical_point', { diff: dadosBloqueioAPI.diff.toFixed(1) })}</span>`;
            }
        }
    } else if (dadosPontoMaisAlto && typeof dadosPontoMaisAlto.lat === 'number' && typeof dadosPontoMaisAlto.elev === 'number') {
        pontoParaMarcador = dadosPontoMaisAlto;
        localIconUrl = MOUNTAIN_ICON_PATH;
        localIconSize = [20, 20];
        mensagemTooltip += `<br>${t('tooltips.highest_point', { elevation: pontoParaMarcador.elev.toFixed(1) })}`;
        usarIconeAtencaoReal = false;
    }
    let deveMostrarMarcador = false;
    if (distanciaTotalPivosFormatada) {
        deveMostrarMarcador = !!dadosBloqueioAPI;
    } else {
        deveMostrarMarcador = !!pontoParaMarcador;
    }
    if (deveMostrarMarcador && pontoParaMarcador) {
        const markerIcon = L.divIcon({
            className: 'label-bloqueio-dinamico',
            html: `<img src="${localIconUrl}" style="width: ${localIconSize[0]}px; height: ${localIconSize[1]}px; filter: drop-shadow(0 1px 2px rgba(0,0,0,0.7));">`,
            iconSize: localIconSize,
            iconAnchor: [localIconSize[0] / 2, localIconSize[1] / 2]
        });
        const marker = L.marker([pontoParaMarcador.lat, pontoParaMarcador.lon], { icon: markerIcon })
            .addTo(visadaLayerGroup)
            .bindTooltip(mensagemTooltip, {
                permanent: false,
                direction: 'top',
                className: 'tooltip-sinal tooltip-visada-diagnostico',
                offset: [0, - (localIconSize[1] / 2 + 5)],
                opacity: 0.95
            });
        marcadoresBloqueio.push(marker);
    }
    linhasDiagnostico.push(linha);
}

function clearMapLayers() {
    if (!map) return;
    if (marcadorAntena) {
        map.removeLayer(marcadorAntena);
        marcadorAntena = null;
    }
    if (antenaCandidatesLayerGroup) {
        antenaCandidatesLayerGroup.clearLayers();
    }
    if (window.marcadorPosicionamento) map.removeLayer(window.marcadorPosicionamento);
    marcadoresPivos.forEach(m => map.removeLayer(m));
    circulosPivos.forEach(c => map.removeLayer(c));
    marcadoresBombas.forEach(b => map.removeLayer(b));
    marcadoresLegenda.forEach(m => map.removeLayer(m));
    repetidoras.forEach(r => {
        if (r.marker) map.removeLayer(r.marker);
        if (r.overlay) map.removeLayer(r.overlay);
        if (r.label) map.removeLayer(r.label);
    });
    if (window.antenaGlobal?.overlay) map.removeLayer(window.antenaGlobal.overlay);
    visadaLayerGroup.clearLayers();
    if (window.candidateRepeaterSitesLayerGroup) {
        window.candidateRepeaterSitesLayerGroup.clearLayers();
    }
     Object.values(pivotsMap).forEach(m => {
        if (m.editMarker && map.hasLayer(m.editMarker)) {
            map.removeLayer(m.editMarker);
            delete m.editMarker;
        }
        if(map.hasLayer(m)) {
            if (typeof m.unbindTooltip === 'function') m.unbindTooltip();
            if (typeof m.unbindPopup === 'function') m.unbindPopup();
            map.removeLayer(m);
        }
    });
    marcadoresPivos = [];
    circulosPivos = [];
    marcadoresBombas = [];
    marcadoresLegenda = [];
    repetidoras = [];
    overlaysVisiveis = [];
    linhasDiagnostico = [];
    marcadoresBloqueio = [];
    pivotsMap = {};
}

function toggleLegendas(show) {
    legendasAtivas = show;
    const toggleLegendaButton = document.getElementById("toggle-legenda");
    const iconSpan = toggleLegendaButton ? toggleLegendaButton.querySelector('.sidebar-icon') : null;
    const isParentVisible = (labelMarker) => {
        const labelType = labelMarker.options.labelType;
        let checkbox = null;
        if (labelType === 'antena') {
            checkbox = document.querySelector("#antena-item input[type='checkbox']");
        } else if (labelType === 'bomba') {
             return true;
        } else if (labelType === 'repetidora') {
            const rep = repetidoras.find(r => r.label === labelMarker);
            if (rep) {
                checkbox = document.querySelector(`#rep-item-${rep.id} input[type='checkbox']`);
            }
        }
        else if (labelType === 'pivot') {
            return true;
        }
        return checkbox ? checkbox.checked : true;
    };
    marcadoresLegenda.forEach(m => {
        const el = m.getElement?.();
        if (el) {
            if (m.options.labelType !== 'pivot') {
                 el.style.display = (show && isParentVisible(m)) ? '' : 'none';
            } else {
                el.style.display = show ? '' : 'none';
            }
        }
    });
    if (toggleLegendaButton) {
        toggleLegendaButton.classList.toggle("glass-button-active", !show);
        toggleLegendaButton.title = show ? t('tooltips.hide_legends') : t('tooltips.show_legends');
        if (iconSpan) {
            const iconPath = show ? CAPTIONS_ON_ICON_PATH : CAPTIONS_OFF_ICON_PATH;
            iconSpan.style.webkitMaskImage = `url(${iconPath})`;
            iconSpan.style.maskImage = `url(${iconPath})`;
        }
    }
}

function updateOverlaysOpacity(opacityValue) {
    const isPanelItemVisible = (overlay) => {
        let visibilityBtn = null;
        if (window.antenaGlobal?.overlay === overlay) {
            visibilityBtn = document.querySelector("#antena-item button[data-visible]");
        } else {
            const rep = repetidoras.find(r => r.overlay === overlay);
            if (rep) {
                visibilityBtn = document.querySelector(`#rep-item-${rep.id} button[data-visible]`);
            }
        }
        return !visibilityBtn || visibilityBtn.getAttribute('data-visible') === 'true';
    };

    overlaysVisiveis.forEach(overlay => {
        if (map.hasLayer(overlay)) {
            if (isPanelItemVisible(overlay)) {
                overlay.setOpacity(opacityValue);
            } else {
                overlay.setOpacity(0);
            }
        }
    });
}

function criarGradienteVisada(id = 'gradient-visada') {
    const svgPane = map.getPane('overlayPane');
    if (!svgPane) {
        console.error("❌ SVG pane do mapa não encontrado.");
        return;
    }
    let svg = svgPane.querySelector('svg');
    if (!svg) {
        const tempLayer = L.polyline([[0,0],[0,0]]).addTo(map);
        svg = svgPane.querySelector('svg');
        map.removeLayer(tempLayer);
        if(!svg) {
            console.error("❌ SVG do mapa não pôde ser criado ou encontrado.");
            return;
        }
    }
    const existente = svg.querySelector(`#${id}`);
    if (existente) return;
    let defs = svg.querySelector('defs');
    if (!defs) {
        defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
        svg.insertBefore(defs, svg.firstChild);
    }
    const gradient = document.createElementNS("http://www.w3.org/2000/svg", "linearGradient");
    gradient.setAttribute("id", id);
    gradient.setAttribute("x1", "0%");
    gradient.setAttribute("y1", "0%");
    gradient.setAttribute("x2", "100%");
    gradient.setAttribute("y2", "0%");
    gradient.innerHTML = `
        <stop offset="0%" stop-color="green"/>
        <stop offset="50%" stop-color="yellow"/>
        <stop offset="100%" stop-color="red"/>
    `;
    defs.appendChild(gradient);
}

function drawVisadaComGradiente(pontoA, pontoB) {
    criarGradienteVisada();
    const linha = L.polyline([pontoA, pontoB], {
        renderer: L.svg(),
        color: `url(#gradient-visada)`,
        weight: 2,
        opacity: visadaVisivel ? 1 : 0.5,
        dashArray: '8 8',
        className: 'linha-pontilhada',
        lineCap: 'round'
    }).addTo(visadaLayerGroup);
    return linha;
}

function drawCandidateRepeaterSites(sites, targetPivotData) {
    if (!map) {
        console.error("Mapa não inicializado ao tentar desenhar locais candidatos.");
        return;
    }
    if (window.candidateRepeaterSitesLayerGroup) {
        window.candidateRepeaterSitesLayerGroup.clearLayers();
    } else {
        window.candidateRepeaterSitesLayerGroup = L.layerGroup().addTo(map);
    }
    if (!sites || sites.length === 0) {
        return;
    }
    sites.forEach((site, index) => {
        if (typeof site.lat === 'undefined' || typeof site.lon === 'undefined') {
            return;
        }
        const siteLatLng = [site.lat, site.lon];
        const uniqueMarkerId = `candidate-${index}-${site.lat.toFixed(5)}-${site.lon.toFixed(5)}`;
        const iconHtml = `
            <div class="candidate-icon-wrapper">
                ⛰️ ${(site.elevation || 0).toFixed(1)}m
                ${site.has_los ? ` <span class="los-ok">${t('tooltips.los_ok')}</span>` : ` <span class="los-no">${t('tooltips.los_no')}</span>`}
                <br><span class="distancia-info">${t('ui.labels.pivo_distance_label')} ${site.distance_to_target ? site.distance_to_target.toFixed(0) + 'm' : 'N/A'}</span>
            </div>`;
        const candidateIcon = L.divIcon({
            className: 'custom-div-icon-ponto-alto',
            html: iconHtml,
            iconSize: [95, 48],
            iconAnchor: [47.5, 24]
        });
        const marker = L.marker(siteLatLng, {
            icon: candidateIcon,
            customId: uniqueMarkerId,
            interactive: false
        });
        marker.addTo(window.candidateRepeaterSitesLayerGroup);
        if (targetPivotData && typeof targetPivotData.lat !== 'undefined' && typeof targetPivotData.lon !== 'undefined') {
            const targetLatLng = [targetPivotData.lat, targetPivotData.lon];
            let lineColor = 'rgba(128, 128, 128, 0.7)';
            if (typeof site.has_los === 'boolean') {
                lineColor = site.has_los ? 'rgba(76, 175, 80, 0.7)' : 'rgba(255, 152, 0, 0.7)';
            }
            const line = L.polyline([siteLatLng, targetLatLng], {
                color: lineColor,
                weight: 2,
                dashArray: '5, 5',
                opacity: 0.75,
                customId: uniqueMarkerId
            });
            line.addTo(window.candidateRepeaterSitesLayerGroup);
        }
    });
}

function togglePivoDistances(show) {
    // Redesenha os Pivôs (esta parte já estava correta, usando a memória de status)
    if (window.lastPivosDataDrawn && window.lastPivosDataDrawn.length > 0) {
        drawPivos(window.lastPivosDataDrawn, false); 
    } else if (Object.keys(pivotsMap).length > 0 && window.currentProcessedKmzData?.pivos) {
        // Lógica de fallback para pivôs
        console.warn("togglePivoDistances: Reconstruindo dados dos pivôs via fallback.");
        const pivosReconstruidos = window.currentProcessedKmzData.pivos.map(pOriginal => {
            const marker = pivotsMap[pOriginal.nome];
            if (marker) {
                const posAtual = marker.getLatLng();
                return {
                    ...pOriginal,
                    lat: posicoesEditadas[pOriginal.nome] ? posicoesEditadas[pOriginal.nome].lat : posAtual.lat,
                    lon: posicoesEditadas[pOriginal.nome] ? posicoesEditadas[pOriginal.nome].lng : posAtual.lng,
                    fora: marker.options.color === 'red'
                };
            }
            return pOriginal;
        });
        drawPivos(pivosReconstruidos, false);
    }
    
    // ✅ CORREÇÃO APLICADA AQUI:
    // Redesenha as Bombas usando a nova variável 'lastBombasDataDrawn' que contém o status correto.
    if (window.lastBombasDataDrawn && window.lastBombasDataDrawn.length > 0) {
        drawBombas(window.lastBombasDataDrawn);
    }

    // Exibe a mensagem de sucesso (código existente)
    if (typeof mostrarMensagem === 'function') {
        mostrarMensagem(t('messages.success.pivot_distances_toggled', { status: show ? t('labels.shown') : t('labels.hidden') }), 'sucesso');
    }
}
window.togglePivoDistances = togglePivoDistances;


// ✅ NOVO: Variável para o círculo temporário
let tempCircle = null;

/**
 * ✅ NOVO: Desenha ou atualiza um círculo temporário no mapa para feedback visual.
 * @param {L.LatLng} center - O centro do círculo.
 * @param {L.LatLng} radiusPoint - Um ponto na borda para definir o raio.
 */
function drawTempCircle(center, radiusPoint) {
    const radius = center.distanceTo(radiusPoint);
    if (tempCircle) {
        tempCircle.setLatLng(center).setRadius(radius);
    } else {
        tempCircle = L.circle(center, {
            radius: radius,
            color: '#3B82F6', // Azul
            weight: 2,
            dashArray: '5, 5',
            fillColor: '#3B82F6',
            fillOpacity: 0.1,
            interactive: false, // O círculo não deve ser clicável
            className: 'temp-drawing-circle' // Para estilização CSS
        }).addTo(map);
    }
}

/**
 * ✅ NOVO: Remove o círculo temporário do mapa.
 */
function removeTempCircle() {
    if (tempCircle) {
        map.removeLayer(tempCircle);
        tempCircle = null;
    }
}

/**
 * ✅ NOVO: Gera um array de coordenadas [lat, lon] que formam um círculo.
 * @param {L.LatLng} center - O centro do círculo.
 * @param {number} radius - O raio em metros.
 * @param {number} [points=60] - O número de pontos para formar o polígono.
 * @returns {Array<[number, number]>} - Array de coordenadas.
 */
function generateCircleCoords(center, radius, points = 60) {
    const coords = [];
    const earthRadius = 6378137; // Raio da Terra em metros
    const lat = center.lat * (Math.PI / 180); // Radianos
    const lon = center.lng * (Math.PI / 180); // Radianos

    for (let i = 0; i < points; i++) {
        const angle = (i / points) * 360;
        const bearing = angle * (Math.PI / 180); // Radianos

        const newLat = Math.asin(Math.sin(lat) * Math.cos(radius / earthRadius) +
                      Math.cos(lat) * Math.sin(radius / earthRadius) * Math.cos(bearing));
        
        const newLon = lon + Math.atan2(Math.sin(bearing) * Math.sin(radius / earthRadius) * Math.cos(lat),
                               Math.cos(radius / earthRadius) - Math.sin(lat) * Math.sin(newLat));

        coords.push([newLat * (180 / Math.PI), newLon * (180 / Math.PI)]);
    }
    // Adiciona o primeiro ponto ao final para fechar o polígono
    coords.push(coords[0]);
    return coords;
}

// ========================================================
// ✅ NOVAS FUNÇÕES PARA DESENHO DE PIVÔ SETORIAL
// ========================================================

/**
 * Desenha ou atualiza o setor temporário no mapa.
 * @param {L.LatLng} center O ponto inicial do desenho.
 * @param {L.LatLng} currentPoint A posição atual do mouse.
 */
function drawTempSector(center, currentPoint) {
    const radius = center.distanceTo(currentPoint);
    if (radius < 5) return; // Evita formas estranhas quando muito perto

    const bearing = calculateBearing(center, currentPoint);
    const coords = generateSectorCoords(center, radius, bearing, 180);

    if (tempSectorShape) {
        tempSectorShape.setLatLngs(coords);
    } else {
        tempSectorShape = L.polygon(coords, {
            color: '#3B82F6', // Azul
            weight: 2,
            dashArray: '8, 8',
            fillColor: '#3B82F6',
            fillOpacity: 0.2,
            interactive: false
        }).addTo(map);
    }
}

/**
 * Remove o setor temporário do mapa.
 */
function removeTempSector() {
    if (tempSectorShape) {
        map.removeLayer(tempSectorShape);
        tempSectorShape = null;
    }
}

/**
 * Calcula o ângulo (azimute) em graus de um ponto a outro.
 * @returns {number} Ângulo em graus de 0 a 360.
 */
function calculateBearing(p1, p2) {
    const lat1 = p1.lat * Math.PI / 180;
    const lon1 = p1.lng * Math.PI / 180;
    const lat2 = p2.lat * Math.PI / 180;
    const lon2 = p2.lng * Math.PI / 180;

    const y = Math.sin(lon2 - lon1) * Math.cos(lat2);
    const x = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(lon2 - lon1);
    let brng = Math.atan2(y, x) * 180 / Math.PI;
    brng = (brng + 360) % 360; // Normaliza para 0-360
    return brng;
}

/**
 * Gera as coordenadas para um polígono em forma de setor.
 */
function generateSectorCoords(center, radius, mainAngle, arcAngle = 180) {
    const vertices = [];
    vertices.push([center.lat, center.lng]); // Ponto central

    const startAngle = mainAngle - (arcAngle / 2);
    const endAngle = mainAngle + (arcAngle / 2);
    const points = 40; // Número de pontos para formar o arco

    for (let i = 0; i <= points; i++) {
        const angle = startAngle + (i * arcAngle / points);
        const point = L.latLng(center).destination(radius, angle);
        vertices.push([point.lat, point.lng]);
    }
    
    return vertices;
}

// Adiciona um método "destination" ao L.LatLng se ele não existir (útil para cálculos)
if (!L.LatLng.prototype.destination) {
    L.LatLng.prototype.destination = function(distance, bearing) {
        const R = 6378137; // Raio da Terra em metros
        const brng = bearing * Math.PI / 180; // Converte para radianos
        const lat1 = this.lat * Math.PI / 180;
        const lon1 = this.lng * Math.PI / 180;

        const lat2 = Math.asin(Math.sin(lat1) * Math.cos(distance / R) +
            Math.cos(lat1) * Math.sin(distance / R) * Math.cos(brng));

        const lon2 = lon1 + Math.atan2(Math.sin(brng) * Math.sin(distance / R) * Math.cos(lat1),
            Math.cos(distance / R) - Math.sin(lat1) * Math.sin(lat2));

        return L.latLng(lat2 * 180 / Math.PI, lon2 * 180 / Math.PI);
    };
}