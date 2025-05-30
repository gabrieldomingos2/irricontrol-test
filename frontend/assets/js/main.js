// --- Variáveis Globais de Estado (Anexadas a 'window') ---

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
window.antenaGlobal = null; // MODIFICADO: Garanta que seja window.antenaGlobal
window.distanciasPivosVisiveis = false; // Novo: controla a visibilidade das distâncias
window.lastPivosDataDrawn = []; // Novo: armazena os últimos dados de pivôs desenhados
window.currentProcessedKmzData = null; // Novo: armazena todos os dados do KMZ processado

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
    setupUIEventListeners();    // setupUIEventListeners deve ser chamado antes de setupMainActionListeners se ele adicionar elementos que main usa
    setupMainActionListeners();
    loadAndPopulateTemplates();
    reposicionarPaineisLaterais();
    lucide.createIcons();
    console.log("Aplicação Pronta.");
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

    // Novo listener para o botão de distâncias
    const toggleDistanciasBtn = document.getElementById('toggle-distancias-pivos');
    if (toggleDistanciasBtn) {
        toggleDistanciasBtn.addEventListener('click', handleToggleDistanciasPivos);
    } else {
        console.error("Botão 'toggle-distancias-pivos' não encontrado no DOM.");
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
        const data = await processKmz(formData); // Função de api.js
        console.log("✅ KMZ Processado:", data);
        window.currentProcessedKmzData = JSON.parse(JSON.stringify(data)); // Novo: armazena dados do KMZ

        if (data.erro) throw new Error(data.erro);

        handleResetClick(false); // Limpa o estado anterior antes de carregar novos dados

        // 🗼 Antena
        window.antenaGlobal = data.antena; // MODIFICADO: usar window.antenaGlobal
        if (window.antenaGlobal) { // MODIFICADO
            marcadorAntena = drawAntena(data.antena); // Função de drawing.js
            addAntenaAoPainel(window.antenaGlobal); // Função de drawing.js (ou ui.js)
        } else {
            console.warn("Dados da antena não encontrados no KMZ processado.");
            mostrarMensagem("⚠️ Antena principal não encontrada no KMZ.", "erro");
        }

        // 💧 Bombas e Círculos
        drawBombas(data.bombas || []); // Função de drawing.js
        window.ciclosGlobais = data.ciclos || []; // Armazena os ciclos globalmente
        drawCirculos(window.ciclosGlobais); // Função de drawing.js

        // 🎯 Desenha os pivôs assumindo que todos estão inicialmente fora de cobertura
        const pivosParaDesenhar = data.pivos || [];
        const pivosComStatusInicial = pivosParaDesenhar.map(p => ({
            ...p,
            fora: true // Assume inicialmente fora de cobertura
        }));
        window.lastPivosDataDrawn = JSON.parse(JSON.stringify(pivosComStatusInicial)); // Novo: armazena dados dos pivôs
        drawPivos(pivosComStatusInicial); // Função de drawing.js

        // 🔍 Ajusta o mapa para mostrar antena e pivôs
        if (window.antenaGlobal && pivosParaDesenhar.length > 0) { // MODIFICADO
            const boundsToFit = [
                [window.antenaGlobal.lat, window.antenaGlobal.lon] // MODIFICADO
            ];
            pivosParaDesenhar.forEach(p => boundsToFit.push([p.lat, p.lon]));
            map.fitBounds(boundsToFit, { padding: [50, 50] });
        } else if (window.antenaGlobal) { // MODIFICADO
            map.setView([window.antenaGlobal.lat, window.antenaGlobal.lon], 13); // MODIFICADO
        } else if (pivosParaDesenhar.length > 0) {
            const pivoBounds = pivosParaDesenhar.map(p => [p.lat, p.lon]);
            if (pivoBounds.length > 0) map.fitBounds(pivoBounds, { padding: [50, 50] });
        }

        atualizarPainelDados(); // Função de ui.js
        mostrarMensagem("✅ KMZ carregado com sucesso.", "sucesso"); // Função de ui.js

        document.getElementById("simular-btn").classList.remove("hidden");
        document.getElementById("painel-dados").classList.remove("hidden");
        document.getElementById("painel-repetidoras").classList.remove("hidden");
        reposicionarPaineisLaterais();

    } catch (error) {
        console.error("❌ Erro no submit do formulário:", error);
        mostrarMensagem(`❌ Erro ao carregar KMZ: ${error.message}`, "erro");
    } finally {
        mostrarLoader(false);
    }
}

async function handleSimulateClick() {
    if (!window.antenaGlobal) { // MODIFICADO
        mostrarMensagem("⚠️ Carregue um KMZ primeiro!", "erro");
        return;
    }

    mostrarLoader(true);

    try {
        templateSelecionado = document.getElementById('template-modelo').value;

        Object.entries(posicoesEditadas).forEach(([nome, novaPos]) => {
            if (pivotsMap[nome]) { pivotsMap[nome].setLatLng(novaPos); }
        });

        const pivos_atuais = Object.entries(pivotsMap).map(([nome, marcador]) => ({
            nome,
            lat: marcador.getLatLng().lat,
            lon: marcador.getLatLng().lng
            // O status 'fora' será determinado pelo backend na simulação
        }));

        const payload = { ...window.antenaGlobal, pivos_atuais, template: templateSelecionado }; // MODIFICADO
        const data = await simulateSignal(payload);
        console.log("✅ Simulação concluída:", data);

        if (data.erro) throw new Error(data.erro);

        overlaysVisiveis.forEach(overlay => {
            if (map.hasLayer(overlay)) map.removeLayer(overlay);
        });
        overlaysVisiveis = [];

        if (window.antenaGlobal.overlay && map.hasLayer(window.antenaGlobal.overlay)) { // MODIFICADO
            map.removeLayer(window.antenaGlobal.overlay); // MODIFICADO
        }

        window.antenaGlobal.overlay = drawImageOverlay(data.imagem_salva, data.bounds); // MODIFICADO
        window.antenaGlobal.bounds = data.bounds; // MODIFICADO

        window.lastPivosDataDrawn = JSON.parse(JSON.stringify(data.pivos)); // Novo: atualiza dados dos pivôs
        drawPivos(data.pivos, true); // 'true' para useEdited
        atualizarPainelDados();

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
    if (window.modoLoSPivotAPivot) return; // Evitar colocar marcador de repetidora ao clicar em pivô para LoS
    if (window.modoBuscaLocalRepetidora) return; // Evitar colocar marcador de repetidora ao clicar em pivô para busca

    window.coordenadaClicada = e.latlng;
    window.removePositioningMarker();

    window.marcadorPosicionamento = L.marker(window.coordenadaClicada, {
        icon: posicionamentoIcon,
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

    mostrarLoader(true);
    document.getElementById('painel-repetidora').classList.add('hidden');
    window.removePositioningMarker();

    const alturaAntena = parseFloat(document.getElementById("altura-antena-rep").value);
    const alturaReceiver = parseFloat(document.getElementById("altura-receiver-rep").value);
    templateSelecionado = document.getElementById('template-modelo').value;

    const id = idsDisponiveis.length > 0 ? idsDisponiveis.shift() : ++contadorRepetidoras;
    const nomeRep = `Repetidora ${id}`;

    const novaRepetidoraMarker = L.marker(window.coordenadaClicada, { icon: antenaIcon })
        .addTo(map);

    const labelWidth = (nomeRep.length * 7) + 10;
    const labelHeight = 20;

    const labelRepetidora = L.marker(window.coordenadaClicada, {
        icon: L.divIcon({
            className: 'label-pivo', // Reutiliza estilo
            html: nomeRep,
            iconSize: [labelWidth, labelHeight],
            iconAnchor: [labelWidth / 2, 45]
        }),
        labelType: 'repetidora' // Identifica como label de repetidora
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
        lon: window.coordenadaClicada.lng
    };
    repetidoras.push(repetidoraObj);

    const pivosParaSimulacaoRepetidora = window.lastPivosDataDrawn.map(p => ({ // Usa lastPivosDataDrawn
        nome: p.nome,
        lat: p.lat, // Usa a posição atual de lastPivosDataDrawn
        lon: p.lon  // Usa a posição atual de lastPivosDataDrawn
    }));


    const payload = {
        lat: window.coordenadaClicada.lat,
        lon: window.coordenadaClicada.lng,
        altura: alturaAntena,
        altura_receiver: alturaReceiver,
        pivos_atuais: pivosParaSimulacaoRepetidora,
        template: templateSelecionado
    };

    try {
        const data = await simulateManual(payload);
        console.log("Simulação Manual Concluída:", data);

        if (data.erro) throw new Error(data.erro);

        repetidoraObj.overlay = drawImageOverlay(data.imagem_salva, data.bounds, 1.0);
        addRepetidoraNoPainel(repetidoraObj); // Em drawing.js
        await reavaliarPivosViaAPI(); // Isso vai atualizar lastPivosDataDrawn e redesenhar

        mostrarMensagem(`📡 Repetidora ${id} adicionada e simulada.`, "sucesso");
        document.getElementById("painel-repetidoras").classList.remove("hidden");
        reposicionarPaineisLaterais();

    } catch (error) {
        console.error("Erro ao confirmar repetidora:", error);
        mostrarMensagem(`❌ Falha ao simular repetidora: ${error.message}`, "erro");
        map.removeLayer(novaRepetidoraMarker);
        map.removeLayer(labelRepetidora);
        marcadoresLegenda = marcadoresLegenda.filter(l => l !== labelRepetidora);
        repetidoras = repetidoras.filter(r => r.id !== id);
        if (!idsDisponiveis.includes(id)) idsDisponiveis.push(id);
        idsDisponiveis.sort((a, b) => a - b);
    } finally {
        mostrarLoader(false);
        window.coordenadaClicada = null;
        atualizarPainelDados();
    }
}

function handleBuscarLocaisRepetidoraActivation() {
    window.modoBuscaLocalRepetidora = !window.modoBuscaLocalRepetidora;
    const btn = document.getElementById('btn-buscar-locais-repetidora');
    btn.classList.toggle('glass-button-active', window.modoBuscaLocalRepetidora);

    if (window.modoBuscaLocalRepetidora) {
        mostrarMensagem("MODO BUSCA LOCAL REPETIDORA: Selecione um pivô SEM SINAL (vermelho) como alvo.", "sucesso");
        window.pivoAlvoParaLocalRepetidora = null;
        if (window.marcadorPosicionamento) removePositioningMarker();
        document.getElementById("painel-repetidora").classList.add("hidden");

        if (window.modoLoSPivotAPivot) {
            toggleLoSPivotAPivotMode();
        }
        if (window.modoEdicaoPivos) {
            const editarPivosBtn = document.getElementById("editar-pivos");
            if (editarPivosBtn.classList.contains('glass-button-active')) {
                togglePivoEditing();
            }
        }
        map.getContainer().style.cursor = 'crosshair';
    } else {
        mostrarMensagem("Modo 'Buscar Locais para Repetidora' desativado.", "sucesso");
        map.getContainer().style.cursor = '';
        // Limpar locais candidatos se o modo for desativado
        if (window.candidateRepeaterSitesLayerGroup) {
            window.candidateRepeaterSitesLayerGroup.clearLayers();
        }
    }
}

async function handlePivotSelectionForRepeaterSite(pivoData, pivoMarker) {
    if (!window.modoBuscaLocalRepetidora) return;

    if (pivoMarker.options.fillColor === 'green') {
        mostrarMensagem("ALVO: Selecione um pivô SEM SINAL (vermelho).", "erro");
        return;
    }

    window.pivoAlvoParaLocalRepetidora = {
        nome: pivoData.nome,
        lat: pivoMarker.getLatLng().lat,
        lon: pivoMarker.getLatLng().lng,
        altura_receiver: (window.antenaGlobal && window.antenaGlobal.altura_receiver) ? window.antenaGlobal.altura_receiver : 3 // MODIFICADO
    };

    mostrarMensagem(`Pivô alvo ${window.pivoAlvoParaLocalRepetidora.nome} selecionado. Buscando locais...`, "info");
    mostrarLoader(true);
    map.getContainer().style.cursor = 'wait';

    const activeOverlaysForSearch = [];
    const antenaCheckbox = document.querySelector("#antena-item input[type='checkbox']");

    if (window.antenaGlobal?.overlay && map.hasLayer(window.antenaGlobal.overlay) && (!antenaCheckbox || antenaCheckbox.checked)) { // MODIFICADO
        const b = window.antenaGlobal.overlay.getBounds(); // MODIFICADO
        activeOverlaysForSearch.push({
            id: 'antena_principal',
            imagem: window.antenaGlobal.overlay._url.replace(BACKEND_URL + '/', ''), // MODIFICADO
            bounds: [b.getSouth(), b.getWest(), b.getNorth(), b.getEast()]
        });
    }

    repetidoras.forEach(rep => {
        const repCheckbox = document.querySelector(`#rep-item-${rep.id} input[type='checkbox']`);
        if (rep.overlay && map.hasLayer(rep.overlay) && (!repCheckbox || repCheckbox.checked)) {
            const b = rep.overlay.getBounds();
            activeOverlaysForSearch.push({
                id: `repetidora_${rep.id}`,
                imagem: rep.overlay._url.replace(BACKEND_URL + '/', ''),
                bounds: [b.getSouth(), b.getWest(), b.getNorth(), b.getEast()]
            });
        }
    });

    if (activeOverlaysForSearch.length === 0) {
        mostrarMensagem("Nenhuma área de sinal (antena/repetidoras) ativa para basear a busca. Ative alguma cobertura.", "erro");
        mostrarLoader(false);
        map.getContainer().style.cursor = window.modoBuscaLocalRepetidora ? 'crosshair' : '';
        return;
    }

    try {
        const payload = {
            target_pivot_lat: window.pivoAlvoParaLocalRepetidora.lat,
            target_pivot_lon: window.pivoAlvoParaLocalRepetidora.lon,
            target_pivot_nome: window.pivoAlvoParaLocalRepetidora.nome,
            altura_antena_repetidora_proposta: parseFloat(document.getElementById("altura-antena-rep").value) || 5,
            altura_receiver_pivo: window.pivoAlvoParaLocalRepetidora.altura_receiver,
            active_overlays: activeOverlaysForSearch
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
    } finally {
        mostrarLoader(false);
        map.getContainer().style.cursor = window.modoBuscaLocalRepetidora ? 'crosshair' : '';
    }
}

function handleResetClick(showMessage = true) {
    console.log("🔄 Resetando aplicação...");
    clearMapLayers();

    window.antenaGlobal = null; // MODIFICADO
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

    // Reset das novas variáveis globais
    window.distanciasPivosVisiveis = false;
    window.lastPivosDataDrawn = [];
    window.currentProcessedKmzData = null;

    // Reseta a UI do botão de distâncias
    const btnDistancias = document.getElementById('toggle-distancias-pivos');
    if (btnDistancias) {
        btnDistancias.classList.remove('glass-button-active');
        btnDistancias.title = "Mostrar Distâncias dos Pivôs";
    }


    if (window.modoEdicaoPivos) {
        if (typeof togglePivoEditing === 'function' && document.getElementById("editar-pivos").classList.contains('glass-button-active')) {
            togglePivoEditing();
        }
        window.modoEdicaoPivos = false;
        const btnEditarReset = document.getElementById("editar-pivos");
        const btnEditarIconSpanReset = btnEditarReset.querySelector('.sidebar-icon');
        if (btnEditarIconSpanReset) {
             btnEditarIconSpanReset.style.webkitMaskImage = 'url(assets/images/pencil.svg)';
             btnEditarIconSpanReset.style.maskImage = 'url(assets/images/pencil.svg)';
        } else {
             btnEditarReset.innerHTML = `<i data-lucide="pencil" class="w-5 h-5"></i>`; // Fallback se o span não existir
             if (typeof lucide !== 'undefined') lucide.createIcons();
        }
        btnEditarReset.title = "Editar Pivôs";
        btnEditarReset.classList.remove('glass-button-active');
        document.getElementById("desfazer-edicao").classList.add("hidden");
    }

    if (window.modoLoSPivotAPivot) {
        if (typeof toggleLoSPivotAPivotMode === 'function' && document.getElementById('btn-los-pivot-a-pivot').classList.contains('glass-button-active')) {
            toggleLoSPivotAPivotMode();
        }
        window.modoLoSPivotAPivot = false;
        window.losSourcePivot = null;
        window.losTargetPivot = null;
        // document.getElementById('btn-los-pivot-a-pivot').classList.remove('glass-button-active'); // toggleLoSPivotAPivotMode já deve fazer isso
    }

    if (window.modoBuscaLocalRepetidora) {
        if (typeof handleBuscarLocaisRepetidoraActivation === 'function' && document.getElementById('btn-buscar-locais-repetidora').classList.contains('glass-button-active')) {
            handleBuscarLocaisRepetidoraActivation();
        }
        window.modoBuscaLocalRepetidora = false;
        window.pivoAlvoParaLocalRepetidora = null;
        // document.getElementById('btn-buscar-locais-repetidora').classList.remove('glass-button-active'); // handleBuscarLocaisRepetidoraActivation já deve fazer isso
    }

    if (map) {
        map.getContainer().style.cursor = '';
    }

    const btnSimular = document.getElementById("simular-btn");
    btnSimular.classList.add("hidden");
    btnSimular.disabled = false;
    btnSimular.classList.remove("opacity-50", "cursor-not-allowed");
    document.getElementById("btn-diagnostico").classList.add("hidden");

    const btnEditar = document.getElementById("editar-pivos");
    const btnEditarIconSpan = btnEditar.querySelector('.sidebar-icon');
    if (btnEditarIconSpan && !window.modoEdicaoPivos) {
        btnEditarIconSpan.style.webkitMaskImage = 'url(assets/images/pencil.svg)';
        btnEditarIconSpan.style.maskImage = 'url(assets/images/pencil.svg)';
        btnEditar.title = "Editar Pivôs";
        btnEditar.classList.remove('glass-button-active');
        document.getElementById("desfazer-edicao").classList.add("hidden");
    } else if (!window.modoEdicaoPivos && !btnEditarIconSpan) { // Fallback se o span não existir
        btnEditar.innerHTML = `<i data-lucide="pencil" class="w-5 h-5"></i>`;
        if (typeof lucide !== 'undefined') lucide.createIcons();
        btnEditar.title = "Editar Pivôs";
        btnEditar.classList.remove('glass-button-active');
        document.getElementById("desfazer-edicao").classList.add("hidden");
    }


    document.getElementById("lista-repetidoras").innerHTML = "";
    document.getElementById("painel-repetidora").classList.add("hidden");
    document.getElementById("painel-dados").classList.add("hidden");
    document.getElementById("painel-repetidoras").classList.add("hidden");

    const formElement = document.getElementById('formulario');
    if (formElement) {
        formElement.reset();
    }
    const nomeArquivoLabelElement = document.getElementById('nome-arquivo-label');
    if (nomeArquivoLabelElement) {
        nomeArquivoLabelElement.textContent = "Escolher Arquivo KMZ";
        nomeArquivoLabelElement.title = "Escolher Arquivo KMZ";
    }
    const rangeOpacidadeElement = document.getElementById("range-opacidade");
    if (rangeOpacidadeElement) {
        rangeOpacidadeElement.value = 1;
    }

    if (map) {
        map.setView([-15, -55], 5);
    }

    atualizarPainelDados();
    reposicionarPaineisLaterais();

    if (typeof toggleLegendas === 'function') {
        toggleLegendas(true); // Assume que true mostra as legendas
    }

    if (showMessage) mostrarMensagem("🔄 Aplicação resetada.", "sucesso");
}

async function handleDiagnosticoClick() {
    if (!window.antenaGlobal || Object.keys(pivotsMap).length === 0) { // MODIFICADO
        mostrarMensagem("⚠️ Rode o estudo de sinal primeiro!", "erro");
        return;
    }

    mostrarLoader(true);
    visadaLayerGroup.clearLayers();
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
                [window.antenaGlobal.lat, window.antenaGlobal.lon], // MODIFICADO
                [marcador.getLatLng().lat, marcador.getLatLng().lng]
            ],
            altura_antena: window.antenaGlobal.altura || 15, // MODIFICADO
            altura_receiver: window.antenaGlobal.altura_receiver || 3 // MODIFICADO
        };

        try {
            const data = await getElevationProfile(payload);
            drawDiagnostico(
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
    visadaVisivel = false; // Controla se a visada será visível inicialmente
    toggleVisada(); // Alterna para o estado desejado (pode precisar ajustar a lógica de toggleVisada)
}

function handleExportClick() {
    if (!window.antenaGlobal?.overlay || !window.antenaGlobal.bounds) { // MODIFICADO
        mostrarMensagem("⚠️ Rode a simulação principal primeiro para gerar a imagem!", "erro");
        return;
    }

    try {
        const latStr = formatCoordForFilename(window.antenaGlobal.lat); // MODIFICADO
        const lonStr = formatCoordForFilename(window.antenaGlobal.lon); // MODIFICADO
        templateSelecionado = document.getElementById('template-modelo').value;
        const template = templateSelecionado.toLowerCase();
        const nomeImagem = `sinal_${template}_${latStr}_${lonStr}.png`;
        const nomeBounds = `sinal_${template}_${latStr}_${lonStr}.json`;
        const url = getExportKmzUrl(nomeImagem, nomeBounds);
        window.open(url, '_blank');
        mostrarMensagem("📦 Preparando KMZ para download...", "sucesso");
    } catch (error) {
        console.error("Erro ao exportar KMZ:", error);
        mostrarMensagem(`❌ Erro ao exportar: ${error.message}`, "erro");
    }
}

async function reavaliarPivosViaAPI() {
    console.log("Reavaliando pivôs...");
    const pivosAtuaisParaReavaliacao = window.lastPivosDataDrawn.map(p => ({ // Usa lastPivosDataDrawn
        nome: p.nome,
        lat: p.lat,
        lon: p.lon
    }));

    if (pivosAtuaisParaReavaliacao.length === 0) {
        console.log("Nenhum pivô para reavaliar (lastPivosDataDrawn está vazio).");
        // Se não há pivôs em lastPivosDataDrawn, mas há no mapa (pivotsMap), poderia usar um fallback
        // Mas idealmente lastPivosDataDrawn deve estar sempre correto.
        return;
    }

    const overlays = [];
    const antenaCheckbox = document.querySelector("#antena-item input[type='checkbox']");
    if (window.antenaGlobal?.overlay && map.hasLayer(window.antenaGlobal.overlay) && (!antenaCheckbox || antenaCheckbox.checked)) { // MODIFICADO
        const b = window.antenaGlobal.overlay.getBounds(); // MODIFICADO
        overlays.push({
            imagem: window.antenaGlobal.overlay._url.replace(BACKEND_URL + '/', ''), // MODIFICADO
            bounds: [b.getSouth(), b.getWest(), b.getNorth(), b.getEast()]
        });
    }

    repetidoras.forEach(rep => {
        const repCheckbox = document.querySelector(`#rep-item-${rep.id} input[type='checkbox']`);
        if (rep.overlay && map.hasLayer(rep.overlay) && (!repCheckbox || repCheckbox.checked)) {
            const b = rep.overlay.getBounds();
            overlays.push({
                imagem: rep.overlay._url.replace(BACKEND_URL + '/', ''),
                bounds: [b.getSouth(), b.getWest(), b.getNorth(), b.getEast()]
            });
        }
    });


    if (overlays.length === 0 && pivosAtuaisParaReavaliacao.length > 0) { // Apenas se houver pivôs
        console.log("Nenhum overlay de sinal visível, marcando todos os pivôs como fora de cobertura.");
        const pivosFora = pivosAtuaisParaReavaliacao.map(p => ({ ...p, fora: true }));
        window.lastPivosDataDrawn = JSON.parse(JSON.stringify(pivosFora)); // Atualiza com status 'fora'
        drawPivos(pivosFora, true); // useEdited = true
        atualizarPainelDados();
        return;
    }
     if (pivosAtuaisParaReavaliacao.length === 0) { // Se não há pivôs, não faz nada
        console.log("Nenhum pivô para reavaliar.");
        return;
    }


    try {
        const data = await reevaluatePivots({ pivos: pivosAtuaisParaReavaliacao, overlays });
        if (data.pivos) {
            window.lastPivosDataDrawn = JSON.parse(JSON.stringify(data.pivos)); // Novo: atualiza dados dos pivôs
            drawPivos(data.pivos, true); // useEdited = true
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
    window.backupPosicoesPivos = {}; // Armazena { nome: LatLng }

    const tamanho = 18;
    const altura = 26;

    // Usa window.lastPivosDataDrawn para obter os dados dos pivôs, incluindo nome e posição atual
    window.lastPivosDataDrawn.forEach(pivoInfo => {
        const nome = pivoInfo.nome;
        const currentLatLng = L.latLng(pivoInfo.lat, pivoInfo.lon); // Posição atual do pivô
        const marcadorOriginal = pivotsMap[nome]; // O circleMarker original

        window.backupPosicoesPivos[nome] = currentLatLng;

        const editMarkerIcon = L.divIcon({
            className: 'pivo-edit-handle-custom-pin',
            html: `
            <svg viewBox="0 0 28 40" width="${tamanho}" height="${altura}" xmlns="http://www.w3.org/2000/svg">
                <path d="M14 0 C7.486 0 2 5.486 2 12.014 C2 20.014 14 40 14 40 C14 40 26 20.014 26 12.014 C26 5.486 20.514 0 14 0 Z
                M14 18 C10.686 18 8 15.314 8 12 C8 8.686 10.686 6 14 6 C17.314 6 20 8.686 20 12 C20 15.314 17.314 18 14 18 Z"
                fill="#FF3333" stroke="#660000" stroke-width="1"/>
            </svg>`,
            iconSize: [tamanho, altura],
            iconAnchor: [tamanho / 2, altura]
        });

        const editMarker = L.marker(currentLatLng, {
            draggable: true,
            icon: editMarkerIcon
        }).addTo(map);

        if (marcadorOriginal) {
            marcadorOriginal.editMarker = editMarker; // Associa ao circleMarker
             map.removeLayer(marcadorOriginal); // Remove o circleMarker temporariamente
        } else {
            console.warn(`Marcador original para ${nome} não encontrado em pivotsMap ao ativar edição.`);
            // Adiciona ao pivotsMap se não existir, para consistência, embora não deva acontecer
             pivotsMap[nome] = { editMarker: editMarker, getLatLng: () => editMarker.getLatLng(), options: { color: 'grey'} };
        }


        // A legenda é gerenciada por drawPivos. Ao arrastar, precisamos atualizar a posição da legenda.
        // No entanto, drawPivos limpa e recria legendas.
        // Melhor abordagem: ao final do drag, atualizar posicoesEditadas e depois chamar drawPivos.
        // Ou, mover a legenda associada se ela for um L.Marker separado.
        // A legenda (L.divIcon) é recriada por drawPivos.
        // Para o drag em tempo real, vamos esconder as legendas dos pivôs ou aceitar que não se movem em tempo real.
        // Simples: `posicoesEditadas` é atualizado no dragend.

        editMarker.on("drag", (e) => {
            // Poderia tentar mover a legenda aqui se ela fosse um objeto persistente e acessível
            // Mas drawPivos vai recriá-la.
        });

        editMarker.on("dragend", (e) => {
            const novaPos = e.target.getLatLng();
            posicoesEditadas[nome] = { lat: novaPos.lat, lng: novaPos.lng }; // Atualiza posições editadas

            // Atualiza a posição em lastPivosDataDrawn para que drawPivos use a correta
            const pivoEmLastData = window.lastPivosDataDrawn.find(p => p.nome === nome);
            if (pivoEmLastData) {
                pivoEmLastData.lat = novaPos.lat;
                pivoEmLastData.lon = novaPos.lng;
            }
            // Redesenha os pivôs para atualizar a legenda e o circleMarker (que foi removido)
            // A função drawPivos agora será responsável por desenhar o circleMarker na nova posição
            // e a legenda.
             if (typeof window.togglePivoDistances === 'function') { // Reutiliza para redesenhar
                window.togglePivoDistances(window.distanciasPivosVisiveis);
            }

            console.log(`📍 Pivô ${nome} movido para:`, novaPos);
        });

        editMarker.on("contextmenu", (e) => {
            L.DomEvent.stopPropagation(e);
            L.DomEvent.preventDefault(e);
            if (confirm(`❌ Tem certeza que deseja remover o pivô ${nome}?`)) {
                map.removeLayer(editMarker);

                // Remove dos dados principais
                window.lastPivosDataDrawn = window.lastPivosDataDrawn.filter(p => p.nome !== nome);
                window.currentProcessedKmzData.pivos = window.currentProcessedKmzData.pivos.filter(p => p.nome !== nome);


                delete pivotsMap[nome]; // Remove de pivotsMap (que armazena os circleMarkers)
                delete posicoesEditadas[nome];
                delete window.backupPosicoesPivos[nome];

                // Redesenha os pivôs restantes
                if (typeof window.togglePivoDistances === 'function') { // Reutiliza para redesenhar
                    window.togglePivoDistances(window.distanciasPivosVisiveis);
                }
                mostrarMensagem(`🗑️ Pivô ${nome} removido.`, "sucesso");
                atualizarPainelDados();
            }
        });
        // Não removemos o circleMarker aqui, drawPivos vai lidar com isso.
        // Em vez disso, os circleMarkers e suas legendas são limpos e recriados por drawPivos.
        // Mas os marcadores de edição (pinos) devem ser os únicos visíveis para os pivôs.
    });

    // Limpa os marcadores de pivôs (círculos e legendas) existentes, deixando apenas os pinos de edição
    marcadoresPivos.forEach(m => map.removeLayer(m));
    marcadoresPivos = [];
    marcadoresLegenda.filter(l => l.options.labelType === 'pivot').forEach(l => map.removeLayer(l));
    marcadoresLegenda = marcadoresLegenda.filter(l => l.options.labelType !== 'pivot');
    // Os circleMarkers em pivotsMap também não são mais necessários no modo de edição,
    // pois os pinos draggable os substituem.
    // Object.values(pivotsMap).forEach(m => { if(m && m.options && map.hasLayer(m)) map.removeLayer(m); });
    // pivotsMap ainda pode ser útil para referenciar os pinos de edição


    mostrarMensagem(
        "✏️ Modo de edição ativado. Arraste o pino vermelho ou clique com botão direito para remover.",
        "sucesso"
    );
}


function disablePivoEditingMode() {
    window.modoEdicaoPivos = false;
    console.log("Desativando modo de edição e salvando.");

    // Remove os marcadores de edição (pinos vermelhos)
    Object.values(pivotsMap).forEach(marcadorWrapper => { // pivotsMap pode agora conter o editMarker
        if (marcadorWrapper && marcadorWrapper.editMarker && map.hasLayer(marcadorWrapper.editMarker)) {
            map.removeLayer(marcadorWrapper.editMarker);
            // delete marcadorWrapper.editMarker; // O wrapper é o antigo circleMarker, que não existe mais
        }
    });
    // Se pivotsMap foi modificado para armazenar os pinos, precisa de ajuste.
    // Assumindo que os pinos foram adicionados ao mapa, mas pivotsMap ainda refere-se aos circleMarkers (que foram removidos).
    // Vamos iterar pelos pinos de edição que foram armazenados nos marcadores originais
     window.lastPivosDataDrawn.forEach(pivoInfo => {
        const marcadorOriginal = pivotsMap[pivoInfo.nome]; // Este é o wrapper do antigo circleMarker
        if (marcadorOriginal && marcadorOriginal.editMarker && map.hasLayer(marcadorOriginal.editMarker)) {
            map.removeLayer(marcadorOriginal.editMarker);
            delete marcadorOriginal.editMarker;
        }
    });


    // Os dados em window.lastPivosDataDrawn já devem ter as posições atualizadas pelo dragend.
    // O status 'fora' também deve estar lá.
    // Recalcular pivos_atuais com base em lastPivosDataDrawn para garantir consistência
    const pivos_atuais_para_desenhar = window.lastPivosDataDrawn.map(p => ({
        nome: p.nome,
        lat: p.lat,
        lon: p.lon,
        fora: p.fora, // Certifique-se que 'fora' está atualizado em lastPivosDataDrawn
        // Inclua outras propriedades do pivô se necessário para drawPivos
        ...(p.raio && { raio: p.raio }),
        ...(p.cor_original && { cor_original: p.cor_original })
    }));

    // Redesenha os pivôs (circleMarkers e legendas) com as posições salvas.
    // A função drawPivos usará as posições de pivos_atuais_para_desenhar.
    // O segundo argumento 'true' (useEdited) em drawPivos pode não ser estritamente necessário
    // se pivos_atuais_para_desenhar já contém as posições finais.
    drawPivos(pivos_atuais_para_desenhar, false); // false para useEdited, pois as posições já estão nos dados

    mostrarMensagem("💾 Posições salvas. Rode a simulação novamente se necessário.", "sucesso");
    window.backupPosicoesPivos = {}; // Limpa o backup
    posicoesEditadas = {}; // Limpa as edições explicitas, pois foram incorporadas em lastPivosDataDrawn
}


function undoPivoEdits() {
    console.log("Desfazendo edições.");
    Object.entries(window.backupPosicoesPivos).forEach(([nome, posicaoOriginalLatLng]) => {
        const pivoEmLastData = window.lastPivosDataDrawn.find(p => p.nome === nome);
        if (pivoEmLastData) {
            pivoEmLastData.lat = posicaoOriginalLatLng.lat;
            pivoEmLastData.lon = posicaoOriginalLatLng.lng;
        }
        // Remove da lista de posições editadas explicitamente
        delete posicoesEditadas[nome];
    });

    // Redesenha os pivôs com as posições restauradas
    // disablePivoEditingMode já remove os pinos de edição e chama drawPivos
    // Mas queremos redesenhar enquanto ainda estamos no modo de edição (com os pinos)
    // Ou, se o "desfazer" também sair do modo de edição:
    // disablePivoEditingMode(); // Isso chamaria drawPivos

    // Se o Desfazer for DENTRO do modo de edição:
    // Precisamos mover os pinos de edição para as posições originais
     Object.entries(window.backupPosicoesPivos).forEach(([nome, posicaoOriginalLatLng]) => {
        const marcadorOriginal = pivotsMap[nome]; // Wrapper do antigo circleMarker
        if (marcadorOriginal && marcadorOriginal.editMarker) {
            marcadorOriginal.editMarker.setLatLng(posicaoOriginalLatLng);
        }
    });
    // E então redesenhar os pivôs para atualizar suas legendas, se drawPivos não for chamado por disablePivoEditingMode
    if (window.modoEdicaoPivos) { // Se ainda estiver no modo de edição
        // A lógica de enablePivoEditingMode remove os circleMarkers.
        // Apenas movendo os pinos é suficiente. As legendas são problema.
        // Solução mais simples: Desfazer SAIRÁ do modo de edição.
        if (typeof togglePivoEditing === 'function') {
            togglePivoEditing(); // Sai do modo de edição, o que chamará disablePivoEditingMode -> drawPivos
        }
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

        // Desativar outros modos
        if (window.modoEdicaoPivos) togglePivoEditing();
        if (window.modoBuscaLocalRepetidora) handleBuscarLocaisRepetidoraActivation();
        map.getContainer().style.cursor = 'help';


    } else {
        mostrarMensagem("Modo 'Diagnóstico Pivô a Pivô' desativado.", "sucesso");
        window.losSourcePivot = null;
        window.losTargetPivot = null;
        map.getContainer().style.cursor = '';
    }
}

async function handleLoSPivotClick(pivoData, pivoMarker) {
    if (!window.modoLoSPivotAPivot) return;

    const isGoodSignalPivot = pivoMarker.options.fillColor === 'green';
    const pivotLatlng = pivoMarker.getLatLng();
    const defaultPivotHeight = window.antenaGlobal?.altura_receiver || 3; // MODIFICADO

    if (!window.losSourcePivot) {
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
    } else {
        if (pivoData.nome === window.losSourcePivot.nome) {
            mostrarMensagem(`ORIGEM: ${pivoData.nome} já é a origem. Selecione o pivô de DESTINO.`, "info");
            return;
        }

        if (isGoodSignalPivot) {
            const confirmaMudanca = confirm(`Você já selecionou ${window.losSourcePivot.nome} como origem. Deseja alterar a origem para ${pivoData.nome}?`);
            if (confirmaMudanca) {
                window.losSourcePivot = {
                    nome: pivoData.nome,
                    latlng: pivotLatlng,
                    altura: defaultPivotHeight
                };
                mostrarMensagem(`ORIGEM ALTERADA para: ${pivoData.nome}. Selecione o pivô de DESTINO (sem sinal/vermelho).`, "sucesso");
            }
            return;
        }

        window.losTargetPivot = {
            nome: pivoData.nome,
            latlng: pivotLatlng,
            altura: defaultPivotHeight
        };

        mostrarLoader(true);
        try {
            const payload = {
                pontos: [
                    [window.losSourcePivot.latlng.lat, window.losSourcePivot.latlng.lng],
                    [window.losTargetPivot.latlng.lat, window.losTargetPivot.latlng.lng]
                ],
                altura_antena: window.losSourcePivot.altura,
                altura_receiver: window.losTargetPivot.altura
            };

            const resultadoApi = await getElevationProfile(payload);
            drawDiagnostico(
                payload.pontos[0],
                payload.pontos[1],
                resultadoApi.bloqueio,
                resultadoApi.ponto_mais_alto,
                `${window.losSourcePivot.nome} → ${window.losTargetPivot.nome}`
            );
            mostrarMensagem(`Visada entre ${window.losSourcePivot.nome} e ${window.losTargetPivot.nome} analisada.`, "sucesso");

            window.losSourcePivot = null;
            window.losTargetPivot = null;
            if (window.modoLoSPivotAPivot) {
                mostrarMensagem("Selecione um novo pivô de ORIGEM (com sinal/verde) ou desative o modo.", "info");
            }
        } catch (error) {
            console.error(`Erro no diagnóstico LoS Pivô a Pivô:`, error);
            mostrarMensagem(`⚠️ Erro ao diagnosticar visada: ${error.message}`, "erro");
            window.losSourcePivot = null;
            window.losTargetPivot = null;
        } finally {
            mostrarLoader(false);
        }
    }
}


// --- NOVA FUNÇÃO PARA CONTROLAR VISIBILIDADE DAS DISTÂNCIAS ---
function handleToggleDistanciasPivos() {
    window.distanciasPivosVisiveis = !window.distanciasPivosVisiveis;
    const btn = document.getElementById('toggle-distancias-pivos');
    if (btn) {
        btn.classList.toggle('glass-button-active', window.distanciasPivosVisiveis);
        btn.title = window.distanciasPivosVisiveis ? "Esconder Distâncias dos Pivôs" : "Mostrar Distâncias dos Pivôs";
    }


    if (typeof window.togglePivoDistances === 'function') {
        window.togglePivoDistances(window.distanciasPivosVisiveis);
    } else {
        console.error("Função togglePivoDistances não encontrada em drawing.js. Certifique-se que drawing.js foi carregado.");
        // Como fallback, se a função não existir, tenta chamar drawPivos diretamente se houver dados.
        // Isso só funcionará se drawPivos em drawing.js já estiver modificado para ler window.distanciasPivosVisiveis.
        if (window.lastPivosDataDrawn && window.lastPivosDataDrawn.length > 0 && typeof drawPivos === 'function') {
            console.warn("Fallback: Chamando drawPivos diretamente para atualizar distâncias.");
            drawPivos(window.lastPivosDataDrawn, true); // true para useEdited
             mostrarMensagem(`Distâncias dos pivôs ${window.distanciasPivosVisiveis ? 'exibidas' : 'ocultas'} (via fallback).`, 'sucesso');
        } else if (typeof drawPivos !== 'function'){
             console.error("Função drawPivos também não encontrada globalmente.");
        }
    }
}