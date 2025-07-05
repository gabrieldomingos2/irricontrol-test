// =================================================================
// ✅ ARQUITETURA DE ESTADO CENTRALIZADA
// =================================================================

const AppState = {
    // --- Estado da Sessão e Dados ---
    jobId: null,
    currentProcessedKmzData: null,
    antenaGlobal: null,
    lastPivosDataDrawn: [],
    lastBombasDataDrawn: [],
    ciclosGlobais: [],
    repetidoras: [],
    
    // --- Estado da UI e Modos de Interação ---
    modoEdicaoPivos: false,
    modoLoSPivotAPivot: false,
    modoBuscaLocalRepetidora: false,
    modoDesenhoPivo: false,
    modoDesenhoPivoSetorial: false,
    modoDesenhoPivoPacman: false,
    pontoRaioTemporario: null,
    distanciasPivosVisiveis: false,
    legendasAtivas: true,

    // --- Variáveis de Apoio e Temporárias ---
    coordenadaClicada: null,
    marcadorPosicionamento: null,
    backupPosicoesPivos: {},
    losSourcePivot: null,
    losTargetPivot: null,
    pivoAlvoParaLocalRepetidora: null,
    templateSelecionado: "",
    centroPivoTemporario: null,
    isDrawingSector: false,
    
    // --- Referências a Camadas do Mapa (Leaflet) ---
    marcadorAntena: null,
    marcadoresPivos: [],
    circulosPivos: [],
    pivotsMap: {},
    contadorRepetidoras: 0,
    idsDisponiveis: [],
    marcadoresLegenda: [],
    marcadoresBombas: [],
    posicoesEditadas: {},
    overlaysVisiveis: [],
    linhasDiagnostico: [],
    marcadoresBloqueio: [],

    /**
     * Define o ID do Job de forma controlada.
     * @param {string} id - O ID da sessão retornado pela API.
     */
    setJobId(id) {
        this.jobId = id;
        console.log(`SESSION_INFO: Novo Job ID definido: ${this.jobId}`);
    },

    /**
     * Reseta todo o estado da aplicação para os valores iniciais.
     * Chamado pela função handleResetClick.
     */
    reset() {
        console.log("🔄 Resetando o estado da aplicação...");
        this.jobId = null;
        this.currentProcessedKmzData = null;
        this.antenaGlobal = null;
        this.lastPivosDataDrawn = [];
        this.lastBombasDataDrawn = [];
        this.ciclosGlobais = [];
        this.repetidoras = [];
        this.modoEdicaoPivos = false;
        this.modoLoSPivotAPivot = false;
        this.modoBuscaLocalRepetidora = false;
        this.modoDesenhoPivo = false;
        this.modoDesenhoPivoSetorial = false;
        this.distanciasPivosVisiveis = false;
        this.legendasAtivas = true;
        this.coordenadaClicada = null;
        this.marcadorPosicionamento = null;
        this.backupPosicoesPivos = {};
        this.losSourcePivot = null;
        this.losTargetPivot = null;
        this.pivoAlvoParaLocalRepetidora = null;
        this.templateSelecionado = "";
        this.centroPivoTemporario = null;
        this.isDrawingSector = false;
        this.marcadorAntena = null;
        this.marcadoresPivos = [];
        this.circulosPivos = [];
        this.pivotsMap = {};
        this.contadorRepetidoras = 0;
        this.idsDisponiveis = [];
        this.marcadoresLegenda = [];
        this.marcadoresBombas = [];
        this.posicoesEditadas = {};
        this.overlaysVisiveis = [];
        this.linhasDiagnostico = [];
        this.marcadoresBloqueio = [];
        this.modoDesenhoPivoPacman = false;
        this.pontoRaioTemporario = null;
    }
};


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
        toggleLegendas(AppState.legendasAtivas);
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
        AppState.setJobId(data.job_id);
        mostrarMensagem(t('messages.success.new_session_started'), "sucesso");
        
        // Simula dados vazios para que o resto do app não quebre
        AppState.currentProcessedKmzData = { antenas: [], pivos: [], ciclos: [], bombas: [] };
        
    } catch (error) {
        console.error("❌ Falha crítica ao iniciar nova sessão:", error);
        mostrarMensagem(t('messages.errors.session_start_fail'), "erro");
        AppState.setJobId(null);
    } finally {
        mostrarLoader(false);
    }
}

// --- Configuração dos Listeners Principais ---

function setupMainActionListeners() {
    document.getElementById('formulario').addEventListener('submit', handleFormSubmit);
    document.getElementById('resetar-btn').addEventListener('click', handleResetClick);
    document.getElementById('exportar-btn').addEventListener('click', handleExportClick);
    document.getElementById('confirmar-repetidora').addEventListener('click', handleConfirmRepetidoraClick);
    document.getElementById('btn-los-pivot-a-pivot').addEventListener('click', toggleLoSPivotAPivotMode);
    document.getElementById('btn-buscar-locais-repetidora').addEventListener('click', handleBuscarLocaisRepetidoraActivation);
    document.getElementById('coord-search-btn').addEventListener('click', handleCoordinateSearch);
    document.getElementById('btn-draw-pivot-pacman').addEventListener('click', toggleModoDesenhoPivoPacman);
    
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
        AppState.setJobId(data.job_id);
        AppState.currentProcessedKmzData = JSON.parse(JSON.stringify(data));
        
        AppState.antenaGlobal = null; 
        const antenasCandidatas = data.antenas || [];
        drawAntenaCandidates(antenasCandidatas);

        if (antenasCandidatas.length > 0) {
            mostrarMensagem(t('messages.success.kmz_loaded_select_tower'), "sucesso");
        } else {
            mostrarMensagem(t('messages.info.no_towers_found'), "info");
        }

        document.getElementById("simular-btn").classList.add("hidden");

        const bombasParaDesenhar = data.bombas || [];
        AppState.lastBombasDataDrawn = JSON.parse(JSON.stringify(bombasParaDesenhar));
        drawBombas(bombasParaDesenhar);
        
        AppState.ciclosGlobais = data.ciclos || [];
        drawCirculos(AppState.ciclosGlobais);

        const pivosParaDesenhar = data.pivos || [];
        const pivosComStatusInicial = pivosParaDesenhar.map(p => ({ ...p, fora: true }));
        AppState.lastPivosDataDrawn = JSON.parse(JSON.stringify(pivosComStatusInicial));
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
    if (!antenaData || !AppState.jobId) {
        mostrarMensagem(t('messages.errors.invalid_data_or_session'), "erro");
        return;
    }

    mostrarLoader(true);
    map.closePopup(); 

    try {
        AppState.templateSelecionado = document.getElementById('template-modelo').value;
        
        const pivos_atuais = (AppState.lastPivosDataDrawn || []).map(p => ({
            nome: p.nome, lat: p.lat, lon: p.lon, type: 'pivo'
        }));
        const bombas_atuais = (AppState.lastBombasDataDrawn || []).map(b => ({
            nome: b.nome, lat: b.lat, lon: b.lon, type: 'bomba'
        }));

        const payload = {
            job_id: AppState.jobId, ...antenaData, pivos_atuais,
            bombas_atuais, template: AppState.templateSelecionado
        };
        
        const data = await simulateSignal(payload);
        console.log("✅ Simulação principal concluída:", data);

        if (window.antenaCandidatesLayerGroup) {
            const idParaRemover = `candidate-${antenaData.nome}-${antenaData.lat}`;
            const camadasParaRemover = [];
            window.antenaCandidatesLayerGroup.eachLayer(layer => {
                if (layer.options.customId === idParaRemover) camadasParaRemover.push(layer);
            });
            camadasParaRemover.forEach(layer => window.antenaCandidatesLayerGroup.removeLayer(layer));
        }

        AppState.antenaGlobal = {
            ...antenaData,
            overlay: drawImageOverlay(data.imagem_salva, data.bounds),
            bounds: data.bounds,
            imagem_filename: data.imagem_filename
        };

        if(AppState.marcadorAntena) map.removeLayer(AppState.marcadorAntena);
        AppState.marcadorAntena = L.marker([AppState.antenaGlobal.lat, AppState.antenaGlobal.lon], { icon: antenaIcon }).addTo(map);

        const tooltipAntenaContent = `
            <div style="text-align: center;">
                ${t('ui.labels.antenna_height_tooltip', { height: AppState.antenaGlobal.altura })}
                <br>
                ${t('ui.labels.receiver_height_tooltip', { height: AppState.antenaGlobal.altura_receiver })}
            </div>
        `;
        AppState.marcadorAntena.bindTooltip(tooltipAntenaContent, {
            permanent: false,
            direction: 'top',
            offset: [0, -40], 
            className: 'tooltip-sinal'
        });

        const nomeAntenaPrincipal = AppState.antenaGlobal.nome;
        const labelWidth = (nomeAntenaPrincipal.length * 7) + 10;
        const labelPrincipal = L.marker([AppState.antenaGlobal.lat, AppState.antenaGlobal.lon], {
            icon: L.divIcon({
                className: 'label-pivo',
                html: nomeAntenaPrincipal,
                iconSize: [labelWidth, 20],
                iconAnchor: [labelWidth / 2, 45]
            }),
            labelType: 'antena'
        }).addTo(map);
        AppState.marcadoresLegenda.push(labelPrincipal);
        
        AppState.antenaGlobal.label = labelPrincipal;
        
        addAntenaAoPainel(AppState.antenaGlobal);
    
        
        if (data.pivos) {
            // Em vez de sobrescrever, mescla os resultados
            AppState.lastPivosDataDrawn = AppState.lastPivosDataDrawn.map(pivoAntigo => {
                const pivoNovoDaAPI = data.pivos.find(p => p.nome.trim() === pivoAntigo.nome.trim());
                // Se encontrou um correspondente na resposta da API, atualiza o status 'fora'.
                // Senão, mantém o pivô antigo como está.
                // Isso preserva 'tipo', 'raio', ângulos, etc.
                return pivoNovoDaAPI ? { ...pivoAntigo, fora: pivoNovoDaAPI.fora } : pivoAntigo;
            });
            drawPivos(AppState.lastPivosDataDrawn, false);
        }
        // ✅ FIM DA CORREÇÃO
        
        if (data.bombas) {
            // (a lógica das bombas já estava correta, mas mantemos para consistência)
            AppState.lastBombasDataDrawn = JSON.parse(JSON.stringify(data.bombas));
            drawBombas(data.bombas);
        }

        atualizarPainelDados();
        mostrarMensagem(t('messages.success.simulation_complete'), "sucesso");

    } catch (error) {
        console.error("❌ Erro ao simular sinal:", error);
        mostrarMensagem(t('messages.errors.simulation_fail', { error: error.message }), "erro");
        AppState.antenaGlobal = null; 
    } finally {
        mostrarLoader(false);
    }
}


function handleMapClick(e) {
    if (AppState.modoDesenhoPivoSetorial || AppState.modoDesenhoPivo) {
        return;
    }
    
    if (AppState.modoEdicaoPivos || AppState.modoLoSPivotAPivot) return;

    window.clickedCandidateData = null;
    window.ultimoCliqueFoiSobrePivo = false;
    AppState.coordenadaClicada = e.latlng;
    
    if(typeof removePositioningMarker === 'function') {
        removePositioningMarker();
    }

    AppState.marcadorPosicionamento = L.marker(AppState.coordenadaClicada, {
        icon: posicionamentoIcon,
        interactive: false,
        opacity: 0.7,
        zIndexOffset: 1000
    }).addTo(map);

    document.getElementById("painel-repetidora").classList.remove("hidden");
}

async function handleConfirmRepetidoraClick() {
    if (!AppState.coordenadaClicada || !AppState.jobId) {
        mostrarMensagem(t('messages.errors.invalid_data_or_session'), "erro");
        return;
    }

    const alturaAntena = parseFloat(document.getElementById("altura-antena-rep").value);
    const alturaReceiver = parseFloat(document.getElementById("altura-receiver-rep").value);
    AppState.templateSelecionado = document.getElementById('template-modelo').value;

    document.getElementById('painel-repetidora').classList.add('hidden');
    mostrarLoader(true);

    let repetidoraObj;
    let nomeRep;
    let id;
    let isFromKmz = false;

    if (window.clickedCandidateData) {
        const candidateData = { ...window.clickedCandidateData };
        window.clickedCandidateData = null;
        isFromKmz = true;

        if (!AppState.antenaGlobal) {
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
            id = AppState.idsDisponiveis.length > 0 ? AppState.idsDisponiveis.shift() : ++AppState.contadorRepetidoras;
            nomeRep = candidateData.nome || `${t('ui.labels.repeater')} ${String(id).padStart(2, '0')}`;
        }
    } 
    else {
        removePositioningMarker();
        id = AppState.idsDisponiveis.length > 0 ? AppState.idsDisponiveis.shift() : ++AppState.contadorRepetidoras;
        nomeRep = `${t('ui.labels.repeater')} ${String(id).padStart(2, '0')}`;
        isFromKmz = false;
    }
    
    const novaRepetidoraMarker = L.marker(AppState.coordenadaClicada, { icon: antenaIcon }).addTo(map);
    const labelRepetidora = L.marker(AppState.coordenadaClicada, {
        icon: L.divIcon({
            className: 'label-pivo', html: nomeRep,
            iconSize: [(nomeRep.length * 7) + 10, 20],
            iconAnchor: [((nomeRep.length * 7) + 10) / 2, 45]
        }),
        labelType: 'repetidora'
    }).addTo(map);
    AppState.marcadoresLegenda.push(labelRepetidora);

    const tooltipRepetidoraContent = `
        <div style="text-align: center;">
            ${t('ui.labels.antenna_height_tooltip', { height: alturaAntena })}
            <br>
            ${t('ui.labels.receiver_height_tooltip', { height: alturaReceiver })}
        </div>
    `;
    novaRepetidoraMarker.bindTooltip(tooltipRepetidoraContent, {
        permanent: false,
        direction: 'top',
        offset: [0, -40],
        className: 'tooltip-sinal'
    });
    
    repetidoraObj = {
        id, marker: novaRepetidoraMarker, overlay: null, label: labelRepetidora,
        altura: alturaAntena, altura_receiver: alturaReceiver,
        lat: AppState.coordenadaClicada.lat, lon: AppState.coordenadaClicada.lng,
        imagem_filename: null, sobre_pivo: window.ultimoCliqueFoiSobrePivo || false, nome: nomeRep,
        is_from_kmz: isFromKmz
    };

    if (repetidoraObj) {
        AppState.repetidoras.push(repetidoraObj);
        
        const payload = {
            job_id: AppState.jobId, lat: repetidoraObj.lat, lon: repetidoraObj.lon,
            altura: repetidoraObj.altura, altura_receiver: repetidoraObj.altura_receiver,
            pivos_atuais: AppState.lastPivosDataDrawn.map(p => ({ nome: p.nome, lat: p.lat, lon: p.lon })),
            template: AppState.templateSelecionado
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
             AppState.repetidoras = AppState.repetidoras.filter(r => r.id !== repetidoraObj.id);
             AppState.idsDisponiveis.push(repetidoraObj.id);
        }
    }

    mostrarLoader(false);
    AppState.coordenadaClicada = null;
    atualizarPainelDados();
    reposicionarPaineisLaterais();
}

function handleBuscarLocaisRepetidoraActivation() {
    AppState.modoBuscaLocalRepetidora = !AppState.modoBuscaLocalRepetidora;
    const btn = document.getElementById('btn-buscar-locais-repetidora');

    if (btn) {
        btn.classList.toggle('glass-button-active', AppState.modoBuscaLocalRepetidora);
    }

    if (AppState.modoBuscaLocalRepetidora) {
        mostrarMensagem(t('messages.info.los_mode_on'), "sucesso");
        AppState.pivoAlvoParaLocalRepetidora = null;

        if (AppState.marcadorPosicionamento && typeof removePositioningMarker === 'function') {
            removePositioningMarker();
        }

        document.getElementById("painel-repetidora")?.classList.add("hidden");

        if (AppState.modoLoSPivotAPivot && typeof toggleLoSPivotAPivotMode === 'function') {
            toggleLoSPivotAPivotMode();
        }

        if (AppState.modoEdicaoPivos) {
            if (document.getElementById("editar-pivos")?.classList.contains('glass-button-active') && typeof togglePivoEditing === 'function') {
                togglePivoEditing();
            }
        }
        
        if (map) map.getContainer().style.cursor = 'crosshair';

    } else {
        mostrarMensagem(t('messages.info.los_mode_off_find_repeater'), "sucesso");
        if (map) map.getContainer().style.cursor = '';
        if (window.candidateRepeaterSitesLayerGroup) {
            window.candidateRepeaterSitesLayerGroup.clearLayers();
        }
    }
}

async function handlePivotSelectionForRepeaterSite(pivoData, pivoMarker) {
    if (!AppState.modoBuscaLocalRepetidora) return;

    if (!AppState.jobId) {
        mostrarMensagem(t('messages.errors.run_study_first'), "erro");
        return;
    }

    if (pivoMarker.options.fillColor === 'green') {
        mostrarMensagem(t('messages.errors.select_uncovered_pivot'), "erro");
        return;
    }

    AppState.pivoAlvoParaLocalRepetidora = {
        nome: pivoData.nome,
        lat: pivoMarker.getLatLng().lat,
        lon: pivoMarker.getLatLng().lng,
        altura_receiver: (AppState.antenaGlobal && typeof AppState.antenaGlobal.altura_receiver === 'number') ? AppState.antenaGlobal.altura_receiver : 3
    };

    mostrarMensagem(t('messages.info.target_pivot_selected', { name: AppState.pivoAlvoParaLocalRepetidora.nome }), "info");
    mostrarLoader(true);
    if (map) map.getContainer().style.cursor = 'wait';

    const activeOverlaysForSearch = [];
    
    const antenaVisBtn = document.querySelector("#antena-item button[data-visible]");
    const isAntenaVisible = !antenaVisBtn || antenaVisBtn.getAttribute('data-visible') === 'true';

    if (AppState.antenaGlobal?.overlay && map.hasLayer(AppState.antenaGlobal.overlay) && isAntenaVisible && AppState.antenaGlobal.imagem_filename) {
        const b = AppState.antenaGlobal.overlay.getBounds();
        activeOverlaysForSearch.push({
            id: 'antena_principal',
            imagem: AppState.antenaGlobal.imagem_filename, 
            bounds: [b.getSouth(), b.getWest(), b.getNorth(), b.getEast()]
        });
    }

    AppState.repetidoras.forEach(rep => {
        const repVisBtn = document.querySelector(`#rep-item-${rep.id} button[data-visible]`);
        const isRepVisible = !repVisBtn || repVisBtn.getAttribute('data-visible') === 'true';
        if (rep.overlay && map.hasLayer(rep.overlay) && isRepVisible && rep.imagem_filename) {
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
        if (map) map.getContainer().style.cursor = AppState.modoBuscaLocalRepetidora ? 'crosshair' : '';
        return;
    }

    try {
        const payload = {
            job_id: AppState.jobId,
            target_pivot_lat: AppState.pivoAlvoParaLocalRepetidora.lat,
            target_pivot_lon: AppState.pivoAlvoParaLocalRepetidora.lon,
            target_pivot_nome: AppState.pivoAlvoParaLocalRepetidora.nome,
            altura_antena_repetidora_proposta: parseFloat(document.getElementById("altura-antena-rep").value) || 5,
            altura_receiver_pivo: AppState.pivoAlvoParaLocalRepetidora.altura_receiver,
            active_overlays: activeOverlaysForSearch,
            pivot_polygons_coords: AppState.ciclosGlobais ? AppState.ciclosGlobais.map(c => c.coordenadas) : []
        };

        const resultados = await findHighPointsForRepeater(payload);

        if (window.candidateRepeaterSitesLayerGroup) {
            window.candidateRepeaterSitesLayerGroup.clearLayers();
        }

        if (resultados?.candidate_sites?.length > 0) {
            drawCandidateRepeaterSites(resultados.candidate_sites, AppState.pivoAlvoParaLocalRepetidora);
            mostrarMensagem(t('messages.success.found_candidate_sites', { count: resultados.candidate_sites.length }), "sucesso");
        } else {
            mostrarMensagem(t('messages.info.no_promising_sites_found'), "info");
        }

    } catch (error) {
        console.error("Erro ao buscar locais para repetidora:", error);
        mostrarMensagem(t('messages.errors.find_repeater_fail', { error: error.message || 'Erro desconhecido' }), "erro");
    } finally {
        mostrarLoader(false);
        if (map) map.getContainer().style.cursor = AppState.modoBuscaLocalRepetidora ? 'crosshair' : '';
    }
}

function toggleModoDesenhoPivo() {
    AppState.modoDesenhoPivo = !AppState.modoDesenhoPivo;
    document.getElementById('btn-draw-pivot').classList.toggle('glass-button-active', AppState.modoDesenhoPivo);

    if (AppState.modoDesenhoPivo) {
        if (AppState.modoDesenhoPivoSetorial) toggleModoDesenhoPivoSetorial();
        if (AppState.modoEdicaoPivos) togglePivoEditing();
        if (AppState.modoLoSPivotAPivot) toggleLoSPivotAPivotMode();
        if (AppState.modoBuscaLocalRepetidora) handleBuscarLocaisRepetidoraActivation();

        map.getContainer().style.cursor = 'crosshair';
        mostrarMensagem(t('messages.info.draw_pivot_step1'), "info");
        
        map.on('click', handlePivotDrawClick);
        map.on('mousemove', handlePivotDrawMouseMove);

    } else {
        map.getContainer().style.cursor = '';
        AppState.centroPivoTemporario = null;
        if (typeof removeTempCircle === 'function') removeTempCircle();
        mostrarMensagem(t('messages.info.draw_pivot_off'), "sucesso");
        
        map.off('click', handlePivotDrawClick);
        map.off('mousemove', handlePivotDrawMouseMove);
    }
}

function handlePivotDrawMouseMove(e) {
    if (AppState.modoDesenhoPivo && AppState.centroPivoTemporario) {
        if (typeof drawTempCircle === 'function') {
            drawTempCircle(AppState.centroPivoTemporario, e.latlng);
        }
    }
}

async function handlePivotDrawClick(e) {
    if (!AppState.modoDesenhoPivo) return;

    if (!AppState.jobId) {
        mostrarMensagem(t('messages.errors.session_not_started_for_draw'), "erro");
        toggleModoDesenhoPivo(); 
        return;
    }

    if (!AppState.centroPivoTemporario) {
        AppState.centroPivoTemporario = e.latlng;
        mostrarMensagem(t('messages.info.draw_pivot_step2'), "info");
        return; 
    }

    const radiusPoint = e.latlng;
    mostrarLoader(true);

    try {
        const payload = {
            job_id: AppState.jobId,
            center: [AppState.centroPivoTemporario.lat, AppState.centroPivoTemporario.lng],
            pivos_atuais: AppState.lastPivosDataDrawn
        };

        const result = await generatePivotInCircle(payload);
        const novoPivo = { ...result.novo_pivo, fora: true };
        const radiusInMeters = AppState.centroPivoTemporario.distanceTo(radiusPoint);
        const circleCoords = generateCircleCoords(AppState.centroPivoTemporario, radiusInMeters);
        const novoCiclo = {
            nome_original_circulo: `Ciclo ${novoPivo.nome}`,
            coordenadas: circleCoords
        };

        AppState.lastPivosDataDrawn.push(novoPivo);
        AppState.ciclosGlobais.push(novoCiclo);
        if (AppState.currentProcessedKmzData?.pivos) AppState.currentProcessedKmzData.pivos.push(novoPivo);
        if (AppState.currentProcessedKmzData?.ciclos) AppState.currentProcessedKmzData.ciclos.push(novoCiclo);

        if (typeof removeTempCircle === 'function') removeTempCircle();

        atualizarPainelDados();
        drawPivos(AppState.lastPivosDataDrawn, false);
        drawCirculos(AppState.ciclosGlobais);
        
        await reavaliarPivosViaAPI();
        mostrarMensagem(t('messages.success.pivot_created', { name: novoPivo.nome }), "sucesso");

        setTimeout(() => {
            if(AppState.modoDesenhoPivo) {
                mostrarMensagem(t('messages.info.draw_pivot_still_active'), "info");
            }
        }, 2500);

    } catch (error) {
        console.error("Falha ao criar o pivô:", error);
        mostrarMensagem(t('messages.errors.generic_error', { error: error.message }), "erro");
        if (typeof removeTempCircle === 'function') removeTempCircle();
    } finally {
        AppState.centroPivoTemporario = null;
        mostrarLoader(false);
    }
}

function handleResetClick(showMessage = true) {
    console.log("🔄 Resetando aplicação...");
    clearMapLayers(); 
    AppState.reset(); // Reseta todo o estado de DADOS primeiro.
    
    if (showMessage) {
      startNewSession();
    }


    const toggleableButtonsIds = [
        'editar-pivos',
        'btn-los-pivot-a-pivot',
        'btn-buscar-locais-repetidora',
        'btn-draw-pivot',
        'btn-draw-pivot-setorial',
        'toggle-distancias-pivos',
        'toggle-legenda'
    ];


    toggleableButtonsIds.forEach(id => {
        const btn = document.getElementById(id);
        if (btn) {
            btn.classList.remove('glass-button-active');
        }
    });
    

    if (map) {
        map.getContainer().style.cursor = '';
        if (window.candidateRepeaterSitesLayerGroup) {
            window.candidateRepeaterSitesLayerGroup.clearLayers();
        }
    }
    

    map.off('click', handlePivotDrawClick);
    map.off('mousemove', handlePivotDrawMouseMove);
    map.off('contextmenu', handleCancelCircularDraw);
    map.off('click', handleSectorialPivotDrawClick);
    map.off('mousemove', handleSectorialDrawMouseMove);
    

    document.getElementById("simular-btn")?.classList.add("hidden");
    document.getElementById("lista-repetidoras").innerHTML = "";
    
    const paineisParaEsconder = ["painel-repetidora", "painel-dados", "painel-repetidoras", "desfazer-edicao"];
    paineisParaEsconder.forEach(id => document.getElementById(id)?.classList.add("hidden"));

    document.getElementById('formulario')?.reset();
    const nomeArquivoLabelElement = document.getElementById('nome-arquivo-label');
    if (nomeArquivoLabelElement) {
        nomeArquivoLabelElement.textContent = t('ui.labels.choose_kmz');
        nomeArquivoLabelElement.title = t('ui.labels.choose_kmz');
    }

    document.getElementById("range-opacidade").value = 1;

    if (map) map.setView([-15, -55], 5);
    
    atualizarPainelDados();
    reposicionarPaineisLaterais();
    toggleLegendas(true); // Garante que as legendas voltem a ser visíveis

    if (showMessage) mostrarMensagem(t('messages.success.app_reset'), "sucesso");
}

async function runTargetedDiagnostic(diagnosticoSource) {
    if (!diagnosticoSource) {
        mostrarMensagem(t('messages.errors.run_study_first'), "erro");
        return;
    }

    const sourceName = diagnosticoSource.nome || (diagnosticoSource.label?.options.icon.options.html) || t('ui.labels.main_antenna_default');
    const sourceLatLng = diagnosticoSource.marker ? diagnosticoSource.marker.getLatLng() : L.latLng(diagnosticoSource.lat, diagnosticoSource.lon);

    mostrarLoader(true);
    
    // ✅ INÍCIO DA CORREÇÃO: Usando AppState para acessar as camadas do mapa
    if (AppState.visadaLayerGroup) {
        AppState.visadaLayerGroup.clearLayers();
    }
    AppState.linhasDiagnostico = [];
    AppState.marcadoresBloqueio = [];
    // ✅ FIM DA CORREÇÃO

    let pivosParaAnalisar;

    if (AppState.modoEdicaoPivos) {
        console.log("Diagnóstico em Modo de Edição: usando 'AppState.lastPivosDataDrawn'.");
        const pivosInfo = AppState.lastPivosDataDrawn.filter(pivo => pivo.fora === true);
        pivosParaAnalisar = pivosInfo.map(pivoInfo => {
            const marcador = AppState.pivotsMap[pivoInfo.nome];
            return marcador ? [pivoInfo.nome, marcador] : null;
        }).filter(Boolean);

    } else {
        console.log("Diagnóstico em Modo Normal: usando a cor dos marcadores.");
        pivosParaAnalisar = Object.entries(AppState.pivotsMap).filter(([, marcador]) => {
            return marcador && marcador.options && marcador.options.fillColor === 'red';
        });
    }

    if (pivosParaAnalisar.length === 0) {
        mostrarMensagem(t('messages.info.no_uncovered_pivots'), "sucesso");
        mostrarLoader(false);
        return;
    }

    mostrarMensagem(t('messages.info.analyzing_pivots_from_source', { count: pivosParaAnalisar.length, source: sourceName }), "sucesso");

    for (const [nomePivo, marcadorPivo] of pivosParaAnalisar) {
        const pivoLatLng = marcadorPivo.getLatLng();

        const payload = {
            pontos: [
                [sourceLatLng.lat, sourceLatLng.lng],
                [pivoLatLng.lat, pivoLatLng.lng]
            ],
            altura_antena: diagnosticoSource.altura || 15,
            altura_receiver: (AppState.antenaGlobal?.altura_receiver) ?? 3
        };

        try {
            const data = await getElevationProfile(payload);
            const nomeDiagnostico = `${sourceName} → ${nomePivo}`;
            drawDiagnostico(
                payload.pontos[0], payload.pontos[1],
                data.bloqueio, data.ponto_mais_alto, nomeDiagnostico
            );
        } catch (error) {
            console.error(`Erro no diagnóstico do pivô ${nomePivo}:`, error);
            mostrarMensagem(t('messages.errors.los_diagnostic_fail', { name: nomePivo }), "erro");
        }
    }

    if (typeof lucide !== 'undefined') lucide.createIcons();
    mostrarLoader(false);
    mostrarMensagem(t('messages.success.los_diagnostic_complete'), "sucesso");
}

async function handleExportClick() {
    if (!AppState.jobId) {
        mostrarMensagem(t('messages.errors.session_not_started'), "erro");
        return;
    }
    if (!AppState.antenaGlobal && AppState.repetidoras.length === 0) {
        mostrarMensagem(t('messages.errors.nothing_to_export'), "erro");
        return;
    }

    mostrarLoader(true);
    mostrarMensagem(t('messages.success.kmz_export_preparing'), "info");

    try {
        const repetidorasSelecionadasParaExport = [];
        AppState.repetidoras.forEach(rep => {
            const visibilityBtn = document.querySelector(`#rep-item-${rep.id} button[data-visible]`);
            const isVisible = !visibilityBtn || visibilityBtn.getAttribute('data-visible') === 'true';

            if (isVisible && rep.imagem_filename) {
                // ✅ LÓGICA DE EXPORTAÇÃO CORRIGIDA
                repetidorasSelecionadasParaExport.push({
                    imagem: rep.imagem_filename,
                    altura: rep.altura,
                    sobre_pivo: rep.sobre_pivo,
                    // Se for um placemark original do KMZ, envie seu nome.
                    // Senão, não envie nome (null), para o backend criar "Repetidora Solar...".
                    nome: rep.is_from_kmz ? rep.nome : null
                });
            }
        });
        
        let antenaDataParaExport = null;
        let imagemPrincipal = null;
        let boundsFilePrincipal = null;

        if (AppState.antenaGlobal) {
            antenaDataParaExport = {
                nome: AppState.antenaGlobal.nome,
                lat: AppState.antenaGlobal.lat,
                lon: AppState.antenaGlobal.lon,
                altura: AppState.antenaGlobal.altura,
                altura_receiver: AppState.antenaGlobal.altura_receiver
            };
            imagemPrincipal = AppState.antenaGlobal.imagem_filename;
            if (imagemPrincipal) {
                boundsFilePrincipal = imagemPrincipal.replace(/\.png$/, '.json');
            }
        }

        const payload = {
            job_id: AppState.jobId,
            template_id: AppState.templateSelecionado || document.getElementById('template-modelo').value,
            antena_principal_data: antenaDataParaExport,
            imagem: imagemPrincipal,
            bounds_file: boundsFilePrincipal,
            pivos_data: AppState.lastPivosDataDrawn,
            ciclos_data: AppState.ciclosGlobais,
            bombas_data: AppState.lastBombasDataDrawn,
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
    if (!AppState.jobId || !AppState.lastPivosDataDrawn || AppState.lastPivosDataDrawn.length === 0) return;

    const pivosParaReavaliar = AppState.lastPivosDataDrawn.map(p => ({ nome: p.nome, lat: p.lat, lon: p.lon, type: 'pivo' }));
    const bombasParaReavaliar = (AppState.lastBombasDataDrawn || []).map(b => ({ nome: b.nome, lat: b.lat, lon: b.lon, type: 'bomba' }));
    
    const overlays = [];
    const antenaVisBtn = document.querySelector("#antena-item button[data-visible]");
    const isAntenaActive = !antenaVisBtn || antenaVisBtn.getAttribute('data-visible') === 'true';

    if (AppState.antenaGlobal?.overlay && map.hasLayer(AppState.antenaGlobal.overlay) && isAntenaActive && AppState.antenaGlobal.imagem_filename) {
        const b = AppState.antenaGlobal.overlay.getBounds();
        overlays.push({ id: 'antena_principal', imagem: AppState.antenaGlobal.imagem_filename, bounds: [b.getSouth(), b.getWest(), b.getNorth(), b.getEast()] });
    }

    AppState.repetidoras.forEach(rep => {
        const repVisBtn = document.querySelector(`#rep-item-${rep.id} button[data-visible]`);
        const isRepActive = !repVisBtn || repVisBtn.getAttribute('data-visible') === 'true';

        if (rep.overlay && map.hasLayer(rep.overlay) && isRepActive && rep.imagem_filename) {
            const b = rep.overlay.getBounds();
            overlays.push({ id: `repetidora_${rep.id}`, imagem: rep.imagem_filename, bounds: [b.getSouth(), b.getWest(), b.getNorth(), b.getEast()] });
        }
    });

    try {
        const payload = { job_id: AppState.jobId, pivos: pivosParaReavaliar, bombas: bombasParaReavaliar, overlays };
        const data = await reevaluatePivots(payload);

        // ✅ INÍCIO DA CORREÇÃO: Lógica de atualização segura
        if (data.pivos) {
            AppState.lastPivosDataDrawn = AppState.lastPivosDataDrawn.map(pivoAntigo => {
                const pivoNovoDaAPI = data.pivos.find(p => p.nome.trim() === pivoAntigo.nome.trim());
                return pivoNovoDaAPI ? { ...pivoAntigo, fora: pivoNovoDaAPI.fora } : pivoAntigo;
            });
            drawPivos(AppState.lastPivosDataDrawn, false);
        }
        // ✅ FIM DA CORREÇÃO

        if (data.bombas) {
            AppState.lastBombasDataDrawn = JSON.parse(JSON.stringify(data.bombas));
            drawBombas(data.bombas);
        }

        atualizarPainelDados();

    } catch (error) {
        console.error("❌ Erro ao reavaliar cobertura via API:", error);
        mostrarMensagem(t('messages.errors.reevaluate_fail', { error: error.message }), "erro");
    }
}

function removePositioningMarker() {
    if (AppState.marcadorPosicionamento && map.hasLayer(AppState.marcadorPosicionamento)) {
        map.removeLayer(AppState.marcadorPosicionamento);
        AppState.marcadorPosicionamento = null;
    }
}

function enablePivoEditingMode() {
    AppState.modoEdicaoPivos = true;
    console.log("✏️ Ativando modo de edição.");
    AppState.backupPosicoesPivos = {};
    
    AppState.marcadoresPivos.forEach(m => map.removeLayer(m));
    AppState.marcadoresPivos = [];
    AppState.marcadoresLegenda.filter(l => l.options.labelType === 'pivot').forEach(l => map.hasLayer(l) && map.removeLayer(l));
    AppState.marcadoresLegenda = AppState.marcadoresLegenda.filter(l => l.options.labelType !== 'pivot');
    Object.values(AppState.pivotsMap).forEach(marker => marker && map.hasLayer(marker) && map.removeLayer(marker));
    AppState.pivotsMap = {};

    AppState.lastPivosDataDrawn.forEach(pivoInfo => {
        const nome = pivoInfo.nome;
        const currentLatLng = L.latLng(pivoInfo.lat, pivoInfo.lon);
        AppState.backupPosicoesPivos[nome] = currentLatLng;
        const editMarkerIcon = L.divIcon({
            className: 'pivo-edit-handle-custom-pin',
            html: `<svg viewBox="0 0 28 40" width="18" height="26" xmlns="http://www.w3.org/2000/svg"><path d="M14 0 C7.486 0 2 5.486 2 12.014 C2 20.014 14 40 14 40 C14 40 26 20.014 26 12.014 C26 5.486 20.514 0 14 0 Z M14 18 C10.686 18 8 15.314 8 12 C8 8.686 10.686 6 14 6 C17.314 6 20 8.686 20 12 C20 15.314 17.314 18 14 18 Z" fill="#FF3333" stroke="#660000" stroke-width="1"/></svg>`,
            iconSize: [18, 26],
            iconAnchor: [9, 26]
        });
        const editMarker = L.marker(currentLatLng, { draggable: true, icon: editMarkerIcon }).addTo(map);
        AppState.pivotsMap[nome] = editMarker;
        editMarker.on("dragend", (e) => {
            const novaPos = e.target.getLatLng();
            AppState.posicoesEditadas[nome] = { lat: novaPos.lat, lng: novaPos.lng };
            const pivoEmLastData = AppState.lastPivosDataDrawn.find(p => p.nome === nome);
            if (pivoEmLastData) {
                pivoEmLastData.lat = novaPos.lat;
                pivoEmLastData.lon = novaPos.lng;
            }
        });
        editMarker.on("contextmenu", (e) => {
            L.DomEvent.stop(e);
            if (confirm(t('messages.confirm.remove_pivot', { name: nome }))) {
                map.removeLayer(editMarker);
                AppState.lastPivosDataDrawn = AppState.lastPivosDataDrawn.filter(p => p.nome !== nome);
                if (AppState.currentProcessedKmzData?.pivos) AppState.currentProcessedKmzData.pivos = AppState.currentProcessedKmzData.pivos.filter(p => p.nome !== nome);
                const nomeCicloParaRemover = `Ciclo ${nome}`;
                AppState.ciclosGlobais = AppState.ciclosGlobais.filter(c => c.nome_original_circulo !== nomeCicloParaRemover);
                if (AppState.currentProcessedKmzData?.ciclos) AppState.currentProcessedKmzData.ciclos = AppState.currentProcessedKmzData.ciclos.filter(c => c.nome_original_circulo !== nomeCicloParaRemover);
                drawCirculos(AppState.ciclosGlobais);
                delete AppState.pivotsMap[nome];
                delete AppState.posicoesEditadas[nome];
                delete AppState.backupPosicoesPivos[nome];
                mostrarMensagem(t('messages.success.pivot_removed', { name: nome }), "sucesso");
                atualizarPainelDados();
            }
        });
    });
    mostrarMensagem(t('messages.info.edit_mode_activated'), "sucesso");
}

function disablePivoEditingMode() {
    AppState.modoEdicaoPivos = false;
    Object.values(AppState.pivotsMap).forEach(editMarker => editMarker && map.hasLayer(editMarker) && map.removeLayer(editMarker));
    AppState.pivotsMap = {};
    drawPivos(AppState.lastPivosDataDrawn, false);
    mostrarMensagem(t('messages.info.positions_updated_resimulate'), "sucesso");
    AppState.backupPosicoesPivos = {};
    AppState.posicoesEditadas = {};
}

function undoPivoEdits() {
    Object.entries(AppState.backupPosicoesPivos).forEach(([nome, posicaoOriginalLatLng]) => {
        const pivoEmLastData = AppState.lastPivosDataDrawn.find(p => p.nome === nome);
        if (pivoEmLastData) {
            pivoEmLastData.lat = posicaoOriginalLatLng.lat;
            pivoEmLastData.lon = posicaoOriginalLatLng.lng;
        }
        const editMarker = AppState.pivotsMap[nome];
        if (editMarker && map.hasLayer(editMarker)) editMarker.setLatLng(posicaoOriginalLatLng);
    });
    AppState.posicoesEditadas = {};
    if (typeof togglePivoEditing === 'function' && AppState.modoEdicaoPivos) togglePivoEditing();
    mostrarMensagem(t('messages.info.edits_undone'), "sucesso");
}

function toggleLoSPivotAPivotMode() {
    AppState.modoLoSPivotAPivot = !AppState.modoLoSPivotAPivot;
    document.getElementById('btn-los-pivot-a-pivot').classList.toggle('glass-button-active', AppState.modoLoSPivotAPivot);
    
    if (AppState.modoLoSPivotAPivot) {
        mostrarMensagem(t('messages.info.los_mode_step1_source'), "sucesso");
        if (AppState.marcadorPosicionamento) removePositioningMarker();
        document.getElementById("painel-repetidora").classList.add("hidden");
        AppState.losSourcePivot = null;
        AppState.losTargetPivot = null;
        if (AppState.modoEdicaoPivos && document.getElementById("editar-pivos").classList.contains('glass-button-active')) togglePivoEditing();
        if (AppState.modoBuscaLocalRepetidora && document.getElementById('btn-buscar-locais-repetidora').classList.contains('glass-button-active')) handleBuscarLocaisRepetidoraActivation();
        map.getContainer().style.cursor = 'help';
    } else {
        mostrarMensagem(t('messages.info.los_mode_deactivated'), "sucesso");
        AppState.losSourcePivot = null;
        AppState.losTargetPivot = null;
        map.getContainer().style.cursor = '';
        if (visadaLayerGroup) {
            visadaLayerGroup.clearLayers();
            AppState.linhasDiagnostico = [];
            AppState.marcadoresBloqueio = [];
        }
    }
}

async function handleLoSPivotClick(pivoData, pivoMarker) {
    if (!AppState.modoLoSPivotAPivot) return;
    const isGoodSignalPivot = pivoMarker.options.fillColor === 'green';
    const pivotLatlng = pivoMarker.getLatLng();
    const defaultPivotHeight = (AppState.antenaGlobal?.altura_receiver) ?? 3;

    if (!AppState.losSourcePivot) {
        if (!isGoodSignalPivot) {
            mostrarMensagem(t('messages.errors.los_source_must_be_green'), "erro");
            return;
        }
        AppState.losSourcePivot = { nome: pivoData.nome, latlng: pivotLatlng, altura: defaultPivotHeight };
        mostrarMensagem(t('messages.info.los_source_selected', { name: pivoData.nome }), "sucesso");
    } else {
        if (pivoData.nome === AppState.losSourcePivot.nome) {
            mostrarMensagem(t('messages.info.los_source_already_selected', { name: pivoData.nome }), "info");
            return;
        }
        if (isGoodSignalPivot) {
            if (confirm(t('messages.confirm.change_los_source', { sourceName: AppState.losSourcePivot.nome, newName: pivoData.nome }))) {
                AppState.losSourcePivot = { nome: pivoData.nome, latlng: pivotLatlng, altura: defaultPivotHeight };
                AppState.losTargetPivot = null;
                visadaLayerGroup.clearLayers();
                AppState.linhasDiagnostico = [];
                AppState.marcadoresBloqueio = [];
                mostrarMensagem(t('messages.info.los_source_changed', { name: pivoData.nome }), "sucesso");
            }
            return;
        }
        AppState.losTargetPivot = { nome: pivoData.nome, latlng: pivotLatlng, altura: defaultPivotHeight };
        mostrarLoader(true);
        let ocorreuErroNaAnalise = false;
        let distanciaFormatada = "N/A";
        try {
            const distanciaEntrePivos = AppState.losSourcePivot.latlng.distanceTo(AppState.losTargetPivot.latlng);
            distanciaFormatada = distanciaEntrePivos > 999 ? (distanciaEntrePivos / 1000).toFixed(1) + ' km' : Math.round(distanciaEntrePivos) + ' m';
            
            const payload = {
                pontos: [ [AppState.losSourcePivot.latlng.lat, AppState.losSourcePivot.latlng.lng], [AppState.losTargetPivot.latlng.lat, AppState.losTargetPivot.latlng.lng] ],
                altura_antena: AppState.losSourcePivot.altura, altura_receiver: AppState.losTargetPivot.altura
            };
            const resultadoApi = await getElevationProfile(payload);
            const estaBloqueado = resultadoApi.bloqueio?.diff > 0.1;
            drawDiagnostico(payload.pontos[0], payload.pontos[1], resultadoApi.bloqueio, resultadoApi.ponto_mais_alto, `${AppState.losSourcePivot.nome} → ${AppState.losTargetPivot.nome}`, distanciaFormatada);
            
            let statusKey = 'los_result_clear';
            if (estaBloqueado) statusKey = 'los_result_blocked';
            else if (resultadoApi.bloqueio) statusKey = 'los_result_clear_critical';

            mostrarMensagem(t(`messages.info.${statusKey}`, { source: AppState.losSourcePivot.nome, target: AppState.losTargetPivot.nome, distance: distanciaFormatada }), estaBloqueado ? "erro" : "sucesso");

        } catch (error) {
            ocorreuErroNaAnalise = true;
            console.error(`Erro no diagnóstico LoS Pivô a Pivô:`, error);
            mostrarMensagem(t('messages.info.los_result_error', { source: AppState.losSourcePivot?.nome || 'Origem', target: AppState.losTargetPivot?.nome || 'Destino', distance: distanciaFormatada, error: error.message }), "erro");
        } finally {
            mostrarLoader(false);
            AppState.losSourcePivot = null;
            AppState.losTargetPivot = null;
            if (AppState.modoLoSPivotAPivot) setTimeout(() => { if (AppState.modoLoSPivotAPivot) mostrarMensagem(t('messages.info.los_new_source_prompt'), "info"); }, ocorreuErroNaAnalise ? 700 : 1800);
        }
    }
}

function handleToggleDistanciasPivos() {
    AppState.distanciasPivosVisiveis = !AppState.distanciasPivosVisiveis;
    const btn = document.getElementById('toggle-distancias-pivos');
    if (btn) {
        btn.classList.toggle('glass-button-active', AppState.distanciasPivosVisiveis);
        btn.title = AppState.distanciasPivosVisiveis ? t('ui.titles.hide_pivot_distances') : t('ui.titles.show_pivot_distances');
    }
    togglePivoDistances(AppState.distanciasPivosVisiveis);
}

function handleCancelDraw(e) {
    let drawCancelled = false;
    let messageKey = '';

    // Lógica de cancelamento para Pivô Circular
    if (AppState.modoDesenhoPivo && AppState.centroPivoTemporario) {
        if (typeof removeTempCircle === 'function') removeTempCircle();
        messageKey = 'messages.info.draw_pivot_cancelled';
        drawCancelled = true;
    }
    // Lógica de cancelamento para Pivô Setorial
    else if (AppState.modoDesenhoPivoSetorial && AppState.centroPivoTemporario) {
        if (typeof removeTempSector === 'function') removeTempSector();
        messageKey = 'messages.info.draw_sector_cancelled';
        drawCancelled = true;
    }
    // Lógica de cancelamento para Pivô Pac-Man
    else if (AppState.modoDesenhoPivoPacman && AppState.centroPivoTemporario) {
        if (typeof removeTempPacman === 'function') removeTempPacman();
        messageKey = 'messages.info.draw_pacman_cancelled';
        drawCancelled = true;
    }

    // Se uma ação de desenho foi cancelada, reseta os estados e mostra a mensagem.
    if (drawCancelled) {
        L.DomEvent.preventDefault(e);
        L.DomEvent.stopPropagation(e);

        console.log("✏️ Ação de desenho cancelada pelo usuário.");
        AppState.centroPivoTemporario = null;
        AppState.pontoRaioTemporario = null; // Reseta para todos os modos por segurança
        
        if (messageKey) {
            mostrarMensagem(t(messageKey), "info");
        }
    }
}

function parseCoordinates(coordString) {
    coordString = coordString.trim();
    const dmsToDd = (degrees, minutes, seconds, direction) => {
        let dd = parseFloat(degrees) + parseFloat(minutes) / 60 + parseFloat(seconds) / 3600;
        if (direction === 'S' || direction === 'W') dd = dd * -1;
        return dd;
    };
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
    const cleanedString = coordString.replace(/,/g, ' ').replace(/\s+/, ' ').trim();
    const parts = cleanedString.split(' ');
    if (parts.length === 2) {
        const lat = parseFloat(parts[0]);
        const lon = parseFloat(parts[1]);
        if (!isNaN(lat) && !isNaN(lon) && lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180) {
            return { lat, lon };
        }
    }
    return null;
}

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
        removePositioningMarker();
        AppState.marcadorPosicionamento = L.marker(latlng, { icon: antenaIcon, interactive: true }).addTo(map);
        map.setView(latlng, 15);
        mostrarMensagem(t('messages.success.location_found'), "sucesso");
        AppState.coordenadaClicada = latlng;
        document.getElementById("painel-repetidora").classList.remove("hidden");
        inputField.value = '';
    } else {
        mostrarMensagem(t('messages.error.invalid_coordinate_format'), "erro");
    }
}

function getNextPivotNumber() {
    let maxNumber = 0;
    AppState.lastPivosDataDrawn.forEach(pivo => {
        const match = pivo.nome.match(/\d+/);
        if (match) {
            const currentNumber = parseInt(match[0], 10);
            if (currentNumber > maxNumber) maxNumber = currentNumber;
        }
    });
    return maxNumber + 1;
}

function toggleModoDesenhoPivoSetorial() {
    AppState.modoDesenhoPivoSetorial = !AppState.modoDesenhoPivoSetorial;
    document.getElementById('btn-draw-pivot-setorial').classList.toggle('glass-button-active', AppState.modoDesenhoPivoSetorial);

    if (AppState.modoDesenhoPivoSetorial) {
        if (AppState.modoDesenhoPivo) toggleModoDesenhoPivo();
        if (AppState.modoEdicaoPivos) togglePivoEditing();
        if (AppState.modoLoSPivotAPivot) toggleLoSPivotAPivotMode();
        if (AppState.modoBuscaLocalRepetidora) handleBuscarLocaisRepetidoraActivation();

        map.getContainer().style.cursor = 'crosshair';
        map.on('click', handleSectorialPivotDrawClick);
        map.on('mousemove', handleSectorialDrawMouseMove);
        mostrarMensagem(t('messages.info.draw_sector_pivot_step1'), "info");
    } else {
        map.getContainer().style.cursor = '';
        map.off('click', handleSectorialPivotDrawClick);
        map.off('mousemove', handleSectorialDrawMouseMove);
        AppState.centroPivoTemporario = null;
        if (typeof removeTempSector === 'function') removeTempSector();
        mostrarMensagem(t('messages.info.draw_sector_pivot_off'), "sucesso");
    }
}

/**
 * Lida com os cliques no mapa para desenhar um pivô setorial.
 * O primeiro clique define o centro; o segundo define o raio e a direção.
 * @param {object} e - O evento de clique do Leaflet.
 */
async function handleSectorialPivotDrawClick(e) {
    // Garante que a função só execute se o modo de desenho setorial estiver ativo.
    if (!AppState.modoDesenhoPivoSetorial) return;

    // Primeiro clique: Define o ponto central do pivô.
    if (!AppState.centroPivoTemporario) {
        AppState.centroPivoTemporario = e.latlng;
        mostrarMensagem(t('messages.info.draw_sector_pivot_step2'), "info");
        return; // Aguarda o próximo clique.
    }

    // Segundo clique: Define o ponto final, que determina o raio e a direção.
    const finalPoint = e.latlng;
    const radius = AppState.centroPivoTemporario.distanceTo(finalPoint);

    // Limpa a forma de pré-visualização do mapa.
    if (typeof removeTempSector === 'function') {
        removeTempSector();
    }

    // Validação para evitar pivôs muito pequenos ou cliques acidentais.
    if (radius < 10) { // Raio mínimo de 10 metros.
        AppState.centroPivoTemporario = null; // Reseta o desenho.
        mostrarMensagem(t('messages.errors.draw_pivot_radius_too_small'), "erro");
        return;
    }

    mostrarLoader(true);
    try {
        // Calcula a direção (azimute) do centro para o ponto final.
        const bearing = calculateBearing(AppState.centroPivoTemporario, finalPoint);
        const novoNumero = getNextPivotNumber();
        const novoNome = `Pivô ${novoNumero}`;
        
        // Cria o objeto de dados para o novo pivô setorial.
        const novoPivo = {
            nome: novoNome,
            lat: AppState.centroPivoTemporario.lat,
            lon: AppState.centroPivoTemporario.lng,
            fora: true, // Começa como "fora da cobertura" até a reavaliação.
            tipo: 'setorial', // Identificador crucial para o frontend e backend.
            raio: radius,
            angulo_central: bearing, // A direção do setor.
            abertura_arco: 180       // A largura do arco (fixa em 180 graus neste caso).
        };
        AppState.lastPivosDataDrawn.push(novoPivo);

        // Cria um "ciclo" correspondente com coordenadas vazias.
        // Isso mantém a consistência da estrutura de dados para a exportação.
        const novoCiclo = {
            nome_original_circulo: `Ciclo ${novoPivo.nome}`,
            coordenadas: []
        };
        AppState.ciclosGlobais.push(novoCiclo);

        // Atualiza a UI para refletir o novo pivô.
        atualizarPainelDados();
        if (typeof drawPivos === 'function') drawPivos(AppState.lastPivosDataDrawn, false);
        if (typeof drawCirculos === 'function') drawCirculos(AppState.ciclosGlobais);
        
        // Chama a API para recalcular a cobertura de sinal com o novo pivô.
        await reavaliarPivosViaAPI();
        
        mostrarMensagem(t('messages.success.sector_pivot_created', { name: novoPivo.nome }), "sucesso");

    } catch (error) {
        console.error("Erro ao criar pivô setorial:", error);
        mostrarMensagem(t('messages.errors.generic_error', { error: error.message }), "erro");
    } finally {
        // Reseta o estado do desenho para permitir a criação de um novo pivô.
        AppState.centroPivoTemporario = null;
        mostrarLoader(false);
        
        // Informa ao usuário que ele pode continuar desenhando.
        setTimeout(() => {
            if (AppState.modoDesenhoPivoSetorial) {
                mostrarMensagem(t('messages.info.draw_sector_pivot_still_active'), "info");
            }
        }, 2000);
    }
}

function handleSectorialDrawMouseMove(e) {
    if (AppState.modoDesenhoPivoSetorial && AppState.centroPivoTemporario) {
        if (typeof drawTempSector === 'function') {
            drawTempSector(AppState.centroPivoTemporario, e.latlng);
        }
    }
}

function handleCancelCircularDraw(e) {
    if (AppState.modoDesenhoPivo && AppState.centroPivoTemporario) {
        L.DomEvent.preventDefault(e);
        L.DomEvent.stopPropagation(e);
        console.log("✏️ Ação de desenho de CÍRCULO cancelada.");
        if (typeof removeTempCircle === 'function') removeTempCircle();
        AppState.centroPivoTemporario = null;
        mostrarMensagem(t('messages.info.draw_pivot_cancelled'), "info");
    }
}

function toggleModoDesenhoPivoPacman() {
    AppState.modoDesenhoPivoPacman = !AppState.modoDesenhoPivoPacman;
    document.getElementById('btn-draw-pivot-pacman').classList.toggle('glass-button-active', AppState.modoDesenhoPivoPacman);

    if (AppState.modoDesenhoPivoPacman) {
        // Desativa outros modos para evitar conflitos
        if (AppState.modoDesenhoPivo) toggleModoDesenhoPivo();
        if (AppState.modoDesenhoPivoSetorial) toggleModoDesenhoPivoSetorial();
        if (AppState.modoEdicaoPivos) togglePivoEditing();
        
        map.getContainer().style.cursor = 'crosshair';
        map.on('click', handlePacmanPivotDrawClick);
        map.on('mousemove', handlePacmanDrawMouseMove);
        mostrarMensagem(t('messages.info.draw_pacman_step1'), "info");
    } else {
        map.getContainer().style.cursor = '';
        map.off('click', handlePacmanPivotDrawClick);
        map.off('mousemove', handlePacmanDrawMouseMove);
        AppState.centroPivoTemporario = null;
        AppState.pontoRaioTemporario = null;
        if (typeof removeTempPacman === 'function') removeTempPacman();
        mostrarMensagem(t('messages.info.draw_pacman_off'), "sucesso");
    }
}

function handlePacmanDrawMouseMove(e) {
    if (AppState.modoDesenhoPivoPacman && AppState.centroPivoTemporario) {
        if (typeof drawTempPacman === 'function') {
            // A função de desenho temporário saberá em que estágio estamos
            drawTempPacman(AppState.centroPivoTemporario, AppState.pontoRaioTemporario, e.latlng);
        }
    }
}

async function handlePacmanPivotDrawClick(e) {
    if (!AppState.modoDesenhoPivoPacman) return;

    // 1. Primeiro clique: Define o centro
    if (!AppState.centroPivoTemporario) {
        AppState.centroPivoTemporario = e.latlng;
        mostrarMensagem(t('messages.info.draw_pacman_step2'), "info");
        return;
    }

    // 2. Segundo clique: Define o raio e o primeiro ângulo
    if (!AppState.pontoRaioTemporario) {
        AppState.pontoRaioTemporario = e.latlng;
        mostrarMensagem(t('messages.info.draw_pacman_step3'), "info");
        return;
    }

    // 3. Terceiro clique: Define o ângulo final e cria o pivô
    const finalPoint = e.latlng;
    mostrarLoader(true);

    try {
        const centro = AppState.centroPivoTemporario;
        const raio = centro.distanceTo(AppState.pontoRaioTemporario);

        if (raio < 10) {
             throw new Error(t('messages.errors.draw_pivot_radius_too_small'));
        }

        const anguloInicio = calculateBearing(centro, AppState.pontoRaioTemporario);
        const anguloFim = calculateBearing(centro, finalPoint);
        
        const novoNumero = getNextPivotNumber();
        const novoNome = `Pivô ${novoNumero}`;

        const novoPivo = {
            nome: novoNome,
            lat: centro.lat,
            lon: centro.lng,
            fora: true,
            tipo: 'pacman',
            raio: raio,
            angulo_inicio: anguloInicio,
            angulo_fim: anguloFim
        };
        
        AppState.lastPivosDataDrawn.push(novoPivo);

        // ✅ INÍCIO DA CORREÇÃO: Adiciona o placeholder na lista de ciclos.
        // Isto é crucial para que o backend saiba que esta área existe.
        const novoCiclo = {
            nome_original_circulo: `Ciclo ${novoPivo.nome}`,
            coordenadas: [] // Coordenadas vazias, pois a forma é gerada por parâmetros.
        };
        AppState.ciclosGlobais.push(novoCiclo);
        // ✅ FIM DA CORREÇÃO

        // Redesenha tudo no mapa
        drawPivos(AppState.lastPivosDataDrawn, false);
        drawCirculos(AppState.ciclosGlobais);
        
        await reavaliarPivosViaAPI();
        mostrarMensagem(t('messages.success.pacman_pivot_created', { name: novoPivo.nome }), "sucesso");

    } catch (error) {
        console.error("Erro ao criar pivô Pac-Man:", error);
        mostrarMensagem(error.message, "erro");
    } finally {
        // Reseta para o próximo desenho
        AppState.centroPivoTemporario = null;
        AppState.pontoRaioTemporario = null;
        if (typeof removeTempPacman === 'function') removeTempPacman();
        mostrarLoader(false);

        setTimeout(() => {
            if (AppState.modoDesenhoPivoPacman) {
                mostrarMensagem(t('messages.info.draw_pacman_still_active'), "info");
            }
        }, 2500);
    }
}