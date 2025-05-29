// --- Variáveis Globais de Estado (Anexadas a 'window') ---

window.modoEdicaoPivos = false;
window.coordenadaClicada = null;
window.marcadorPosicionamento = null;
window.backupPosicoesPivos = {}; // <<< ADICIONADO AQUI TAMBÉM
window.modoLoSPivotAPivot = false; // Controla o novo modo de diagnóstico
window.losSourcePivot = null;      // Armazena o pivô de origem selecionado {nome, latlng, altura}
window.losTargetPivot = null;    // Armazena o pivô de destino selecionado {nome, latlng, altura}
window.modoBuscaLocalRepetidora = false; // Controla o modo de busca por locais de repetidora
window.pivoAlvoParaLocalRepetidora = null; // Armazena o pivô alvo para a busca

let antenaGlobal = null;
let marcadorAntena = null;
let marcadoresPivos = [];
let circulosPivos = [];
let pivotsMap = {};
let repetidoras = [];
let contadorRepetidoras = 0;
let idsDisponiveis = [];
let legendasAtivas = true;
let marcadoresLegenda = []; // <<< Será usado para Antena, Bombas, etc., mas não mais para pivôs.
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

        if (data.erro) throw new Error(data.erro);

        handleResetClick(false);

        // 🗼 Antena
        antenaGlobal = data.antena;
        marcadorAntena = drawAntena(data.antena);
        addAntenaAoPainel(antenaGlobal);

        // 💧 Bombas e Círculos
        drawBombas(data.bombas);
        drawCirculos(data.ciclos);

        // 🎯 Desenha os pivôs assumindo que todos estão inicialmente fora de cobertura
        const pivosComStatusInicial = data.pivos.map(p => ({
            ...p,
            fora: true
        }));
        drawPivos(pivosComStatusInicial);

        // 🔍 Ajusta o mapa
        map.fitBounds(
            [
                [antenaGlobal.lat, antenaGlobal.lon],
                ...data.pivos.map(p => [p.lat, p.lon])
            ],
            { padding: [50, 50] }
        );

        atualizarPainelDados();
        mostrarMensagem("✅ KMZ carregado com sucesso.", "sucesso");

        // 🔥 Ativa os botões e paineis
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
    if (!antenaGlobal) {
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
        }));

        const payload = { ...antenaGlobal, pivos_atuais, template: templateSelecionado };
        const data = await simulateSignal(payload);
        console.log("✅ Simulação concluída:", data);

        if (data.erro) throw new Error(data.erro);

        overlaysVisiveis.forEach(overlay => {
            if (map.hasLayer(overlay)) map.removeLayer(overlay);
        });
        overlaysVisiveis = [];

        if (antenaGlobal.overlay && map.hasLayer(antenaGlobal.overlay)) {
            map.removeLayer(antenaGlobal.overlay);
        }

        antenaGlobal.overlay = drawImageOverlay(data.imagem_salva, data.bounds);
        antenaGlobal.bounds = data.bounds;

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
        })
    }).addTo(map);
    marcadoresLegenda.push(labelRepetidora); // Adiciona legenda da repetidora

    const repetidoraObj = {
        id,
        marker: novaRepetidoraMarker,
        overlay: null,
        label: labelRepetidora, // Guarda o label
        altura: alturaAntena,
        altura_receiver: alturaReceiver,
        lat: window.coordenadaClicada.lat,
        lon: window.coordenadaClicada.lng
    };
    repetidoras.push(repetidoraObj);

    const payload = {
        lat: window.coordenadaClicada.lat,
        lon: window.coordenadaClicada.lng,
        altura: alturaAntena,
        altura_receiver: alturaReceiver,
        pivos_atuais: Object.entries(pivotsMap).map(([nome, marcador]) => ({
            nome,
            lat: marcador.getLatLng().lat,
            lon: marcador.getLatLng().lng
        })),
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
    const btn = document.getElementById('btn-buscar-locais-repetidora'); // Verifique o ID
    btn.classList.toggle('glass-button-active', window.modoBuscaLocalRepetidora);

    if (window.modoBuscaLocalRepetidora) {
        mostrarMensagem("MODO BUSCA LOCAL REPETIDORA: Selecione um pivô SEM SINAL (vermelho) como alvo.", "sucesso");
        window.pivoAlvoParaLocalRepetidora = null;
        if (window.marcadorPosicionamento) removePositioningMarker();
        document.getElementById("painel-repetidora").classList.add("hidden");

        // Desativa outros modos interativos para evitar conflitos
        if (window.modoLoSPivotAPivot) {
            toggleLoSPivotAPivotMode(); // Assume que esta função alterna e atualiza a UI
        }
        if (window.modoEdicaoPivos) {
            // Chama a função que desativa o modo de edição (que você já tem em ui.js: togglePivoEditing)
            // Mas precisamos garantir que ela DESATIVE se estiver ativa.
            // A função togglePivoEditing em ui.js já tem lógica para isso, mas é chamada por um clique no botão.
            // Para garantir, podemos fazer:
            const editarPivosBtn = document.getElementById("editar-pivos");
            if (editarPivosBtn.classList.contains('glass-button-active')) { // Se o modo edição estiver ativo
                togglePivoEditing(); // Chamada da função em ui.js que também atualiza o botão.
            }
        }
        map.getContainer().style.cursor = 'crosshair'; // Muda o cursor para indicar seleção

    } else {
        mostrarMensagem("Modo 'Buscar Locais para Repetidora' desativado.", "sucesso");
        map.getContainer().style.cursor = ''; // Restaura o cursor padrão
    }
}

// 👇 ADICIONE A FUNÇÃO DE SELEÇÃO DE PIVÔ E CHAMADA À API AQUI 👇
// main.js

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
        altura_receiver: (antenaGlobal && antenaGlobal.altura_receiver) ? antenaGlobal.altura_receiver : 3
    };

    mostrarMensagem(`Pivô alvo ${window.pivoAlvoParaLocalRepetidora.nome} selecionado. Buscando locais...`, "info");
    mostrarLoader(true);
    map.getContainer().style.cursor = 'wait';

    // --- NOVO: Coleta de overlays ativos ---
    const activeOverlaysForSearch = [];
    const antenaCheckbox = document.querySelector("#antena-item input[type='checkbox']");

    // Adiciona overlay da antena principal se estiver visível e marcado
    if (antenaGlobal?.overlay && map.hasLayer(antenaGlobal.overlay) && (!antenaCheckbox || antenaCheckbox.checked)) {
        const b = antenaGlobal.overlay.getBounds();
        activeOverlaysForSearch.push({
            id: 'antena_principal', // ID opcional para depuração no backend
            imagem: antenaGlobal.overlay._url.replace(BACKEND_URL + '/', ''), // Caminho relativo
            bounds: [b.getSouth(), b.getWest(), b.getNorth(), b.getEast()]
        });
    }

    // Adiciona overlays das repetidoras ativas
    repetidoras.forEach(rep => {
        const repCheckbox = document.querySelector(`#rep-item-${rep.id} input[type='checkbox']`);
        if (rep.overlay && map.hasLayer(rep.overlay) && (!repCheckbox || repCheckbox.checked)) {
            const b = rep.overlay.getBounds();
            activeOverlaysForSearch.push({
                id: `repetidora_${rep.id}`, // ID opcional
                imagem: rep.overlay._url.replace(BACKEND_URL + '/', ''), // Caminho relativo
                bounds: [b.getSouth(), b.getWest(), b.getNorth(), b.getEast()]
            });
        }
    });

    if (activeOverlaysForSearch.length === 0) {
        mostrarMensagem("Nenhuma área de sinal (antena/repetidoras) ativa para basear a busca. Ative alguma cobertura.", "erro");
        mostrarLoader(false);
        map.getContainer().style.cursor = window.modoBuscaLocalRepetidora ? 'crosshair' : ''; // Restaura cursor apropriado
        return;
    }
    // --- FIM NOVO ---

    try {
        const payload = {
            target_pivot_lat: window.pivoAlvoParaLocalRepetidora.lat,
            target_pivot_lon: window.pivoAlvoParaLocalRepetidora.lon,
            target_pivot_nome: window.pivoAlvoParaLocalRepetidora.nome,
            // search_radius_m: 2000, // REMOVIDO ou opcional: não mais o principal driver da área de busca
            altura_antena_repetidora_proposta: parseFloat(document.getElementById("altura-antena-rep").value) || 5,
            altura_receiver_pivo: window.pivoAlvoParaLocalRepetidora.altura_receiver,
            active_overlays: activeOverlaysForSearch // ALTERADO: Passa os overlays coletados
        };

        const resultados = await findHighPointsForRepeater(payload); // Em api.js

        if (window.candidateRepeaterSitesLayerGroup) {
            window.candidateRepeaterSitesLayerGroup.clearLayers();
        } else {
            console.warn("candidateRepeaterSitesLayerGroup não definido.");
        }

        if (resultados && resultados.candidate_sites && resultados.candidate_sites.length > 0) {
            drawCandidateRepeaterSites(resultados.candidate_sites, window.pivoAlvoParaLocalRepetidora); // Em drawing.js
            mostrarMensagem(`Encontrados ${resultados.candidate_sites.length} locais candidatos. Clique em um para simular.`, "sucesso");
        } else {
            mostrarMensagem("Nenhum local promissor encontrado nas áreas de cobertura existentes.", "info");
        }

    } catch (error) {
        console.error("Erro ao buscar locais para repetidora:", error);
        // A função findHighPointsForRepeater em api.js já deve mostrar uma mensagem de erro apropriada.
    } finally {
        mostrarLoader(false);
        map.getContainer().style.cursor = window.modoBuscaLocalRepetidora ? 'crosshair' : ''; // Restaura cursor apropriado
    }
}


function handleResetClick(showMessage = true) {
    console.log("🔄 Resetando aplicação...");
    clearMapLayers(); // Esta função deve estar em drawing.js e agora limpará o candidateRepeaterSitesLayerGroup também

    // Reset de variáveis globais de estado
    antenaGlobal = null;
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
    
    // --- NOVO: Resetar explicitamente os modos interativos ---
    if (window.modoEdicaoPivos) {
        // Se a função togglePivoEditing também lida com a UI do botão, chamá-la para desativar
        // Assumindo que togglePivoEditing está em ui.js e altera window.modoEdicaoPivos
        if (typeof togglePivoEditing === 'function' && document.getElementById("editar-pivos").classList.contains('glass-button-active')) {
            togglePivoEditing(); // Isso deve reverter o botão e o estado
        } else {
             window.modoEdicaoPivos = false; // Fallback
             const btnEditar = document.getElementById("editar-pivos");
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
    }

    if (window.modoLoSPivotAPivot) {
        // Se a função toggleLoSPivotAPivotMode também lida com a UI do botão, chamá-la para desativar
        if (typeof toggleLoSPivotAPivotMode === 'function' && document.getElementById('btn-los-pivot-a-pivot').classList.contains('glass-button-active')) {
            toggleLoSPivotAPivotMode();
        } else {
            window.modoLoSPivotAPivot = false; // Fallback
            window.losSourcePivot = null;
            window.losTargetPivot = null;
            document.getElementById('btn-los-pivot-a-pivot').classList.remove('glass-button-active');
        }
    }

    if (window.modoBuscaLocalRepetidora) {
        // Se a função handleBuscarLocaisRepetidoraActivation também lida com a UI do botão, chamá-la para desativar
        if (typeof handleBuscarLocaisRepetidoraActivation === 'function' && document.getElementById('btn-buscar-locais-repetidora').classList.contains('glass-button-active')) {
            // A função original alterna, então chamamos se estiver ativo para desativar
             handleBuscarLocaisRepetidoraActivation();
        } else {
            window.modoBuscaLocalRepetidora = false; // Fallback
            window.pivoAlvoParaLocalRepetidora = null;
            document.getElementById('btn-buscar-locais-repetidora').classList.remove('glass-button-active');
        }
    }
    map.getContainer().style.cursor = ''; // Restaura o cursor padrão do mapa
    // --- FIM NOVO ---

    const btnSimular = document.getElementById("simular-btn");
    btnSimular.classList.add("hidden");
    btnSimular.disabled = false;
    btnSimular.classList.remove("opacity-50", "cursor-not-allowed");
    document.getElementById("btn-diagnostico").classList.add("hidden");

    // Reset do botão de edição (já estava bom, mas mantido para clareza)
    const btnEditar = document.getElementById("editar-pivos");
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

    document.getElementById("lista-repetidoras").innerHTML = "";
    document.getElementById("painel-repetidora").classList.add("hidden");
    document.getElementById("painel-dados").classList.add("hidden");
    document.getElementById("painel-repetidoras").classList.add("hidden");

    document.getElementById('formulario').reset();
    document.getElementById('nome-arquivo-label').textContent = "Escolher Arquivo KMZ";
    document.getElementById("range-opacidade").value = 1;

    map.setView([-15, -55], 5);

    atualizarPainelDados();
    reposicionarPaineisLaterais();

    if (typeof toggleLegendas === 'function') {
        toggleLegendas(true); // Garante que legendas sejam mostradas (ou estado padrão)
    } else {
        console.error("Função toggleLegendas não está definida globalmente ou não foi carregada.");
    }

    if (showMessage) mostrarMensagem("🔄 Aplicação resetada.", "sucesso");
}

async function handleDiagnosticoClick() {
    if (!antenaGlobal || Object.keys(pivotsMap).length === 0) {
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
            [antenaGlobal.lat, antenaGlobal.lon],
            [marcador.getLatLng().lat, marcador.getLatLng().lng]
        ],
        altura_antena: antenaGlobal.altura || 15,
        altura_receiver: antenaGlobal.altura_receiver || 3
    };

    try {
        const data = await getElevationProfile(payload);
        drawDiagnostico(
            payload.pontos[0],
            payload.pontos[1],
            data.bloqueio,
            data.ponto_mais_alto, // 👈 ESSENCIAL AGORA!
            nome
        );
    } catch (error) {
        console.error(`Erro no diagnóstico do pivô ${nome}:`, error);
        mostrarMensagem(`⚠️ Erro ao diagnosticar ${nome}.`, "erro");
    }
}


    lucide.createIcons();
    mostrarLoader(false);
    mostrarMensagem("🔍 Diagnóstico de visada concluído.", "sucesso");
    visadaVisivel = false;
    toggleVisada();
}

function handleExportClick() {
    if (!antenaGlobal?.overlay || !antenaGlobal.bounds) {
        mostrarMensagem("⚠️ Rode a simulação principal primeiro para gerar a imagem!", "erro");
        return;
    }

    try {
        const latStr = formatCoordForFilename(antenaGlobal.lat);
        const lonStr = formatCoordForFilename(antenaGlobal.lon);
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
    const pivos = Object.entries(pivotsMap).map(([nome, marcador]) => ({
        nome,
        lat: marcador.getLatLng().lat,
        lon: marcador.getLatLng().lng
    }));

    const overlays = [];
    const antenaCheckbox = document.querySelector("#antena-item input[type='checkbox']");
    if (antenaGlobal?.overlay && map.hasLayer(antenaGlobal.overlay) && (!antenaCheckbox || antenaCheckbox.checked)) {
        const b = antenaGlobal.overlay.getBounds();
        overlays.push({
            imagem: antenaGlobal.overlay._url.replace(BACKEND_URL + '/', ''),
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

    if (pivos.length === 0) { console.log("Nenhum pivô para reavaliar."); return; }

    if (overlays.length === 0) {
        console.log("Nenhum overlay de sinal visível, marcando todos os pivôs como fora de cobertura.");
        drawPivos(pivos.map(p => ({ ...p, fora: true })), true);
        atualizarPainelDados();
        return;
    }

    try {
        const data = await reevaluatePivots({ pivos, overlays });
        if (data.pivos) {
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

    const tamanho = 18;   // Largura do ícone
    const altura = 26;    // Altura do ícone

    Object.entries(pivotsMap).forEach(([nome, marcador]) => {
        window.backupPosicoesPivos[nome] = marcador.getLatLng();

        const editMarkerIcon = L.divIcon({
            className: 'pivo-edit-handle-custom-pin',
            html: `
            <svg viewBox="0 0 28 40" width="${tamanho}" height="${altura}" xmlns="http://www.w3.org/2000/svg">
                <path d="M14 0 C7.486 0 2 5.486 2 12.014 C2 20.014 14 40 14 40 C14 40 26 20.014 26 12.014 C26 5.486 20.514 0 14 0 Z 
                M14 18 C10.686 18 8 15.314 8 12 C8 8.686 10.686 6 14 6 C17.314 6 20 8.686 20 12 C20 15.314 17.314 18 14 18 Z"
                fill="#FF3333" stroke="#660000" stroke-width="1"/>
            </svg>`,
            iconSize: [tamanho, altura],
            iconAnchor: [tamanho / 2, altura] // Ponta inferior central
        });

        const editMarker = L.marker(marcador.getLatLng(), {
            draggable: true,
            icon: editMarkerIcon
        }).addTo(map);

        marcador.editMarker = editMarker;

        const label = marcadoresLegenda.find(lbl => {
            return lbl?.getLatLng()?.equals(marcador.getLatLng()) &&
                   lbl?.options?.icon?.options?.html?.includes(nome);
        });

        editMarker.on("drag", (e) => {
            const novaPos = e.target.getLatLng();
            if (label) label.setLatLng(novaPos);
            marcador.setLatLng(novaPos);
        });

        editMarker.on("dragend", (e) => {
            const novaPos = e.target.getLatLng();
            posicoesEditadas[nome] = novaPos;
            if (label) label.setLatLng(novaPos);
            marcador.setLatLng(novaPos);
            console.log(`📍 Pivô ${nome} movido para:`, novaPos);
        });

        editMarker.on("contextmenu", (e) => {
            L.DomEvent.stopPropagation(e);
            L.DomEvent.preventDefault(e);
            if (confirm(`❌ Tem certeza que deseja remover o pivô ${nome}?`)) {
                map.removeLayer(editMarker);
                if (pivotsMap[nome] && map.hasLayer(pivotsMap[nome])) {
                    map.removeLayer(pivotsMap[nome]);
                }
                if (label && map.hasLayer(label)) {
                    map.removeLayer(label);
                    marcadoresLegenda = marcadoresLegenda.filter(l => l !== label);
                }
                delete pivotsMap[nome];
                delete posicoesEditadas[nome];
                delete window.backupPosicoesPivos[nome];
                marcadoresPivos = marcadoresPivos.filter(m => m !== marcador);
                mostrarMensagem(`🗑️ Pivô ${nome} removido.`, "sucesso");
                atualizarPainelDados();
            }
        });

        map.removeLayer(marcador);
    });

    mostrarMensagem(
        "✏️ Modo de edição ativado. Arraste o pino vermelho ou clique com botão direito para remover.",
        "sucesso"
    );
}

// --- ALTERADO: Função disablePivoEditingMode ---
function disablePivoEditingMode() {
    window.modoEdicaoPivos = false;
    console.log("Desativando modo de edição e salvando.");

    // Coleta os dados atuais dos pivôs (posição e status)
    const pivos_atuais = Object.entries(pivotsMap).map(([nome, marcador]) => {
        const currentMarker = marcador.editMarker || marcador; // Pega o marcador de edição ou o original
        const pos = currentMarker.getLatLng();
        // Determina o status 'fora'. Se não tem editMarker, usa o original.
        // Se tem editMarker, precisamos saber qual era o status ANTES de editar
        // OU, idealmente, o 'marcador' (circleMarker) deveria manter seu status (cor).
        // Como removemos o original, temos que confiar no backup ou recalcular.
        // A Abordagem mais simples é: ao sair da edição, recalcular tudo.
        // Mas por agora, vamos usar a posição atualizada e manter o status antigo
        // ou assumir um status padrão antes de redesenhar.
        // **** A MELHOR ABORDAGEM É REDESENHAR ****
        return {
            nome: nome,
            lat: pos.lat,
            lon: pos.lng,
            // Precisamos da cor/status. Se o 'marcador' ainda existir, podemos usar.
            // Se não, teremos que buscar. Por segurança, vamos apenas pegar lat/lon.
            fora: marcador.options.color === 'red' // Tenta pegar a cor do marcador original
        };
    });

     // Remove apenas os marcadores de edição
     Object.values(pivotsMap).forEach(marcador => {
        if (marcador.editMarker) {
            map.removeLayer(marcador.editMarker);
            delete marcador.editMarker;
        }
    });

    // Chama drawPivos para redesenhar TUDO com as novas posições
    // e readicionar TODOS os listeners corretamente.
    drawPivos(pivos_atuais, true);

    mostrarMensagem("💾 Posições salvas. Rode a simulação novamente se necessário.", "sucesso");
    window.backupPosicoesPivos = {}; // <<< Usa window.
}
// --- FIM DA ALTERAÇÃO ---


function undoPivoEdits() {
    console.log("Desfazendo edições.");
    Object.entries(window.backupPosicoesPivos).forEach(([nome, posicaoOriginal]) => { // <<< Usa window.
        const marcador = pivotsMap[nome];
        // const label = marcadoresLegenda.find(lbl => lbl.options.icon.options.html.includes(nome)); // Label não existe mais como marcador
        if (marcador && marcador.editMarker) {
            marcador.editMarker.setLatLng(posicaoOriginal);
            // if (label) label.setLatLng(posicaoOriginal); // Não precisa mais
        }
    });
    posicoesEditadas = {};
    mostrarMensagem("↩️ Edições desfeitas.", "sucesso");
}

function toggleLoSPivotAPivotMode() {
    window.modoLoSPivotAPivot = !window.modoLoSPivotAPivot;
    const btn = document.getElementById('btn-los-pivot-a-pivot');
    btn.classList.toggle('glass-button-active', window.modoLoSPivotAPivot); // Feedback visual

    if (window.modoLoSPivotAPivot) {
        mostrarMensagem("MODO DIAGNÓSTICO PIVÔ A PIVÔ: Selecione o pivô de ORIGEM (com sinal/verde).", "sucesso");
        // Desativa outros modos se necessário (ex: posicionamento de repetidora)
        if (window.marcadorPosicionamento) removePositioningMarker();
        document.getElementById("painel-repetidora").classList.add("hidden");
        window.losSourcePivot = null; // Reseta a seleção anterior ao (re)entrar no modo
        window.losTargetPivot = null;
    } else {
        mostrarMensagem("Modo 'Diagnóstico Pivô a Pivô' desativado.", "sucesso");
        window.losSourcePivot = null;
        window.losTargetPivot = null;
    }
    // Poderia adicionar mudança de cursor aqui: document.body.style.cursor = window.modoLoSPivotAPivot ? 'crosshair' : 'default';
}

async function handleLoSPivotClick(pivoData, pivoMarker) {
    if (!window.modoLoSPivotAPivot) return;

    const isGoodSignalPivot = pivoMarker.options.fillColor === 'green'; // Ou !== 'red'
    const pivotLatlng = pivoMarker.getLatLng();
    const defaultPivotHeight = antenaGlobal?.altura_receiver || 3; // Altura padrão do receptor/transmissor do pivô

    if (!window.losSourcePivot) { // Fase 1: Selecionando o Pivô de Origem
        if (!isGoodSignalPivot) {
            mostrarMensagem("ORIGEM: Selecione um pivô COM SINAL (verde).", "erro");
            return;
        }
        window.losSourcePivot = {
            nome: pivoData.nome,
            latlng: pivotLatlng,
            altura: defaultPivotHeight // Altura da antena do pivô de origem
        };
        mostrarMensagem(`ORIGEM: ${pivoData.nome} selecionado. Agora selecione o pivô de DESTINO (sem sinal/vermelho).`, "sucesso");
        // Visualmente destacar o pivô de origem (opcional, ex: mudar borda, adicionar ícone temporário)

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
                mostrarMensagem(`ORIGEM ALTERADA para: ${pivoData.nome}. Selecione o pivô de DESTINO (sem sinal/vermelho).`, "sucesso");
            }
            return;
        }

        // Se chegou aqui, é um pivô vermelho (destino)
        window.losTargetPivot = {
            nome: pivoData.nome,
            latlng: pivotLatlng,
            altura: defaultPivotHeight // Altura do receptor do pivô de destino
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

            const resultadoApi = await getElevationProfile(payload); // de api.js

            // Limpa apenas as linhas de diagnóstico pivô a pivô anteriores se quiser
            // ou pode deixar acumular e usar o botão #btn-visada para limpar/mostrar todas juntas.
            // visadaLayerGroup.clearLayers(); // Cuidado: Isso limpa o diagnóstico da antena principal também.

            drawDiagnostico( // de drawing.js
                payload.pontos[0],
                payload.pontos[1],
                resultadoApi.bloqueio,
                resultadoApi.ponto_mais_alto,
                `${window.losSourcePivot.nome} → ${window.losTargetPivot.nome}` // Nome da linha
            );
            mostrarMensagem(`Visada entre ${window.losSourcePivot.nome} e ${window.losTargetPivot.nome} analisada.`, "sucesso");

            // Resetar seleção para permitir nova análise
            window.losSourcePivot = null;
            window.losTargetPivot = null;
            // Poderia sair do modo automaticamente ou permitir múltiplas análises:
            // toggleLoSPivotAPivotMode(); // Descomente para sair do modo após uma análise
            // Se não sair do modo, o próximo clique em pivô verde será nova origem.
             if (window.modoLoSPivotAPivot) { // Se ainda no modo, pedir nova origem
                 mostrarMensagem("Selecione um novo pivô de ORIGEM (com sinal/verde) ou desative o modo.", "info");
             }


        } catch (error) {
            console.error(`Erro no diagnóstico LoS Pivô a Pivô:`, error);
            mostrarMensagem(`⚠️ Erro ao diagnosticar visada: ${error.message}`, "erro");
            // Resetar seleção em caso de erro
            window.losSourcePivot = null;
            window.losTargetPivot = null;
        } finally {
            mostrarLoader(false);
        }
    }
}

