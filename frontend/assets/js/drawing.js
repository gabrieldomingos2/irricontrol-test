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
    pivotsMap = {};

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

        // 🎯 Legenda fixa abaixo do pivô (mantém o nome do pivô no mapa)
        const labelWidth = (pivo.nome.length * 7) + 10;
        const labelHeight = 20;

        const label = L.marker(pos, {
            icon: L.divIcon({
                className: 'label-pivo',
                html: pivo.nome,
                iconSize: [labelWidth, labelHeight],
                iconAnchor: [labelWidth / 2, -15] // 👈 Legenda abaixo do círculo
            }),
            labelType: 'pivot'
        }).addTo(map);

        marcadoresLegenda.push(label);

        // 🧠 Tooltip SOMENTE com o status (sem nome do pivô)
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
    offset: [0, -15], // 🔥 Pode ajustar para -20, -25 ou -30 se quiser mais acima
    className: 'tooltip-sinal'
});

        // ⚡ CLICK: Adiciona repetidora
        marker.on('click', (e) => {
            console.log(`[DEBUG] Clique detectado no pivô: ${pivo.nome}`);
            L.DomEvent.stopPropagation(e);

            if (window.modoEdicaoPivos === true) {
                marker.bindPopup(`
                    <div class="popup-glass">
                        ✏️ ${pivo.fora ? '❌ Fora de sinal' : '✔️ Com sinal'}
                    </div>
                `).openPopup();
                return;
            }

            window.coordenadaClicada = e.latlng;
            console.log("[DEBUG] Coordenada definida:", window.coordenadaClicada);

            if (typeof window.removePositioningMarker === 'function') {
                window.removePositioningMarker();
                console.log("[DEBUG] Marcador de posicionamento anterior removido.");
            } else {
                console.error("[DEBUG] ERRO: Função 'removePositioningMarker' não encontrada!");
                return;
            }

            const painel = document.getElementById("painel-repetidora");
            if (painel) {
                painel.classList.remove("hidden");
                console.log("[DEBUG] Painel de repetidora deveria estar visível agora.");
            } else {
                console.error("[DEBUG] ERRO: Painel 'painel-repetidora' não encontrado!");
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
    // Atualiza filtro para remover apenas labels de bomba
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
                iconAnchor: [labelWidth / 2, -5] // Posição acima do ícone
            }),
            labelType: 'bomba' // Identifica como label de bomba
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
    label.textContent = `📡 ${repetidora.label.options.icon.options.html}`; // Pega o nome do label
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
            if(labelEl) labelEl.style.display = (isChecked && legendasAtivas) ? '' : 'none'; // Respeita 'legendasAtivas'
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
        // Remove a legenda da repetidora da lista geral
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
 * @param {object} antena - Objeto da antena principal.
 */
function addAntenaAoPainel(antena) {
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

        const antenaLabel = marcadoresLegenda.find(m => m.options.labelType === 'antena'); // Busca por tipo
        if (antenaLabel) {
            const labelEl = antenaLabel.getElement();
            if(labelEl) labelEl.style.display = (isChecked && legendasAtivas) ? '' : 'none';
        }

        if (antenaGlobal.overlay) antenaGlobal.overlay.setOpacity(isChecked ? opacityValue : 0);
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

    // 🔥 Linha de visada
    const linha = drawVisadaComGradiente(latlonAntena, latlonPivo);

    // 🏔️ Desenha SOMENTE o ponto mais alto (com legenda de bloqueio se houver)
    if (pontoMaisAltoData) {
        const highPointIcon = L.divIcon({
    className: 'label-bloqueio',
    html: `
        <img src="./assets/images/attention-icon-original.svg" 
             style="width: 24px; height: 24px;">
    `,
    iconSize: [24, 24],
    iconAnchor: [12, 12]
});

        const mensagem = bloqueioData
            ? `⛔ Visada bloqueada para <strong>${pivoNome}</strong><br>Elevação: ${pontoMaisAltoData.elev.toFixed(1)}m`
            : `⛔ Visada bloqueada para <strong>${pivoNome}</strong><br>Elevação: ${pontoMaisAltoData.elev.toFixed(1)}m`;

        const markerHigh = L.marker([pontoMaisAltoData.lat, pontoMaisAltoData.lon], { icon: highPointIcon })
    .addTo(visadaLayerGroup)
    .bindTooltip(`
        ⛔ Visada bloqueada para <strong>${pivoNome}</strong><br>Elevação: ${pontoMaisAltoData.elev.toFixed(1)}m
    `, {
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
    marcadoresLegenda.forEach(m => map.removeLayer(m)); // Limpa L.Markers antigos

    repetidoras.forEach(r => {
        if (r.marker) map.removeLayer(r.marker);
        if (r.overlay) map.removeLayer(r.overlay);
        if (r.label) map.removeLayer(r.label);
    });

    if (antenaGlobal?.overlay) map.removeLayer(antenaGlobal.overlay);

    visadaLayerGroup.clearLayers();

     Object.values(pivotsMap).forEach(m => {
        if (m.editMarker && map.hasLayer(m.editMarker)) {
            map.removeLayer(m.editMarker);
        }
        delete m.editMarker;
        // Precisamos limpar o tooltip se ele existir
        m.unbindTooltip();
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


/**
 * Alterna a visibilidade das legendas L.Marker (Antena, Bombas, Repetidoras).
 * Pivôs são controlados por hover (Tooltip) e não são afetados aqui.
 * @param {boolean} show - True para mostrar legendas, false para esconder.
 */
function toggleLegendas(show) {
    legendasAtivas = show; // Atualiza o estado global

    const toggleLegendaButton = document.getElementById("toggle-legenda");
    // Seleciona o span dentro do botão para trocar o ícone
    const iconSpan = toggleLegendaButton ? toggleLegendaButton.querySelector('.sidebar-icon') : null;

    const isParentVisible = (labelMarker) => {
        const labelType = labelMarker.options.labelType;
        // const html = labelMarker.options.icon.options.html; // Não usado aqui
        let checkbox = null;

        if (labelType === 'antena') {
            checkbox = document.querySelector("#antena-item input[type='checkbox']");
        } else if (labelType === 'bomba') {
             return true; // Bombas não têm checkbox, sempre seguem 'show'
        } else { // Deve ser 'repetidora'
            const rep = repetidoras.find(r => r.label === labelMarker);
            if (rep) {
                checkbox = document.querySelector(`#rep-item-${rep.id} input[type='checkbox']`);
            }
        }
        return checkbox ? checkbox.checked : true;
    };

    // Aplica visibilidade APENAS para L.Markers (não afeta tooltips de pivôs)
    marcadoresLegenda.forEach(m => {
        const el = m.getElement?.();
        if (el) {
            // Só mostra se 'show' for true E o checkbox do pai estiver marcado
            el.style.display = (show && isParentVisible(m)) ? '' : 'none';
        }
    });

    if (toggleLegendaButton) {
        // ATUALIZADO: O botão fica "ativo" (glass-button-active) quando as legendas estão ESCONDIDAS (show === false)
        toggleLegendaButton.classList.toggle("glass-button-active", !show);
        toggleLegendaButton.title = show ? "Esconder Legendas" : "Mostrar Legendas";

        // ATUALIZADO: Muda o ícone com base no estado 'show'
        if (iconSpan) {
            if (show) {
                iconSpan.style.webkitMaskImage = 'url(assets/images/captions.svg)';
                iconSpan.style.maskImage = 'url(assets/images/captions.svg)';
            } else {
                // Assumindo que você tem um ícone para legendas desligadas
                // CRIE ESTE ARQUIVO: assets/images/captions-off.svg
                iconSpan.style.webkitMaskImage = 'url(assets/images/captions-off.svg)';
                iconSpan.style.maskImage = 'url(assets/images/captions-off.svg)';
            }
        }
    }
}


/**
 * Atualiza a opacidade de todos os overlays de sinal.
 * @param {number} opacityValue - Valor da opacidade (0 a 1).
 */
function updateOverlaysOpacity(opacityValue) {

    const isPanelItemChecked = (overlay) => {
        if (antenaGlobal?.overlay === overlay) {
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
        } else if (map.hasLayer(overlay)) {
            overlay.setOpacity(0);
        }
    });
}

function criarGradienteVisada(id = 'gradient-visada') {
    const svg = document.querySelector('.leaflet-overlay-pane svg');
    if (!svg) {
        console.error("❌ SVG do mapa não encontrado.");
        return;
    }

    const existente = svg.querySelector(`#${id}`);
    if (existente) return;

    const defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
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
    svg.appendChild(defs);
}


function drawVisadaComGradiente(pontoA, pontoB) {
    criarGradienteVisada();

    const linha = L.polyline([pontoA, pontoB], {
        color: 'url(#gradient-visada)',
        weight: 2,
        opacity: visadaVisivel ? 1 : 0.5,
        dashArray: '8 8',
        className: 'linha-pontilhada',
        lineCap: 'round'
    }).addTo(visadaLayerGroup);

    return linha;
}

