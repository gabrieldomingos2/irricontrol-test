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

function drawAntena(antenaData) {
    if (!map || !antenaData) return null;

    const marker = L.marker([antenaData.lat, antenaData.lon], { icon: antenaIcon })
        .addTo(map);

    const labelWidth = (antenaData.nome.length * 7) + 10;
    const labelHeight = 20;

    const label = L.marker([antenaData.lat, antenaData.lon], {
        icon: L.divIcon({
            className: 'label-pivo',
            html: antenaData.nome || 'Antena',
            iconSize: [labelWidth, labelHeight],
            iconAnchor: [labelWidth / 2, 45]
        }),
        labelType: 'antena'
    }).addTo(map);

    marcadoresLegenda.push(label);
    return marker;
}

function drawPivos(pivosData, useEdited = false) {
    if (!map || !pivosData) return;

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

        const labelNome = pivo.nome;
        let distanciaHtml = "";
        let hasDistancia = false;

        if (window.distanciasPivosVisiveis && window.antenaGlobal && typeof window.antenaGlobal.lat === 'number' && typeof window.antenaGlobal.lon === 'number') {
            const antenaLatLng = L.latLng(window.antenaGlobal.lat, window.antenaGlobal.lon);
            const pivoLatLng = pos;
            const distancia = antenaLatLng.distanceTo(pivoLatLng);
            distanciaHtml = `<br><span class="distancia-pivo">${distancia > 999 ? (distancia / 1000).toFixed(1) + ' km' : Math.round(distancia) + ' m'}</span>`;
            hasDistancia = true;
        }
        const finalHtml = `${labelNome}${distanciaHtml}`;

        const labelWidth = (labelNome.length * 7) + 20;
        const labelHeight = hasDistancia ? 35 : 20;

        const label = L.marker(pos, {
            icon: L.divIcon({
                className: 'label-pivo',
                html: finalHtml,
                iconSize: [labelWidth, labelHeight],
                iconAnchor: [labelWidth / 2, -15]
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
            direction: 'top', // Isso já ajuda a posicionar em cima
            offset: [0, -15],  // Ajusta a distância vertical do ícone
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

function drawBombas(bombasData) { // bombasData agora é um array de objetos como: { nome, lat, lon, fora }
    if (!map) return;

    Object.values(window.bombasMap || {}).forEach(bombaObj => { // Assumindo window.bombasMap de main.js
        if (bombaObj.marker && map.hasLayer(bombaObj.marker)) map.removeLayer(bombaObj.marker);
        if (bombaObj.label && map.hasLayer(bombaObj.label)) map.removeLayer(bombaObj.label);
    });
    if(window.bombasMap) window.bombasMap = {}; // Reseta

    marcadoresLegenda = marcadoresLegenda.filter(m => m.options.labelType !== 'bomba');
    // A variável marcadoresBombas (array de L.marker) que você tem pode ser usada para rastrear
    // os marcadores de ícone para facilitar a remoção, ou você pode usar o bombasMap.
    // Vamos manter sua lógica de limpar marcadoresBombas array por enquanto.
    marcadoresBombas.forEach(markerIconOnly => map.removeLayer(markerIconOnly));
    marcadoresBombas = [];


    if (!bombasData || bombasData.length === 0) {
        toggleLegendas(legendasAtivas);
        return;
    }

    bombasData.forEach(bomba => { // Agora 'bomba' aqui tem a propriedade 'fora'
        const pos = L.latLng(bomba.lat, bomba.lon);

        const marcadorBombaIcon = L.marker(pos, { icon: bombaIcon }) // Renomeado para clareza
            .addTo(map);
        marcadoresBombas.push(marcadorBombaIcon); // Adiciona apenas o marcador do ícone à sua lista atual

        const labelNome = bomba.nome;
        const labelWidth = (labelNome.length * 7) + 10;
        const labelHeight = 20;
        const labelBomba = L.marker(pos, {
            icon: L.divIcon({
                className: 'label-pivo',
                html: labelNome,
                iconSize: [labelWidth, labelHeight],
                iconAnchor: [labelWidth / 2, -10] // Ajustado para posicionar abaixo do ícone
            }),
            labelType: 'bomba'
        }).addTo(map);
        marcadoresLegenda.push(labelBomba);

        // --- LÓGICA DO TOOLTIP ADICIONADA ---
        const statusTexto = bomba.fora
            ? `<span style="color:#ff4d4d; font-weight:bold;">❌ Fora de sinal</span>`
            : `<span style="color:#22c55e; font-weight:bold;">✅ Com sinal</span>`;

        const tooltipContent = `
            <div style="text-align:center;">
                ${statusTexto}
            </div>
        `;

        marcadorBombaIcon.bindTooltip(tooltipContent, {
            permanent: false,
            direction: 'top',
            offset: [0, -28], // Ajuste conforme o tamanho do bombaIcon e seu iconAnchor
            className: 'tooltip-sinal' // Reutiliza o estilo de tooltip dos pivôs
        });
        // --- FIM DA LÓGICA DO TOOLTIP ---

        // Armazenar no bombasMap para referência futura (se bombasMap for gerenciado em main.js)
        if (window.bombasMap) {
            window.bombasMap[bomba.nome] = {
                marker: marcadorBombaIcon, // Marcador do ícone
                label: labelBomba,      // Marcador do label
                data: { ...bomba }      // Guarda todos os dados da bomba, incluindo o status 'fora'
            };
        }
    });
    toggleLegendas(legendasAtivas);
}

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

        const antenaLabel = marcadoresLegenda.find(m => m.options.labelType === 'antena');
        if (antenaLabel) {
            const labelEl = antenaLabel.getElement();
            if(labelEl) labelEl.style.display = (isChecked && legendasAtivas) ? '' : 'none';
        }

        if (window.antenaGlobal.overlay) window.antenaGlobal.overlay.setOpacity(isChecked ? opacityValue : 0);
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

/**
 * Desenha a linha de visada e o marcador de bloqueio/ponto mais alto.
 * @param {Array<number>} latlonOrigem - Coordenadas do ponto de origem da visada.
 * @param {Array<number>} latlonDestino - Coordenadas do ponto de destino da visada.
 * @param {object | null} dadosBloqueioAPI - Objeto {lat, lon, elev, diff, dist} da API, ou null.
 * @param {object | null} dadosPontoMaisAlto - Objeto {lat, lon, elev} do ponto de maior elevação geodésica.
 * @param {string} nomeDiagnostico - Nome da linha/diagnóstico (ex: "Pivô A → Pivô B" ou "Antena → Pivô X").
 * @param {string | null} distanciaTotalPivosFormatada - Distância total formatada (usado APENAS para LoS entre pivôs).
 */
function drawDiagnostico(latlonOrigem, latlonDestino, dadosBloqueioAPI, dadosPontoMaisAlto, nomeDiagnostico, distanciaTotalPivosFormatada = null) {
    if (!map) return;

    const linha = drawVisadaComGradiente(latlonOrigem, latlonDestino);

    let pontoParaMarcador = null;
    let mensagemTooltip = `<strong>${nomeDiagnostico}</strong>`;
    let usarIconeAtencaoReal = false; // Indica se há um bloqueio efetivo
    let localIconUrl = "./assets/images/attention-icon-original.svg"; // Ícone padrão para ponto mais alto
    let localIconSize = [20, 20];

    // Caso 1: Diagnóstico de Visada entre Pivôs (distanciaTotalPivosFormatada é fornecida)
    if (distanciaTotalPivosFormatada) {
        mensagemTooltip += `<br>Dist. Total: ${distanciaTotalPivosFormatada}`;
    }

    // Analisa os dados de bloqueio da API (objeto {lat, lon, elev, diff, dist})
    // Este objeto é o 'ponto crítico' retornado pela API.
    if (dadosBloqueioAPI && typeof dadosBloqueioAPI.lat === 'number' && typeof dadosBloqueioAPI.elev === 'number' && typeof dadosBloqueioAPI.diff === 'number') {
        pontoParaMarcador = dadosBloqueioAPI; // O marcador será no ponto crítico retornado pela API
        usarIconeAtencaoReal = dadosBloqueioAPI.diff > 0.1; // Considera bloqueio se diff > 0.1m

        mensagemTooltip += `<br>Ponto Crítico: Elev. ${pontoParaMarcador.elev.toFixed(1)}m`;
        
        if (usarIconeAtencaoReal) {
            localIconUrl = "./assets/images/attention-icon-original.svg";
            localIconSize = [24, 24];
            mensagemTooltip += `<br><span style="color: #FF9800;">⛔ Bloqueio: ${dadosBloqueioAPI.diff.toFixed(1)}m acima</span>`;
        } else {
            // Se diff <= 0.1, o ponto crítico não é um bloqueio real.
            // Se estamos no diagnóstico Pivô-Pivô, podemos mostrar que está livre nesse ponto.
            // Se for diagnóstico Torre-Pivô e o pivô está sem sinal, não diremos "livre" aqui,
            // pois o "sem sinal" já indica o problema geral.
            localIconUrl = "./assets/images/circle-check-big.svg";
            localIconSize = [22, 22];
            if (distanciaTotalPivosFormatada) { // Só adiciona "Livre" se for diagnóstico Pivô-Pivô
                 mensagemTooltip += `<br><span style="color: #4CAF50;">✅ Livre no Ponto Crítico (${dadosBloqueioAPI.diff.toFixed(1)}m)</span>`;
            } else {
                 // Para Torre-Pivô, se não há bloqueio no ponto crítico, apenas mostramos a elevação.
                 // A informação de "sem sinal" do pivô já é o indicativo principal.
            }
        }
    } else if (dadosPontoMaisAlto && typeof dadosPontoMaisAlto.lat === 'number' && typeof dadosPontoMaisAlto.elev === 'number') {
        // Caso 2: Sem dados de bloqueio da API (ou diff não é número), mas temos o ponto mais alto geodésico.
        // ISSO É IMPORTANTE PARA O DIAGNÓSTICO DA TORRE PRINCIPAL -> PIVÔ SEM SINAL.
        pontoParaMarcador = dadosPontoMaisAlto;
        localIconUrl = "./assets/images/attention-icon-original.svg"; // Ícone de montanha para ponto mais alto
        localIconSize = [20, 20];
        mensagemTooltip += `<br>Ponto Mais Alto: Elev. ${pontoParaMarcador.elev.toFixed(1)}m`;
        usarIconeAtencaoReal = false; // Não é um bloqueio confirmado pela API, apenas o ponto mais alto.
    }

    // Desenha o marcador SE houver um pontoParaMarcador definido
    // E, no caso do diagnóstico da TORRE PRINCIPAL, queremos mostrar o ponto mais alto SEMPRE que ele existir,
    // mesmo que não haja bloqueio (usarIconeAtencaoReal = false).
    // No caso PIVÔ-PIVÔ, só mostramos o marcador se houver dadosBloqueioAPI (ponto crítico).
    let deveMostrarMarcador = false;
    if (distanciaTotalPivosFormatada) { // Diagnóstico Pivô-Pivô
        deveMostrarMarcador = !!dadosBloqueioAPI; // Só mostra se a API retornou um ponto crítico
    } else { // Diagnóstico Torre Principal -> Pivô
        deveMostrarMarcador = !!pontoParaMarcador; // Mostra se tiver ponto crítico OU ponto mais alto
    }


    if (deveMostrarMarcador && pontoParaMarcador) {
        // Se for diagnóstico Torre-Pivô e não há bloqueio real no ponto crítico, mas temos um ponto mais alto,
        // o ícone será mountain-icon-grey. Se há bloqueio real, será attention.
        if (!distanciaTotalPivosFormatada && dadosBloqueioAPI && !usarIconeAtencaoReal && dadosPontoMaisAlto && pontoParaMarcador === dadosBloqueioAPI) {
            // Pivô sem sinal, API retornou ponto crítico mas não é bloqueio.
            // Se quisermos mostrar o ponto mais alto geodésico em vez do ponto crítico "livre":
            // pontoParaMarcador = dadosPontoMaisAlto; // Descomente se preferir
            // localIconUrl = "./assets/images/mountain-icon-grey.svg";
            // localIconSize = [20, 20];
            // mensagemTooltip = `<strong>${nomeDiagnostico}</strong><br>Ponto Mais Alto: Elev. ${dadosPontoMaisAlto.elev.toFixed(1)}m`; // Atualiza tooltip
            // A lógica atual já deve usar mountain-icon-grey se usarIconeAtencaoReal for false após o if/else de dadosBloqueioAPI.
        }


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
        direction: 'top', // Isso já ajuda a posicionar em cima
        className: 'tooltip-sinal tooltip-visada-diagnostico', //tooltip-sinal aplicará o fade
        offset: [0, - (localIconSize[1] / 2 + 5)], // Ajusta dinamicamente
        opacity: 0.95 // Opacidade final do tooltip em si, não da transição
    });
        marcadoresBloqueio.push(marker);
    }

    linhasDiagnostico.push(linha);
}


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
        toggleLegendaButton.title = show ? "Esconder Legendas" : "Mostrar Legendas";
        if (iconSpan) {
            // Correção do ícone para o botão de legenda (ruler-captions.svg não existe)
            const iconPath = show ? 'assets/images/captions.svg' : 'assets/images/captions-off.svg'; // Assumindo que captions-off.svg existe
            iconSpan.style.webkitMaskImage = `url(${iconPath})`;
            iconSpan.style.maskImage = `url(${iconPath})`;
        }
    }
}

function updateOverlaysOpacity(opacityValue) {
    const isPanelItemChecked = (overlay) => {
        if (window.antenaGlobal?.overlay === overlay) {
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
        console.warn("candidateRepeaterSitesLayerGroup não está definido.");
        window.candidateRepeaterSitesLayerGroup = L.layerGroup().addTo(map);
    }

    if (!sites || sites.length === 0) {
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
                ${site.has_los ? '<br><span class="los-ok">✅LoS</span>' : '<br><span class="los-no">❌¬LoS</span>'}
                <br><span class="distancia-info">Dist: ${site.distance_to_target ? site.distance_to_target.toFixed(0) + 'm' : 'N/A'}</span>
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
}

function togglePivoDistances(show) {
    if (window.lastPivosDataDrawn && window.lastPivosDataDrawn.length > 0) {
        drawPivos(window.lastPivosDataDrawn, true);
        if (typeof mostrarMensagem === 'function') {
             mostrarMensagem(`Distâncias dos pivôs ${show ? 'exibidas' : 'ocultas'}.`, 'sucesso');
        }
    } else if (Object.keys(pivotsMap).length > 0 && window.currentProcessedKmzData && window.currentProcessedKmzData.pivos) {
        console.warn("togglePivoDistances: Reconstruindo dados dos pivôs pois window.lastPivosDataDrawn estava vazio.");
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
        drawPivos(pivosReconstruidos, true);
         if (typeof mostrarMensagem === 'function') {
            mostrarMensagem(`Distâncias dos pivôs ${show ? 'exibidas' : 'ocultas'} (via fallback).`, 'sucesso');
        }
    }
}
window.togglePivoDistances = togglePivoDistances;