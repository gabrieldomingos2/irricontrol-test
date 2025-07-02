// ==========================
// 🔗 ELEMENTOS DA UI
// ==========================
const mensagemDiv = document.getElementById('mensagem');
const loaderDiv = document.getElementById('loader');
const painelDadosDiv = document.getElementById('painel-dados');
const painelRepetidorasDiv = document.getElementById('painel-repetidoras');
const painelConfigRepetidoraDiv = document.getElementById('painel-repetidora');
const rangeOpacidade = document.getElementById("range-opacidade");
const templateSelect = document.getElementById('template-modelo');
const arquivoInput = document.getElementById('arquivo');
const nomeArquivoLabel = document.getElementById('nome-arquivo-label');

// ==========================
// 🔥 FUNÇÕES DE MENSAGEM E LOADER
// ==========================
function mostrarMensagem(texto, tipo = 'sucesso') {
    const mensagemDiv = document.getElementById('mensagem');
    mensagemDiv.className = 'fixed bottom-16 left-1/2 transform -translate-x-1/2 flex items-center gap-x-3 text-white px-4 py-3 rounded-lg shadow-lg border-l-4 bg-gray-800/90 z-[10000]'; // Base classes

    let iconeHtml = '';
    let borderClass = '';

    if (tipo === 'sucesso') {
        iconeHtml = `<i data-lucide="check-circle-2" class="w-5 h-5 text-green-400"></i>`;
        borderClass = 'border-green-400';
    } else if (tipo === 'erro') {
        iconeHtml = `<i data-lucide="alert-triangle" class="w-5 h-5 text-red-500"></i>`;
        borderClass = 'border-red-500';
    } else { // 'info' ou 'aviso'
        iconeHtml = `<i data-lucide="info" class="w-5 h-5 text-yellow-400"></i>`;
        borderClass = 'border-yellow-400';
    }

    mensagemDiv.classList.add(borderClass);
    mensagemDiv.innerHTML = `${iconeHtml}<span>${texto}</span>`;
    lucide.createIcons();
    
    setTimeout(() => mensagemDiv.classList.add('hidden'), 4000);
}


function mostrarLoader(ativo) {
    loaderDiv.classList.toggle('hidden', !ativo);
}

// ==========================
// 📊 ATUALIZAÇÕES DE PAINÉIS
// ==========================
function atualizarPainelDados() {
    const totalPivos = AppState.lastPivosDataDrawn.length;
    const foraCobertura = AppState.lastPivosDataDrawn.filter(p => p.fora).length;
    const antena = AppState.antenaGlobal || {};
    const totalRepetidoras = AppState.repetidoras.length + (AppState.antenaGlobal ? 1 : 0);
    const totalBombas = AppState.marcadoresBombas.length;

    document.getElementById("total-repetidoras").textContent = `${t('ui.labels.total_repeaters')} ${totalRepetidoras}`;
    document.getElementById("total-pivos").textContent = `${t('ui.labels.total_pivots')} ${totalPivos}`;
    document.getElementById("fora-cobertura").textContent = `${t('ui.labels.out_of_coverage')} ${foraCobertura}`;
    document.getElementById("altura-antena-info").textContent = `${t('ui.labels.main_antenna')} ${antena.altura || '--'} m`;
    document.getElementById("altura-receiver-info").textContent = `${t('ui.labels.receiver')} ${antena.altura_receiver || '--'} m`;
    document.getElementById("template-info").textContent = `🌐 Template: ${AppState.templateSelecionado || '--'}`;
    
    const bombasElemento = document.getElementById("total-bombas");
    bombasElemento.textContent = `${t('ui.labels.pump_houses')} ${totalBombas}`;
    bombasElemento.classList.toggle("hidden", totalBombas === 0);
}


function reposicionarPaineisLaterais() {
    const paineis = [painelDadosDiv, painelRepetidorasDiv];
    let topoAtual = 16;
    paineis.forEach(painel => {
        if (painel && !painel.classList.contains("hidden")) {
            painel.style.top = `${topoAtual}px`;
            topoAtual += painel.offsetHeight + 16;
        }
    });
}

function togglePainel(id) {
    document.getElementById(id)?.classList.toggle("hidden");
    setTimeout(reposicionarPaineisLaterais, 50);
}

// ==========================
// 📂 UPLOAD E TEMPLATE
// ==========================
function updateFileName(e) {
    const nome = e.target.files[0]?.name || t('ui.labels.choose_kmz');
    nomeArquivoLabel.textContent = nome;
    nomeArquivoLabel.title = nome;
}

async function loadAndPopulateTemplates() {
    try {
        const templates = await getTemplates();
        templateSelect.innerHTML = templates.map(t => {
            const prefix = t.includes("Brazil") ? "🇧🇷 " : t.includes("Europe") ? "🇪🇺 " : "🌐 ";
            return `<option value="${t}">${prefix}${t}</option>`;
        }).join('');

        const savedTemplate = localStorage.getItem('templateSelecionado');
        templateSelect.value = savedTemplate && templates.includes(savedTemplate) ? savedTemplate : templates[0];
        templateSelect.dispatchEvent(new Event('change'));
    } catch (error) {
        console.error("⚠️ Erro ao carregar templates:", error);
        mostrarMensagem(t('messages.errors.template_load_fail'), "erro");
    }
}

// ==========================
// 🧠 TOGGLES INTERATIVOS
// ==========================
function togglePivoEditing() {
    // A lógica de estado agora é gerenciada em enable/disablePivoEditingMode em main.js
    // Esta função agora apenas lida com a UI do botão.
    const isEditing = !AppState.modoEdicaoPivos; // O novo estado será o oposto do atual

    const btn = document.getElementById("editar-pivos");
    const btnUndo = document.getElementById("desfazer-edicao");

    btn.innerHTML = isEditing ? `<i data-lucide="save" class="w-5 h-5"></i>` : `<i data-lucide="pencil" class="w-5 h-5"></i>`;
    btn.title = isEditing ? t('ui.buttons.save_edit') : t('ui.titles.edit_pivots');
    btn.classList.toggle('glass-button-active', isEditing);
    btnUndo.classList.toggle("hidden", !isEditing);
    
    if (isEditing) {
        enablePivoEditingMode();
    } else {
        disablePivoEditingMode();
    }

    lucide.createIcons();
}

// ==========================
// 🛠️ SETUP DOS EVENTOS
// ==========================
function setupUIEventListeners() {
    document.getElementById("toggle-painel").addEventListener("click", () => togglePainel("painel-dados"));
    document.getElementById("toggle-repetidoras").addEventListener("click", () => togglePainel("painel-repetidoras"));
    
    document.getElementById("toggle-legenda").addEventListener("click", () => {
        toggleLegendas(!AppState.legendasAtivas);
    });

    rangeOpacidade.addEventListener("input", () => {
        updateOverlaysOpacity(parseFloat(rangeOpacidade.value));
    });

    arquivoInput.addEventListener("change", updateFileName);

    templateSelect.addEventListener("change", (e) => {
        AppState.templateSelecionado = e.target.value;
        localStorage.setItem('templateSelecionado', AppState.templateSelecionado);
        atualizarPainelDados();
        console.log("Template selecionado:", AppState.templateSelecionado);
    });

    document.getElementById("fechar-painel-rep").addEventListener("click", () => {
        painelConfigRepetidoraDiv.classList.add('hidden');
        removePositioningMarker();
    });

    document.getElementById("editar-pivos").addEventListener("click", togglePivoEditing);
    document.getElementById("desfazer-edicao").addEventListener("click", undoPivoEdits);

    document.querySelectorAll('[data-lang]').forEach(button => {
        button.addEventListener('click', (e) => {
            const lang = e.currentTarget.getAttribute('data-lang');
            if (lang) setLanguage(lang);
        });
    });

    lucide.createIcons();
}