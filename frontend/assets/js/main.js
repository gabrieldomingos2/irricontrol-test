// --- Variáveis Globais de Estado (Anexadas a 'window') ---

window.jobId = null;
window.modoEdicaoPivos = false;
window.coordenadaClicada = null;
window.marcadorPosicionamento = null;
window.backupPosicoesPivos = {};
window.modoLoSPivotAPivot = false; 
window.losSourcePivot = null;
window.losTargetPivot = null;
window.modoBuscaLocalRepetidora = false;
window.pivoAlvoParaLocalRepetidora = null;
window.ciclosGlobais = [];
window.lastBombasDataDrawn = [];
window.modoDesenhoPivo = false;
window.modoDesenhoPivoSetorial = false;
window.antenaGlobal = null; 
window.distanciasPivosVisiveis = false;
window.lastPivosDataDrawn = [];
window.currentProcessedKmzData = null;

// Variáveis globais que não precisam ser window explicitamente se este script for o principal
let marcadorAntena = null;
let marcadoresPivos = [];
let circulosPivos = [];
let pivotsMap = {};
let repetidoras = [];
let contadorRepetidoras = 0;
let idsDisponiveis = [];
let legendasAtivas = true;
let marcadoresLegenda = [];
let marcadoresBombas = [];
let posicoesEditadas = {};
let overlaysVisiveis = [];
let templateSelecionado = "";
let linhasDiagnostico = [];
let marcadoresBloqueio = [];
let centroPivoTemporario = null;
let isDrawingSector = false;


// --- Inicialização ---

document.addEventListener("DOMContentLoaded", async () => {
    console.log("DOM Carregado. Iniciando Aplicação...");
    
    // Inicializa o sistema de tradução antes de tudo
    const savedLang = localStorage.getItem('preferredLanguage') || 'pt-br';
    await setLanguage(savedLang);
    
    initMap();
    setupUIEventListeners();
    setupMainActionListeners();
    loadAndPopulateTemplates();
    reposicionarPaineisLaterais();
    lucide.createIcons();
    
    // Inicia uma sessão de trabalho vazia ao carregar a página
    await startNewSession();

    console.log("Aplicação Pronta.");

    if (typeof toggleLegendas === 'function') {
        toggleLegendas(legendasAtivas);
    }
});

/**
 * Inicia uma nova sessão de trabalho (job) no backend.
 * Esta função destrava a aplicação para uso imediato.
 */
async function startNewSession() {
    mostrarLoader(true);
    try {
        const data = await startEmptyJob(); // Chama a nova função da API
        if (!data.job_id) {
            throw new Error("A resposta do servidor não incluiu um ID de job.");
        }
        window.jobId = data.job_id;
        console.log(`SESSION_INFO: Novo Job ID definido: ${window.jobId}`);
        mostrarMensagem(t('messages.success.new_session_started'), "sucesso");
        
        // Simula dados vazios para que o resto do app não quebre
        window.currentProcessedKmzData = { antenas: [], pivos: [], ciclos: [], bombas: [] };
        
    } catch (error) {
        console.error("❌ Falha crítica ao iniciar nova sessão:", error);
        mostrarMensagem(t('messages.errors.session_start_fail'), "erro");
        window.jobId = null;
    } finally {
        mostrarLoader(false);
    }
}

// --- Configuração dos Listeners Principais ---

function setupMainActionListeners() {
    document.getElementById('formulario').addEventListener('submit', handleFormSubmit);
    document.getElementById('resetar-btn').addEventListener('click', handleResetClick);
    document.getElementById('btn-diagnostico').addEventListener('click', handleDiagnosticoClick);
    document.getElementById('exportar-btn').addEventListener('click', handleExportClick);
    document.getElementById('confirmar-repetidora').addEventListener('click', handleConfirmRepetidoraClick);
    document.getElementById('btn-los-pivot-a-pivot').addEventListener('click', toggleLoSPivotAPivotMode);
    document.getElementById('btn-buscar-locais-repetidora').addEventListener('click', handleBuscarLocaisRepetidoraActivation);
    document.getElementById('coord-search-btn').addEventListener('click', handleCoordinateSearch);
    
    // Listeners do mapa
    map.on("click", handleMapClick); 
    map.on("contextmenu", handleCancelDraw);

    // Listeners de botões da UI
    document.getElementById('btn-draw-pivot').addEventListener('click', toggleModoDesenhoPivo);
    document.getElementById('btn-draw-pivot-setorial').addEventListener('click', toggleModoDesenhoPivoSetorial);

    const toggleDistanciasBtn = document.getElementById('toggle-distancias-pivos');
    if (toggleDistanciasBtn) {
        toggleDistanciasBtn.addEventListener('click', handleToggleDistanciasPivos);
    }
}


// --- Handlers de Ações Principais ---

async function handleFormSubmit(e) {
    e.preventDefault();
    const fileInput = document.getElementById('arquivo');
    if (!fileInput.files || fileInput.files.length === 0) {
        mostrarMensagem(t('messages.errors.select_kmz'), "erro");
        return;
    }
    mostrarLoader(true);
    const formData = new FormData();
    formData.append("file", fileInput.files[0]);

    try {
        const data = await processKmz(formData);
        console.log("✅ KMZ Processado:", data);

        if (!data.job_id) {
            throw new Error("A resposta do servidor não incluiu um ID de job.");
        }
        
        // Limpa a sessão anterior e inicia com os dados do KMZ
        handleResetClick(false);
        
        // Define o novo Job ID e os dados do KMZ
        window.jobId = data.job_id;
        console.log(`SESSION_INFO: Job ID de KMZ definido como: ${window.jobId}`);
        window.currentProcessedKmzData = JSON.parse(JSON.stringify(data));
        
        window.antenaGlobal = null; 
        const antenasCandidatas = data.antenas || [];
        drawAntenaCandidates(antenasCandidatas);

        if (antenasCandidatas.length > 0) {
            mostrarMensagem(t('messages.success.kmz_loaded_select_tower'), "sucesso");
        } else {
            mostrarMensagem(t('messages.info.no_towers_found'), "info");
        }

        document.getElementById("simular-btn").classList.add("hidden");

        const bombasParaDesenhar = data.bombas || [];
        window.lastBombasDataDrawn = JSON.parse(JSON.stringify(bombasParaDesenhar));
        drawBombas(bombasParaDesenhar);
        
        window.ciclosGlobais = data.ciclos || [];
        drawCirculos(window.ciclosGlobais);

        const pivosParaDesenhar = data.pivos || [];
        const pivosComStatusInicial = pivosParaDesenhar.map(p => ({ ...p, fora: true }));
        window.lastPivosDataDrawn = JSON.parse(JSON.stringify(pivosComStatusInicial));
        drawPivos(pivosComStatusInicial);

        if (pivosParaDesenhar.length > 0 || antenasCandidatas.length > 0) {
            const boundsToFit = [];
            pivosParaDesenhar.forEach(p => boundsToFit.push([p.lat, p.lon]));
            antenasCandidatas.forEach(a => boundsToFit.push([a.lat, a.lon]));
            if (boundsToFit.length > 0) {
               map.fitBounds(boundsToFit, { padding: [50, 50] });
            }
        }
        
        atualizarPainelDados();
        document.getElementById("painel-dados").classList.remove("hidden");
        document.getElementById("painel-repetidoras").classList.remove("hidden");
        reposicionarPaineisLaterais();

    } catch (error) {
        console.error("❌ Erro no submit do formulário:", error);
        mostrarMensagem(t('messages.errors.kmz_load_fail', { error: error.message }), "erro");
        await startNewSession(); // Tenta iniciar uma sessão vazia em caso de falha
    } finally {
        mostrarLoader(false);
    }
}

async function startMainSimulation(antenaData) {
    if (!antenaData || !window.jobId) {
        mostrarMensagem(t('messages.errors.invalid_data_or_session'), "erro");
        return;
    }

    mostrarLoader(true);
    map.closePopup(); 

    try {
        templateSelecionado = document.getElementById('template-modelo').value;
        const pivos_atuais = (window.lastPivosDataDrawn || []).map(p => ({
            nome: p.nome, lat: p.lat, lon: p.lon
        }));

        const payload = {
            job_id: window.jobId,
            ...antenaData, // Inclui lat, lon, altura, nome, etc.
            pivos_atuais,
            template: templateSelecionado
        };
        
        const data = await simulateSignal(payload);
        console.log("✅ Simulação principal concluída:", data);

        if (antenaCandidatesLayerGroup) {
            const idParaRemover = `candidate-${antenaData.nome}-${antenaData.lat}`;
            const camadasParaRemover = [];
            antenaCandidatesLayerGroup.eachLayer(layer => {
                if (layer.options.customId === idParaRemover) camadasParaRemover.push(layer);
            });
            camadasParaRemover.forEach(layer => antenaCandidatesLayerGroup.removeLayer(layer));
        }

        window.antenaGlobal = {
            ...antenaData,
            overlay: drawImageOverlay(data.imagem_salva, data.bounds),
            bounds: data.bounds,
            imagem_filename: data.imagem_salva.split('/').pop() // Correção para pegar apenas o nome do arquivo
        };

        if(marcadorAntena) map.removeLayer(marcadorAntena);
        marcadorAntena = L.marker([window.antenaGlobal.lat, window.antenaGlobal.lon], { icon: antenaIcon }).addTo(map);
        addAntenaAoPainel(window.antenaGlobal);

        const nomeAntenaPrincipal = window.antenaGlobal.nome;
        const labelWidth = (nomeAntenaPrincipal.length * 7) + 10;
        const labelHeight = 20;

        const labelPrincipal = L.marker([window.antenaGlobal.lat, window.antenaGlobal.lon], {
            icon: L.divIcon({
                className: 'label-pivo',
                html: nomeAntenaPrincipal,
                iconSize: [labelWidth, labelHeight],
                iconAnchor: [labelWidth / 2, 45]
            }),
            labelType: 'antena'
        }).addTo(map);
        marcadoresLegenda.push(labelPrincipal);
        
        if (data.pivos) {
            window.lastPivosDataDrawn = JSON.parse(JSON.stringify(data.pivos));
            drawPivos(data.pivos, false);
        }
        if (data.bombas) {
            window.lastBombasDataDrawn = JSON.parse(JSON.stringify(data.bombas));
            drawBombas(data.bombas);
        }

        atualizarPainelDados();
        mostrarMensagem(t('messages.success.simulation_complete'), "sucesso");
        document.getElementById("btn-diagnostico").classList.remove("hidden");

    } catch (error) {
        console.error("❌ Erro ao simular sinal:", error);
        mostrarMensagem(t('messages.errors.simulation_fail', { error: error.message }), "erro");
        window.antenaGlobal = null; 
    } finally {
        mostrarLoader(false);
    }
}


function handleMapClick(e) {
    // A verificação para modoDesenhoPivo FOI REMOVIDA DAQUI, pois ele agora tem seu próprio listener.
    
    // A verificação do setorial pode ser removida também para maior limpeza,
    // pois ele também é autônomo, mas vamos mantê-la por segurança para evitar cliques indesejados.
    if (window.modoDesenhoPivoSetorial) {
        return;
    }

    // Não faz nada se algum destes modos estiverem ativos
    if (window.modoEdicaoPivos || window.modoLoSPivotAPivot) return;

    // Lógica para posicionar repetidora (continua igual)
    window.clickedCandidateData = null;
    window.ultimoCliqueFoiSobrePivo = false;
    window.coordenadaClicada = e.latlng;
    
    if(typeof window.removePositioningMarker === 'function') {
        window.removePositioningMarker();
    }

    window.marcadorPosicionamento = L.marker(window.coordenadaClicada, {
        icon: posicionamentoIcon,
        interactive: false,
        opacity: 0.7,
        zIndexOffset: 1000
    }).addTo(map);

    document.getElementById("painel-repetidora").classList.remove("hidden");
}

async function handleConfirmRepetidoraClick() {
    if (!window.coordenadaClicada || !window.jobId) {
        mostrarMensagem(t('messages.errors.invalid_data_or_session'), "erro");
        return;
    }

    const alturaAntena = parseFloat(document.getElementById("altura-antena-rep").value);
    const alturaReceiver = parseFloat(document.getElementById("altura-receiver-rep").value);
    templateSelecionado = document.getElementById('template-modelo').value;

    document.getElementById('painel-repetidora').classList.add('hidden');
    mostrarLoader(true);

    let repetidoraObj;

    if (window.clickedCandidateData) {
        const candidateData = { ...window.clickedCandidateData };
        window.clickedCandidateData = null;

        if (!window.antenaGlobal) {
            await startMainSimulation({ ...candidateData, altura: alturaAntena || candidateData.altura });
            mostrarLoader(false);
            return;
        } 
        else {
            if (antenaCandidatesLayerGroup) {
                const idToRemove = `candidate-${candidateData.nome}-${candidateData.lat}`;
                const layersToRemove = [];
                antenaCandidatesLayerGroup.eachLayer(layer => {
                    if (layer.options.customId === idToRemove) layersToRemove.push(layer);
                });
                layersToRemove.forEach(layer => antenaCandidatesLayerGroup.removeLayer(layer));
            }
            
            const id = idsDisponiveis.length > 0 ? idsDisponiveis.shift() : ++contadorRepetidoras;
            const nomeRep = candidateData.nome || `${t('ui.labels.repeater')} ${String(id).padStart(2, '0')}`;

            const novaRepetidoraMarker = L.marker(window.coordenadaClicada, { icon: antenaIcon }).addTo(map);
            const labelRepetidora = L.marker(window.coordenadaClicada, {
                icon: L.divIcon({
                    className: 'label-pivo',
                    html: nomeRep,
                    iconSize: [(nomeRep.length * 7) + 10, 20],
                    iconAnchor: [((nomeRep.length * 7) + 10) / 2, 45]
                }),
                labelType: 'repetidora'
            }).addTo(map);
            marcadoresLegenda.push(labelRepetidora);
            
            repetidoraObj = {
                id, marker: novaRepetidoraMarker, overlay: null, label: labelRepetidora,
                altura: alturaAntena, altura_receiver: alturaReceiver,
                lat: window.coordenadaClicada.lat, lon: window.coordenadaClicada.lng,
                imagem_filename: null, sobre_pivo: false, nome: nomeRep
            };
        }
    } 
    else {
        window.removePositioningMarker();
        const id = idsDisponiveis.length > 0 ? idsDisponiveis.shift() : ++contadorRepetidoras;
        const nomeRep = `${t('ui.labels.repeater')} ${String(id).padStart(2, '0')}`;

        const novaRepetidoraMarker = L.marker(window.coordenadaClicada, { icon: antenaIcon }).addTo(map);
        const labelRepetidora = L.marker(window.coordenadaClicada, {
            icon: L.divIcon({
                className: 'label-pivo', html: nomeRep,
                iconSize: [(nomeRep.length * 7) + 10, 20],
                iconAnchor: [((nomeRep.length * 7) + 10) / 2, 45]
            }),
            labelType: 'repetidora'
        }).addTo(map);
        marcadoresLegenda.push(labelRepetidora);
        
        repetidoraObj = {
            id, marker: novaRepetidoraMarker, overlay: null, label: labelRepetidora,
            altura: alturaAntena, altura_receiver: alturaReceiver,
            lat: window.coordenadaClicada.lat, lon: window.coordenadaClicada.lng,
            imagem_filename: null, sobre_pivo: window.ultimoCliqueFoiSobrePivo || false, nome: nomeRep
        };
    }

    if (repetidoraObj) {
        repetidoras.push(repetidoraObj);
        window.fonteDeDistanciaPrioritaria = repetidoraObj;
        
        const payload = {
            job_id: window.jobId, lat: repetidoraObj.lat, lon: repetidoraObj.lon,
            altura: repetidoraObj.altura, altura_receiver: repetidoraObj.altura_receiver,
            pivos_atuais: window.lastPivosDataDrawn.map(p => ({ nome: p.nome, lat: p.lat, lon: p.lon })),
            template: templateSelecionado
        };
        try {
            const data = await simulateManual(payload);
            repetidoraObj.overlay = drawImageOverlay(data.imagem_salva, data.bounds, 1.0);
            repetidoraObj.imagem_filename = data.imagem_filename.split('/').pop();
            addRepetidoraNoPainel(repetidoraObj);
            await reavaliarPivosViaAPI();
            mostrarMensagem(t('messages.success.repeater_added', { name: repetidoraObj.nome }), "sucesso");
        } catch(error) {
             mostrarMensagem(t('messages.errors.simulation_fail', { error: error.message }), "erro");
             map.removeLayer(repetidoraObj.marker);
             if (repetidoraObj.label) map.removeLayer(repetidoraObj.label);
             repetidoras = repetidoras.filter(r => r.id !== repetidoraObj.id);
             idsDisponiveis.push(repetidoraObj.id);
        }
    }

    mostrarLoader(false);
    window.coordenadaClicada = null;
    atualizarPainelDados();
    reposicionarPaineisLaterais();
}

function handleBuscarLocaisRepetidoraActivation() {
    window.modoBuscaLocalRepetidora = !window.modoBuscaLocalRepetidora;
    const btn = document.getElementById('btn-buscar-locais-repetidora');

    if (btn) {
        btn.classList.toggle('glass-button-active', window.modoBuscaLocalRepetidora);
    }

    if (window.modoBuscaLocalRepetidora) {
        mostrarMensagem(t('messages.info.los_mode_on'), "sucesso");
        window.pivoAlvoParaLocalRepetidora = null;

        if (window.marcadorPosicionamento && typeof removePositioningMarker === 'function') {
            removePositioningMarker();
        }

        const painelRepetidora = document.getElementById("painel-repetidora");
        if (painelRepetidora) {
            painelRepetidora.classList.add("hidden");
        }

        if (window.modoLoSPivotAPivot && typeof toggleLoSPivotAPivotMode === 'function') {
            toggleLoSPivotAPivotMode();
        }

        if (window.modoEdicaoPivos) {
            const editarPivosBtn = document.getElementById("editar-pivos");
            if (editarPivosBtn && editarPivosBtn.classList.contains('glass-button-active') && typeof togglePivoEditing === 'function') {
                togglePivoEditing();
            }
        }
        
        if (map) {
            map.getContainer().style.cursor = 'crosshair';
        }

    } else {
        mostrarMensagem(t('messages.info.los_mode_off_find_repeater'), "sucesso");

        if (map) {
            map.getContainer().style.cursor = '';
        }

        if (window.candidateRepeaterSitesLayerGroup) {
            window.candidateRepeaterSitesLayerGroup.clearLayers();
        }
    }
}

async function handlePivotSelectionForRepeaterSite(pivoData, pivoMarker) {
    if (!window.modoBuscaLocalRepetidora) return;

    if (!window.jobId) {
        mostrarMensagem(t('messages.errors.run_study_first'), "erro");
        return;
    }

    if (pivoMarker.options.fillColor === 'green') {
        mostrarMensagem(t('messages.errors.select_uncovered_pivot'), "erro");
        return;
    }

    window.pivoAlvoParaLocalRepetidora = {
        nome: pivoData.nome,
        lat: pivoMarker.getLatLng().lat,
        lon: pivoMarker.getLatLng().lng,
        altura_receiver: (window.antenaGlobal && typeof window.antenaGlobal.altura_receiver === 'number') ? window.antenaGlobal.altura_receiver : 3
    };

    mostrarMensagem(t('messages.info.target_pivot_selected', { name: window.pivoAlvoParaLocalRepetidora.nome }), "info");
    mostrarLoader(true);
    if (map) map.getContainer().style.cursor = 'wait';

    const activeOverlaysForSearch = [];
    const antenaCheckbox = document.querySelector("#antena-item input[type='checkbox']");

    if (window.antenaGlobal?.overlay && map.hasLayer(window.antenaGlobal.overlay) && (!antenaCheckbox || antenaCheckbox.checked) && window.antenaGlobal.imagem_filename) {
        const b = window.antenaGlobal.overlay.getBounds();
        activeOverlaysForSearch.push({
            id: 'antena_principal',
            imagem: window.antenaGlobal.imagem_filename, 
            bounds: [b.getSouth(), b.getWest(), b.getNorth(), b.getEast()]
        });
    }


    repetidoras.forEach(rep => {
        const repCheckbox = document.querySelector(`#rep-item-${rep.id} input[type='checkbox']`);
        if (rep.overlay && map.hasLayer(rep.overlay) && (!repCheckbox || repCheckbox.checked) && rep.imagem_filename) {
            const b = rep.overlay.getBounds();
            activeOverlaysForSearch.push({
                id: `repetidora_${rep.id}`,
                imagem: rep.imagem_filename,
                bounds: [b.getSouth(), b.getWest(), b.getNorth(), b.getEast()]
            });
        }
    });

    if (activeOverlaysForSearch.length === 0) {
        mostrarMensagem(t('messages.errors.no_coverage_to_search'), "erro");
        mostrarLoader(false);
        if (map) map.getContainer().style.cursor = window.modoBuscaLocalRepetidora ? 'crosshair' : '';
        return;
    }

    try {
        const payload = {
            job_id: window.jobId,
            target_pivot_lat: window.pivoAlvoParaLocalRepetidora.lat,
            target_pivot_lon: window.pivoAlvoParaLocalRepetidora.lon,
            target_pivot_nome: window.pivoAlvoParaLocalRepetidora.nome,
            altura_antena_repetidora_proposta: parseFloat(document.getElementById("altura-antena-rep").value) || 5,
            altura_receiver_pivo: window.pivoAlvoParaLocalRepetidora.altura_receiver,
            active_overlays: activeOverlaysForSearch,
            pivot_polygons_coords: window.ciclosGlobais ? window.ciclosGlobais.map(c => c.coordenadas) : []
        };

        const resultados = await findHighPointsForRepeater(payload);

        if (window.candidateRepeaterSitesLayerGroup) {
            window.candidateRepeaterSitesLayerGroup.clearLayers();
        }

        if (resultados && resultados.candidate_sites && resultados.candidate_sites.length > 0) {
            drawCandidateRepeaterSites(resultados.candidate_sites, window.pivoAlvoParaLocalRepetidora);
            mostrarMensagem(t('messages.success.found_candidate_sites', { count: resultados.candidate_sites.length }), "sucesso");
        } else {
            mostrarMensagem(t('messages.info.no_promising_sites_found'), "info");
        }

    } catch (error) {
        console.error("Erro ao buscar locais para repetidora:", error);
        mostrarMensagem(t('messages.errors.find_repeater_fail', { error: error.message || 'Erro desconhecido' }), "erro");
    } finally {
        mostrarLoader(false);
        if (map) map.getContainer().style.cursor = window.modoBuscaLocalRepetidora ? 'crosshair' : '';
    }
}

function toggleModoDesenhoPivo() {
    window.modoDesenhoPivo = !window.modoDesenhoPivo;
    const btn = document.getElementById('btn-draw-pivot');
    btn.classList.toggle('glass-button-active', window.modoDesenhoPivo);

    if (window.modoDesenhoPivo) {
        // Garante que outros modos estejam desativados
        if (window.modoDesenhoPivoSetorial) toggleModoDesenhoPivoSetorial();
        if (window.modoEdicaoPivos) togglePivoEditing();
        if (window.modoLoSPivotAPivot) toggleLoSPivotAPivotMode();
        if (window.modoBuscaLocalRepetidora) handleBuscarLocaisRepetidoraActivation();

        map.getContainer().style.cursor = 'crosshair';
        mostrarMensagem(t('messages.info.draw_pivot_step1'), "info");
        
        // ✅ Gerencia TODOS os seus próprios listeners de forma isolada
        map.on('click', handlePivotDrawClick);
        map.on('mousemove', handlePivotDrawMouseMove);
        map.on('contextmenu', handleCancelCircularDraw); // <-- Usa a nova função

    } else {
        map.getContainer().style.cursor = '';
        centroPivoTemporario = null;
        if (typeof removeTempCircle === 'function') removeTempCircle();
        mostrarMensagem(t('messages.info.draw_pivot_off'), "sucesso");
        
        // ✅ Remove TODOS os seus listeners ao ser desativado
        map.off('click', handlePivotDrawClick);
        map.off('mousemove', handlePivotDrawMouseMove);
        map.off('contextmenu', handleCancelCircularDraw); // <-- Remove o listener de cancelamento
    }
}

function handlePivotDrawMouseMove(e) {
    if (window.modoDesenhoPivo && centroPivoTemporario) {
        if (typeof drawTempCircle === 'function') {
            drawTempCircle(centroPivoTemporario, e.latlng);
        }
    }
}

async function handlePivotDrawClick(e) {

    if (!window.modoDesenhoPivo) return;

    if (!window.jobId) {
        mostrarMensagem(t('messages.errors.session_not_started_for_draw'), "erro");
        toggleModoDesenhoPivo(); 
        return;
    }

    if (!centroPivoTemporario) {
        centroPivoTemporario = e.latlng;
        mostrarMensagem(t('messages.info.draw_pivot_step2'), "info");
        return; 
    }

    const radiusPoint = e.latlng;
    mostrarLoader(true);

    try {
        const payload = {
            job_id: window.jobId,
            center: [centroPivoTemporario.lat, centroPivoTemporario.lng],
            pivos_atuais: window.lastPivosDataDrawn
        };

        const result = await generatePivotInCircle(payload);
        const novoPivo = { ...result.novo_pivo, fora: true };
        const radiusInMeters = centroPivoTemporario.distanceTo(radiusPoint);
        const circleCoords = generateCircleCoords(centroPivoTemporario, radiusInMeters);
        const novoCiclo = {
            nome_original_circulo: `Ciclo ${novoPivo.nome}`,
            coordenadas: circleCoords
        };

        window.lastPivosDataDrawn.push(novoPivo);
        window.ciclosGlobais.push(novoCiclo);
        if (window.currentProcessedKmzData?.pivos) window.currentProcessedKmzData.pivos.push(novoPivo);
        if (window.currentProcessedKmzData?.ciclos) window.currentProcessedKmzData.ciclos.push(novoCiclo);

        if (typeof removeTempCircle === 'function') {
            removeTempCircle();
        }

        drawPivos(window.lastPivosDataDrawn, false);
        drawCirculos(window.ciclosGlobais);
        atualizarPainelDados();

        await reavaliarPivosViaAPI();
        mostrarMensagem(t('messages.success.pivot_created', { name: novoPivo.nome }), "sucesso");

        setTimeout(() => {
            if(window.modoDesenhoPivo) {
                mostrarMensagem(t('messages.info.draw_pivot_still_active'), "info");
            }
        }, 2500);

    } catch (error) {
        console.error("Falha ao criar o pivô:", error);
        mostrarMensagem(t('messages.errors.generic_error', 'Ocorreu um erro ao criar o pivô.'), "erro");
        
        if (typeof removeTempCircle === 'function') {
            removeTempCircle();
        }
    } finally {

        centroPivoTemporario = null;
        mostrarLoader(false);
    }
}

function handleResetClick(showMessage = true) {
    console.log("🔄 Resetando aplicação...");
    clearMapLayers(); 
    window.jobId = null;
    window.antenaGlobal = null;
    marcadorAntena = null;
    window.marcadorPosicionamento = null;
    marcadoresPivos = [];
    circulosPivos = [];
    pivotsMap = {};
    window.coordenadaClicada = null;
    repetidoras = [];
    contadorRepetidoras = 0;
    idsDisponiveis = [];
    legendasAtivas = true;
    marcadoresLegenda = [];
    marcadoresBombas = [];
    posicoesEditadas = {};
    window.backupPosicoesPivos = {};
    overlaysVisiveis = [];
    linhasDiagnostico = [];
    marcadoresBloqueio = [];
    window.ciclosGlobais = [];
    window.distanciasPivosVisiveis = false;
    window.lastPivosDataDrawn = [];
    window.lastBombasDataDrawn = [];
    window.currentProcessedKmzData = null;
    
    if (showMessage) {
      startNewSession();
    }

    if (window.modoDesenhoPivo) {
        toggleModoDesenhoPivo();
    }

    const btnDistancias = document.getElementById('toggle-distancias-pivos');
    if (btnDistancias) {
        btnDistancias.classList.remove('glass-button-active');
        btnDistancias.title = t('ui.titles.show_pivot_distances');
    }

    if (window.modoEdicaoPivos && typeof togglePivoEditing === 'function' && document.getElementById("editar-pivos")?.classList.contains('glass-button-active')) {
        togglePivoEditing();
    }
    if (window.modoLoSPivotAPivot && typeof toggleLoSPivotAPivotMode === 'function' && document.getElementById('btn-los-pivot-a-pivot')?.classList.contains('glass-button-active')) {
        toggleLoSPivotAPivotMode();
    }
    if (window.modoBuscaLocalRepetidora && typeof handleBuscarLocaisRepetidoraActivation === 'function' && document.getElementById('btn-buscar-locais-repetidora')?.classList.contains('glass-button-active')) {
        handleBuscarLocaisRepetidoraActivation();
    }
    if (map) {
        map.getContainer().style.cursor = '';
        if (window.candidateRepeaterSitesLayerGroup) {
            window.candidateRepeaterSitesLayerGroup.clearLayers();
        }
    }

    const btnSimular = document.getElementById("simular-btn");
    if (btnSimular) btnSimular.classList.add("hidden");
    const btnDiagnostico = document.getElementById("btn-diagnostico");
    if (btnDiagnostico) btnDiagnostico.classList.add("hidden");
    const listaRepetidoras = document.getElementById("lista-repetidoras");
    if (listaRepetidoras) listaRepetidoras.innerHTML = "";
    const paineisParaEsconder = ["painel-repetidora", "painel-dados", "painel-repetidoras", "desfazer-edicao"];
    paineisParaEsconder.forEach(id => {
        const painel = document.getElementById(id);
        if (painel) painel.classList.add("hidden");
    });

    const formElement = document.getElementById('formulario');
    if (formElement) formElement.reset();
    const nomeArquivoLabelElement = document.getElementById('nome-arquivo-label');
    if (nomeArquivoLabelElement) {
        nomeArquivoLabelElement.textContent = t('ui.labels.choose_kmz');
        nomeArquivoLabelElement.title = t('ui.labels.choose_kmz');
    }

    const rangeOpacidadeElement = document.getElementById("range-opacidade");
    if (rangeOpacidadeElement) rangeOpacidadeElement.value = 1;

    if (map) map.setView([-15, -55], 5);
    if (typeof atualizarPainelDados === 'function') atualizarPainelDados();
    if (typeof reposicionarPaineisLaterais === 'function') reposicionarPaineisLaterais();
    if (typeof toggleLegendas === 'function') toggleLegendas(true);

    if (showMessage) mostrarMensagem(t('messages.success.app_reset'), "sucesso");
}

async function handleDiagnosticoClick() {
    if (!window.antenaGlobal || Object.keys(pivotsMap).length === 0) {
        mostrarMensagem(t('messages.errors.run_study_first'), "erro");
        return;
    }

    mostrarLoader(true);
    linhasDiagnostico = [];
    marcadoresBloqueio = [];

    const pivosVermelhos = Object.entries(pivotsMap).filter(([_, m]) => m.options.fillColor === 'red');

    if (pivosVermelhos.length === 0) {
        mostrarMensagem(t('messages.info.no_uncovered_pivots'), "sucesso");
        mostrarLoader(false);
        return;
    }

    mostrarMensagem(t('messages.info.analyzing_pivots', { count: pivosVermelhos.length }), "sucesso");

    for (const [nome, marcador] of pivosVermelhos) {
        const payload = {
            pontos: [
                [window.antenaGlobal.lat, window.antenaGlobal.lon],
                [marcador.getLatLng().lat, marcador.getLatLng().lng]
            ],
            altura_antena: window.antenaGlobal.altura || 15,
            altura_receiver: (window.antenaGlobal && typeof window.antenaGlobal.altura_receiver === 'number') ? window.antenaGlobal.altura_receiver : 3
        };

        try {
            const data = await getElevationProfile(payload);
            drawDiagnostico(
                payload.pontos[0], payload.pontos[1],
                data.bloqueio, data.ponto_mais_alto, nome
            );
        } catch (error) {
            console.error(`Erro no diagnóstico do pivô ${nome}:`, error);
            mostrarMensagem(t('messages.errors.los_diagnostic_fail', { name: nome }), "erro");
        }
    }

    if (typeof lucide !== 'undefined') lucide.createIcons();
    mostrarLoader(false);
    mostrarMensagem(t('messages.success.los_diagnostic_complete'), "sucesso");
}

// ✅ FUNÇÃO FINAL E CORRIGIDA
async function handleExportClick() {
    // ✅ LÓGICA DE VALIDAÇÃO ATUALIZADA
    if (!window.jobId) {
        mostrarMensagem(t('messages.errors.session_not_started'), "erro");
        return;
    }
    // Permite exportar se tiver uma antena principal OU pelo menos uma repetidora.
    if (!window.antenaGlobal && repetidoras.length === 0) {
        mostrarMensagem(t('messages.errors.nothing_to_export'), "erro");
        return;
    }

    mostrarLoader(true);
    mostrarMensagem(t('messages.success.kmz_export_preparing'), "info");

    try {
        const repetidorasSelecionadasParaExport = [];
        repetidoras.forEach(rep => {
            const checkbox = document.querySelector(`#rep-item-${rep.id} input[type='checkbox']`);
            if (checkbox?.checked && rep.imagem_filename) {
                repetidorasSelecionadasParaExport.push({
                    imagem: rep.imagem_filename,
                    altura: rep.altura,
                    sobre_pivo: rep.sobre_pivo,
                    nome: rep.nome
                });
            }
        });
        
        let antenaDataParaExport = null;
        let imagemPrincipal = null;
        let boundsFilePrincipal = null;

        // ✅ Preenche os dados da antena principal somente se ela existir
        if (window.antenaGlobal) {
            antenaDataParaExport = {
                nome: window.antenaGlobal.nome,
                lat: window.antenaGlobal.lat,
                lon: window.antenaGlobal.lon,
                altura: window.antenaGlobal.altura,
                altura_receiver: window.antenaGlobal.altura_receiver
            };
            imagemPrincipal = window.antenaGlobal.imagem_filename;
            boundsFilePrincipal = window.antenaGlobal.imagem_filename.replace(/\.png$/, '.json');
        }

        const payload = {
            job_id: window.jobId,
            template_id: templateSelecionado || document.getElementById('template-modelo').value,
            antena_principal_data: antenaDataParaExport,
            imagem: imagemPrincipal,
            bounds_file: boundsFilePrincipal,
            pivos_data: window.lastPivosDataDrawn,
            ciclos_data: window.ciclosGlobais,
            bombas_data: window.lastBombasDataDrawn,
            repetidoras_data: repetidorasSelecionadasParaExport
        };

        await exportKmz(payload);

    } catch (error) {
        console.error("Erro no processo de exportação KMZ:", error);
    } finally {
        mostrarLoader(false);
    }
}

async function reavaliarPivosViaAPI() {
    if (!window.jobId || !window.lastPivosDataDrawn || window.lastPivosDataDrawn.length === 0) return;

    // Prepara os dados para enviar à API (esta parte está correta)
    const pivosParaReavaliar = window.lastPivosDataDrawn.map(p => ({ nome: p.nome, lat: p.lat, lon: p.lon, type: 'pivo' }));
    const bombasParaReavaliar = (window.lastBombasDataDrawn || []).map(b => ({ nome: b.nome, lat: b.lat, lon: b.lon, type: 'bomba' }));
    
    const overlays = [];
    const antenaCheckbox = document.querySelector("#antena-item input[type='checkbox']");
    if (window.antenaGlobal?.overlay && map.hasLayer(window.antenaGlobal.overlay) && (!antenaCheckbox || antenaCheckbox.checked) && window.antenaGlobal.imagem_filename) {
        const b = window.antenaGlobal.overlay.getBounds();
        overlays.push({ id: 'antena_principal', imagem: window.antenaGlobal.imagem_filename, bounds: [b.getSouth(), b.getWest(), b.getNorth(), b.getEast()] });
    }
    repetidoras.forEach(rep => {
        const repCheckbox = document.querySelector(`#rep-item-${rep.id} input[type='checkbox']`);
        if (rep.overlay && map.hasLayer(rep.overlay) && (!repCheckbox || repCheckbox.checked) && rep.imagem_filename) {
            const b = rep.overlay.getBounds();
            overlays.push({ id: `repetidora_${rep.id}`, imagem: rep.imagem_filename, bounds: [b.getSouth(), b.getWest(), b.getNorth(), b.getEast()] });
        }
    });

    try {
        const payload = { job_id: window.jobId, pivos: pivosParaReavaliar, bombas: bombasParaReavaliar, overlays };
        const data = await reevaluatePivots(payload);

        if (data.pivos) {

            const pivosAtualizadosDaAPI = data.pivos;
            
            window.lastPivosDataDrawn = window.lastPivosDataDrawn.map(pivoAntigo => {
                const pivoNovoDaAPI = pivosAtualizadosDaAPI.find(p => p.nome === pivoAntigo.nome);
                
                if (pivoNovoDaAPI) {
                    return { ...pivoAntigo, ...pivoNovoDaAPI };
                }
                
                return pivoAntigo;
            });

            drawPivos(window.lastPivosDataDrawn, false);
        }

        if (data.bombas) {
            window.lastBombasDataDrawn = JSON.parse(JSON.stringify(data.bombas));
            drawBombas(data.bombas);
        }

        atualizarPainelDados();

    } catch (error) {
        console.error("❌ Erro ao reavaliar cobertura via API:", error);
        mostrarMensagem(t('messages.errors.reevaluate_fail', { error: error.message }), "erro");
    }
}


function removePositioningMarker() {
    if (window.marcadorPosicionamento && map.hasLayer(window.marcadorPosicionamento)) {
        map.removeLayer(window.marcadorPosicionamento);
        window.marcadorPosicionamento = null;
    }
}
window.removePositioningMarker = removePositioningMarker;

function enablePivoEditingMode() {
    window.modoEdicaoPivos = true;
    console.log("✏️ Ativando modo de edição com ícone de pino SVG.");
    window.backupPosicoesPivos = {};
    const tamanho = 18; const altura = 26;
    marcadoresPivos.forEach(m => map.removeLayer(m));
    marcadoresPivos = [];
    marcadoresLegenda.filter(l => l.options.labelType === 'pivot').forEach(l => { if (map.hasLayer(l)) map.removeLayer(l); });
    marcadoresLegenda = marcadoresLegenda.filter(l => l.options.labelType !== 'pivot');
    Object.values(pivotsMap).forEach(marker => { if (marker && map.hasLayer(marker)) map.removeLayer(marker); });
    pivotsMap = {};
    window.lastPivosDataDrawn.forEach(pivoInfo => {
        const nome = pivoInfo.nome;
        const currentLatLng = L.latLng(pivoInfo.lat, pivoInfo.lon);
        window.backupPosicoesPivos[nome] = currentLatLng;
        const editMarkerIcon = L.divIcon({
            className: 'pivo-edit-handle-custom-pin',
            html: `<svg viewBox="0 0 28 40" width="${tamanho}" height="${altura}" xmlns="http://www.w3.org/2000/svg"><path d="M14 0 C7.486 0 2 5.486 2 12.014 C2 20.014 14 40 14 40 C14 40 26 20.014 26 12.014 C26 5.486 20.514 0 14 0 Z M14 18 C10.686 18 8 15.314 8 12 C8 8.686 10.686 6 14 6 C17.314 6 20 8.686 20 12 C20 15.314 17.314 18 14 18 Z" fill="#FF3333" stroke="#660000" stroke-width="1"/></svg>`,
            iconSize: [tamanho, altura],
            iconAnchor: [tamanho / 2, altura]
        });
        const editMarker = L.marker(currentLatLng, { draggable: true, icon: editMarkerIcon }).addTo(map);
        pivotsMap[nome] = editMarker;
        editMarker.on("dragend", (e) => {
            const novaPos = e.target.getLatLng();
            posicoesEditadas[nome] = { lat: novaPos.lat, lng: novaPos.lng };
            const pivoEmLastData = window.lastPivosDataDrawn.find(p => p.nome === nome);
            if (pivoEmLastData) {
                pivoEmLastData.lat = novaPos.lat;
                pivoEmLastData.lon = novaPos.lng;
            }
        });
        editMarker.on("contextmenu", (e) => {
            L.DomEvent.stopPropagation(e);
            L.DomEvent.preventDefault(e);
            if (confirm(t('messages.confirm.remove_pivot', { name: nome }))) {
                map.removeLayer(editMarker);
                window.lastPivosDataDrawn = window.lastPivosDataDrawn.filter(p => p.nome !== nome);
                if (window.currentProcessedKmzData?.pivos) window.currentProcessedKmzData.pivos = window.currentProcessedKmzData.pivos.filter(p => p.nome !== nome);
                const nomeCicloParaRemover = `Ciclo ${nome}`;
                window.ciclosGlobais = window.ciclosGlobais.filter(c => c.nome_original_circulo !== nomeCicloParaRemover);
                if (window.currentProcessedKmzData?.ciclos) window.currentProcessedKmzData.ciclos = window.currentProcessedKmzData.ciclos.filter(c => c.nome_original_circulo !== nomeCicloParaRemover);
                if (typeof drawCirculos === 'function') drawCirculos(window.ciclosGlobais);
                delete pivotsMap[nome];
                delete posicoesEditadas[nome];
                delete window.backupPosicoesPivos[nome];
                mostrarMensagem(t('messages.success.pivot_removed', { name: nome }), "sucesso");
                atualizarPainelDados();
            }
        });
    });
    mostrarMensagem(t('messages.info.edit_mode_activated'), "sucesso");
}

function disablePivoEditingMode() {
    window.modoEdicaoPivos = false;
    Object.values(pivotsMap).forEach(editMarker => { if (editMarker && map.hasLayer(editMarker)) map.removeLayer(editMarker); });
    pivotsMap = {};
    drawPivos(window.lastPivosDataDrawn, false);
    mostrarMensagem(t('messages.info.positions_updated_resimulate'), "sucesso");
    window.backupPosicoesPivos = {};
    posicoesEditadas = {};
}

function undoPivoEdits() {
    Object.entries(window.backupPosicoesPivos).forEach(([nome, posicaoOriginalLatLng]) => {
        const pivoEmLastData = window.lastPivosDataDrawn.find(p => p.nome === nome);
        if (pivoEmLastData) {
            pivoEmLastData.lat = posicaoOriginalLatLng.lat;
            pivoEmLastData.lon = posicaoOriginalLatLng.lng;
        }
        const editMarker = pivotsMap[nome];
        if (editMarker && map.hasLayer(editMarker)) editMarker.setLatLng(posicaoOriginalLatLng);
    });
    posicoesEditadas = {};
    if (typeof togglePivoEditing === 'function' && window.modoEdicaoPivos) togglePivoEditing();
    mostrarMensagem(t('messages.info.edits_undone'), "sucesso");
}

function toggleLoSPivotAPivotMode() {
    window.modoLoSPivotAPivot = !window.modoLoSPivotAPivot;
    const btn = document.getElementById('btn-los-pivot-a-pivot');
    btn.classList.toggle('glass-button-active', window.modoLoSPivotAPivot);
    if (window.modoLoSPivotAPivot) {
        mostrarMensagem(t('messages.info.los_mode_step1_source'), "sucesso");
        if (window.marcadorPosicionamento) removePositioningMarker();
        document.getElementById("painel-repetidora").classList.add("hidden");
        window.losSourcePivot = null;
        window.losTargetPivot = null;
        if (window.modoEdicaoPivos && typeof togglePivoEditing === 'function' && document.getElementById("editar-pivos").classList.contains('glass-button-active')) togglePivoEditing();
        if (window.modoBuscaLocalRepetidora && typeof handleBuscarLocaisRepetidoraActivation === 'function' && document.getElementById('btn-buscar-locais-repetidora').classList.contains('glass-button-active')) handleBuscarLocaisRepetidoraActivation();
        map.getContainer().style.cursor = 'help';
    } else {
        mostrarMensagem(t('messages.info.los_mode_deactivated'), "sucesso");
        window.losSourcePivot = null;
        window.losTargetPivot = null;
        map.getContainer().style.cursor = '';
        if (visadaLayerGroup) {
            visadaLayerGroup.clearLayers();
            linhasDiagnostico = [];
            marcadoresBloqueio = [];
        }
    }
}

async function handleLoSPivotClick(pivoData, pivoMarker) {
    if (!window.modoLoSPivotAPivot) return;
    const isGoodSignalPivot = pivoMarker.options.fillColor === 'green';
    const pivotLatlng = pivoMarker.getLatLng();
    const defaultPivotHeight = (window.antenaGlobal && typeof window.antenaGlobal.altura_receiver === 'number') ? window.antenaGlobal.altura_receiver : 3;
    if (!window.losSourcePivot) {
        if (!isGoodSignalPivot) {
            mostrarMensagem(t('messages.errors.los_source_must_be_green'), "erro");
            return;
        }
        window.losSourcePivot = { nome: pivoData.nome, latlng: pivotLatlng, altura: defaultPivotHeight };
        mostrarMensagem(t('messages.info.los_source_selected', { name: pivoData.nome }), "sucesso");
    } else {
        if (pivoData.nome === window.losSourcePivot.nome) {
            mostrarMensagem(t('messages.info.los_source_already_selected', { name: pivoData.nome }), "info");
            return;
        }
        if (isGoodSignalPivot) {
            const confirmaMudanca = confirm(t('messages.confirm.change_los_source', { 
                sourceName: window.losSourcePivot.nome, 
                newName: pivoData.nome 
            }));
            if (confirmaMudanca) {
                window.losSourcePivot = { nome: pivoData.nome, latlng: pivotLatlng, altura: defaultPivotHeight };
                window.losTargetPivot = null;
                linhasDiagnostico = [];
                marcadoresBloqueio = [];
                mostrarMensagem(t('messages.info.los_source_changed', { name: pivoData.nome }), "sucesso");
            }
            return;
        }
        window.losTargetPivot = { nome: pivoData.nome, latlng: pivotLatlng, altura: defaultPivotHeight };
        mostrarLoader(true);
        let ocorreuErroNaAnalise = false;
        let distanciaFormatada = "N/A";
        try {
            linhasDiagnostico = [];
            marcadoresBloqueio = [];
            if (!window.losSourcePivot.latlng || !window.losTargetPivot.latlng) throw new Error("LatLng de origem ou destino indefinido para cálculo de distância.");
            if (!(window.losSourcePivot.latlng instanceof L.LatLng) || !(window.losTargetPivot.latlng instanceof L.LatLng) ) throw new Error("Objeto LatLng inválido para cálculo de distância.");
            const distanciaEntrePivos = window.losSourcePivot.latlng.distanceTo(window.losTargetPivot.latlng);
            if (isNaN(distanciaEntrePivos)) {
                distanciaFormatada = "Erro no cálculo";
            } else {
                distanciaFormatada = distanciaEntrePivos > 999 ? (distanciaEntrePivos / 1000).toFixed(1) + ' km' : Math.round(distanciaEntrePivos) + ' m';
            }
            const payload = {
                pontos: [ [window.losSourcePivot.latlng.lat, window.losSourcePivot.latlng.lng], [window.losTargetPivot.latlng.lat, window.losTargetPivot.latlng.lng] ],
                altura_antena: window.losSourcePivot.altura, altura_receiver: window.losTargetPivot.altura
            };
            const resultadoApi = await getElevationProfile(payload);
            const estaBloqueado = resultadoApi.bloqueio && typeof resultadoApi.bloqueio.diff === 'number' && resultadoApi.bloqueio.diff > 0.1;
            drawDiagnostico(payload.pontos[0], payload.pontos[1], resultadoApi.bloqueio, resultadoApi.ponto_mais_alto, `${window.losSourcePivot.nome} → ${window.losTargetPivot.nome}`, distanciaFormatada);
            let statusKey;
            if (estaBloqueado) {
                statusKey = 'los_result_blocked';
            } else if (resultadoApi.bloqueio && typeof resultadoApi.bloqueio.diff === 'number') {
                statusKey = 'los_result_clear_critical';
            } else {
                statusKey = 'los_result_clear';
            }
            mostrarMensagem(t(`messages.info.${statusKey}`, {
                source: window.losSourcePivot.nome,
                target: window.losTargetPivot.nome,
                distance: distanciaFormatada
            }), estaBloqueado ? "erro" : "sucesso");

        } catch (error) {
            ocorreuErroNaAnalise = true;
            console.error(`Erro no diagnóstico LoS Pivô a Pivô:`, error);
            mostrarMensagem(t('messages.info.los_result_error', {
                source: window.losSourcePivot?.nome || 'Source',
                target: window.losTargetPivot?.nome || 'Target',
                distance: distanciaFormatada,
                error: error.message || 'Unknown error'
            }), "erro");
        } finally {
            mostrarLoader(false);
            window.losSourcePivot = null;
            window.losTargetPivot = null;
            if (window.modoLoSPivotAPivot) setTimeout(() => { if (window.modoLoSPivotAPivot) mostrarMensagem(t('messages.info.los_new_source_prompt'), "info"); }, ocorreuErroNaAnalise ? 700 : 1800);
        }
    }
}

function handleToggleDistanciasPivos() {
    window.distanciasPivosVisiveis = !window.distanciasPivosVisiveis;
    const btn = document.getElementById('toggle-distancias-pivos');
    if (btn) {
        btn.classList.toggle('glass-button-active', window.distanciasPivosVisiveis);
        btn.title = window.distanciasPivosVisiveis 
            ? t('ui.titles.hide_pivot_distances') 
            : t('ui.titles.show_pivot_distances');
    }
    if (typeof window.togglePivoDistances === 'function') {
        window.togglePivoDistances(window.distanciasPivosVisiveis);
    } else {
        console.error("Função togglePivoDistances não encontrada em drawing.js. Tentando fallback.");
        if (window.lastPivosDataDrawn && window.lastPivosDataDrawn.length > 0 && typeof drawPivos === 'function') {
            drawPivos(window.lastPivosDataDrawn, true);
            mostrarMensagem(`Distâncias dos pivôs ${window.distanciasPivosVisiveis ? 'exibidas' : 'ocultas'} (via fallback).`, 'sucesso');
        } else {
             console.error("Fallback para drawPivos falhou.");
        }
    }
}

function handleCancelDraw(e) {
    // Esta função agora cuida APENAS do cancelamento do modo SETORIAL.
    if (window.modoDesenhoPivoSetorial && centroPivoTemporario) {
        L.DomEvent.preventDefault(e);
        L.DomEvent.stopPropagation(e);

        console.log("✏️ Ação de desenho de SETOR cancelada.");
        centroPivoTemporario = null;
        
        if (typeof removeTempSector === 'function') {
            removeTempSector();
        }
        
        mostrarMensagem(t('messages.info.draw_sector_cancelled', 'Desenho de setor cancelado. Clique para definir um novo centro.'), "info");
    }
}


// ========================================================
// ✅ NOVO: FUNCIONALIDADE DE BUSCA POR COORDENADAS
// ========================================================

/**
 * Converte uma string de coordenada em vários formatos para um objeto de latitude/longitude.
 * Suporta:
 * - Graus, Minutos, Segundos (ex: 19°26'29.5"S 44°29'26.8"W)
 * - Decimal com vírgula ou espaço (ex: -19.441535, -44.490771)
 * @param {string} coordString - A string da coordenada.
 * @returns {{lat: number, lon: number} | null} - Objeto com lat/lon ou null se inválido.
 */
function parseCoordinates(coordString) {
    coordString = coordString.trim();

    // Função auxiliar para converter DMS (Graus, Minutos, Segundos) para DD (Graus Decimais)
    const dmsToDd = (degrees, minutes, seconds, direction) => {
        let dd = parseFloat(degrees) + parseFloat(minutes) / 60 + parseFloat(seconds) / 3600;
        if (direction === 'S' || direction === 'W') {
            dd = dd * -1;
        }
        return dd;
    };

    // Tenta corresponder ao formato DMS (ex: 19° 26' 29.5"S 44° 29' 26.8"W)
    // Esta regex é flexível com ou sem espaços e símbolos.
    const dmsRegex = /^(\d{1,3})[°\s]+(\d{1,2})['\s]+(\d{1,2}(?:\.\d+)?)["\s]*([NS])\s*,?\s*(\d{1,3})[°\s]+(\d{1,2})['\s]+(\d{1,2}(?:\.\d+)?)["\s]*([WE])$/i;
    const dmsMatch = coordString.match(dmsRegex);

    if (dmsMatch) {
        try {
            const lat = dmsToDd(dmsMatch[1], dmsMatch[2], dmsMatch[3], dmsMatch[4].toUpperCase());
            const lon = dmsToDd(dmsMatch[5], dmsMatch[6], dmsMatch[7], dmsMatch[8].toUpperCase());
            if (!isNaN(lat) && !isNaN(lon)) return { lat, lon };
        } catch (e) {
            console.error("Erro ao converter DMS:", e);
            return null;
        }
    }

    // Tenta corresponder ao formato Decimal (ex: -19.441535, -44.490771 ou -19.441535 -44.490771)
    const cleanedString = coordString.replace(/,/g, ' ').replace(/\s+/, ' ').trim();
    const parts = cleanedString.split(' ');

    if (parts.length === 2) {
        const lat = parseFloat(parts[0]);
        const lon = parseFloat(parts[1]);

        // Validação básica de latitude e longitude
        if (!isNaN(lat) && !isNaN(lon) && lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180) {
            return { lat, lon };
        }
    }

    return null; // Retorna null se nenhum formato for reconhecido
}

/**
 * Manipula o clique no botão de busca de coordenadas.
 */
function handleCoordinateSearch() {
    const inputField = document.getElementById('lat-long-input-field');
    const coordString = inputField.value;

    if (!coordString) {
        mostrarMensagem(t('messages.error.coordinate_input_empty'), "erro");
        return;
    }

    const coords = parseCoordinates(coordString);


    if (coords) {
        const latlng = L.latLng(coords.lat, coords.lon);

        // Remove o marcador de posicionamento anterior, se houver
        if (window.marcadorPosicionamento) {
            map.removeLayer(window.marcadorPosicionamento);
        }

        // Adiciona um novo marcador no local (usando o ícone da antena principal)
        // O ícone 'antenaIcon' já está definido em drawing.js
        window.marcadorPosicionamento = L.marker(latlng, {
            icon: antenaIcon,
            interactive: true // Permite que o painel de repetidora seja aberto
        }).addTo(map);

        // Centraliza o mapa na nova coordenada com um bom nível de zoom
        map.setView(latlng, 15);
        mostrarMensagem(t('messages.success.location_found'), "sucesso");

        // Simula um clique no mapa para abrir o painel de configuração de repetidora
        window.coordenadaClicada = latlng;
        document.getElementById("painel-repetidora").classList.remove("hidden");
        
        // Limpa o campo de texto após a busca
        inputField.value = '';

    } else {
        // Mensagem de erro mais detalhada
        mostrarMensagem(t('messages.error.invalid_coordinate_format'), "erro");
    }
}

// ✅ INÍCIO DO TRECHO PARA SUBSTITUIR

// ========================================================
// LÓGICA CORRIGIDA PARA DESENHO DE PIVÔ SETORIAL
// ========================================================

/**
 * Encontra o maior número usado nos nomes de pivôs existentes ("Pivô X" ou "Setor X")
 * e retorna o próximo número disponível na sequência.
 * @returns {number} O próximo número sequencial para um novo pivô.
 */
function getNextPivotNumber() {
    let maxNumber = 0;
    // Itera sobre todos os pivôs já desenhados no mapa
    window.lastPivosDataDrawn.forEach(pivo => {
        // Usa uma expressão regular para encontrar o primeiro conjunto de dígitos no nome do pivô
        const match = pivo.nome.match(/\d+/);
        if (match) {
            const currentNumber = parseInt(match[0], 10);
            if (currentNumber > maxNumber) {
                maxNumber = currentNumber;
            }
        }
    });
    // Retorna o maior número encontrado + 1
    return maxNumber + 1;
}

/**
 * Ativa ou desativa o modo de desenho de pivô setorial (método de 2 cliques).
 */
function toggleModoDesenhoPivoSetorial() {
    window.modoDesenhoPivoSetorial = !window.modoDesenhoPivoSetorial;
    const btn = document.getElementById('btn-draw-pivot-setorial');
    btn.classList.toggle('glass-button-active', window.modoDesenhoPivoSetorial);

    if (window.modoDesenhoPivoSetorial) {
        // Garante que outros modos de desenho ou edição estejam desativados
        if (window.modoDesenhoPivo) toggleModoDesenhoPivo();
        if (window.modoEdicaoPivos && typeof togglePivoEditing === 'function') togglePivoEditing();
        if (window.modoLoSPivotAPivot && typeof toggleLoSPivotAPivotMode === 'function') toggleLoSPivotAPivotMode();
        if (window.modoBuscaLocalRepetidora && typeof handleBuscarLocaisRepetidoraActivation === 'function') handleBuscarLocaisRepetidoraActivation();

        map.getContainer().style.cursor = 'crosshair';
        
        // Adiciona os listeners de evento para o modo de 2 cliques
        map.on('click', handleSectorialPivotDrawClick);
        map.on('mousemove', handleSectorialDrawMouseMove);
        
        mostrarMensagem(t('messages.info.draw_sector_pivot_step1', 'Modo Setorial: Clique no mapa para definir o centro do pivô.'), "info");

    } else {
        map.getContainer().style.cursor = '';

        // Remove os listeners de evento para não interferir com outras ações
        map.off('click', handleSectorialPivotDrawClick);
        map.off('mousemove', handleSectorialDrawMouseMove);
        
        // Limpa qualquer desenho temporário que possa ter ficado no mapa
        centroPivoTemporario = null;
        if (typeof removeTempSector === 'function') {
            removeTempSector();
        }

        mostrarMensagem(t('messages.info.draw_sector_pivot_off', 'Modo de Desenho Setorial desativado.'), "sucesso");
    }
}


/**
 * Manipula os cliques no mapa para desenhar o pivô setorial.
 * O primeiro clique define o centro, o segundo finaliza o desenho.
 */
async function handleSectorialPivotDrawClick(e) {
    if (!window.modoDesenhoPivoSetorial) return;

    // Primeiro clique: Define o centro do pivô
    if (!centroPivoTemporario) {
        centroPivoTemporario = e.latlng;
        mostrarMensagem(t('messages.info.draw_sector_pivot_step2', 'Centro definido. Mova o mouse para ajustar e clique novamente para finalizar.'), "info");
    } 
    // Segundo clique: Define o raio e a orientação, e cria o pivô
    else {
        const finalPoint = e.latlng;
        const radius = centroPivoTemporario.distanceTo(finalPoint);

        // Remove o desenho de pré-visualização
        if (typeof removeTempSector === 'function') {
            removeTempSector();
        }

        // Validação para evitar pivôs muito pequenos
        if (radius < 10) {
            centroPivoTemporario = null; // Reinicia o processo
            mostrarMensagem(t('messages.errors.draw_pivot_radius_too_small', 'Raio muito pequeno. Clique para definir um novo centro.'), "erro");
            return;
        }

        mostrarLoader(true);
        try {
            const bearing = calculateBearing(centroPivoTemporario, finalPoint);
            
            // Lógica de nomeação unificada
            const novoNumero = getNextPivotNumber();
            const novoNome = `Pivô ${String(novoNumero).padStart(2, '0')}`;
            
            const novoPivo = {
                // CORREÇÃO: Usa a variável 'novoNome'
                nome: novoNome,
                lat: centroPivoTemporario.lat,
                lon: centroPivoTemporario.lng,
                fora: true,
                tipo: 'setorial',
                raio: radius,
                angulo_central: bearing,
                abertura_arco: 180 
            };
            
            window.lastPivosDataDrawn.push(novoPivo);

            // Adiciona um "ciclo placeholder" para manter a consistência dos dados
            const novoCiclo = {
                nome_original_circulo: `Ciclo ${novoPivo.nome}`,
                coordenadas: []
            };
            window.ciclosGlobais.push(novoCiclo);

            // Redesenha todos os pivôs e suas áreas
            if (typeof drawPivos === 'function') drawPivos(window.lastPivosDataDrawn, false);
            if (typeof drawCirculos === 'function') drawCirculos(window.ciclosGlobais);
            
            await reavaliarPivosViaAPI();
            atualizarPainelDados();

            // Mensagem de sucesso corrigida para refletir o nome correto
            mostrarMensagem(t('messages.success.sector_pivot_created', `Pivô '${novoPivo.nome}' (setorial) criado com sucesso.`), "sucesso");

        } catch (error) {
            console.error("Erro ao criar pivô setorial:", error);
            mostrarMensagem(t('messages.errors.generic_error', 'Ocorreu um erro.'), "erro");
        } finally {
            // Reinicia para permitir desenhar outro pivô em seguida
            centroPivoTemporario = null;
            mostrarLoader(false);
            
            setTimeout(() => {
                if (window.modoDesenhoPivoSetorial) {
                    mostrarMensagem(t('messages.info.draw_sector_pivot_still_active', 'Modo Setorial ainda ativo. Clique para um novo centro.'), "info");
                }
            }, 2000);
        }
    }
}

/**
 * Desenha uma pré-visualização do setor no mapa enquanto o usuário move o mouse.
 * Só é ativado após o primeiro clique (quando o centro já está definido).
 */
function handleSectorialDrawMouseMove(e) {
    if (window.modoDesenhoPivoSetorial && centroPivoTemporario) {
        if (typeof drawTempSector === 'function') {
            drawTempSector(centroPivoTemporario, e.latlng);
        }
    }
}


/**
 * ✅ NOVA FUNÇÃO: Manipula o cancelamento (clique direito) especificamente
 * para o modo de desenho de pivô CIRCULAR.
 */
function handleCancelCircularDraw(e) {
    // Só faz algo se o modo circular estiver ativo e um desenho tiver começado
    if (window.modoDesenhoPivo && centroPivoTemporario) {
        // Impede o menu padrão do navegador de aparecer
        L.DomEvent.preventDefault(e);
        L.DomEvent.stopPropagation(e);

        console.log("✏️ Ação de desenho de CÍRCULO cancelada.");
        
        // Remove o círculo de pré-visualização do mapa
        if (typeof removeTempCircle === 'function') {
            removeTempCircle();
        }

        // Zera a variável de estado para interromper o processo
        centroPivoTemporario = null;
        
        // Exibe mensagem para o usuário
        mostrarMensagem(t('messages.info.draw_pivot_cancelled', 'Desenho de pivô cancelado.'), "info");
    }
}