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

let tempSectorShape = null;
let tempPacmanShape = null;

// --- FUNÇÕES DE LÓGICA DE DESENHO DINÂMICO ---

function getDynamicIconSize(zoom) {
    const minZoom = 10; // Zoom mínimo em que o ícone começa a diminuir
    const maxZoom = 17; // Zoom em que o ícone atinge o tamanho máximo
    const minSize = 4;  // Tamanho mínimo do ícone em pixels
    const maxSize = 16; // Tamanho máximo do ícone em pixels

    if (zoom <= minZoom) {
        return minSize;
    }
    if (zoom >= maxZoom) {
        return maxSize;
    }

    // Interpolação linear para calcular o tamanho nos zooms intermediários
    const zoomRange = maxZoom - minZoom;
    const sizeRange = maxSize - minSize;
    const size = ((zoom - minZoom) / zoomRange) * sizeRange + minSize;
    
    return Math.round(size);
}


function updatePivotIcons() {
    if (!map || !AppState.lastPivosDataDrawn) return;
    if (AppState.modoEdicaoPivos) {
        return;
    }

    const newSize = getDynamicIconSize(map.getZoom());

    AppState.lastPivosDataDrawn.forEach(pivo => {
        const marker = AppState.pivotsMap[pivo.nome];
        if (marker) {
            const cor = pivo.fora ? 'red' : 'green';

            let iconClasses = 'pivo-marker-container';

            if (AppState.selectedPivoMarker === marker) {
                iconClasses += ' pivo-marker-container-selected';
            }

            const newIcon = L.divIcon({
                className: iconClasses,
                iconSize: [newSize, newSize],
                html: `<div class="pivo-marker-dot" style="background-color: ${cor};"></div>`
            });
            marker.setIcon(newIcon);
        }
    });
}

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
                id: 'main_antenna', // ID para referência
                name: AppState.antenaGlobal.nome || t('ui.labels.main_antenna_default'), // Nome original ou padrão
                distance: distance,
                isMainAntenna: true,
                type: AppState.antenaGlobal.type // Adiciona o tipo
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
                    id: rep.id, // ID da repetidora
                    name: rep.nome, // Nome original da repetidora
                    distance: distance,
                    isMainAntenna: false,
                    type: rep.type // Adiciona o tipo
                };
            }
        }
    });

    return closestSource;
}

// NOVO: Função para obter o nome formatado da antena/repetidora para a legenda
function getFormattedAntennaOrRepeaterName(entity) {
    console.log("DEBUG: getFormattedAntennaOrRepeaterName received entity:", entity);

    const alturaStr = entity.altura ? `${entity.altura}m` : '';

    if (entity.isMainAntenna) {
        // Lógica para a ANTENA PRINCIPAL (não alterada)
        if (entity.type === 'central') {
            return `${t('entity_names.central')} - ${alturaStr}`;
        }
        if (entity.type === 'central_repeater_combined') {
            return `${t('entity_names.central_repeater_combined')} - ${alturaStr}`;
        }
        if (entity.type === 'tower') {
            return `${t('entity_names.tower')} - ${alturaStr}`;
        }
        return entity.original_name || entity.nome || t('ui.labels.main_antenna_default');
    } else {
        // Lógica para as REPETIDORAS (NÃO a antena principal)
        if (entity.type === 'central') { // <--- ADICIONADO para repetidoras
            return `${t('entity_names.central')} - ${alturaStr}`;
        }
        if (entity.type === 'central_repeater_combined') { // <--- ADICIONADO para repetidoras
            return `${t('entity_names.central_repeater_combined')} - ${alturaStr}`;
        }
        if (entity.type && entity.type !== 'default') { // Tipos como 'tower', 'post', 'water_tank'
            return `${t(`entity_names.${entity.type}`)} - ${alturaStr}`; // Formata como "Torre - 5m"
        }
        // Tipo 'default' ou se não houver tipo específico (ex: "Repetidora 01")
        return entity.nome;
    }
}

// Função auxiliar para criar e exibir o menu de contexto
function showRenameRepeaterMenu(marker, currentName, isMainAntenna, entityId) {
    // Remove qualquer menu existente para evitar múltiplos menus
    removeRenameMenu();

    const menu = document.createElement('div');
    menu.className = 'rename-menu absolute bg-gray-900 border border-gray-700 rounded-md shadow-lg p-2 z-[10002]';

    // Define as opções de renomeação com base no tipo de entidade
    let options = [];
    if (isMainAntenna) {
        options = [
            { text: t('entity_names.central'), value: 'central' },
            { text: t('entity_names.central_repeater_combined'), value: 'central_repeater_combined' }
        ];
    } else { // Opções para REPETIDORAS
        options = [
            { text: t('entity_names.tower'), value: 'tower' },
            { text: t('entity_names.post'), value: 'post' },
            { text: t('entity_names.water_tank'), value: 'water_tank' },
            { text: t('entity_names.central'), value: 'central' },
            { text: t('entity_names.central_repeater_combined'), value: 'central_repeater_combined' }
        ];
    }

    // Cria os botões de opção
    options.forEach(option => {
        const button = document.createElement('button');
        button.textContent = option.text;
        button.className = 'block w-full text-left px-3 py-1 text-white hover:bg-gray-700 rounded-sm text-sm';
        button.onclick = (e) => {
            e.stopPropagation();
            if (isMainAntenna) {
                handleRenameMainAntenna(option.value); // Esta função já cuida de fechar o menu
            } else {
                handleRenameRepeater(entityId, option.value);
                removeRenameMenu(); // Fecha o menu para repetidoras
            }
        };
        menu.appendChild(button);
    });

    // --- LÓGICA CORRIGIDA E SIMPLIFICADA ---
    // Adiciona o botão "Voltar ao Nome Original"
    const restoreOriginalButton = document.createElement('button');
    restoreOriginalButton.textContent = t('ui.titles.restore_original_name');
    restoreOriginalButton.className = 'block w-full text-left px-3 py-1 text-white hover:bg-gray-700 rounded-sm text-sm mt-2 border-t border-gray-600 pt-2';

    restoreOriginalButton.onclick = (e) => {
        e.stopPropagation();
        if (isMainAntenna) {
            // Apenas chama a função principal. Ela já tem a lógica para reverter e fechar o menu.
            if (AppState.antenaGlobal?.original_name) {
                handleRenameMainAntenna('default');
            }
        } else {
            // Apenas chama a função principal para a repetidora.
            const repetidora = AppState.repetidoras.find(r => r.id === entityId);
            if (repetidora?.original_name) {
                handleRenameRepeater(entityId, 'default');
                removeRenameMenu(); // Fecha o menu
            }
        }
    };
    menu.appendChild(restoreOriginalButton);

    // Posiciona o menu no mapa
    const mapContainer = map.getContainer();
    const markerPos = map.latLngToContainerPoint(marker.getLatLng());
    menu.style.left = `${markerPos.x + 20}px`;
    menu.style.top = `${markerPos.y}px`;

    mapContainer.appendChild(menu);

    // Adiciona um listener para fechar o menu se o usuário clicar fora
    setTimeout(() => {
        document.addEventListener('click', removeRenameMenu, { once: true });
    }, 100);
}

/**
 * Remove o menu de renomeação do DOM.
 */
function removeRenameMenu() {
    const existingMenu = document.querySelector('.rename-menu');
    if (existingMenu) {
        existingMenu.remove();
        // O listener de clique fora é removido automaticamente com `once: true`
    }
}

// --- Funções de Desenho ---

function drawAntenaCandidates(antenasList) {
    if (!map || !AppState.antenaCandidatesLayerGroup) return;

    AppState.antenaCandidatesLayerGroup.clearLayers();
    
    antenasList.forEach(antenaData => {
        const uniqueId = `candidate-${antenaData.nome}-${antenaData.lat}`;
        
        const marker = L.marker([antenaData.lat, antenaData.lon], { icon: antenaIcon, customData: antenaData, customId: uniqueId })
            .addTo(AppState.antenaCandidatesLayerGroup);

        const nomeAntena = antenaData.nome;
        // Modificado: a label agora considera o tipo, mesmo para candidatas se aplicável.
        // As candidatas não terão um `type` definido, então `getFormattedAntennaOrRepeaterName` usará o `nome` original.
        const formattedName = getFormattedAntennaOrRepeaterName({
            isMainAntenna: true, // É uma candidata para antena principal
            type: antenaData.type, // Pega o tipo se existir (do KMZ, por exemplo)
            nome: nomeAntena,
            altura: antenaData.altura
        });
        const labelWidth = (formattedName.length * 7) + 10;
        const label = L.marker([antenaData.lat, antenaData.lon], {
            icon: L.divIcon({ 
                className: 'label-pivo', 
                html: formattedName, 
                iconSize: [labelWidth, 20], 
                iconAnchor: [labelWidth / 2, 45] 
            }),
            interactive: false, 
            customId: uniqueId,
            labelType: 'antena_candidate'
        }).addTo(AppState.antenaCandidatesLayerGroup);
        
        AppState.marcadoresLegenda.push(label);

        marker.on('click', (e) => {
            L.DomEvent.stopPropagation(e);
            const data = e.target.options.customData;
            AppState.coordenadaClicada = e.latlng;
            window.clickedCandidateData = data;
            const painelRepetidora = document.getElementById("painel-repetidora");
            const inputAltura = document.getElementById("altura-antena-rep");
            if (painelRepetidora && inputAltura) {
                inputAltura.value = data.altura;
                // Preenche também a altura do receptor se disponível nos dados da candidata
                const inputAlturaRx = document.getElementById("altura-receiver-rep");
                if (inputAlturaRx && data.altura_receiver) {
                    inputAlturaRx.value = data.altura_receiver;
                }
                painelRepetidora.classList.remove("hidden");
                mostrarMensagem(t('messages.success.tower_selected_for_simulation', { name: data.nome }), "sucesso");
            }
        });
    });

    updateLegendsVisibility()
}

function drawPivos(pivosData, useEdited = false) {
    if (!map || !pivosData) return;

    // Limpa marcadores e legenda de pivôs antigos
    AppState.marcadoresPivos.forEach(m => map.removeLayer(m));
    AppState.marcadoresPivos = [];
    AppState.pivotsMap = {};
    const legendasRestantes = AppState.marcadoresLegenda.filter(l => l.options.labelType !== 'pivot');
    AppState.marcadoresLegenda.filter(l => l.options.labelType === 'pivot').forEach(l => map.removeLayer(l));
    AppState.marcadoresLegenda = legendasRestantes;

    pivosData.forEach(pivo => {
        const cor = pivo.fora ? 'red' : 'green';
        const pos = useEdited && AppState.posicoesEditadas[pivo.nome] ? L.latLng(AppState.posicoesEditadas[pivo.nome].lat, AppState.posicoesEditadas[pivo.nome].lng) : L.latLng(pivo.lat, pivo.lon);
        
        const initialSize = getDynamicIconSize(map.getZoom());
        const pivoIcon = L.divIcon({
            className: 'pivo-marker-container',
            iconSize: [initialSize, initialSize],
            html: `<div class="pivo-marker-dot" style="background-color: ${cor};"></div>`
        });

        const marker = L.marker(pos, { icon: pivoIcon }).addTo(map);

        // Lógica para criar o label com nome e distância
        let finalHtml = pivo.nome;
        let hasDistancia = false;
        let labelWidth = (pivo.nome.length * 6.5) + 15;

        if (AppState.distanciasPivosVisiveis) {
            const closest = findClosestSignalSource(pos);
            if (closest) {
                const distanciaFormatada = closest.distance > 999 ? (closest.distance / 1000).toFixed(1) + ' km' : Math.round(closest.distance) + ' m';
                
                // NOVO: Adicionar o nome formatado da fonte (antena/repetidora)
                let sourceFormattedName = "";
                if (closest.isMainAntenna) {
                    sourceFormattedName = getFormattedAntennaOrRepeaterName({
                        isMainAntenna: true,
                        type: AppState.antenaGlobal?.type,
                        nome: AppState.antenaGlobal?.nome,
                        altura: AppState.antenaGlobal?.altura
                    });
                } else {
                    const rep = AppState.repetidoras.find(r => r.id === closest.id);
                    if (rep) {
                        sourceFormattedName = getFormattedAntennaOrRepeaterName({
                            isMainAntenna: false,
                            type: rep.type,
                            nome: rep.nome,
                            altura: rep.altura
                        });
                    }
                }

                finalHtml = `${pivo.nome}<br><span class="source-name-pivo">${sourceFormattedName}</span><br><span class="distancia-pivo">${distanciaFormatada}</span>`;
                hasDistancia = true;
                // Ajusta a largura da label para o texto mais longo entre o nome do pivô e o nome da fonte
                labelWidth = Math.max(labelWidth, (sourceFormattedName.length * 6.5) + 15, (distanciaFormatada.length * 6.5) + 15);
            }
        }

        const labelHeight = hasDistancia ? 55 : 20;
        const label = L.marker(pos, {
            icon: L.divIcon({ className: 'label-pivo', html: finalHtml, iconSize: [labelWidth, labelHeight], iconAnchor: [labelWidth / 2, -15] }),
            labelType: 'pivot'
        }).addTo(map);
        AppState.marcadoresLegenda.push(label);
        
        const statusTexto = pivo.fora ? `<span style="color:#ff4d4d; font-weight:bold;">${t('tooltips.out_of_signal')}</span>` : `<span style="color:#22c55e; font-weight:bold;">${t('tooltips.in_signal')}</span>`;
        marker.bindTooltip(`<div style="text-align:center;">${statusTexto}</div>`, { permanent: false, direction: 'top', offset: [0, -10], className: 'tooltip-sinal' });

        // Manipulador de clique com toda a lógica
        marker.on('click', (e) => {
            L.DomEvent.stopPropagation(e); 

            // Lógica de seleção visual
            const pivoElement = marker.getElement();
            if (pivoElement) {
                if (AppState.selectedPivoMarker === marker) {
                    pivoElement.classList.remove('pivo-marker-container-selected');
                    AppState.selectedPivoMarker = null;
                } else {
                    if (AppState.selectedPivoMarker) {
                        const oldSelectedElement = AppState.selectedPivoMarker.getElement();
                        if (oldSelectedElement) {
                            oldSelectedElement.classList.remove('pivo-marker-container-selected');
                        }
                    }
                    pivoElement.classList.add('pivo-marker-container-selected');
                    AppState.selectedPivoMarker = marker;
                }
            }

            // Lógica dos diferentes modos de operação
            if (AppState.modoEdicaoPivos) {
                 marker.bindPopup(`<div class="popup-glass">✏️ ${pivo.fora ? t('tooltips.out_of_signal') : t('tooltips.in_signal')}</div>`).openPopup();
            } 
            else if (AppState.modoLoSPivotAPivot) {
                if (typeof handleLoSTargetClick === 'function') handleLoSTargetClick(pivo, marker);
            } 
            else if (AppState.modoBuscaLocalRepetidora) {
                if (typeof handlePivotSelectionForRepeaterSite === 'function') handlePivotSelectionForRepeaterSite(pivo, marker);
            } else {
                window.ultimoCliqueFoiSobrePivo = true;
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
    updateLegendsVisibility();
}

function updateAntenaOrRepeaterLabel(entity) {
    if (entity.label && map.hasLayer(entity.label)) {
        const newHtml = getFormattedAntennaOrRepeaterName(entity);
        const labelWidth = (newHtml.length * 7) + 10; // Recalcula largura
        entity.label.setIcon(L.divIcon({
            className: 'label-pivo',
            html: newHtml,
            iconSize: [labelWidth, 20],
            iconAnchor: [labelWidth / 2, 45]
        }));
    }
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
        
        marcadorBomba.on('click', (e) => {
            L.DomEvent.stopPropagation(e);
            if (AppState.modoLoSPivotAPivot) {
                if (typeof handleLoSTargetClick === 'function') {
                    const bombaDataForHandler = {
                        nome: nomeBomba,
                        fora: bomba.fora
                    };
                    handleLoSTargetClick(bombaDataForHandler, marcadorBomba);
                }
            }
        });

        marcadorBomba.on('contextmenu', (e) => {
            L.DomEvent.stop(e); 
            if (confirm(t('messages.confirm.remove_irripump', { name: nomeBomba }))) {
                map.removeLayer(marcadorBomba);
                const labelParaRemover = AppState.marcadoresLegenda.find(l => 
                    l.getLatLng().equals(marcadorBomba.getLatLng()) && 
                    l.options.labelType === 'bomba' && 
                    l.options.icon.options.html.includes(nomeBomba)
                );
                if (labelParaRemover) {
                    map.removeLayer(labelParaRemover);
                    AppState.marcadoresLegenda = AppState.marcadoresLegenda.filter(l => l !== labelParaRemover);
                }

                AppState.lastBombasDataDrawn = AppState.lastBombasDataDrawn.filter(b => 
                    !(b.lat === bomba.lat && b.lon === bomba.lon)
                );
                drawBombas(AppState.lastBombasDataDrawn); 
                atualizarPainelDados();
                reavaliarPivosViaAPI(); 
                mostrarMensagem(t('messages.success.irripump_removed', { name: nomeBomba }), 'sucesso');
            }
        });

        let finalHtml = nomeBomba;
        let hasDistancia = false;
        let labelWidth = (nomeBomba.length * 6.5) + 15;

        if (AppState.distanciasPivosVisiveis) {
            const closest = findClosestSignalSource(L.latLng(bomba.lat, bomba.lon));
            if (closest) {
                const distanciaFormatada = closest.distance > 999 ? (closest.distance / 1000).toFixed(1) + ' km' : Math.round(closest.distance) + ' m';
                
                // NOVO: Adicionar o nome formatado da fonte (antena/repetidora)
                let sourceFormattedName = "";
                if (closest.isMainAntenna) {
                    sourceFormattedName = getFormattedAntennaOrRepeaterName({
                        isMainAntenna: true,
                        type: AppState.antenaGlobal?.type,
                        nome: AppState.antenaGlobal?.nome,
                        altura: AppState.antenaGlobal?.altura
                    });
                } else {
                    const rep = AppState.repetidoras.find(r => r.id === closest.id);
                    if (rep) {
                        sourceFormattedName = getFormattedAntennaOrRepeaterName({
                            isMainAntenna: false,
                            type: rep.type,
                            nome: rep.nome,
                            altura: rep.altura
                        });
                    }
                }

                finalHtml = `${nomeBomba}<br><span class="source-name-pivo">${sourceFormattedName}</span><br><span class="distancia-pivo">${distanciaFormatada}</span>`;
                hasDistancia = true;
                labelWidth = Math.max(labelWidth, (sourceFormattedName.length * 6.5) + 15, (distanciaFormatada.length * 6.5) + 15);
            }
        }
        
        const labelHeight = hasDistancia ? 55 : 20;
        const labelBomba = L.marker([bomba.lat, bomba.lon], {
            icon: L.divIcon({ className: 'label-pivo', html: finalHtml, iconSize: [labelWidth, labelHeight], iconAnchor: [labelWidth / 2, -5] }),
            labelType: 'bomba', interactive: false
        }).addTo(map);
        AppState.marcadoresLegenda.push(labelBomba);
    });
    updateLegendsVisibility()
}


function drawCirculos(ciclosData) {
    if (!map) return;

    AppState.circulosPivos.forEach(c => map.removeLayer(c));
    AppState.circulosPivos = [];
    AppState.lastPivosDataDrawn.forEach(pivo => {
        const pivoLatLng = L.latLng(pivo.lat, pivo.lon);

        if (pivo.tipo === 'custom' && Array.isArray(pivo.coordenadas) && pivo.coordenadas.length > 0) {
            const polygon = L.polygon(pivo.coordenadas, {
                color: '#cc0000',
                weight: 3,
                opacity: 0.9,
                fillOpacity: 0,
                className: 'circulo-custom-kmz'
            }).addTo(map);
            AppState.circulosPivos.push(polygon);
        }

        else if (pivo.tipo === 'setorial') {
            const sectorCoords = generateSectorCoords(pivoLatLng, pivo.raio, pivo.angulo_central, pivo.abertura_arco);
            const sectorPolygon = L.polygon(sectorCoords, {
                color: '#cc0000',
                weight: 3,
                opacity: 0.9,
                fillOpacity: 0,
                className: 'circulo-pivo-setorial'
            }).addTo(map);
            AppState.circulosPivos.push(sectorPolygon);
        }

        else if (pivo.tipo === 'pacman') {
            const pacmanCoords = generatePacmanCoords(pivoLatLng, pivo.raio, pivo.angulo_inicio, pivo.angulo_fim);
            const pacmanPolygon = L.polygon(pacmanCoords, {
                color: '#cc0000',
                weight: 3,
                opacity: 0.9,
                fillOpacity: 0,
                className: 'circulo-pivo-pacman'
            }).addTo(map);
            AppState.circulosPivos.push(pacmanPolygon);
        }

        else {
            const circle = L.circle(pivoLatLng, {
                radius: pivo.raio || 100,
                color: '#cc0000',
                weight: 3,
                opacity: 0.9,
                fillOpacity: 0,
                className: 'circulo-vermelho-pulsante'
            }).addTo(map);
            AppState.circulosPivos.push(circle);
        }
    });
}


function drawImageOverlay(url, bounds, opacity = 1.0) {
    if (!map || !url || !bounds) return null;

    // Determina se estamos em ambiente local.
    const isLocal = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1";
    // Define a URL base do backend.
    const BACKEND_URL = isLocal ? "http://localhost:8000" : "https://irricontrol-test.onrender.com";

    // Constrói a URL completa para a imagem, garantindo que ela seja carregada do servidor backend.
    const fullUrl = url.startsWith('http') ? url : `${BACKEND_URL}${url}`;

    const imageBounds = [[bounds[0], bounds[1]], [bounds[2], bounds[3]]];
    // Usa a URL completa para criar o overlay.
    const overlay = L.imageOverlay(fullUrl, imageBounds, { opacity, interactive: false }).addTo(map);
    AppState.overlaysVisiveis.push(overlay);
    return overlay;
}


function addRepetidoraNoPainel(repetidora) {
    const container = document.getElementById("lista-repetidoras");
    const item = document.createElement("div");
    item.className = "flex justify-between items-center bg-gray-800/60 px-3 py-2 rounded-lg border border-white/10";
    item.id = `rep-item-${repetidora.id}`;
    
    const diagBtnHtml = `<button class="text-white/60 hover:text-sky-300 transition relative top-px" title="${t('tooltips.run_diagnostic_from_source')}" data-id="${repetidora.id}" data-action="diagnostico">
        <span class="sidebar-icon w-4 h-4" style="-webkit-mask-image: url(assets/images/mountain.svg); mask-image: url(assets/images/mountain.svg);"></span>
    </button>`;

    // NOVO: Exibe o nome formatado
    item.innerHTML = `
        <span class="text-white/80 text-sm">${getFormattedAntennaOrRepeaterName(repetidora)}</span>
        <div class="flex gap-3 items-center">
            ${diagBtnHtml}
            <button class="text-white/60 hover:text-sky-300 transition" title="${t('tooltips.show_hide_coverage')}" data-id="${repetidora.id}" data-action="toggle-visibility" data-visible="true">
                <i data-lucide="eye" class="w-4 h-4 text-green-500"></i>
            </button>
            <button class="text-red-500 hover:text-red-400 text-xs font-bold transition" title="Remover Repetidora" data-id="${repetidora.id}" data-action="remover">
                ❌
            </button>
        </div>`;
    
    container.appendChild(item);
    lucide.createIcons();

    // NOVO: Adiciona o event listener para o menu de contexto no marcador da repetidora
    repetidora.marker.on('contextmenu', (e) => {
        L.DomEvent.stop(e); // Previne o menu de contexto padrão do navegador
        showRenameRepeaterMenu(repetidora.marker, repetidora.nome, false, repetidora.id, repetidora.type);
    });

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

    const diagBtnHtml = `<button class="text-white/60 hover:text-sky-300 transition relative top-px" title="${t('tooltips.run_diagnostic_from_source')}" data-action="diagnostico">
        <span class="sidebar-icon w-4 h-4" style="-webkit-mask-image: url(assets/images/mountain.svg); mask-image: url(assets/images/mountain.svg);"></span>
    </button>`;

    // Exibe o nome formatado (o que já está sendo feito)
    item.innerHTML = `
        <span class="text-white/90 font-semibold text-sm">${getFormattedAntennaOrRepeaterName(antena)}</span>
        <div class="flex gap-3 items-center">
            ${diagBtnHtml}
            <button class="text-white/60 hover:text-sky-300 transition" title="${t('tooltips.show_hide_coverage')}" data-action="toggle-visibility" data-visible="true">
                <i data-lucide="eye" class="w-4 h-4 text-green-500"></i>
            </button>
        </div>`;
    
    container.firstChild ? container.insertBefore(item, container.firstChild) : container.appendChild(item);
    lucide.createIcons();

    // ADICIONE AQUI O LISTENER PARA O CLIQUE DIREITO NO ELEMENTO DO PAINEL,
    // ALÉM DO MARCADOR NO MAPA. Isso garante que a atualização do tipo funcione de ambos.
    item.addEventListener('contextmenu', (e) => {
        L.DomEvent.stop(e); // Previne o menu de contexto padrão do navegador
        // Passa o marcador da antena, nome atual, true para antena principal e null para ID
        showRenameRepeaterMenu(AppState.marcadorAntena, antena.nome, true, null); // Passa o marcador da antena
    });

    // O listener do marcador do mapa já está OK
    if (AppState.marcadorAntena) {
        AppState.marcadorAntena.on('contextmenu', (e) => {
            L.DomEvent.stop(e); // Previne o menu de contexto padrão do navegador
            showRenameRepeaterMenu(AppState.marcadorAntena, antena.nome, true, null);
        });
    }

    item.querySelector('[data-action="diagnostico"]').addEventListener('click', () => runTargetedDiagnostic(antena));
    
    const visibilityBtn = item.querySelector('[data-action="toggle-visibility"]');
    visibilityBtn.addEventListener('click', () => {
        const isVisible = visibilityBtn.getAttribute('data-visible') === 'true';
        const newState = !isVisible;
        visibilityBtn.setAttribute('data-visible', String(newState));
        
        const opacityValue = parseFloat(rangeOpacidade.value);
        if (antena?.overlay) antena.overlay.setOpacity(newState ? opacityValue : 0);
        
        visibilityBtn.innerHTML = newState ? `<i data-lucide="eye" class="w-4 h-4 text-green-500"></i>` : `<i data-lucide="eye-off" class="w-4 h-4 text-gray-500"></i>`;
        lucide.createIcons();
        setTimeout(reavaliarPivosViaAPI, 100);
    });
}

function drawDiagnostico(latlonOrigem, latlonDestino, dadosBloqueioAPI, dadosPontoMaisAlto, nomeDiagnostico, distanciaFormatada = null) {
    if (!map || !AppState.visadaLayerGroup) return;

    const linha = drawVisadaComGradiente(latlonOrigem, latlonDestino);
    
    const estaBloqueado = dadosBloqueioAPI?.diff > 0.1;

    let iconUrl;
    let iconSize;
    let mensagemTooltip;
    let markerLatLng;
    let tooltipColor; 

    if (estaBloqueado) {
        iconUrl = ATTENTION_ICON_PATH;
        iconSize = [24, 24];
        markerLatLng = [dadosBloqueioAPI.lat, dadosBloqueioAPI.lon];
        mensagemTooltip = `<strong>${nomeDiagnostico}</strong>`;
        if (distanciaFormatada) {
            mensagemTooltip += `<br>${t('ui.labels.pivo_distance_label')} ${distanciaFormatada}`;
        }
        mensagemTooltip += `<br>${t('tooltips.blockage_point', { elevation: dadosBloqueioAPI.elev.toFixed(1) })}`;
        tooltipColor = '#FF9800'; 
        mensagemTooltip += `<br><span style="color: ${tooltipColor};">${t('tooltips.blockage_present', { diff: dadosBloqueioAPI.diff.toFixed(1) })}</span>`;
    } else {
        iconUrl = MOUNTAIN_ICON_PATH;
        iconSize = [22, 22]; 
        markerLatLng = [dadosPontoMaisAlto.lat, dadosPontoMaisAlto.lon];
        mensagemTooltip = `<strong>${nomeDiagnostico}</strong>`;
        if (distanciaFormatada) {
            mensagemTooltip += `<br>${t('ui.labels.pivo_distance_label')} ${distanciaFormatada}`;
        }
        tooltipColor = '#FF9800'; 
        mensagemTooltip += `<br><span style="color: ${tooltipColor};">${t('tooltips.highest_point_short', { elevation: dadosPontoMaisAlto.elev.toFixed(1) })}</span>`; 
    }

    if (markerLatLng && markerLatLng[0] && markerLatLng[1]) {
        const markerIcon = L.divIcon({
            className: 'label-bloqueio-dinamico',
            html: `<img src="${iconUrl}" style="width:${iconSize[0]}px; height:${iconSize[1]}px;">`,
            iconSize: iconSize, iconAnchor: [iconSize[0]/2, iconSize[1]/2]
        });
        const marker = L.marker(markerLatLng, { icon: markerIcon })
            .addTo(AppState.visadaLayerGroup)
            .bindTooltip(mensagemTooltip, { permanent: false, direction: 'top', className: 'tooltip-sinal tooltip-visada-diagnostico', offset: [0, -(iconSize[1]/2 + 5)] });
        AppState.marcadoresBloqueio.push(marker);
    }
    
    AppState.linhasDiagnostico.push(linha);
}

function clearMapLayers() {
    if (!map) return;
    
    const layersAndGroups = [
        AppState.marcadorAntena, 
        AppState.antenaCandidatesLayerGroup, 
        AppState.marcadorPosicionamento,
        AppState.visadaLayerGroup,
        window.candidateRepeaterSitesLayerGroup,
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


}


function updateLegendsVisibility() {
    if (!AppState.marcadoresLegenda) return;

    AppState.marcadoresLegenda.forEach(marker => {
        const el = marker.getElement?.();
        if (!el) return;

        const type = marker.options.labelType;
        let shouldBeVisible = false;

        if (type === 'pivot' || type === 'bomba') {
            shouldBeVisible = AppState.legendasAtivas;
        } else if (type === 'antena' || type === 'repetidora' || type === 'antena_candidate') {
            shouldBeVisible = AppState.antenaLegendasAtivas;
        }

        el.style.display = shouldBeVisible ? '' : 'none';
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
    const messageKey = show ? 'messages.success.pivot_distances_shown' : 'messages.success.pivot_distances_hidden';
    mostrarMensagem(t(messageKey), 'sucesso');
}

let tempCircle = null;

function drawTempCircle(center, radiusPoint) {
    const radius = center.distanceTo(radiusPoint);

    if (tempCircle) {
        tempCircle.setLatLng(center).setRadius(radius);
    } else {
        tempCircle = L.circle(center, {
            radius: radius,
            color: '#D97706',
            weight: 3,
            dashArray: '5, 5',
            fillColor: '#D97706',
            fillOpacity: 0.1,
            interactive: false
        }).addTo(map);
    }
}


function removeTempCircle() {
    if (tempCircle) {
        map.removeLayer(tempCircle);
        tempCircle = null;
    }
}

function generateCircleCoords(center, radius, points = 240) {
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
            color: '#D97706',
            weight: 3,
            dashArray: '8, 8',
            fillColor: '#D97706',
            fillOpacity: 0.2,
            interactive: false
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

function generatePacmanCoords(center, radius, startAngle, endAngle, points = 80) {
    let anguloInicioNormalizado = startAngle;
    let anguloFimNormalizado = endAngle;

    if (anguloFimNormalizado <= anguloInicioNormalizado) {
        anguloFimNormalizado += 360;
    }

    const vertices = [[center.lat, center.lng]];
    const arcAngle = anguloFimNormalizado - anguloInicioNormalizado;
    const irrigatedAngle = 360 - arcAngle;

    for (let i = 0; i <= points; i++) {
        const angle = anguloFimNormalizado + (i * irrigatedAngle / points);
        const point = center.destination(radius, angle);
        vertices.push([point.lat, point.lng]);
    }
    
    vertices.push([center.lat, center.lng]);

    return vertices;
}

function drawTempPacman(center, radiusPoint, currentMousePoint) {
    if (tempPacmanShape) {
        map.removeLayer(tempPacmanShape);
        tempPacmanShape = null;
    }

    if (!radiusPoint) {
        const radius = center.distanceTo(currentMousePoint);
        if (radius > 5) {
            tempPacmanShape = L.circle(center, {
                radius: radius,
                color: '#D97706',
                weight: 3,
                dashArray: '5, 5',
                fillColor: '#D97706',
                fillOpacity: 0.1,
                interactive: false
            }).addTo(map);
        }
    } else {
        const radius = center.distanceTo(radiusPoint);
        const startAngle = calculateBearing(center, radiusPoint);
        const endAngle = calculateBearing(center, currentMousePoint);
        const coords = generatePacmanCoords(center, radius, startAngle, endAngle);

        tempPacmanShape = L.polygon(coords, {
            color: '#D97706',
            weight: 3,
            dashArray: '8, 8',
            fillColor: '#D97706',
            fillOpacity: 0.2,
            interactive: false
        }).addTo(map);
    }
}


function removeTempPacman() {
    if (tempPacmanShape) {
        map.removeLayer(tempPacmanShape);
        tempPacmanShape = null;
    }
}