// --- Variáveis Globais de Estado (Anexadas a 'window') ---

window.jobId = null;
window.modoEdicaoPivos = false;
window.coordenadaClicada = null;
window.marcadorPosicionamento = null;
window.backupPosicoesPivos = {};
window.modoLoSPivotAPivot = false; // Controla o novo modo de diagnóstico
window.losSourcePivot = null;      // Armazena o pivô de origem selecionado {nome, latlng, altura}
window.losTargetPivot = null;    // Armazena o pivô de destino selecionado {nome, latlng, altura}
window.modoBuscaLocalRepetidora = false; // Controla o modo de busca por locais de repetidora
window.pivoAlvoParaLocalRepetidora = null; // Armazena o pivô alvo para a busca
window.ciclosGlobais = [];

// Novas/Modificadas variáveis globais para a funcionalidade de distância
window.antenaGlobal = null; // Será um objeto como { lat, lon, altura, altura_receiver, nome, overlay, bounds, imagem_filename_principal }
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


// --- Inicialização ---

document.addEventListener("DOMContentLoaded", () => {
    console.log("DOM Carregado. Iniciando Aplicação...");
    initMap();
    setupUIEventListeners();
    setupMainActionListeners();
    loadAndPopulateTemplates();
    reposicionarPaineisLaterais();
    lucide.createIcons();
    console.log("Aplicação Pronta.");

    if (typeof toggleLegendas === 'function') { // Garante que foi carregada
        toggleLegendas(legendasAtivas); // Chama para definir o estado inicial do ícone
    }
});

// --- Configuração dos Listeners Principais ---

function setupMainActionListeners() {
    document.getElementById('formulario').addEventListener('submit', handleFormSubmit);
    document.getElementById('simular-btn').addEventListener('click', handleSimulateClick);
    document.getElementById('resetar-btn').addEventListener('click', handleResetClick);
    document.getElementById('btn-diagnostico').addEventListener('click', handleDiagnosticoClick);
    document.getElementById('exportar-btn').addEventListener('click', handleExportClick);
    document.getElementById('confirmar-repetidora').addEventListener('click', handleConfirmRepetidoraClick);
    document.getElementById('btn-los-pivot-a-pivot').addEventListener('click', toggleLoSPivotAPivotMode);
    document.getElementById('btn-buscar-locais-repetidora').addEventListener('click', handleBuscarLocaisRepetidoraActivation);
    map.on("click", handleMapClick);

    const toggleDistanciasBtn = document.getElementById('toggle-distancias-pivos');
    if (toggleDistanciasBtn) {
        toggleDistanciasBtn.addEventListener('click', handleToggleDistanciasPivos);
    } else {
        // console.error("Botão 'toggle-distancias-pivos' não encontrado no DOM.");
    }
}

// --- Handlers de Ações Principais ---

async function handleFormSubmit(e) {
    e.preventDefault();
    const fileInput = document.getElementById('arquivo');
    if (!fileInput.files || fileInput.files.length === 0) {
        mostrarMensagem("Por favor, selecione um arquivo KMZ.", "erro");
        return;
    }
    mostrarLoader(true);
    const formData = new FormData();
    formData.append("file", fileInput.files[0]);

    try {
        const data = await processKmz(formData); //
        console.log("✅ KMZ Processado:", data);

        // 👇 ALTERADO: Armazena o ID do Job retornado pelo backend
        if (!data.job_id) {
            throw new Error("A resposta do servidor não incluiu um ID de job. A API pode estar desatualizada.");
        }
        window.jobId = data.job_id;
        console.log(`SESSION_INFO: Job ID definido como: ${window.jobId}`);

        window.currentProcessedKmzData = JSON.parse(JSON.stringify(data));

        handleResetClick(false);

        // 👇 NOVO: Após o reset, o jobId e os dados precisam ser restaurados, pois handleResetClick os limpa.
        window.jobId = data.job_id;
        window.currentProcessedKmzData = JSON.parse(JSON.stringify(data));

        window.antenaGlobal = data.antena;
        if (window.antenaGlobal) {
            marcadorAntena = drawAntena(data.antena); //
            addAntenaAoPainel(window.antenaGlobal); //
        } else {
            mostrarMensagem("⚠️ Antena principal não encontrada no KMZ.", "erro");
        }

        drawBombas(data.bombas || []); //
        window.ciclosGlobais = data.ciclos || [];
        drawCirculos(window.ciclosGlobais); //

        const pivosParaDesenhar = data.pivos || [];
        const pivosComStatusInicial = pivosParaDesenhar.map(p => ({
            ...p,
            fora: true
        }));
        window.lastPivosDataDrawn = JSON.parse(JSON.stringify(pivosComStatusInicial));
        drawPivos(pivosComStatusInicial); //

        if (window.antenaGlobal && pivosParaDesenhar.length > 0) {
            const boundsToFit = [
                [window.antenaGlobal.lat, window.antenaGlobal.lon]
            ];
            pivosParaDesenhar.forEach(p => boundsToFit.push([p.lat, p.lon]));
            map.fitBounds(boundsToFit, { padding: [50, 50] });
        } else if (window.antenaGlobal) {
            map.setView([window.antenaGlobal.lat, window.antenaGlobal.lon], 13);
        } else if (pivosParaDesenhar.length > 0) {
            const pivoBounds = pivosParaDesenhar.map(p => [p.lat, p.lon]);
            if (pivoBounds.length > 0) map.fitBounds(pivoBounds, { padding: [50, 50] });
        }

        atualizarPainelDados(); //
        mostrarMensagem("✅ KMZ carregado com sucesso.", "sucesso");

        document.getElementById("simular-btn").classList.remove("hidden");
        document.getElementById("painel-dados").classList.remove("hidden");
        document.getElementById("painel-repetidoras").classList.remove("hidden");
        reposicionarPaineisLaterais(); //

    } catch (error) {
        console.error("❌ Erro no submit do formulário:", error);
        mostrarMensagem(`❌ Erro ao carregar KMZ: ${error.message}`, "erro");
        window.jobId = null; // Limpa o job id em caso de erro
    } finally {
        mostrarLoader(false);
    }
}

async function handleSimulateClick() {
    // 👇 ALTERADO: Verifica se um job válido foi iniciado
    if (!window.antenaGlobal || !window.jobId) {
        mostrarMensagem("⚠️ Carregue um KMZ primeiro para iniciar um job!", "erro");
        return;
    }

    mostrarLoader(true);

    try {
        templateSelecionado = document.getElementById('template-modelo').value;
        const pivos_atuais = window.lastPivosDataDrawn.map(p => ({
            nome: p.nome,
            lat: p.lat,
            lon: p.lon
        }));

        // 👇 ALTERADO: Adiciona o jobId ao payload da simulação
        const payload = {
            job_id: window.jobId,
            ...window.antenaGlobal,
            pivos_atuais,
            template: templateSelecionado
        };
        delete payload.overlay;
        delete payload.bounds;
        delete payload.imagem_filename_principal;

        const data = await simulateSignal(payload); //
        console.log("✅ Simulação concluída:", data);

        if (window.antenaGlobal.overlay && map.hasLayer(window.antenaGlobal.overlay)) {
            map.removeLayer(window.antenaGlobal.overlay);
             const index = overlaysVisiveis.indexOf(window.antenaGlobal.overlay);
             if (index > -1) {
                 overlaysVisiveis.splice(index, 1);
             }
        }

        window.antenaGlobal.overlay = drawImageOverlay(data.imagem_salva, data.bounds); //
        window.antenaGlobal.bounds = data.bounds;
        window.antenaGlobal.imagem_filename_principal = data.imagem_filename;

        window.lastPivosDataDrawn = JSON.parse(JSON.stringify(data.pivos));
        drawPivos(data.pivos, true); //
        atualizarPainelDados(); //

        mostrarMensagem("📡 Estudo de sinal concluído.", "sucesso");
        document.getElementById("btn-diagnostico").classList.remove("hidden");

        const btnSimular = document.getElementById("simular-btn");
        btnSimular.disabled = true;
        btnSimular.classList.add("opacity-50", "cursor-not-allowed");

    } catch (error) {
        console.error("❌ Erro ao simular sinal:", error);
        mostrarMensagem(`❌ Falha na simulação: ${error.message}`, "erro");
    } finally {
        mostrarLoader(false);
    }
}

function handleMapClick(e) {
    if (window.modoEdicaoPivos) return;
    if (window.modoLoSPivotAPivot) return;
    if (window.modoBuscaLocalRepetidora) return;

    window.ultimoCliqueFoiSobrePivo = false;
    window.coordenadaClicada = e.latlng;
    window.removePositioningMarker();

    window.marcadorPosicionamento = L.marker(window.coordenadaClicada, {
        icon: posicionamentoIcon, //
        interactive: false,
        opacity: 0.7,
        zIndexOffset: 1000
    }).addTo(map);

    document.getElementById("painel-repetidora").classList.remove("hidden");
}

async function handleConfirmRepetidoraClick() {
    if (!window.coordenadaClicada) {
        mostrarMensagem("⚠️ Clique no mapa primeiro para definir a posição!", "erro");
        return;
    }
    // 👇 ALTERADO: Verifica se um job válido foi iniciado
    if (!window.jobId) {
        mostrarMensagem("⚠️ Inicie um job carregando um KMZ primeiro.", "erro");
        return;
    }

    mostrarLoader(true);
    document.getElementById('painel-repetidora').classList.add('hidden');
    window.removePositioningMarker();

    const alturaAntena = parseFloat(document.getElementById("altura-antena-rep").value);
    const alturaReceiver = parseFloat(document.getElementById("altura-receiver-rep").value);
    templateSelecionado = document.getElementById('template-modelo').value;

    const id = idsDisponiveis.length > 0 ? idsDisponiveis.shift() : ++contadorRepetidoras;
    const nomeRep = `Repetidora ${id}`;

    const novaRepetidoraMarker = L.marker(window.coordenadaClicada, { icon: antenaIcon }).addTo(map); //
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

    const repetidoraObj = {
        id,
        marker: novaRepetidoraMarker,
        overlay: null,
        label: labelRepetidora,
        altura: alturaAntena,
        altura_receiver: alturaReceiver,
        lat: window.coordenadaClicada.lat,
        lon: window.coordenadaClicada.lng,
        imagem_filename: null,
        sobre_pivo: window.ultimoCliqueFoiSobrePivo || false
    };
    repetidoras.push(repetidoraObj);

    const pivosParaSimulacaoRepetidora = window.lastPivosDataDrawn.map(p => ({
        nome: p.nome, lat: p.lat, lon: p.lon
    }));

    // 👇 ALTERADO: Adiciona o jobId ao payload da simulação manual
    const payload = {
        job_id: window.jobId,
        lat: window.coordenadaClicada.lat,
        lon: window.coordenadaClicada.lng,
        altura: alturaAntena,
        altura_receiver: alturaReceiver,
        pivos_atuais: pivosParaSimulacaoRepetidora,
        template: templateSelecionado
    };

    try {
        const data = await simulateManual(payload); //
        console.log("Simulação Manual Concluída:", data);

        if (data.erro) throw new Error(data.erro);

        repetidoraObj.overlay = drawImageOverlay(data.imagem_salva, data.bounds, 1.0); //
        repetidoraObj.imagem_filename = data.imagem_filename;
        
        addRepetidoraNoPainel(repetidoraObj); //
        await reavaliarPivosViaAPI();

        mostrarMensagem(`📡 Repetidora ${id} adicionada e simulada.`, "sucesso");
        document.getElementById("painel-repetidoras").classList.remove("hidden");
        reposicionarPaineisLaterais(); //

    } catch (error) {
        console.error("Erro ao confirmar repetidora:", error);
        mostrarMensagem(`❌ Falha ao simular repetidora: ${error.message}`, "erro");
        map.removeLayer(novaRepetidoraMarker);
        map.removeLayer(labelRepetidora);
        marcadoresLegenda = marcadoresLegenda.filter(l => l !== labelRepetidora);
        repetidoras = repetidoras.filter(r => r.id !== id);
        if (repetidoraObj.overlay && map.hasLayer(repetidoraObj.overlay)) {
             map.removeLayer(repetidoraObj.overlay);
             const index = overlaysVisiveis.indexOf(repetidoraObj.overlay);
             if (index > -1) overlaysVisiveis.splice(index, 1);
        }
        if (!idsDisponiveis.includes(id)) idsDisponiveis.push(id);
        idsDisponiveis.sort((a, b) => a - b);
    } finally {
        mostrarLoader(false);
        window.coordenadaClicada = null;
        atualizarPainelDados(); //
    }
}

function handleBuscarLocaisRepetidoraActivation() {
    window.modoBuscaLocalRepetidora = !window.modoBuscaLocalRepetidora;
    const btn = document.getElementById('btn-buscar-locais-repetidora');

    if (btn) {
        btn.classList.toggle('glass-button-active', window.modoBuscaLocalRepetidora);
    }

    if (window.modoBuscaLocalRepetidora) {
        mostrarMensagem("MODO BUSCA LOCAL REPETIDORA: Selecione um pivô SEM SINAL (vermelho) como alvo.", "sucesso");
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
        mostrarMensagem("Modo 'Buscar Locais para Repetidora' desativado.", "sucesso");

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

    // 👇 ALTERADO: Adicionada verificação de job ativo no início da função.
    if (!window.jobId) {
        mostrarMensagem("⚠️ Inicie um job carregando um KMZ primeiro.", "erro");
        return;
    }

    if (pivoMarker.options.fillColor === 'green') {
        mostrarMensagem("ALVO: Selecione um pivô SEM SINAL (vermelho).", "erro");
        return;
    }

    window.pivoAlvoParaLocalRepetidora = {
        nome: pivoData.nome,
        lat: pivoMarker.getLatLng().lat,
        lon: pivoMarker.getLatLng().lng,
        altura_receiver: (window.antenaGlobal && typeof window.antenaGlobal.altura_receiver === 'number') ? window.antenaGlobal.altura_receiver : 3
    };

    mostrarMensagem(`Pivô alvo ${window.pivoAlvoParaLocalRepetidora.nome} selecionado. Buscando locais...`, "info");
    mostrarLoader(true);
    if (map) map.getContainer().style.cursor = 'wait';

    const activeOverlaysForSearch = [];
    const antenaCheckbox = document.querySelector("#antena-item input[type='checkbox']");

    // 👇 ALTERADO: Usa o nome do arquivo salvo (imagem_filename_principal) em vez de manipular a URL.
    if (window.antenaGlobal?.overlay && map.hasLayer(window.antenaGlobal.overlay) && (!antenaCheckbox || antenaCheckbox.checked) && window.antenaGlobal.imagem_filename_principal) {
        const b = window.antenaGlobal.overlay.getBounds();
        activeOverlaysForSearch.push({
            id: 'antena_principal',
            imagem: window.antenaGlobal.imagem_filename_principal,
            bounds: [b.getSouth(), b.getWest(), b.getNorth(), b.getEast()]
        });
    }

    repetidoras.forEach(rep => {
        const repCheckbox = document.querySelector(`#rep-item-${rep.id} input[type='checkbox']`);
         // 👇 ALTERADO: Usa o nome do arquivo salvo (imagem_filename) em vez de manipular a URL.
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
        mostrarMensagem("Nenhuma área de sinal (antena/repetidoras) ativa para basear a busca. Ative alguma cobertura.", "erro");
        mostrarLoader(false);
        if (map) map.getContainer().style.cursor = window.modoBuscaLocalRepetidora ? 'crosshair' : '';
        return;
    }

    try {
        // 👇 ALTERADO: O payload agora inclui o job_id, que é obrigatório no backend.
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
        } else {
            console.warn("candidateRepeaterSitesLayerGroup não definido.");
        }

        if (resultados && resultados.candidate_sites && resultados.candidate_sites.length > 0) {
            drawCandidateRepeaterSites(resultados.candidate_sites, window.pivoAlvoParaLocalRepetidora);
            mostrarMensagem(`Encontrados ${resultados.candidate_sites.length} locais candidatos. Clique em um para simular.`, "sucesso");
        } else {
            mostrarMensagem("Nenhum local promissor encontrado nas áreas de cobertura existentes.", "info");
        }

    } catch (error) {
        console.error("Erro ao buscar locais para repetidora:", error);
        mostrarMensagem(`Falha ao buscar locais: ${error.message || 'Erro desconhecido'}`, "erro");
    } finally {
        mostrarLoader(false);
        if (map) map.getContainer().style.cursor = window.modoBuscaLocalRepetidora ? 'crosshair' : '';
    }
}

function handleResetClick(showMessage = true) {
    console.log("🔄 Resetando aplicação...");
    clearMapLayers(); // de drawing.js

    // 👇 ALTERADO: A linha mais importante - garante que a sessão/job atual seja limpa.
    window.jobId = null;

    // Reset de todas as variáveis de estado globais
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
    window.currentProcessedKmzData = null;

    const btnDistancias = document.getElementById('toggle-distancias-pivos');
    if (btnDistancias) {
        btnDistancias.classList.remove('glass-button-active');
        btnDistancias.title = "Mostrar Distâncias dos Pivôs";
    }

    // Desativa e reseta todos os modos especiais
    if (window.modoEdicaoPivos) {
        if (typeof togglePivoEditing === 'function' && document.getElementById("editar-pivos")?.classList.contains('glass-button-active')) {
            togglePivoEditing();
        }
    }

    if (window.modoLoSPivotAPivot) {
        if (typeof toggleLoSPivotAPivotMode === 'function' && document.getElementById('btn-los-pivot-a-pivot')?.classList.contains('glass-button-active')) {
            toggleLoSPivotAPivotMode();
        }
    }

    if (window.modoBuscaLocalRepetidora) {
        if (typeof handleBuscarLocaisRepetidoraActivation === 'function' && document.getElementById('btn-buscar-locais-repetidora')?.classList.contains('glass-button-active')) {
            handleBuscarLocaisRepetidoraActivation();
        }
    }

    if (map) {
        map.getContainer().style.cursor = '';
        if (window.candidateRepeaterSitesLayerGroup) {
            window.candidateRepeaterSitesLayerGroup.clearLayers();
        }
    }

    // Reseta o estado dos botões e painéis da UI
    const btnSimular = document.getElementById("simular-btn");
    if (btnSimular) {
        btnSimular.classList.add("hidden");
        btnSimular.disabled = false;
        btnSimular.classList.remove("opacity-50", "cursor-not-allowed");
    }

    const btnDiagnostico = document.getElementById("btn-diagnostico");
    if (btnDiagnostico) {
        btnDiagnostico.classList.add("hidden");
    }

    const listaRepetidoras = document.getElementById("lista-repetidoras");
    if (listaRepetidoras) {
        listaRepetidoras.innerHTML = "";
    }
    
    // Esconde todos os painéis principais
    const paineisParaEsconder = ["painel-repetidora", "painel-dados", "painel-repetidoras", "desfazer-edicao"];
    paineisParaEsconder.forEach(id => {
        const painel = document.getElementById(id);
        if (painel) painel.classList.add("hidden");
    });

    // Reseta o formulário de upload de arquivo
    const formElement = document.getElementById('formulario');
    if (formElement) formElement.reset();

    const nomeArquivoLabelElement = document.getElementById('nome-arquivo-label');
    if (nomeArquivoLabelElement) {
        nomeArquivoLabelElement.textContent = "Escolher Arquivo KMZ";
        nomeArquivoLabelElement.title = "Escolher Arquivo KMZ";
    }

    const rangeOpacidadeElement = document.getElementById("range-opacidade");
    if (rangeOpacidadeElement) rangeOpacidadeElement.value = 1;

    if (map) map.setView([-15, -55], 5);

    if (typeof atualizarPainelDados === 'function') atualizarPainelDados();
    if (typeof reposicionarPaineisLaterais === 'function') reposicionarPaineisLaterais();
    if (typeof toggleLegendas === 'function') toggleLegendas(true);

    if (showMessage) mostrarMensagem("🔄 Aplicação resetada.", "sucesso");
}

async function handleDiagnosticoClick() {
    if (!window.antenaGlobal || Object.keys(pivotsMap).length === 0) {
        mostrarMensagem("⚠️ Rode o estudo de sinal primeiro!", "erro");
        return;
    }

    mostrarLoader(true);
    visadaLayerGroup.clearLayers(); // de map.js
    linhasDiagnostico = [];
    marcadoresBloqueio = [];

    const pivosVermelhos = Object.entries(pivotsMap).filter(([_, m]) => m.options.fillColor === 'red');

    if (pivosVermelhos.length === 0) {
        mostrarMensagem("✅ Nenhum pivô fora de cobertura para diagnosticar.", "sucesso");
        mostrarLoader(false);
        return;
    }

    mostrarMensagem(`🔍 Analisando ${pivosVermelhos.length} pivôs...`, "sucesso");

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
            const data = await getElevationProfile(payload); // de api.js
            drawDiagnostico( // de drawing.js
                payload.pontos[0],
                payload.pontos[1],
                data.bloqueio,
                data.ponto_mais_alto,
                nome
            );
        } catch (error) {
            console.error(`Erro no diagnóstico do pivô ${nome}:`, error);
            mostrarMensagem(`⚠️ Erro ao diagnosticar ${nome}.`, "erro");
        }
    }

    if (typeof lucide !== 'undefined') lucide.createIcons();
    mostrarLoader(false);
    mostrarMensagem("🔍 Diagnóstico de visada concluído.", "sucesso");
}

function handleExportClick() {
    // 👇 ALTERADO: Adicionada a verificação para garantir que um job válido está ativo (!window.jobId).
    if (!window.antenaGlobal?.overlay || !window.antenaGlobal.bounds || !window.antenaGlobal.imagem_filename_principal || !window.jobId) {
        mostrarMensagem("⚠️ Rode a simulação principal primeiro para um job válido!", "erro");
        return;
    }

    try {
        const nomeImagemPrincipal = window.antenaGlobal.imagem_filename_principal;
        const nomeBoundsPrincipal = nomeImagemPrincipal.replace(/\.png$/, '.json');

        // 1. Coleta os dados detalhados das repetidoras cujo checkbox está marcado.
        const repetidorasSelecionadasParaExport = [];
        repetidoras.forEach(rep => {
            const checkbox = document.querySelector(`#rep-item-${rep.id} input[type='checkbox']`);
            
            // A lógica aqui já está correta, usando o .imagem_filename salvo.
            if (checkbox && checkbox.checked && rep.imagem_filename) {
                repetidorasSelecionadasParaExport.push({
                    imagem: rep.imagem_filename,
                    altura: rep.altura,
                    sobre_pivo: rep.sobre_pivo
                });
            }
        });

        console.log("Dados das repetidoras para exportação:", repetidorasSelecionadasParaExport);

        // 👇 ALTERADO: Passa o window.jobId como o primeiro argumento para a função, conforme a nova assinatura em api.js.
        const url = getExportKmzUrl(window.jobId, nomeImagemPrincipal, nomeBoundsPrincipal, repetidorasSelecionadasParaExport);
        
        // Se a getExportKmzUrl retornar uma URL inválida (ex: por jobId nulo), não tenta abrir.
        if (url && url !== "#") {
            window.open(url, '_blank');
            mostrarMensagem("📦 Preparando KMZ para download...", "sucesso");
        }

    } catch (error) {
        console.error("Erro ao exportar KMZ:", error);
        mostrarMensagem(`❌ Erro ao exportar: ${error.message}`, "erro");
    }
}

async function reavaliarPivosViaAPI() {
    console.log("Reavaliando pivôs...");

    // 👇 ALTERADO: Verifica se um job válido foi iniciado
    if (!window.jobId) {
        console.log("Nenhum job ativo para reavaliar.");
        return;
    }

    const pivosAtuaisParaReavaliacao = window.lastPivosDataDrawn.map(p => ({
        nome: p.nome,
        lat: p.lat,
        lon: p.lon
    }));

    // Lógica de fallback para reconstruir a lista de pivôs, caso esteja vazia (sem alterações, já era robusta)
    if (pivosAtuaisParaReavaliacao.length === 0 && Object.keys(pivotsMap).length > 0) {
        console.warn("Reavaliando pivôs: lastPivosDataDrawn estava vazio, usando pivotsMap ou currentProcessedKmzData.");
        const pivosBase = (window.currentProcessedKmzData?.pivos) 
            ? window.currentProcessedKmzData.pivos
            : Object.entries(pivotsMap).map(([nome, marcador]) => ({
                nome,
                lat: marcador.getLatLng().lat,
                lon: marcador.getLatLng().lng
              }));
        
        if (pivosBase.length > 0) {
            window.lastPivosDataDrawn = JSON.parse(JSON.stringify(pivosBase.map(p => ({...p, fora: true}))));
            pivosAtuaisParaReavaliacao.push(...pivosBase.map(p => ({ nome: p.nome, lat: p.lat, lon: p.lon })));
        }
    }
    
    if (pivosAtuaisParaReavaliacao.length === 0) {
        console.log("Nenhum pivô encontrado para reavaliar.");
        return;
    }

    const overlays = [];
    const antenaCheckbox = document.querySelector("#antena-item input[type='checkbox']");

    // 👇 ALTERADO: Usa o nome do arquivo salvo (imagem_filename_principal) em vez de manipular a URL.
    if (window.antenaGlobal?.overlay && map.hasLayer(window.antenaGlobal.overlay) && (!antenaCheckbox || antenaCheckbox.checked) && window.antenaGlobal.imagem_filename_principal) {
        const b = window.antenaGlobal.overlay.getBounds();
        overlays.push({
            id: 'antena_principal',
            imagem: window.antenaGlobal.imagem_filename_principal,
            bounds: [b.getSouth(), b.getWest(), b.getNorth(), b.getEast()]
        });
    }

    repetidoras.forEach(rep => {
        const repCheckbox = document.querySelector(`#rep-item-${rep.id} input[type='checkbox']`);
        // 👇 ALTERADO: Usa o nome do arquivo salvo (imagem_filename) em vez de manipular a URL.
        if (rep.overlay && map.hasLayer(rep.overlay) && (!repCheckbox || repCheckbox.checked) && rep.imagem_filename) {
            const b = rep.overlay.getBounds();
            overlays.push({
                id: `repetidora_${rep.id}`,
                imagem: rep.imagem_filename,
                bounds: [b.getSouth(), b.getWest(), b.getNorth(), b.getEast()]
            });
        }
    });

    if (overlays.length === 0) {
        console.log("Nenhum overlay de sinal visível, marcando todos os pivôs como fora de cobertura.");
        const pivosFora = pivosAtuaisParaReavaliacao.map(p => ({ ...p, fora: true }));
        window.lastPivosDataDrawn = JSON.parse(JSON.stringify(pivosFora));
        drawPivos(pivosFora, true);
        atualizarPainelDados();
        return;
    }

    try {
        // 👇 ALTERADO: Adiciona o jobId ao payload da reavaliação.
        const data = await reevaluatePivots({
            job_id: window.jobId,
            pivos: pivosAtuaisParaReavaliacao,
            overlays
        });
        if (data.pivos) {
            window.lastPivosDataDrawn = JSON.parse(JSON.stringify(data.pivos));
            drawPivos(data.pivos, true);
            atualizarPainelDados();
            console.log("Pivôs reavaliados.");
        }
    } catch (error) {
        console.error("Erro ao reavaliar pivôs via API:", error);
        mostrarMensagem("⚠️ Erro ao atualizar cobertura.", "erro");
    }
}

function formatCoordForFilename(coord) {
    return coord.toFixed(6).replace('.', '_').replace('-', 'm');
}

function removePositioningMarker() {
    if (window.marcadorPosicionamento && map.hasLayer(window.marcadorPosicionamento)) {
        map.removeLayer(window.marcadorPosicionamento);
        window.marcadorPosicionamento = null;
    }
}
window.removePositioningMarker = removePositioningMarker;

// --- Funções de Edição de Pivôs ---

function enablePivoEditingMode() {
    window.modoEdicaoPivos = true;
    console.log("✏️ Ativando modo de edição com ícone de pino SVG.");
    window.backupPosicoesPivos = {}; // Limpa backups antigos

    const tamanho = 18; // Tamanho do ícone de edição
    const altura = 26;  // Altura do ícone de edição

    // Remove os marcadores de pivô existentes (círculos coloridos e legendas)
    marcadoresPivos.forEach(m => map.removeLayer(m));
    marcadoresPivos = [];
    marcadoresLegenda.filter(l => l.options.labelType === 'pivot').forEach(l => {
        if (map.hasLayer(l)) map.removeLayer(l);
    });
    marcadoresLegenda = marcadoresLegenda.filter(l => l.options.labelType !== 'pivot');

    // Remove referências antigas de pivotsMap se ainda estiverem no mapa (improvável, mas seguro)
    Object.values(pivotsMap).forEach(marker => {
        if (marker && map.hasLayer(marker)) {
            map.removeLayer(marker);
        }
    });
    pivotsMap = {}; // Reseta o pivotsMap para os novos marcadores de edição

    // Adiciona novos marcadores de edição para cada pivô em lastPivosDataDrawn
    window.lastPivosDataDrawn.forEach(pivoInfo => {
        const nome = pivoInfo.nome;
        const currentLatLng = L.latLng(pivoInfo.lat, pivoInfo.lon);
        window.backupPosicoesPivos[nome] = currentLatLng; // Salva posição original para 'desfazer'

        const editMarkerIcon = L.divIcon({
            className: 'pivo-edit-handle-custom-pin', // Classe para estilização CSS se necessário
            html: `<svg viewBox="0 0 28 40" width="${tamanho}" height="${altura}" xmlns="http://www.w3.org/2000/svg"><path d="M14 0 C7.486 0 2 5.486 2 12.014 C2 20.014 14 40 14 40 C14 40 26 20.014 26 12.014 C26 5.486 20.514 0 14 0 Z M14 18 C10.686 18 8 15.314 8 12 C8 8.686 10.686 6 14 6 C17.314 6 20 8.686 20 12 C20 15.314 17.314 18 14 18 Z" fill="#FF3333" stroke="#660000" stroke-width="1"/></svg>`,
            iconSize: [tamanho, altura],
            iconAnchor: [tamanho / 2, altura] // Ponta do pino
        });

        const editMarker = L.marker(currentLatLng, {
            draggable: true,
            icon: editMarkerIcon
        }).addTo(map);

        pivotsMap[nome] = editMarker; // Adiciona o marcador de EDIÇÃO ao pivotsMap

        editMarker.on("dragend", (e) => {
            const novaPos = e.target.getLatLng();
            posicoesEditadas[nome] = { lat: novaPos.lat, lng: novaPos.lng }; // Armazena a nova posição editada

            // Atualiza a posição em lastPivosDataDrawn para que, se o modo for desativado,
            // os pivôs sejam redesenhados na nova posição.
            const pivoEmLastData = window.lastPivosDataDrawn.find(p => p.nome === nome);
            if (pivoEmLastData) {
                pivoEmLastData.lat = novaPos.lat;
                pivoEmLastData.lon = novaPos.lng;
            }
            console.log(`📍 Pivô ${nome} movido para:`, novaPos);
        });

        editMarker.on("contextmenu", (e) => { // Botão direito para remover
            L.DomEvent.stopPropagation(e);
            L.DomEvent.preventDefault(e);
            if (confirm(`❌ Tem certeza que deseja remover o pivô ${nome}? Esta ação não pode ser desfeita aqui.`)) {
                map.removeLayer(editMarker);
                // Remove dos dados principais
                window.lastPivosDataDrawn = window.lastPivosDataDrawn.filter(p => p.nome !== nome);
                if (window.currentProcessedKmzData && window.currentProcessedKmzData.pivos) {
                     window.currentProcessedKmzData.pivos = window.currentProcessedKmzData.pivos.filter(p => p.nome !== nome);
                }
                // Remove das estruturas de edição
                delete pivotsMap[nome];
                delete posicoesEditadas[nome];
                delete window.backupPosicoesPivos[nome];
                mostrarMensagem(`🗑️ Pivô ${nome} removido.`, "sucesso");
                atualizarPainelDados();
            }
        });
    });
    mostrarMensagem("✏️ Modo de edição ativado. Arraste os pinos vermelhos. Clique com botão direito para remover.", "sucesso");
}

function disablePivoEditingMode() {
    window.modoEdicaoPivos = false;
    console.log("Desativando modo de edição e 'salvando' posições em lastPivosDataDrawn.");

    // Remove os marcadores de edição (pinos vermelhos) do mapa
    Object.values(pivotsMap).forEach(editMarker => {
        if (editMarker && map.hasLayer(editMarker)) {
            map.removeLayer(editMarker);
        }
    });
    pivotsMap = {}; // Limpa o pivotsMap, pois os marcadores de edição foram removidos

    // As posições já foram atualizadas em window.lastPivosDataDrawn durante o 'dragend'.
    // Agora, apenas redesenha os pivôs no modo normal (círculos coloridos e legendas).
    // O 'true' em drawPivos(..., true) indica para usar posicoesEditadas, mas como elas
    // já foram refletidas em lastPivosDataDrawn, e posicoesEditadas será limpo,
    // passar 'false' ou não passar o segundo argumento seria mais limpo aqui,
    // confiando que lastPivosDataDrawn é a fonte da verdade.
    // No entanto, a lógica atual de drawPivos pode depender de posicoesEditadas se `useEdited` for true.
    // Para segurança, vamos manter como estava, assumindo que drawPivos(..., true) pega de lastPivosDataDrawn
    // se posicoesEditadas[nome] não existir.
    // Melhor: drawPivos deve ser chamado com os dados de lastPivosDataDrawn, e ele decide internamente
    // se usa posicoesEditadas ou não.

    // Redesenha os pivôs com base nas posições atualizadas em window.lastPivosDataDrawn
    drawPivos(window.lastPivosDataDrawn, false); // Passa 'false' para useEdited, pois as posições já estão em lastPivosDataDrawn

    mostrarMensagem("💾 Posições atualizadas. Rode a simulação novamente para refletir mudanças na cobertura.", "sucesso");
    window.backupPosicoesPivos = {}; // Limpa o backup, pois as "edições" foram "salvas"
    posicoesEditadas = {}; // Limpa as edições pendentes
}

function undoPivoEdits() {
    console.log("Desfazendo edições.");
    // Restaura as posições em lastPivosDataDrawn a partir do backup
    Object.entries(window.backupPosicoesPivos).forEach(([nome, posicaoOriginalLatLng]) => {
        const pivoEmLastData = window.lastPivosDataDrawn.find(p => p.nome === nome);
        if (pivoEmLastData) {
            pivoEmLastData.lat = posicaoOriginalLatLng.lat;
            pivoEmLastData.lon = posicaoOriginalLatLng.lng;
        }
        // Se os marcadores de edição ainda estiverem no mapa (o que não deveriam estar se o modo foi desativado antes),
        // atualiza suas posições. Mas o principal é atualizar lastPivosDataDrawn.
        const editMarker = pivotsMap[nome]; // pivotsMap ainda conteria os marcadores de edição
        if (editMarker && map.hasLayer(editMarker)) {
            editMarker.setLatLng(posicaoOriginalLatLng);
        }
    });

    posicoesEditadas = {}; // Limpa quaisquer edições pendentes
    // Não precisa limpar backupPosicoesPivos aqui, pois o modo de edição será desativado.

    // Desativa o modo de edição, o que irá redesenhar os pivôs com as posições restauradas de lastPivosDataDrawn.
    if (typeof togglePivoEditing === 'function' && window.modoEdicaoPivos) { // togglePivoEditing está em ui.js
        togglePivoEditing(); // Isso chamará disablePivoEditingMode
    }
    mostrarMensagem("↩️ Edições desfeitas. Modo de edição encerrado.", "sucesso");
}


function toggleLoSPivotAPivotMode() {
    window.modoLoSPivotAPivot = !window.modoLoSPivotAPivot;
    const btn = document.getElementById('btn-los-pivot-a-pivot');
    btn.classList.toggle('glass-button-active', window.modoLoSPivotAPivot);

    if (window.modoLoSPivotAPivot) {
        mostrarMensagem("MODO DIAGNÓSTICO PIVÔ A PIVÔ: Selecione o pivô de ORIGEM (com sinal/verde).", "sucesso");
        if (window.marcadorPosicionamento) removePositioningMarker();
        document.getElementById("painel-repetidora").classList.add("hidden");
        window.losSourcePivot = null;
        window.losTargetPivot = null;

        // Desativa outros modos
        if (window.modoEdicaoPivos && typeof togglePivoEditing === 'function' && document.getElementById("editar-pivos").classList.contains('glass-button-active')) {
            togglePivoEditing();
        }
        if (window.modoBuscaLocalRepetidora && typeof handleBuscarLocaisRepetidoraActivation === 'function' && document.getElementById('btn-buscar-locais-repetidora').classList.contains('glass-button-active')) {
            handleBuscarLocaisRepetidoraActivation();
        }
        map.getContainer().style.cursor = 'help';
    } else {
        mostrarMensagem("Modo 'Diagnóstico Pivô a Pivô' desativado.", "sucesso");
        window.losSourcePivot = null;
        window.losTargetPivot = null;
        map.getContainer().style.cursor = '';
         // Limpa apenas as linhas de diagnóstico LoS se existirem
        if (visadaLayerGroup) { // visadaLayerGroup é de map.js
            // É melhor ter uma forma mais seletiva de limpar apenas as linhas de diagnóstico LoS,
            // em vez de limpar todo o grupo, que pode conter outras coisas.
            // Por agora, se este modo é o único que adiciona a este grupo, pode ser ok.
            // Assumindo que drawDiagnostico adiciona a visadaLayerGroup.
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

    if (!window.losSourcePivot) { // Fase 1: Selecionando o Pivô de Origem
        if (!isGoodSignalPivot) {
            mostrarMensagem("ORIGEM: Selecione um pivô COM SINAL (verde).", "erro");
            return;
        }
        window.losSourcePivot = {
            nome: pivoData.nome,
            latlng: pivotLatlng,
            altura: defaultPivotHeight
        };
        mostrarMensagem(`ORIGEM: ${pivoData.nome} selecionado. Agora selecione o pivô de DESTINO (sem sinal/vermelho).`, "sucesso");

    } else { // Fase 2: Selecionando o Pivô de Destino (ou mudando a origem)
        if (pivoData.nome === window.losSourcePivot.nome) {
            mostrarMensagem(`ORIGEM: ${pivoData.nome} já é a origem. Selecione o pivô de DESTINO.`, "info");
            return;
        }

        if (isGoodSignalPivot) { // Usuário clicou em outro pivô verde, talvez queira mudar a origem
            const confirmaMudanca = confirm(`Você já selecionou ${window.losSourcePivot.nome} como origem. Deseja alterar a origem para ${pivoData.nome}? As linhas de diagnóstico anteriores serão removidas.`);
            if (confirmaMudanca) {
                window.losSourcePivot = {
                    nome: pivoData.nome,
                    latlng: pivotLatlng,
                    altura: defaultPivotHeight
                };
                window.losTargetPivot = null; // Reseta o alvo ao mudar a origem
                if (visadaLayerGroup) visadaLayerGroup.clearLayers(); // Limpa diagnóstico anterior
                linhasDiagnostico = [];
                marcadoresBloqueio = [];
                mostrarMensagem(`ORIGEM ALTERADA para: ${pivoData.nome}. Selecione o pivô de DESTINO (sem sinal/vermelho).`, "sucesso");
            }
            return;
        }

        // Se chegou aqui, é um pivô vermelho (destino)
        window.losTargetPivot = {
            nome: pivoData.nome,
            latlng: pivotLatlng,
            altura: defaultPivotHeight
        };

        mostrarLoader(true);
        let ocorreuErroNaAnalise = false;
        let distanciaFormatada = "N/A";

        try {
            // Limpa diagnóstico anterior antes de desenhar um novo
            if (visadaLayerGroup) visadaLayerGroup.clearLayers();
            linhasDiagnostico = [];
            marcadoresBloqueio = [];

            console.log("[DEBUG LoS] Source Pivot:", JSON.stringify(window.losSourcePivot));
            console.log("[DEBUG LoS] Target Pivot:", JSON.stringify(window.losTargetPivot));

            if (!window.losSourcePivot.latlng || !window.losTargetPivot.latlng) {
                console.error("[DEBUG LoS] Erro: LatLng de origem ou destino indefinido.");
                throw new Error("LatLng de origem ou destino indefinido para cálculo de distância.");
            }
            if (!(window.losSourcePivot.latlng instanceof L.LatLng) || !(window.losTargetPivot.latlng instanceof L.LatLng) ) {
                 console.error("[DEBUG LoS] Erro: latlng não é um objeto L.LatLng válido.");
                 throw new Error("Objeto LatLng inválido para cálculo de distância.");
            }

            const distanciaEntrePivos = window.losSourcePivot.latlng.distanceTo(window.losTargetPivot.latlng);
            console.log("[DEBUG LoS] Distância calculada (metros):", distanciaEntrePivos);

            if (isNaN(distanciaEntrePivos)) {
                console.error("[DEBUG LoS] Erro: Distância calculada resultou em NaN.");
                distanciaFormatada = "Erro no cálculo";
            } else {
                distanciaFormatada = distanciaEntrePivos > 999
                    ? (distanciaEntrePivos / 1000).toFixed(1) + ' km'
                    : Math.round(distanciaEntrePivos) + ' m';
            }
            console.log("[DEBUG LoS] Distância formatada:", distanciaFormatada);

            const payload = {
                pontos: [
                    [window.losSourcePivot.latlng.lat, window.losSourcePivot.latlng.lng],
                    [window.losTargetPivot.latlng.lat, window.losTargetPivot.latlng.lng]
                ],
                altura_antena: window.losSourcePivot.altura,
                altura_receiver: window.losTargetPivot.altura
            };

            const resultadoApi = await getElevationProfile(payload); // de api.js
            console.log("[DEBUG LoS] Resultado API:", resultadoApi);

            const estaBloqueado = resultadoApi.bloqueio && typeof resultadoApi.bloqueio.diff === 'number' && resultadoApi.bloqueio.diff > 0.1; // Pequena margem para bloqueio

            drawDiagnostico( // de drawing.js
                payload.pontos[0],
                payload.pontos[1],
                resultadoApi.bloqueio,
                resultadoApi.ponto_mais_alto,
                `${window.losSourcePivot.nome} → ${window.losTargetPivot.nome}`,
                distanciaFormatada
            );

            let mensagemVisada = `Visada ${window.losSourcePivot.nome} → ${window.losTargetPivot.nome} (Dist: ${distanciaFormatada})`;
            if (estaBloqueado) {
                mensagemVisada += ` ⛔ Bloqueada.`;
            } else if (resultadoApi.bloqueio && typeof resultadoApi.bloqueio.diff === 'number') { // Não bloqueado, mas tem ponto crítico
                mensagemVisada += ` ✅ Livre no ponto crítico.`;
            } else { // Sem ponto crítico retornado (LoS completamente livre ou erro na API não capturado antes)
                 mensagemVisada += ` ✅ Livre.`;
            }
            console.log("[DEBUG LoS] Mensagem de visada final:", mensagemVisada);
            mostrarMensagem(mensagemVisada, estaBloqueado ? "erro" : "sucesso");

        } catch (error) {
            ocorreuErroNaAnalise = true;
            console.error(`Erro no diagnóstico LoS Pivô a Pivô:`, error);
            let msgErroDiagnostico = `⚠️ Erro ao diagnosticar visada`;
            if (distanciaFormatada !== "N/A" && distanciaFormatada !== "Erro no cálculo") {
                msgErroDiagnostico += ` entre ${window.losSourcePivot?.nome || 'Pivô Origem'} → ${window.losTargetPivot?.nome || 'Pivô Destino'} (Dist: ${distanciaFormatada})`;
            }
            msgErroDiagnostico += `: ${error.message || 'Erro desconhecido'}`;
            mostrarMensagem(msgErroDiagnostico, "erro");
        } finally {
            mostrarLoader(false);

            // Reseta para permitir nova seleção de origem e destino
            window.losSourcePivot = null;
            window.losTargetPivot = null;

            if (window.modoLoSPivotAPivot) { // Se o modo ainda estiver ativo
                setTimeout(() => {
                    if (window.modoLoSPivotAPivot) { // Verifica novamente, caso o usuário tenha desativado rapidamente
                        mostrarMensagem("Selecione um novo pivô de ORIGEM (com sinal/verde) ou desative o modo.", "info");
                    }
                }, ocorreuErroNaAnalise ? 700 : 1800); // Delay para não sobrepor a mensagem de erro/sucesso
            }
        }
    }
}

function handleToggleDistanciasPivos() {
    window.distanciasPivosVisiveis = !window.distanciasPivosVisiveis;
    const btn = document.getElementById('toggle-distancias-pivos');
    if (btn) {
        btn.classList.toggle('glass-button-active', window.distanciasPivosVisiveis);
        btn.title = window.distanciasPivosVisiveis ? "Esconder Distâncias dos Pivôs" : "Mostrar Distâncias dos Pivôs";
    }

    // A função window.togglePivoDistances é definida em drawing.js e atribuída a window lá.
    // Ela internamente chama drawPivos.
    if (typeof window.togglePivoDistances === 'function') {
        window.togglePivoDistances(window.distanciasPivosVisiveis);
    } else {
        console.error("Função togglePivoDistances não encontrada em drawing.js. Tentando fallback direto para drawPivos.");
        // Fallback caso togglePivoDistances não esteja disponível por algum motivo
        if (window.lastPivosDataDrawn && window.lastPivosDataDrawn.length > 0 && typeof drawPivos === 'function') {
            drawPivos(window.lastPivosDataDrawn, true); // true para useEdited, assumindo que as posições editadas são relevantes
            mostrarMensagem(`Distâncias dos pivôs ${window.distanciasPivosVisiveis ? 'exibidas' : 'ocultas'} (via fallback).`, 'sucesso');
        } else if (typeof drawPivos !== 'function'){
             console.error("Função drawPivos também não encontrada globalmente para o fallback.");
        } else {
            console.warn("Fallback para drawPivos não executado: lastPivosDataDrawn está vazio ou drawPivos não existe.");
        }
    }
}