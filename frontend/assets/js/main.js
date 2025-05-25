// --- Variáveis Globais de Estado ---

let antenaGlobal = null;
let marcadorAntena = null;
let marcadorPosicionamento = null;
let marcadoresPivos = [];
let circulosPivos = [];
let pivotsMap = {}; // Mapeia nome do pivô para seu marcador L.circleMarker
let coordenadaClicada = null;
let repetidoras = [];
let contadorRepetidoras = 0;
let idsDisponiveis = []; // IDs de repetidoras removidas para reuso
let legendasAtivas = true;
let marcadoresLegenda = [];
let marcadoresBombas = [];
let posicoesEditadas = {}; // Guarda { nomePivo: L.LatLng }
let overlaysVisiveis = []; // Guarda os L.ImageOverlay para controle de opacidade
let templateSelecionado = "";
let linhasDiagnostico = [];
let marcadoresBloqueio = [];
// As vars modoEdicaoPivos e backupPosicoesPivos estão em ui.js, mas poderiam estar aqui.

// --- Inicialização ---

// Garante que o código só roda depois que o HTML foi totalmente carregado
document.addEventListener("DOMContentLoaded", () => {
    console.log("DOM Carregado. Iniciando Aplicação...");
    initMap(); // Inicializa o mapa (de map.js)
    setupUIEventListeners(); // Configura listeners da UI (de ui.js)
    setupMainActionListeners(); // Configura listeners de ações principais (deste arquivo)
    loadAndPopulateTemplates(); // Carrega templates (de ui.js)
    reposicionarPaineisLaterais(); // Ajusta painéis iniciais
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

    // Listener de clique no mapa (para adicionar repetidoras)
    map.on("click", handleMapClick);
}

// --- Handlers de Ações Principais ---

/**
 * Lida com o envio do formulário de upload KMZ.
 * @param {Event} e - O evento de submit.
 */
async function handleFormSubmit(e) {
    e.preventDefault(); // Impede o recarregamento da página
    const fileInput = document.getElementById('arquivo');
    if (!fileInput.files || fileInput.files.length === 0) {
        mostrarMensagem("Por favor, selecione um arquivo KMZ.", "erro");
        return;
    }

    mostrarLoader(true);
    const formData = new FormData();
    formData.append("file", fileInput.files[0]);

    try {
        const data = await processKmz(formData); // Chama api.js
        console.log("KMZ Processado:", data);

        if (data.erro) {
            throw new Error(data.erro);
        }

        // Limpa mapa antes de adicionar novos dados (exceto camada base)
        handleResetClick(false); // Reset 'suave' sem mensagem

        antenaGlobal = data.antena;

        marcadorAntena = drawAntena(data.antena); // Chama drawing.js
        drawPivos(data.pivos); // Chama drawing.js
        drawBombas(data.bombas); // Chama drawing.js
        drawCirculos(data.ciclos); // Chama drawing.js

        // Adiciona antena ao painel de repetidoras/torres
        addAntenaAoPainel(antenaGlobal); // Chama drawing.js

        map.fitBounds([[antenaGlobal.lat, antenaGlobal.lon], ...data.pivos.map(p => [p.lat, p.lon])], { padding: [50, 50] });

        atualizarPainelDados(); // Chama ui.js
        mostrarMensagem("✅ KMZ carregado com sucesso.", "sucesso");
        document.getElementById("simular-btn").classList.remove("hidden");
        document.getElementById("painel-dados").classList.remove("hidden");
        document.getElementById("painel-repetidoras").classList.remove("hidden");
        reposicionarPaineisLaterais();


    } catch (error) {
        console.error("Erro no submit do formulário:", error);
        mostrarMensagem(`❌ Erro ao carregar KMZ: ${error.message}`, "erro");
    } finally {
        mostrarLoader(false);
    }
}

/**
 * Lida com o clique no botão "Rodar Estudo de Sinal".
 */
async function handleSimulateClick() {
    if (!antenaGlobal) {
        mostrarMensagem("⚠️ Carregue um KMZ primeiro!", "erro");
        return;
    }

    mostrarLoader(true);

    // Garante que pega o template certo
    templateSelecionado = document.getElementById('template-modelo').value;

    // Aplica posições editadas, se houver
    Object.entries(posicoesEditadas).forEach(([nome, novaPos]) => {
        if (pivotsMap[nome]) {
            pivotsMap[nome].setLatLng(novaPos);
        }
    });

    const pivos_atuais = Object.entries(pivotsMap).map(([nome, marcador]) => ({
        nome,
        lat: marcador.getLatLng().lat,
        lon: marcador.getLatLng().lng
    }));

    const payload = {
        ...antenaGlobal,
        pivos_atuais,
        template: templateSelecionado
    };

    try {
        const data = await simulateSignal(payload); // Chama api.js
        console.log("Simulação Concluída:", data);

        if (data.erro) throw new Error(data.erro);

        // Remove overlays antigos
        overlaysVisiveis.forEach(o => map.hasLayer(o) && map.removeLayer(o));
        overlaysVisiveis = [];
        if (antenaGlobal.overlay) map.hasLayer(antenaGlobal.overlay) && map.removeLayer(antenaGlobal.overlay);


        // Adiciona novo overlay
        antenaGlobal.overlay = drawImageOverlay(data.imagem_salva, data.bounds); // Chama drawing.js
        antenaGlobal.bounds = data.bounds; // Salva bounds para exportar

        // Redesenha pivôs com status e posições (possivelmente editadas)
        drawPivos(data.pivos, true); // Chama drawing.js, usando posições editadas

        map.fitBounds(antenaGlobal.overlay.getBounds(), { padding: [30, 30] });

        atualizarPainelDados(); // Chama ui.js
        mostrarMensagem("📡 Estudo de sinal concluído.", "sucesso");
        document.getElementById("btn-diagnostico").classList.remove("hidden");
        // Desativa o botão para evitar re-simulação sem reset
        const btnSimular = document.getElementById("simular-btn");
        btnSimular.disabled = true;
        btnSimular.classList.add("opacity-50", "cursor-not-allowed");

    } catch (error) {
        console.error("Erro ao simular sinal:", error);
        mostrarMensagem(`❌ Falha na simulação: ${error.message}`, "erro");
    } finally {
        mostrarLoader(false);
    }
}

/**
 * Lida com o clique no mapa para adicionar repetidora.
 * @param {L.LeafletMouseEvent} e - O evento de clique do Leaflet.
 */
function handleMapClick(e) {
    // Não faz nada se estiver em modo de edição
    if (modoEdicaoPivos) return;

    coordenadaClicada = e.latlng;

    // Remove marcador antigo se houver
    removePositioningMarker();

    // Adiciona novo marcador de posicionamento
    marcadorPosicionamento = L.marker(coordenadaClicada, {
        icon: posicionamentoIcon,
        interactive: false,
        opacity: 0.7,
        zIndexOffset: 1000 // Garante que fica visível
    }).addTo(map);

    // Mostra e posiciona o painel de configuração
    const painel = document.getElementById("painel-repetidora");
    painel.classList.remove("hidden");

    // Opcional: Posicionar perto do clique (mais complexo)
    // Por enquanto, ele aparece onde está no HTML (canto esquerdo).
}

/**
 * Lida com o clique no botão "Confirmar Repetidora".
 */
async function handleConfirmRepetidoraClick() {
    if (!coordenadaClicada) {
        mostrarMensagem("⚠️ Clique no mapa primeiro para definir a posição!", "erro");
        return;
    }

    mostrarLoader(true);
    document.getElementById('painel-repetidora').classList.add('hidden');
    removePositioningMarker();

    const alturaAntena = parseFloat(document.getElementById("altura-antena-rep").value);
    const alturaReceiver = parseFloat(document.getElementById("altura-receiver-rep").value);
    templateSelecionado = document.getElementById('template-modelo').value; // Garante o template atual

    const id = idsDisponiveis.length > 0 ? idsDisponiveis.shift() : ++contadorRepetidoras;

    const novaRepetidoraMarker = L.marker(coordenadaClicada, { icon: antenaIcon })
        .addTo(map)
        .bindPopup(`<div class="popup-glass">📡 Repetidora ${id}</div>`);

    const labelRepetidora = L.marker(coordenadaClicada, {
        icon: L.divIcon({
            className: 'label-pivo',
            html: `Repetidora ${id}`,
            iconSize: [80, 20],
            iconAnchor: [40, 45]
        })
    }).addTo(map);
    marcadoresLegenda.push(labelRepetidora);

    const repetidoraObj = {
        id,
        marker: novaRepetidoraMarker,
        overlay: null,
        label: labelRepetidora,
        altura: alturaAntena,
        altura_receiver: alturaReceiver,
        lat: coordenadaClicada.lat,
        lon: coordenadaClicada.lng
    };
    repetidoras.push(repetidoraObj);

    const payload = {
        lat: coordenadaClicada.lat,
        lon: coordenadaClicada.lng,
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
        const data = await simulateManual(payload); // Chama api.js
        console.log("Simulação Manual Concluída:", data);

        if (data.erro) throw new Error(data.erro);

        // Adiciona overlay da repetidora
        repetidoraObj.overlay = drawImageOverlay(data.imagem_salva, data.bounds, rangeOpacidade.value); // Usa opacidade atual

        // Adiciona ao painel
        addRepetidoraNoPainel(repetidoraObj); // Chama drawing.js (ou ui.js se preferir)

        // Reavalia os pivôs agora com a nova cobertura
        await reavaliarPivosViaAPI();

        mostrarMensagem(`📡 Repetidora ${id} adicionada e simulada.`, "sucesso");
        document.getElementById("painel-repetidoras").classList.remove("hidden");
        reposicionarPaineisLaterais();

    } catch (error) {
        console.error("Erro ao confirmar repetidora:", error);
        mostrarMensagem(`❌ Falha ao simular repetidora: ${error.message}`, "erro");
        // Remove a repetidora se a API falhou
        map.removeLayer(novaRepetidoraMarker);
        map.removeLayer(labelRepetidora);
        repetidoras = repetidoras.filter(r => r.id !== id);
        idsDisponiveis.push(id);
    } finally {
        mostrarLoader(false);
        coordenadaClicada = null; // Limpa a coordenada
        atualizarPainelDados();
    }
}


/**
 * Lida com o clique no botão "Resetar".
 * @param {boolean} [showMessage=true] - Mostrar mensagem de reset.
 */
function handleResetClick(showMessage = true) {
    console.log("🔄 Resetando aplicação...");
    clearMapLayers(); // Chama drawing.js

    // Reseta variáveis globais
    antenaGlobal = null;
    marcadorAntena = null;
    marcadorPosicionamento = null;
    marcadoresPivos = [];
    circulosPivos = [];
    pivotsMap = {};
    coordenadaClicada = null;
    repetidoras = [];
    contadorRepetidoras = 0;
    idsDisponiveis = [];
    legendasAtivas = true;
    marcadoresLegenda = [];
    marcadoresBombas = [];
    posicoesEditadas = {};
    backupPosicoesPivos = {};
    overlaysVisiveis = [];
    linhasDiagnostico = [];
    marcadoresBloqueio = [];
    modoEdicaoPivos = false;

    // Reseta UI
    document.getElementById("simular-btn").classList.add("hidden");
    const btnSimular = document.getElementById("simular-btn");
    btnSimular.disabled = false;
    btnSimular.classList.remove("opacity-50", "cursor-not-allowed");
    document.getElementById("btn-diagnostico").classList.add("hidden");

    document.getElementById("lista-repetidoras").innerHTML = "";
    document.getElementById("painel-repetidora").classList.add("hidden");
    document.getElementById("painel-dados").classList.add("hidden");
    document.getElementById("painel-repetidoras").classList.add("hidden");
    document.getElementById("painel-opacidade").classList.add("hidden");

    const btnEditar = document.getElementById("editar-pivos");
    btnEditar.innerHTML = "✏️";
    btnEditar.classList.remove('bg-yellow-600', 'hover:bg-yellow-700');
    document.getElementById("desfazer-edicao").classList.add("hidden");


    document.getElementById('formulario').reset(); // Limpa o formulário
    nomeArquivoLabel.textContent = "Escolher Arquivo KMZ"; // Reseta label
    rangeOpacidade.value = 1; // Reseta opacidade

    map.setView([-15, -55], 5); // Volta ao zoom inicial
    if (showMessage) mostrarMensagem("🔄 Aplicação resetada.", "sucesso");
    atualizarPainelDados(); // Limpa o painel
    reposicionarPaineisLaterais();
}

/**
 * Lida com o clique no botão "Diagnóstico de Visada".
 */
async function handleDiagnosticoClick() {
    if (!antenaGlobal || Object.keys(pivotsMap).length === 0) {
        mostrarMensagem("⚠️ Rode o estudo de sinal primeiro!", "erro");
        return;
    }

    mostrarLoader(true);
    visadaLayerGroup.clearLayers(); // Limpa visadas antigas
    linhasDiagnostico = [];
    marcadoresBloqueio = [];

    const pivosVermelhos = Object.entries(pivotsMap).filter(([_, m]) => m.options.fillColor === 'red');

    if(pivosVermelhos.length === 0) {
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
            const data = await getElevationProfile(payload); // Chama api.js
            drawDiagnostico(
                payload.pontos[0],
                payload.pontos[1],
                data.bloqueio,
                nome
            ); // Chama drawing.js
        } catch (error) {
            console.error(`Erro no diagnóstico do pivô ${nome}:`, error);
            mostrarMensagem(`⚠️ Erro ao diagnosticar ${nome}.`, "erro");
        }
    }

    mostrarLoader(false);
    mostrarMensagem("🔍 Diagnóstico de visada concluído.", "sucesso");
    // Garante que a camada de visada está visível
    visadaVisivel = true;
    toggleVisada(); // Chama para garantir o estado correto
    toggleVisada(); // Chama de novo para voltar ao estado 'true'
}


/**
 * Lida com o clique no botão "Exportar KMZ".
 */
function handleExportClick() {
    if (!antenaGlobal?.overlay || !antenaGlobal.bounds) {
        mostrarMensagem("⚠️ Rode a simulação principal primeiro para gerar a imagem!", "erro");
        return;
    }

    try {
        const latStr = formatCoordForFilename(antenaGlobal.lat);
        const lonStr = formatCoordForFilename(antenaGlobal.lon);
        const template = templateSelecionado.toLowerCase();

        const nomeImagem = `sinal_${template}_${latStr}_${lonStr}.png`;
        const nomeBounds = `sinal_${template}_${latStr}_${lonStr}.json`;

        const url = getExportKmzUrl(nomeImagem, nomeBounds); // Chama api.js
        window.open(url, '_blank'); // Abre em nova aba
        mostrarMensagem("📦 Preparando KMZ para download...", "sucesso");
    } catch (error) {
        console.error("Erro ao exportar KMZ:", error);
        mostrarMensagem(`❌ Erro ao exportar: ${error.message}`, "erro");
    }
}

// --- Funções Auxiliares e Lógica Adicional ---

/**
 * Reavalia os pivôs com base nas camadas de sinal visíveis.
 */
async function reavaliarPivosViaAPI() {
    console.log("Reavaliando pivôs...");
    const pivos = Object.entries(pivotsMap).map(([nome, marcador]) => ({
        nome,
        lat: marcador.getLatLng().lat,
        lon: marcador.getLatLng().lng
    }));

    const overlays = [];

    // Antena principal
    if (antenaGlobal?.overlay && map.hasLayer(antenaGlobal.overlay)) {
        const b = antenaGlobal.overlay.getBounds();
        overlays.push({
            imagem: antenaGlobal.overlay._url.replace(BACKEND_URL + '/', ''), // Envia caminho relativo
            bounds: [b.getSouth(), b.getWest(), b.getNorth(), b.getEast()]
        });
    }

    // Repetidoras
    repetidoras.forEach(rep => {
        if (rep.overlay && map.hasLayer(rep.overlay)) {
            const b = rep.overlay.getBounds();
            overlays.push({
                imagem: rep.overlay._url.replace(BACKEND_URL + '/', ''), // Envia caminho relativo
                bounds: [b.getSouth(), b.getWest(), b.getNorth(), b.getEast()]
            });
        }
    });

    if (pivos.length === 0 || overlays.length === 0) {
        console.log("Nada a reavaliar.");
        // Se não há overlays, todos ficam vermelhos
        if(pivos.length > 0) {
            drawPivos(pivos.map(p => ({...p, fora: true })), true);
            atualizarPainelDados();
        }
        return;
    }

    try {
        const data = await reevaluatePivots({ pivos, overlays }); // Chama api.js
        if (data.pivos) {
            drawPivos(data.pivos, true); // Redesenha com o novo status
            atualizarPainelDados();
            console.log("Pivôs reavaliados.");
        }
    } catch (error) {
        console.error("Erro ao reavaliar pivôs via API:", error);
        mostrarMensagem("⚠️ Erro ao atualizar cobertura.", "erro");
    }
}


/**
 * Formata coordenada para usar em nomes de arquivos (semelhante ao Python).
 * @param {number} coord - A coordenada.
 * @returns {string} - Coordenada formatada.
 */
function formatCoordForFilename(coord) {
    return coord.toFixed(6).replace('.', '_').replace('-', 'm');
}


/**
 * Remove o marcador de posicionamento temporário.
 */
function removePositioningMarker() {
    if (marcadorPosicionamento && map.hasLayer(marcadorPosicionamento)) {
        map.removeLayer(marcadorPosicionamento);
        marcadorPosicionamento = null;
    }
}

// --- Funções de Edição de Pivôs ---

/**
 * Ativa o modo de edição de pivôs, tornando-os arrastáveis.
 */
function enablePivoEditingMode() {
    console.log("Ativando modo de edição.");
    backupPosicoesPivos = {}; // Limpa e recria backup
    Object.entries(pivotsMap).forEach(([nome, marcador]) => {
        backupPosicoesPivos[nome] = marcador.getLatLng(); // Salva posição original

        const editMarker = L.marker(marcador.getLatLng(), {
            draggable: true,
            icon: L.divIcon({
                className: 'label-pivo', // Pode criar um estilo específico
                html: `📍`, // Ícone de pino
                iconSize: [20, 20],
                iconAnchor: [10, 20] // Ponta do pino
            })
        }).addTo(map);

        marcador.editMarker = editMarker; // Associa o marcador de edição ao original

        const label = marcadoresLegenda.find(lbl =>
            lbl.getLatLng().equals(marcador.getLatLng()) && lbl.options.icon.options.html.includes(nome)
        );

        editMarker.on("drag", (e) => {
            const novaPos = e.target.getLatLng();
            if (label) label.setLatLng(novaPos); // Move a legenda junto
        });

        editMarker.on("dragend", (e) => {
            const novaPos = e.target.getLatLng();
            posicoesEditadas[nome] = novaPos; // Salva a nova posição
            if (label) label.setLatLng(novaPos);
            console.log(`Pivô ${nome} movido para:`, novaPos);
        });

        editMarker.on("contextmenu", (e) => { // Clique direito para deletar
             L.DomEvent.stopPropagation(e); // Impede o menu do mapa
             L.DomEvent.preventDefault(e);

             if(confirm(`Tem certeza que deseja remover o pivô ${nome}?`)) {
                map.removeLayer(editMarker);
                if (label) map.removeLayer(label);

                delete pivotsMap[nome];
                delete posicoesEditadas[nome];
                delete backupPosicoesPivos[nome];
                marcadoresPivos = marcadoresPivos.filter(m => m !== marcador);
                marcadoresLegenda = marcadoresLegenda.filter(l => l !== label);

                mostrarMensagem(`🗑️ Pivô ${nome} removido.`, "sucesso");
                atualizarPainelDados();
             }
        });

        map.removeLayer(marcador); // Esconde o marcador original (círculo)
    });
     mostrarMensagem("✏️ Modo de edição ativado. Arraste 📍 ou clique com botão direito para remover.", "sucesso");
}

/**
 * Desativa o modo de edição, aplicando as mudanças.
 */
function disablePivoEditingMode() {
    console.log("Desativando modo de edição e salvando.");
    Object.entries(pivotsMap).forEach(([nome, marcador]) => {
        if (marcador.editMarker) {
            const novaPos = marcador.editMarker.getLatLng();
            marcador.setLatLng(novaPos); // Atualiza a posição do círculo original
            posicoesEditadas[nome] = novaPos; // Garante que está salvo

            const label = marcadoresLegenda.find(lbl => lbl.options.icon.options.html.includes(nome));
            if (label) label.setLatLng(novaPos);

            map.removeLayer(marcador.editMarker); // Remove o marcador de edição
            delete marcador.editMarker;
            marcador.addTo(map); // Mostra o círculo original na nova posição
        }
    });
    mostrarMensagem("💾 Posições salvas. Rode a simulação novamente se necessário.", "sucesso");
    backupPosicoesPivos = {}; // Limpa o backup após salvar
}

/**
 * Desfaz as edições de pivôs, voltando às posições originais.
 */
function undoPivoEdits() {
    console.log("Desfazendo edições.");
    Object.entries(backupPosicoesPivos).forEach(([nome, posicaoOriginal]) => {
        const marcador = pivotsMap[nome];
        const label = marcadoresLegenda.find(lbl => lbl.options.icon.options.html.includes(nome));

        if (marcador && marcador.editMarker) {
            marcador.editMarker.setLatLng(posicaoOriginal);
            if (label) label.setLatLng(posicaoOriginal);
        }
    });
    posicoesEditadas = {}; // Limpa as edições salvas
    mostrarMensagem("↩️ Edições desfeitas.", "sucesso");
}