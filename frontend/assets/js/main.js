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
        const data = await processKmz(formData);
        console.log("✅ KMZ Processado:", data);
        window.currentProcessedKmzData = JSON.parse(JSON.stringify(data));

        if (data.erro) throw new Error(data.erro);

        handleResetClick(false);

        window.antenaGlobal = data.antena;
        if (window.antenaGlobal) {
            marcadorAntena = drawAntena(data.antena);
            addAntenaAoPainel(window.antenaGlobal);
        } else {
            console.warn("Dados da antena não encontrados no KMZ processado.");
            mostrarMensagem("⚠️ Antena principal não encontrada no KMZ.", "erro");
        }

        drawBombas(data.bombas || []);
        window.ciclosGlobais = data.ciclos || [];
        drawCirculos(window.ciclosGlobais);

        const pivosParaDesenhar = data.pivos || [];
        const pivosComStatusInicial = pivosParaDesenhar.map(p => ({
            ...p,
            fora: true
        }));
        window.lastPivosDataDrawn = JSON.parse(JSON.stringify(pivosComStatusInicial));
        drawPivos(pivosComStatusInicial);

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

        atualizarPainelDados();
        mostrarMensagem("✅ KMZ carregado com sucesso.", "sucesso");

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
    if (!window.antenaGlobal) {
        mostrarMensagem("⚠️ Carregue um KMZ primeiro!", "erro");
        return;
    }

    mostrarLoader(true);

    try {
        templateSelecionado = document.getElementById('template-modelo').value;

        Object.entries(posicoesEditadas).forEach(([nome, novaPos]) => {
            if (pivotsMap[nome]) { pivotsMap[nome].setLatLng(novaPos); }
        });

        const pivos_atuais = window.lastPivosDataDrawn.map(p => ({ 
            nome: p.nome,
            lat: p.lat,
            lon: p.lon
        }));


        const payload = { ...window.antenaGlobal, pivos_atuais, template: templateSelecionado };
        const data = await simulateSignal(payload);
        console.log("✅ Simulação concluída:", data);

        if (data.erro) throw new Error(data.erro);

        overlaysVisiveis.forEach(overlay => {
            if (map.hasLayer(overlay)) map.removeLayer(overlay);
        });
        overlaysVisiveis = [];

        if (window.antenaGlobal.overlay && map.hasLayer(window.antenaGlobal.overlay)) {
            map.removeLayer(window.antenaGlobal.overlay);
        }

        window.antenaGlobal.overlay = drawImageOverlay(data.imagem_salva, data.bounds);
        window.antenaGlobal.bounds = data.bounds;

        window.lastPivosDataDrawn = JSON.parse(JSON.stringify(data.pivos));
        drawPivos(data.pivos, true);
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
    if (window.modoLoSPivotAPivot) return;
    if (window.modoBuscaLocalRepetidora) return;

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
            className: 'label-pivo',
            html: nomeRep,
            iconSize: [labelWidth, labelHeight],
            iconAnchor: [labelWidth / 2, 45]
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
        lon: window.coordenadaClicada.lng
    };
    repetidoras.push(repetidoraObj);

    const pivosParaSimulacaoRepetidora = window.lastPivosDataDrawn.map(p => ({
        nome: p.nome,
        lat: p.lat,
        lon: p.lon
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
        addRepetidoraNoPainel(repetidoraObj);
        await reavaliarPivosViaAPI();

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

        if (window.modoLoSPivotAPivot) toggleLoSPivotAPivotMode();
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
        altura_receiver: (window.antenaGlobal && window.antenaGlobal.altura_receiver) ? window.antenaGlobal.altura_receiver : 3
    };

    mostrarMensagem(`Pivô alvo ${window.pivoAlvoParaLocalRepetidora.nome} selecionado. Buscando locais...`, "info");
    mostrarLoader(true);
    map.getContainer().style.cursor = 'wait';

    const activeOverlaysForSearch = [];
    const antenaCheckbox = document.querySelector("#antena-item input[type='checkbox']");

    if (window.antenaGlobal?.overlay && map.hasLayer(window.antenaGlobal.overlay) && (!antenaCheckbox || antenaCheckbox.checked)) {
        const b = window.antenaGlobal.overlay.getBounds();
        activeOverlaysForSearch.push({
            id: 'antena_principal',
            imagem: window.antenaGlobal.overlay._url.replace(BACKEND_URL + '/', ''),
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
             btnEditarReset.innerHTML = `<i data-lucide="pencil" class="w-5 h-5"></i>`;
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
    }

    if (window.modoBuscaLocalRepetidora) {
        if (typeof handleBuscarLocaisRepetidoraActivation === 'function' && document.getElementById('btn-buscar-locais-repetidora').classList.contains('glass-button-active')) {
            handleBuscarLocaisRepetidoraActivation();
        }
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
    if (!window.modoEdicaoPivos) {
        const btnEditarIconSpan = btnEditar.querySelector('.sidebar-icon');
        if (btnEditarIconSpan) {
            btnEditarIconSpan.style.webkitMaskImage = 'url(assets/images/pencil.svg)';
            btnEditarIconSpan.style.maskImage = 'url(assets/images/pencil.svg)';
        } else {
            btnEditar.innerHTML = `<i data-lucide="pencil" class="w-5 h-5"></i>`;
            if (typeof lucide !== 'undefined') lucide.createIcons();
        }
        btnEditar.title = "Editar Pivôs";
        btnEditar.classList.remove('glass-button-active');
        document.getElementById("desfazer-edicao").classList.add("hidden");
    }

    document.getElementById("lista-repetidoras").innerHTML = "";
    document.getElementById("painel-repetidora").classList.add("hidden");
    document.getElementById("painel-dados").classList.add("hidden");
    document.getElementById("painel-repetidoras").classList.add("hidden");

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

    atualizarPainelDados();
    reposicionarPaineisLaterais();

    if (typeof toggleLegendas === 'function') toggleLegendas(true);

    if (showMessage) mostrarMensagem("🔄 Aplicação resetada.", "sucesso");
}

async function handleDiagnosticoClick() {
    if (!window.antenaGlobal || Object.keys(pivotsMap).length === 0) {
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
                [window.antenaGlobal.lat, window.antenaGlobal.lon],
                [marcador.getLatLng().lat, marcador.getLatLng().lng]
            ],
            altura_antena: window.antenaGlobal.altura || 15,
            altura_receiver: window.antenaGlobal.altura_receiver || 3
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
}

function handleExportClick() {
    if (!window.antenaGlobal?.overlay || !window.antenaGlobal.bounds) {
        mostrarMensagem("⚠️ Rode a simulação principal primeiro para gerar a imagem!", "erro");
        return;
    }

    try {
        const latStr = formatCoordForFilename(window.antenaGlobal.lat);
        const lonStr = formatCoordForFilename(window.antenaGlobal.lon);
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
    const pivosAtuaisParaReavaliacao = window.lastPivosDataDrawn.map(p => ({
        nome: p.nome,
        lat: p.lat,
        lon: p.lon
    }));

    if (pivosAtuaisParaReavaliacao.length === 0) {
        console.log("Nenhum pivô para reavaliar (lastPivosDataDrawn está vazio).");
        if (Object.keys(pivotsMap).length === 0) return;
    }

    const overlays = [];
    const antenaCheckbox = document.querySelector("#antena-item input[type='checkbox']");
    if (window.antenaGlobal?.overlay && map.hasLayer(window.antenaGlobal.overlay) && (!antenaCheckbox || antenaCheckbox.checked)) {
        const b = window.antenaGlobal.overlay.getBounds();
        overlays.push({
            imagem: window.antenaGlobal.overlay._url.replace(BACKEND_URL + '/', ''),
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

    if (pivosAtuaisParaReavaliacao.length === 0 && Object.keys(pivotsMap).length > 0) {
        console.warn("Reavaliando pivôs: lastPivosDataDrawn estava vazio, usando pivotsMap.");
        const pivosDoMapa = Object.entries(pivotsMap).map(([nome, marcador]) => ({
            nome,
            lat: marcador.getLatLng().lat,
            lon: marcador.getLatLng().lng
        }));
        if (pivosDoMapa.length === 0) {
            console.log("Nenhum pivô no mapa para reavaliar.");
            return;
        }
        window.lastPivosDataDrawn = JSON.parse(JSON.stringify(pivosDoMapa.map(p => ({...p, fora: true}))));
        pivosAtuaisParaReavaliacao.push(...pivosDoMapa);
    } else if (pivosAtuaisParaReavaliacao.length === 0) {
        console.log("Nenhum pivô para reavaliar.");
        return;
    }

    if (overlays.length === 0) {
        console.log("Nenhum overlay de sinal visível, marcando todos os pivôs como fora de cobertura.");
        const pivosFora = pivosAtuaisParaReavaliacao.map(p => ({ ...p, fora: true }));
        window.lastPivosDataDrawn = JSON.parse(JSON.stringify(pivosFora));
        drawPivos(pivosFora, true);
        atualizarPainelDados();
        return;
    }

    try {
        const data = await reevaluatePivots({ pivos: pivosAtuaisParaReavaliacao, overlays });
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
    window.backupPosicoesPivos = {};

    const tamanho = 18;
    const altura = 26;

    marcadoresPivos.forEach(m => map.removeLayer(m));
    marcadoresPivos = [];
    marcadoresLegenda.filter(l => l.options.labelType === 'pivot').forEach(l => map.hasLayer(l) && map.removeLayer(l));
    marcadoresLegenda = marcadoresLegenda.filter(l => l.options.labelType !== 'pivot');

    Object.keys(pivotsMap).forEach(nomePivo => {
        if (pivotsMap[nomePivo] && map.hasLayer(pivotsMap[nomePivo])) {
            map.removeLayer(pivotsMap[nomePivo]);
        }
    });


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

        const editMarker = L.marker(currentLatLng, {
            draggable: true,
            icon: editMarkerIcon
        }).addTo(map);

        pivotsMap[nome] = editMarker;

        editMarker.on("dragend", (e) => {
            const novaPos = e.target.getLatLng();
            posicoesEditadas[nome] = { lat: novaPos.lat, lng: novaPos.lng };

            const pivoEmLastData = window.lastPivosDataDrawn.find(p => p.nome === nome);
            if (pivoEmLastData) {
                pivoEmLastData.lat = novaPos.lat;
                pivoEmLastData.lon = novaPos.lng;
            }
            console.log(`📍 Pivô ${nome} movido para:`, novaPos);
        });

        editMarker.on("contextmenu", (e) => {
            L.DomEvent.stopPropagation(e);
            L.DomEvent.preventDefault(e);
            if (confirm(`❌ Tem certeza que deseja remover o pivô ${nome}?`)) {
                map.removeLayer(editMarker);
                window.lastPivosDataDrawn = window.lastPivosDataDrawn.filter(p => p.nome !== nome);
                if (window.currentProcessedKmzData && window.currentProcessedKmzData.pivos) {
                     window.currentProcessedKmzData.pivos = window.currentProcessedKmzData.pivos.filter(p => p.nome !== nome);
                }
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
    console.log("Desativando modo de edição e salvando.");

    Object.values(pivotsMap).forEach(editMarker => {
        if (editMarker && map.hasLayer(editMarker)) {
            map.removeLayer(editMarker);
        }
    });

    const pivosParaRedesenhar = window.lastPivosDataDrawn.map(p => ({
        ...p
    }));

    drawPivos(pivosParaRedesenhar, false);

    mostrarMensagem("💾 Posições salvas. Rode a simulação novamente para atualizar a cobertura.", "sucesso");
    window.backupPosicoesPivos = {};
    posicoesEditadas = {};
}

function undoPivoEdits() {
    console.log("Desfazendo edições.");
    Object.entries(window.backupPosicoesPivos).forEach(([nome, posicaoOriginalLatLng]) => {
        const pivoEmLastData = window.lastPivosDataDrawn.find(p => p.nome === nome);
        if (pivoEmLastData) {
            pivoEmLastData.lat = posicaoOriginalLatLng.lat;
            pivoEmLastData.lon = posicaoOriginalLatLng.lng;
        }
        const editMarker = pivotsMap[nome];
        if (editMarker && map.hasLayer(editMarker)) {
            editMarker.setLatLng(posicaoOriginalLatLng);
        }
        delete posicoesEditadas[nome];
    });

    if (typeof togglePivoEditing === 'function') {
        togglePivoEditing();
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

        if (window.modoEdicaoPivos && typeof togglePivoEditing === 'function') togglePivoEditing();
        if (window.modoBuscaLocalRepetidora && typeof handleBuscarLocaisRepetidoraActivation === 'function') handleBuscarLocaisRepetidoraActivation();
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
    const defaultPivotHeight = window.antenaGlobal?.altura_receiver || 3;

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
            const confirmaMudanca = confirm(`Você já selecionou ${window.losSourcePivot.nome} como origem. Deseja alterar a origem para ${pivoData.nome}?`);
            if (confirmaMudanca) {
                window.losSourcePivot = {
                    nome: pivoData.nome,
                    latlng: pivotLatlng,
                    altura: defaultPivotHeight
                };
                window.losTargetPivot = null; // Reseta o alvo ao mudar a origem
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

            const resultadoApi = await getElevationProfile(payload);
            console.log("[DEBUG LoS] Resultado API:", resultadoApi);

            // Ajuste para determinar 'estaBloqueado' com base na estrutura real de 'resultadoApi.bloqueio'
            // Seu log anterior mostrava 'resultadoApi.bloqueio' como um objeto com 'diff'.
            const estaBloqueado = resultadoApi.bloqueio && typeof resultadoApi.bloqueio.diff === 'number' && resultadoApi.bloqueio.diff > 0;

            drawDiagnostico(
                payload.pontos[0],
                payload.pontos[1],
                resultadoApi.bloqueio, // Passa o objeto de bloqueio inteiro
                resultadoApi.ponto_mais_alto,
                `${window.losSourcePivot.nome} → ${window.losTargetPivot.nome}`,
                distanciaFormatada // Passando a distância total formatada
            );

            let mensagemVisada = `Visada ${window.losSourcePivot.nome} → ${window.losTargetPivot.nome} (Dist: ${distanciaFormatada})`;
            if (estaBloqueado) {
                mensagemVisada += ` ⛔ Bloqueada.`;
            } else if (estaBloqueado === false) { // Se não está bloqueado (diff <= 0 ou bloqueio é null/undefined)
                mensagemVisada += ` ✅ Livre.`;
            } else {
                // Se 'estaBloqueado' não for nem true nem false (ex: resultadoApi.bloqueio é um objeto mas diff não indica bloqueio claro)
                mensagemVisada += ` (Status de bloqueio incerto).`;
                console.warn("[DEBUG LoS] Status de bloqueio não determinado claramente como true/false:", resultadoApi.bloqueio);
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
            msgErroDiagnostico += `: ${error.message}`;
            mostrarMensagem(msgErroDiagnostico, "erro");
        } finally {
            mostrarLoader(false);

            window.losSourcePivot = null;
            window.losTargetPivot = null;

            if (window.modoLoSPivotAPivot) {
                setTimeout(() => {
                    if (window.modoLoSPivotAPivot) {
                        mostrarMensagem("Selecione um novo pivô de ORIGEM (com sinal/verde) ou desative o modo.", "info");
                    }
                }, ocorreuErroNaAnalise ? 700 : 1800);
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

    if (typeof window.togglePivoDistances === 'function') {
        window.togglePivoDistances(window.distanciasPivosVisiveis);
    } else {
        console.error("Função togglePivoDistances não encontrada em drawing.js.");
        if (window.lastPivosDataDrawn && window.lastPivosDataDrawn.length > 0 && typeof drawPivos === 'function') {
            console.warn("Fallback: Chamando drawPivos diretamente para atualizar distâncias.");
            drawPivos(window.lastPivosDataDrawn, true);
            mostrarMensagem(`Distâncias dos pivôs ${window.distanciasPivosVisiveis ? 'exibidas' : 'ocultas'} (via fallback).`, 'sucesso');
        } else if (typeof drawPivos !== 'function'){
             console.error("Função drawPivos também não encontrada globalmente.");
        }
    }
}