// --- Variáveis Globais de Estado (Anexadas a 'window') ---

window.modoEdicaoPivos = false;
window.coordenadaClicada = null;
window.marcadorPosicionamento = null;
window.backupPosicoesPivos = {}; // <<< ADICIONADO AQUI TAMBÉM

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

function handleResetClick(showMessage = true) {
    console.log("🔄 Resetando aplicação...");
    clearMapLayers();

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
    window.backupPosicoesPivos = {}; // <<< Usa window.
    overlaysVisiveis = [];
    linhasDiagnostico = [];
    marcadoresBloqueio = [];
    window.modoEdicaoPivos = false;

    const btnSimular = document.getElementById("simular-btn");
    btnSimular.classList.add("hidden");
    btnSimular.disabled = false;
    btnSimular.classList.remove("opacity-50", "cursor-not-allowed");
    document.getElementById("btn-diagnostico").classList.add("hidden");

    const btnEditar = document.getElementById("editar-pivos");
    btnEditar.innerHTML = `<i data-lucide="pencil" class="w-5 h-5"></i>`;
    btnEditar.title = "Editar Pivôs";
    btnEditar.classList.remove('glass-button-active');
    document.getElementById("desfazer-edicao").classList.add("hidden");
    lucide.createIcons();

    document.getElementById("lista-repetidoras").innerHTML = "";
    document.getElementById("painel-repetidora").classList.add("hidden");
    document.getElementById("painel-dados").classList.add("hidden");
    document.getElementById("painel-repetidoras").classList.add("hidden");

    document.getElementById('formulario').reset();
    document.getElementById('nome-arquivo-label').textContent = "Escolher Arquivo KMZ";
    document.getElementById("range-opacidade").value = 1;

    map.setView([-15, -55], 5);

    if (showMessage) mostrarMensagem("🔄 Aplicação resetada.", "sucesso");

    atualizarPainelDados();
    reposicionarPaineisLaterais();
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
    console.log("Ativando modo de edição.");
    window.backupPosicoesPivos = {}; // <<< Usa window.
    Object.entries(pivotsMap).forEach(([nome, marcador]) => {
        window.backupPosicoesPivos[nome] = marcador.getLatLng(); // <<< Usa window.

        const editMarker = L.marker(marcador.getLatLng(), {
            draggable: true,
            icon: L.divIcon({
                className: 'label-pivo', html: `📍`, iconSize: [20, 20], iconAnchor: [10, 20]
            })
        }).addTo(map);

        marcador.editMarker = editMarker;
        const label = marcadoresLegenda.find(lbl => lbl.getLatLng().equals(marcador.getLatLng()) && lbl.options.icon.options.html.includes(nome));

        editMarker.on("drag", (e) => { if (label) label.setLatLng(e.target.getLatLng()); });
        editMarker.on("dragend", (e) => {
            const novaPos = e.target.getLatLng();
            posicoesEditadas[nome] = novaPos;
            if (label) label.setLatLng(novaPos);
            console.log(`Pivô ${nome} movido para:`, novaPos);
        });

        editMarker.on("contextmenu", (e) => {
            L.DomEvent.stopPropagation(e); L.DomEvent.preventDefault(e);
            if (confirm(`Tem certeza que deseja remover o pivô ${nome}?`)) {
                map.removeLayer(editMarker);
                if (pivotsMap[nome] && map.hasLayer(pivotsMap[nome])) { map.removeLayer(pivotsMap[nome]); }
                if (label) map.removeLayer(label);
                delete pivotsMap[nome]; delete posicoesEditadas[nome]; delete window.backupPosicoesPivos[nome]; // <<< Usa window.
                marcadoresPivos = marcadoresPivos.filter(m => m !== marcador);
                marcadoresLegenda = marcadoresLegenda.filter(l => l !== label);
                mostrarMensagem(`🗑️ Pivô ${nome} removido.`, "sucesso");
                atualizarPainelDados();
            }
        });
        map.removeLayer(marcador);
    });
    mostrarMensagem("✏️ Modo de edição ativado. Arraste 📍 ou clique com botão direito para remover.", "sucesso");
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