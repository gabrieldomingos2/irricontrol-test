// --- Definições de Ícones ---

const antenaIcon = L.icon({
  iconUrl: getTowerIconUrl(), // Usa a função de api.js
  iconSize: [28, 28],
  iconAnchor: [14, 28],
});

const bombaIcon = L.icon({
  iconUrl: getPumpIconUrl(), // Usa a função de api.js
  iconSize: [28, 28],
  iconAnchor: [14, 28],
});

const posicionamentoIcon = L.icon({
  iconUrl: getTowerIconUrl(),
  iconSize: [28, 28],
  iconAnchor: [14, 28],
  popupAnchor: [0, -30]
});

window.candidateRepeaterSitesLayerGroup = null; // Será inicializado no initMap (map.js)

// --- Funções de Desenho ---

/**
 * Desenha o marcador da antena principal no mapa.
 * @param {object} antenaData - Dados da antena (lat, lon, nome).
 * @returns {L.Marker} - O marcador da antena.
 */
function drawAntena(antenaData) {
    if (!map || !antenaData) return null;

    const marker = L.marker([antenaData.lat, antenaData.lon], { icon: antenaIcon })
        .addTo(map);

    const labelWidth = (antenaData.nome.length * 7) + 10;
    const labelHeight = 20;

    const label = L.marker([antenaData.lat, antenaData.lon], {
        icon: L.divIcon({
            className: 'label-pivo', // Reutiliza estilo, mas pode criar um 'label-antena'
            html: antenaData.nome || 'Antena',
            iconSize: [labelWidth, labelHeight],
            iconAnchor: [labelWidth / 2, 45]
        }),
        labelType: 'antena' // Identifica como label de antena
    }).addTo(map);

    marcadoresLegenda.push(label);
    return marker;
}

/**
 * Desenha os marcadores dos pivôs no mapa (com hover e click).
 * @param {Array<object>} pivosData - Array com dados dos pivôs.
 * @param {boolean} useEdited - Usar posições editadas se existirem.
 */
function drawPivos(pivosData, useEdited = false) {
    if (!map || !pivosData) return;

    // 🔄 Limpa marcadores antigos de pivôs e suas legendas
    marcadoresPivos.forEach(m => map.removeLayer(m));
    marcadoresPivos = [];
    pivotsMap = {}; // Limpa o mapa de pivôs para reconstrução

    const legendasRestantes = [];
    marcadoresLegenda.forEach(legenda => {
        if (legenda.options.labelType !== 'pivot') {
            legendasRestantes.push(legenda);
        } else {
            map.removeLayer(legenda);
        }
    });
    marcadoresLegenda = legendasRestantes;

    // 🔥 Cria novos marcadores de pivôs
    pivosData.forEach(pivo => {
        const cor = pivo.fora ? 'red' : 'green';
        const pos = useEdited && posicoesEditadas[pivo.nome]
            ? L.latLng(posicoesEditadas[pivo.nome].lat, posicoesEditadas[pivo.nome].lng)
            : L.latLng(pivo.lat, pivo.lon);

        const marker = L.circleMarker(pos, {
            radius: 8,
            color: cor,
            fillColor: cor,
            fillOpacity: 0.7,
            weight: 2,
        }).addTo(map);

        // --- MODIFICADO: Cálculo e formatação da distância ---
        const labelNome = pivo.nome;
        let distanciaHtml = "";
        let hasDistancia = false;

        // window.distanciasPivosVisiveis e window.antenaGlobal são definidos em main.js
        if (window.distanciasPivosVisiveis && window.antenaGlobal && typeof window.antenaGlobal.lat === 'number' && typeof window.antenaGlobal.lon === 'number') {
            const antenaLatLng = L.latLng(window.antenaGlobal.lat, window.antenaGlobal.lon);
            const pivoLatLng = pos; // pos já é um L.latLng
            const distancia = antenaLatLng.distanceTo(pivoLatLng); // em metros
            distanciaHtml = `<br><span class="distancia-pivo">${distancia > 999 ? (distancia / 1000).toFixed(1) + ' km' : Math.round(distancia) + ' m'}</span>`;
            hasDistancia = true;
        }
        const finalHtml = `${labelNome}${distanciaHtml}`;
        // --- FIM MODIFICAÇÃO ---

        // Ajusta a largura e altura da legenda
        const labelWidth = (labelNome.length * 7) + 20; // Largura baseada no nome, com um pouco de padding
        const labelHeight = hasDistancia ? 35 : 20;    // Altura ajustada para uma ou duas linhas

        const label = L.marker(pos, {
            icon: L.divIcon({
                className: 'label-pivo', // O CSS pode precisar de ajustes para altura/centralização
                html: finalHtml,         // USA finalHtml com a distância
                iconSize: [labelWidth, labelHeight], // USA altura ajustada
                iconAnchor: [labelWidth / 2, -15]    // Mantém a legenda abaixo do círculo (ancoragem no centro inferior do divIcon)
            }),
            labelType: 'pivot'
        }).addTo(map);

        marcadoresLegenda.push(label);

        const statusTexto = pivo.fora
            ? `<span style="color:#ff4d4d; font-weight:bold;">❌ Fora de sinal</span>`
            : `<span style="color:#22c55e; font-weight:bold;">✅ Com sinal</span>`;

        const tooltipContent = `
            <div style="text-align:center;">
                ${statusTexto}
            </div>
        `;

        marker.bindTooltip(tooltipContent, {
            permanent: false,
            direction: 'top',
            offset: [0, -15],
            className: 'tooltip-sinal'
        });

        marker.on('click', (e) => {
            L.DomEvent.stopPropagation(e);

            if (window.modoEdicaoPivos === true) {
                marker.bindPopup(`
                    <div class="popup-glass">
                        ✏️ ${pivo.fora ? '❌ Fora de sinal' : '✔️ Com sinal'}
                    </div>
                `).openPopup();
                return;
            }
            else if (window.modoLoSPivotAPivot) {
                if (typeof handleLoSPivotClick === 'function') {
                    handleLoSPivotClick(pivo, marker);
                } else {
                    console.error("Função handleLoSPivotClick não encontrada!");
                }
                return;
            }
            else if (window.modoBuscaLocalRepetidora && typeof handlePivotSelectionForRepeaterSite === 'function') {
                handlePivotSelectionForRepeaterSite(pivo, marker);
                return;
            }
            else {
                console.log(`[DEBUG] Clique padrão no pivô (para posicionar repetidora): ${pivo.nome}`);
                window.coordenadaClicada = e.latlng;

                if (typeof window.removePositioningMarker === 'function') {
                    window.removePositioningMarker();
                } else {
                    console.error("[DEBUG] ERRO: Função 'removePositioningMarker' não está definida globalmente!");
                }

                const painel = document.getElementById("painel-repetidora");
                if (painel) {
                    painel.classList.remove("hidden");
                } else {
                    console.error("[DEBUG] ERRO: Painel 'painel-repetidora' não encontrado no DOM!");
                }
            }
        });

        marcadoresPivos.push(marker);
        pivotsMap[pivo.nome] = marker;
    });

    toggleLegendas(legendasAtivas);
}

/**
 * Desenha os marcadores das casas de bomba.
 * @param {Array<object>} bombasData - Array com dados das bombas.
 */
function drawBombas(bombasData) {
    if (!map || !bombasData) return;

    marcadoresBombas.forEach(b => map.removeLayer(b));
    marcadoresBombas = [];
    marcadoresLegenda = marcadoresLegenda.filter(m => m.options.labelType !== 'bomba');

    bombasData.forEach(bomba => {
        const marcadorBomba = L.marker([bomba.lat, bomba.lon], { icon: bombaIcon })
            .addTo(map);
        marcadoresBombas.push(marcadorBomba);

        const labelWidth = (bomba.nome.length * 7) + 10;
        const labelHeight = 20;
        const labelBomba = L.marker([bomba.lat, bomba.lon], {
            icon: L.divIcon({
                className: 'label-pivo',
                html: bomba.nome,
                iconSize: [labelWidth, labelHeight],
                iconAnchor: [labelWidth / 2, -5]
            }),
            labelType: 'bomba'
        }).addTo(map);
        marcadoresLegenda.push(labelBomba);
    });
     toggleLegendas(legendasAtivas);
}

/**
 * Desenha os círculos (LineString) do KMZ.
 * @param {Array<object>} ciclosData - Array com dados dos círculos.
 */
function drawCirculos(ciclosData) {
    if (!map || !ciclosData) return;

    circulosPivos.forEach(c => map.removeLayer(c));
    circulosPivos = [];

    circulosPivos = ciclosData.map(circulo =>
        L.polygon(circulo.coordenadas, {
            color: '#cc0000',
            weight: 2,
            opacity: 0.9,
            fillOpacity: 0,
            className: 'circulo-vermelho-pulsante'
        }).addTo(map)
    );
}

/**
 * Adiciona ou atualiza um overlay de imagem no mapa.
 * @param {string} url - URL da imagem.
 * @param {Array<number>} bounds - Limites do overlay [sul, oeste, norte, leste].
 * @param {number} opacity - Opacidade inicial (0 a 1).
 * @returns {L.ImageOverlay} - O overlay criado.
 */
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


/**
 * Adiciona uma repetidora ao painel lateral e gerencia seus eventos.
 * @param {object} repetidora - Objeto contendo dados da repetidora.
 */
function addRepetidoraNoPainel(repetidora) {
    const container = document.getElementById("lista-repetidoras");
    const item = document.createElement("div");
    item.className = "flex justify-between items-center bg-gray-800/60 px-3 py-2 rounded-lg border border-white/10";
    item.id = `rep-item-${repetidora.id}`;

    const label = document.createElement("span");
    label.textContent = `📡 ${repetidora.label.options.icon.options.html}`;
    label.className = "text-white/80 text-sm";

    const controls = document.createElement("div");
    controls.className = "flex gap-3 items-center";

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = true;
    checkbox.className = "form-checkbox h-4 w-4 text-green-500 bg-gray-700 border-gray-600 rounded focus:ring-green-600";
    checkbox.title = "Mostrar/Esconder Cobertura";

    checkbox.addEventListener("change", () => {
        const isChecked = checkbox.checked;
        const opacityValue = parseFloat(document.getElementById("range-opacidade").value);

        if (repetidora.marker) repetidora.marker.setOpacity(isChecked ? 1 : 0);
        if (repetidora.label) {
            const labelEl = repetidora.label.getElement();
            if(labelEl) labelEl.style.display = (isChecked && legendasAtivas) ? '' : 'none';
        }
        if (repetidora.overlay) repetidora.overlay.setOpacity(isChecked ? opacityValue : 0);

        if(repetidora.marker) repetidora.marker.options.interactive = isChecked;
        if(repetidora.label) repetidora.label.options.interactive = isChecked;

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

    controls.appendChild(checkbox);
    controls.appendChild(removerBtn);
    item.appendChild(label);
    item.appendChild(controls);
    container.appendChild(item);
}


/**
 * Adiciona o marcador da antena principal ao painel lateral.
 * @param {object} antena - Objeto da antena principal (deve ser window.antenaGlobal).
 */
function addAntenaAoPainel(antena) { // antena aqui é window.antenaGlobal
    const container = document.getElementById("lista-repetidoras");
    const item = document.createElement("div");
    item.className = "flex justify-between items-center bg-gray-700/60 px-3 py-2 rounded-lg border border-white/10";
    item.id = `antena-item`;

    const label = document.createElement("span");
    label.textContent = `🗼 ${antena.nome || 'Antena Principal'}`;
    label.className = "text-white/90 font-semibold text-sm";

    const controls = document.createElement("div");
    controls.className = "flex gap-3 items-center";

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = true;
    checkbox.className = "form-checkbox h-4 w-4 text-green-500 bg-gray-700 border-gray-600 rounded focus:ring-green-600";
    checkbox.title = "Mostrar/Esconder Cobertura";

    checkbox.addEventListener("change", () => {
        const isChecked = checkbox.checked;
        const opacityValue = parseFloat(document.getElementById("range-opacidade").value);

        if (marcadorAntena) marcadorAntena.setOpacity(isChecked ? 1 : 0);

        const antenaLabel = marcadoresLegenda.find(m => m.options.labelType === 'antena');
        if (antenaLabel) {
            const labelEl = antenaLabel.getElement();
            if(labelEl) labelEl.style.display = (isChecked && legendasAtivas) ? '' : 'none';
        }

        if (window.antenaGlobal.overlay) window.antenaGlobal.overlay.setOpacity(isChecked ? opacityValue : 0); // Usa window.antenaGlobal
        if(marcadorAntena) marcadorAntena.options.interactive = isChecked;
        setTimeout(reavaliarPivosViaAPI, 100);
    });

    controls.appendChild(checkbox);
    item.appendChild(label);
    item.appendChild(controls);

    if (container.firstChild) {
        container.insertBefore(item, container.firstChild);
    } else {
        container.appendChild(item);
    }
}


function drawDiagnostico(latlonAntena, latlonPivo, bloqueioData, pontoMaisAltoData, pivoNome) {
    if (!map) return;

    const linha = drawVisadaComGradiente(latlonAntena, latlonPivo);

    if (pontoMaisAltoData) {
        const highPointIcon = L.divIcon({
            className: 'label-bloqueio',
            html: `<img src="./assets/images/attention-icon-original.svg" style="width: 24px; height: 24px;">`,
            iconSize: [24, 24],
            iconAnchor: [12, 12]
        });

        const markerHigh = L.marker([pontoMaisAltoData.lat, pontoMaisAltoData.lon], { icon: highPointIcon })
            .addTo(visadaLayerGroup)
            .bindTooltip(
                `⛔ Visada bloqueada para <strong>${pivoNome}</strong><br>Elevação: ${pontoMaisAltoData.elev.toFixed(1)}m`, {
                permanent: false,
                direction: 'top',
                className: 'tooltip-sinal',
                offset: [0, -15],
                opacity: 0.9
            });
        marcadoresBloqueio.push(markerHigh);
    }
    linhasDiagnostico.push(linha);
}


/**
 * Limpa todas as camadas adicionadas dinamicamente ao mapa.
 */
function clearMapLayers() {
    if (!map) return;

    if (marcadorAntena) map.removeLayer(marcadorAntena);
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

    if (window.antenaGlobal?.overlay) map.removeLayer(window.antenaGlobal.overlay); // Usa window.antenaGlobal

    visadaLayerGroup.clearLayers();

    if (window.candidateRepeaterSitesLayerGroup) {
        window.candidateRepeaterSitesLayerGroup.clearLayers();
        console.log("Camada de locais candidatos (candidateRepeaterSitesLayerGroup) limpa no reset.");
    }

     Object.values(pivotsMap).forEach(m => {
        if (m.editMarker && map.hasLayer(m.editMarker)) {
            map.removeLayer(m.editMarker);
        }
        // m é o circleMarker, que já foi limpo de marcadoresPivos.
        // Se m é apenas o wrapper com editMarker, e o circleMarker já foi removido, ok.
        // A limpeza de pivotsMap={} abaixo deve resolver.
        if (map.hasLayer(m)) { // Garante que removemos o próprio circleMarker se ele ainda existir
            m.unbindTooltip();
            map.removeLayer(m);
        }
        delete m.editMarker;
    });

    marcadoresPivos = [];
    circulosPivos = [];
    marcadoresBombas = [];
    marcadoresLegenda = [];
    repetidoras = [];
    overlaysVisiveis = [];
    linhasDiagnostico = [];
    marcadoresBloqueio = [];
    pivotsMap = {}; // Limpa o mapa de pivôs
}


/**
 * Alterna a visibilidade das legendas L.Marker (Antena, Bombas, Repetidoras).
 * Pivôs são controlados por hover (Tooltip) e não são afetados aqui.
 * @param {boolean} show - True para mostrar legendas, false para esconder.
 */
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
        } else if (labelType === 'repetidora') { // Adicionado para repetidoras
            const rep = repetidoras.find(r => r.label === labelMarker);
            if (rep) {
                checkbox = document.querySelector(`#rep-item-${rep.id} input[type='checkbox']`);
            }
        }
        // Para legendas de pivôs, a visibilidade é controlada por window.distanciasPivosVisiveis
        // e pela própria renderização em drawPivos. Aqui, só tratamos outros tipos de legendas.
        else if (labelType === 'pivot') {
            return true; // A legenda do pivô em si (nome/distância) é sempre "visível" no DOM, mas seu conteúdo muda.
        }
        return checkbox ? checkbox.checked : true;
    };

    marcadoresLegenda.forEach(m => {
        const el = m.getElement?.();
        if (el) {
            // Para pivôs, a lógica de mostrar/esconder a distância já está em drawPivos.
            // Aqui, só controlamos a visibilidade geral das legendas de antena, bomba, repetidora.
            if (m.options.labelType !== 'pivot') {
                 el.style.display = (show && isParentVisible(m)) ? '' : 'none';
            } else {
                // Para pivôs, se as legendas gerais estão desligadas, escondemos tudo.
                // Se ligadas, a drawPivos decide o que mostrar (nome vs nome+distância).
                el.style.display = show ? '' : 'none';
            }
        }
    });

    if (toggleLegendaButton) {
        toggleLegendaButton.classList.toggle("glass-button-active", !show);
        toggleLegendaButton.title = show ? "Esconder Legendas" : "Mostrar Legendas";
        if (iconSpan) {
            const iconName = show ? 'captions' : 'captions-off';
            iconSpan.style.webkitMaskImage = `url(assets/images/${iconName}.svg)`;
            iconSpan.style.maskImage = `url(assets/images/${iconName}.svg)`;
        }
    }
}


/**
 * Atualiza a opacidade de todos os overlays de sinal.
 * @param {number} opacityValue - Valor da opacidade (0 a 1).
 */
function updateOverlaysOpacity(opacityValue) {
    const isPanelItemChecked = (overlay) => {
        if (window.antenaGlobal?.overlay === overlay) { // Usa window.antenaGlobal
            const checkbox = document.querySelector("#antena-item input[type='checkbox']");
            return checkbox ? checkbox.checked : true;
        }
        const rep = repetidoras.find(r => r.overlay === overlay);
        if (rep) {
            const checkbox = document.querySelector(`#rep-item-${rep.id} input[type='checkbox']`);
            return checkbox ? checkbox.checked : true;
        }
        return true;
    };

    overlaysVisiveis.forEach(overlay => {
        if (map.hasLayer(overlay) && isPanelItemChecked(overlay)) {
             overlay.setOpacity(opacityValue);
        } else if (map.hasLayer(overlay)) { // Se não estiver checado mas estiver no mapa, torna invisível
            overlay.setOpacity(0);
        }
    });
}

function criarGradienteVisada(id = 'gradient-visada') {
    const svgPane = map.getPane('overlayPane'); // Melhor forma de pegar o SVG pane
    if (!svgPane) {
        console.error("❌ SVG pane do mapa não encontrado.");
        return;
    }
    let svg = svgPane.querySelector('svg');
    if (!svg) { // Se o SVG não existir (primeira vez), o Leaflet o criará com a primeira camada vetorial
        // Adiciona uma camada temporária para forçar a criação do SVG se necessário
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
        svg.insertBefore(defs, svg.firstChild); // Adiciona defs no início do SVG
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
        renderer: L.svg(), // Garante que está usando SVG para gradientes
        color: `url(#gradient-visada)`, // Referencia o gradiente
        weight: 2,
        opacity: visadaVisivel ? 1 : 0.5, // visadaVisivel deve ser uma var global
        dashArray: '8 8',
        className: 'linha-pontilhada', // Para CSS se necessário
        lineCap: 'round'
    }).addTo(visadaLayerGroup);

    return linha;
}

/**
 * Desenha os marcadores e linhas para os locais candidatos de repetidoras.
 * @param {Array<object>} sites - Lista de locais candidatos do backend.
 * @param {object} targetPivotData - Dados do pivô alvo (com lat, lon, nome).
 */
function drawCandidateRepeaterSites(sites, targetPivotData) {
    if (!map) {
        console.error("Mapa não inicializado ao tentar desenhar locais candidatos.");
        return;
    }

    if (window.candidateRepeaterSitesLayerGroup) {
        window.candidateRepeaterSitesLayerGroup.clearLayers();
        // console.log("Camada de locais candidatos anteriores limpa.");
    } else {
        console.warn("candidateRepeaterSitesLayerGroup não está definido. Os marcadores de busca podem se acumular.");
         // Inicializa se não existir, para segurança
        window.candidateRepeaterSitesLayerGroup = L.layerGroup().addTo(map);
    }

    if (!sites || sites.length === 0) {
        // console.log("Nenhum local candidato para desenhar.");
        return;
    }

    sites.forEach((site, index) => {
        if (typeof site.lat === 'undefined' || typeof site.lon === 'undefined') {
            console.warn("Site candidato ignorado por falta de lat/lon:", site);
            return;
        }
        const siteLatLng = [site.lat, site.lon];
        const uniqueMarkerId = `candidate-${index}-${site.lat.toFixed(5)}-${site.lon.toFixed(5)}`;

        const iconHtml = `
            <div class="candidate-icon-wrapper">
                <span class="candidate-remove-btn" data-marker-id="${uniqueMarkerId}">&times;</span>
                ⛰️ ${(site.elevation || 0).toFixed(1)}m
                ${site.has_los ? '<br><span style="color:#4CAF50;">✅LoS</span>' : '<br><span style="color:#FF9800;">❌¬LoS</span>'}
                <br><span style="color:#FFF;">Dist: ${site.distance_to_target ? site.distance_to_target.toFixed(0) + 'm' : 'N/A'}</span>
            </div>`;

        const candidateIcon = L.divIcon({
            className: 'custom-div-icon-ponto-alto',
            html: iconHtml,
            iconSize: [95, 48],
            iconAnchor: [47.5, 24]
        });

        const marker = L.marker(siteLatLng, {
            icon: candidateIcon,
            customId: uniqueMarkerId
        });

        marker.addTo(window.candidateRepeaterSitesLayerGroup);


        marker.on('click', function (e) {
            if (e.originalEvent.target.classList.contains('candidate-remove-btn')) {
                return;
            }
            L.DomEvent.stopPropagation(e);
            window.coordenadaClicada = L.latLng(site.lat, site.lon);
            const painelRep = document.getElementById("painel-repetidora");
            if (painelRep) {
                painelRep.classList.remove("hidden");
                 // Pré-preenche a altura da antena se disponível, caso contrário, usa o valor padrão do input
                const alturaRepInput = document.getElementById("altura-antena-rep");
                if (alturaRepInput) {
                    alturaRepInput.value = site.altura_necessaria_torre || alturaRepInput.value || 5;
                }
            }
            if (typeof mostrarMensagem === 'function') {
                 mostrarMensagem(`Ponto alto (${(site.elevation || 0).toFixed(1)}m) selecionado. Configure e simule a repetidora.`, "info");
            }
        });

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
    // console.log(`${sites.length} locais candidatos desenhados.`);
}


// --- NOVA FUNÇÃO PARA ATIVAR/DESATIVAR DISTÂNCIAS ---
/**
 * Alterna a exibição das distâncias dos pivôs e redesenha-os.
 * Chamada por handleToggleDistanciasPivos em main.js.
 * @param {boolean} show - True para mostrar distâncias, false para esconder.
 */
function togglePivoDistances(show) {
    // window.distanciasPivosVisiveis já foi atualizado em main.js
    // Apenas precisamos redesenhar os pivôs.

    if (window.lastPivosDataDrawn && window.lastPivosDataDrawn.length > 0) {
        // Redesenha os pivôs usando os últimos dados conhecidos.
        // O segundo argumento 'true' para useEdited garante que as posições editadas sejam consideradas
        // se lastPivosDataDrawn não tiver as posições já atualizadas (o que deveria ter).
        // Se lastPivosDataDrawn TEM as posições corretas, useEdited pode ser false.
        // Para segurança e consistência, é bom que lastPivosDataDrawn sempre reflita o estado atual.
        drawPivos(window.lastPivosDataDrawn, true); // Passa 'true' para useEdited
        if (typeof mostrarMensagem === 'function') { // Verifica se mostrarMensagem está disponível
             mostrarMensagem(`Distâncias dos pivôs ${show ? 'exibidas' : 'ocultas'}.`, 'sucesso');
        }
    } else if (Object.keys(pivotsMap).length > 0 && window.currentProcessedKmzData && window.currentProcessedKmzData.pivos) {
        // Fallback: se lastPivosDataDrawn estiver vazio, tenta reconstruir os dados.
        console.warn("togglePivoDistances: Reconstruindo dados dos pivôs pois window.lastPivosDataDrawn estava vazio.");
        const pivosReconstruidos = window.currentProcessedKmzData.pivos.map(pOriginal => {
            const marker = pivotsMap[pOriginal.nome]; // pivotsMap contém os L.CircleMarkers
            if (marker) {
                const posAtual = marker.getLatLng(); // Posição atual do L.CircleMarker
                return {
                    ...pOriginal, // Mantém dados originais como raio, etc.
                    lat: posicoesEditadas[pOriginal.nome] ? posicoesEditadas[pOriginal.nome].lat : posAtual.lat,
                    lon: posicoesEditadas[pOriginal.nome] ? posicoesEditadas[pOriginal.nome].lng : posAtual.lng,
                    fora: marker.options.color === 'red' // Status atual do L.CircleMarker
                };
            }
            return pOriginal; // Retorna original se não encontrado no mapa
        });
        drawPivos(pivosReconstruidos, true); // Passa 'true' para useEdited
         if (typeof mostrarMensagem === 'function') {
            mostrarMensagem(`Distâncias dos pivôs ${show ? 'exibidas' : 'ocultas'} (via fallback).`, 'sucesso');
        }
    } else {
        // console.log("Nenhum pivô carregado para mostrar/ocultar distâncias.");
        // Não mostra mensagem se não houver pivôs, para não ser intrusivo.
    }
}
// Expor a função globalmente para que main.js possa chamá-la
window.togglePivoDistances = togglePivoDistances;