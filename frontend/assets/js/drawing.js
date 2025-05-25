// --- Definições de Ícones ---

const antenaIcon = L.icon({
  iconUrl: getTowerIconUrl(), // Usa a função de api.js
  iconSize: [28, 28],
  iconAnchor: [14, 28],
  popupAnchor: [0, -30] // Ajustado para popup aparecer acima
});

const bombaIcon = L.icon({
  iconUrl: getPumpIconUrl(), // Usa a função de api.js
  iconSize: [28, 28],
  iconAnchor: [14, 28],
  popupAnchor: [0, -28] // Ajustado
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
        .addTo(map)
        .bindPopup(`<div class="popup-glass">📡 ${antenaData.nome || 'Antena'}</div>`, { offset: [0, -30] }); // Offset ajustado

    const label = L.marker([antenaData.lat, antenaData.lon], {
        icon: L.divIcon({
            className: 'label-pivo',
            html: antenaData.nome || 'Antena',
            iconSize: [80, 20], // Aumentado para nomes maiores
            iconAnchor: [40, 45] // Ajustado para centralizar abaixo
        })
    }).addTo(map);

    marcadoresLegenda.push(label);
    return marker;
}

/**
 * Desenha os marcadores dos pivôs no mapa.
 * @param {Array<object>} pivosData - Array com dados dos pivôs.
 * @param {boolean} useEdited - Usar posições editadas se existirem.
 */
function drawPivos(pivosData, useEdited = false) {
    if (!map || !pivosData) return;

    // Limpa pivôs existentes antes de desenhar
    marcadoresPivos.forEach(m => map.removeLayer(m));
    Object.values(pivotsMap).forEach(m => map.removeLayer(m));
    marcadoresPivos = [];
    pivotsMap = {};
    // Limpa apenas legendas de pivôs antigos
    marcadoresLegenda = marcadoresLegenda.filter(m => !m.options.icon.options.html.toLowerCase().includes('piv'));

    pivosData.forEach(pivo => {
        const cor = pivo.fora ? 'red' : 'green';
        const classeCss = pivo.fora ? 'circulo-vermelho-pulsante' : 'circulo-verde'; // Usa classes CSS

        const pos = useEdited && posicoesEditadas[pivo.nome]
                    ? L.latLng(posicoesEditadas[pivo.nome].lat, posicoesEditadas[pivo.nome].lng)
                    : L.latLng(pivo.lat, pivo.lon);

        const marker = L.circleMarker(pos, {
            radius: 6,
            color: cor,
            fillColor: cor,
            fillOpacity: 0.6,
            className: classeCss // Adiciona a classe CSS
        }).addTo(map).bindPopup(
            `<div class="popup-glass">${pivo.fora ? '❌' : '✅'} ${pivo.nome}</div>`
        );

        marcadoresPivos.push(marker);
        pivotsMap[pivo.nome] = marker;

        const label = L.marker(pos, {
            icon: L.divIcon({
                className: 'label-pivo',
                html: pivo.nome,
                iconSize: [60, 20],
                iconAnchor: [30, -10] // Ajustado para acima e à direita
            })
        }).addTo(map);

        marcadoresLegenda.push(label);
    });
    toggleLegendas(legendasAtivas); // Garante que novas legendas respeitem o estado atual
}

/**
 * Desenha os marcadores das casas de bomba.
 * @param {Array<object>} bombasData - Array com dados das bombas.
 */
function drawBombas(bombasData) {
    if (!map || !bombasData) return;

    marcadoresBombas.forEach(b => map.removeLayer(b));
    marcadoresBombas = [];
    // Limpa apenas legendas de bombas antigas
    marcadoresLegenda = marcadoresLegenda.filter(m => !m.options.icon.options.html.toLowerCase().includes('bomba'));

    bombasData.forEach(bomba => {
        const marcadorBomba = L.marker([bomba.lat, bomba.lon], { icon: bombaIcon })
            .addTo(map)
            .bindPopup(`<div class="popup-glass">🚰 ${bomba.nome}</div>`);

        marcadoresBombas.push(marcadorBomba);

        const labelBomba = L.marker([bomba.lat, bomba.lon], {
            icon: L.divIcon({
                className: 'label-pivo',
                html: bomba.nome,
                iconSize: [80, 20], // Aumentado
                iconAnchor: [40, 45] // Abaixo
            })
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
        L.polygon(circulo.coordenadas, { // Usa L.polygon que pode ser mais adequado que polyline para círculos
            color: '#ff3b3b',
            weight: 2, // Mais fino
            opacity: 0.8,
            fillOpacity: 0, // Sem preenchimento
            className: 'circulo-vermelho-pulsante' // Usa a classe para pulsar
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
        interactive: false // Geralmente não precisa de interação
    }).addTo(map);

    overlaysVisiveis.push(overlay); // Adiciona à lista para controle de opacidade
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

    const label = document.createElement("span"); // Usar span
    label.textContent = `📡 Repetidora ${repetidora.id}`;
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
        repetidora.marker.setOpacity(isChecked ? 1 : 0);
        if (repetidora.label) repetidora.label.setOpacity(isChecked ? 1 : 0);
        if (repetidora.overlay) repetidora.overlay.setOpacity(isChecked ? rangeOpacidade.value : 0);

        // Torna não interativo quando escondido
        repetidora.marker.options.interactive = isChecked;
        if (repetidora.label) repetidora.label.options.interactive = isChecked;

        // Reavalia os pivôs após um pequeno delay para garantir que o mapa atualizou
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
        idsDisponiveis.push(repetidora.id); // Devolve o ID para reuso
        idsDisponiveis.sort((a, b) => a - b);
        repetidoras = repetidoras.filter(r => r.id !== repetidora.id);
        overlaysVisiveis = overlaysVisiveis.filter(o => o !== repetidora.overlay);

        atualizarPainelDados(); // Atualiza contagem no painel
        setTimeout(reavaliarPivosViaAPI, 100); // Reavalia
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
        marcadorAntena.setOpacity(isChecked ? 1 : 0);
        // A legenda da antena é controlada pelo 'toggle-legenda'
        if (antena.overlay) antena.overlay.setOpacity(isChecked ? rangeOpacidade.value : 0);

        marcadorAntena.options.interactive = isChecked;

        setTimeout(reavaliarPivosViaAPI, 100);
    });

    controls.appendChild(checkbox);
    item.appendChild(label);
    item.appendChild(controls);

    // Adiciona no início da lista
    if (container.firstChild) {
        container.insertBefore(item, container.firstChild);
    } else {
        container.appendChild(item);
    }
}


/**
 * Desenha as linhas de diagnóstico e marcadores de bloqueio.
 * @param {Array} latlonAntena - [lat, lon] da antena.
 * @param {Array} latlonPivo - [lat, lon] do pivô.
 * @param {object | null} bloqueioData - Dados do ponto de bloqueio, ou null.
 * @param {string} pivoNome - Nome do pivô.
 */
function drawDiagnostico(latlonAntena, latlonPivo, bloqueioData, pivoNome) {
    if (!map) return;

    const linha = L.polyline([latlonAntena, latlonPivo], {
        className: 'linha-futurista', // Usa CSS para animação
        interactive: false
    }).addTo(visadaLayerGroup); // Adiciona ao grupo controlável

    // Muda o estilo após a animação para algo mais leve
    setTimeout(() => {
        if (map.hasLayer(linha)) {
            linha.setStyle({
                stroke: '#00ffff',
                strokeWidth: 1,
                strokeDasharray: '5, 5', // Tracejado
                opacity: visadaVisivel ? 0.6 : 0 // Respeita a visibilidade atual
            });
            // Remove a classe para parar a animação
            if (linha.getElement) {
                 linha.getElement().classList.remove('linha-futurista');
            }
        }
    }, 1600); // Um pouco depois da animação

    if (bloqueioData) {
        const bloqueioIcon = L.divIcon({
            className: 'label-bloqueio', // Usa CSS
            html: '⛰️',
            iconSize: [20, 20],
            iconAnchor: [10, 10]
        });

        const marker = L.marker([bloqueioData.lat, bloqueioData.lon], { icon: bloqueioIcon })
            .addTo(visadaLayerGroup) // Adiciona ao grupo controlável
            .bindPopup(`
                <div class="popup-glass text-center leading-snug">
                ⛔ Visada bloqueada para <strong>${pivoNome}</strong><br>
                Elevação: ${bloqueioData.elev.toFixed(1)}m
                </div>
            `);
        marcadoresBloqueio.push(marker);
    }

    linhasDiagnostico.push(linha);
}

/**
 * Limpa todas as camadas adicionadas dinamicamente ao mapa.
 */
function clearMapLayers() {
    if (!map) return;

    if (marcadorAntena) map.removeLayer(marcadorAntena);
    if (marcadorPosicionamento) map.removeLayer(marcadorPosicionamento);

    marcadoresPivos.forEach(m => map.removeLayer(m));
    circulosPivos.forEach(c => map.removeLayer(c));
    marcadoresBombas.forEach(b => map.removeLayer(b));
    marcadoresLegenda.forEach(m => map.removeLayer(m));

    repetidoras.forEach(r => {
        if (r.marker) map.removeLayer(r.marker);
        if (r.overlay) map.removeLayer(r.overlay);
        if (r.label) map.removeLayer(r.label);
    });

    if (antenaGlobal?.overlay) map.removeLayer(antenaGlobal.overlay);

    visadaLayerGroup.clearLayers(); // Limpa linhas e marcadores de bloqueio

    // Limpa marcadores de edição, se houver
     Object.values(pivotsMap).forEach(m => {
        if (m.editMarker && map.hasLayer(m.editMarker)) {
            map.removeLayer(m.editMarker);
        }
        delete m.editMarker;
    });
}

/**
 * Alterna a visibilidade de todas as legendas (nomes) no mapa.
 * @param {boolean} show - True para mostrar, false para esconder.
 */
function toggleLegendas(show) {
    legendasAtivas = show; // Atualiza o estado global
    marcadoresLegenda.forEach(m => {
        const el = m.getElement?.(); // Pega o elemento HTML do marcador
        if (el) {
            el.style.display = show ? '' : 'none'; // Mostra ou esconde
        }
    });
    document.getElementById("toggle-legenda").classList.toggle("opacity-50", !show);
}

/**
 * Atualiza a opacidade de todos os overlays de sinal.
 * @param {number} opacityValue - Valor da opacidade (0 a 1).
 */
function updateOverlaysOpacity(opacityValue) {
    overlaysVisiveis.forEach(overlay => {
        // Só muda a opacidade se o overlay estiver visível (controlado pelo checkbox)
        if (map.hasLayer(overlay)) {
             overlay.setOpacity(opacityValue);
        }
    });

    // Também atualiza a antena principal
    if (antenaGlobal?.overlay && map.hasLayer(antenaGlobal.overlay)) {
        antenaGlobal.overlay.setOpacity(opacityValue);
    }

    // E as repetidoras (verificando se o checkbox dela está ativo)
    repetidoras.forEach(rep => {
         const itemPanel = document.getElementById(`rep-item-${rep.id}`);
         const checkbox = itemPanel ? itemPanel.querySelector('input[type="checkbox"]') : null;
         if (rep.overlay && map.hasLayer(rep.overlay) && checkbox && checkbox.checked) {
             rep.overlay.setOpacity(opacityValue);
         }
    });
}