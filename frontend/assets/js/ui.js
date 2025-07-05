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
const legendContainer = document.getElementById('legend-container');
const legendImage = document.getElementById('legend-image'); 

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

/**
 * ATUALIZA A IMAGEM DA LEGENDA DE CORES COM BASE NO TEMPLATE SELECIONADO
 * @param {string} templateName - O nome do template (ex: "Brazil_v6").
 */
function updateLegendImage(templateName) {
    if (!legendContainer || !legendImage) return;

    let imagePath = null;
    const normalizedName = templateName.toLowerCase();

    if (normalizedName.includes("brazil_v6")) {
        imagePath = "assets/images/IRRICONTRO.dBm.key.png";
    } else if (normalizedName.includes("europe") && normalizedName.includes("v6")) {
        // Captura "Europe_v6", "europe v6", etc.
        imagePath = "assets/images/IRRIEUROPE.dBm.key.png";
    }

    if (imagePath) {
        legendImage.src = imagePath;
        legendContainer.classList.remove('hidden');
    } else {
        legendContainer.classList.add('hidden');
    }
}


// ==========================
// 📊 ATUALIZAÇÕES DE PAINÉIS
// ==========================
function atualizarPainelDados() {
    const totalPivos = AppState.lastPivosDataDrawn.length;
    const foraCobertura = AppState.lastPivosDataDrawn.filter(p => p.fora).length;
    const totalRepetidoras = AppState.repetidoras.length + (AppState.antenaGlobal ? 1 : 0);
    const totalBombas = AppState.marcadoresBombas.length;

    document.getElementById("total-repetidoras").textContent = `${t('ui.labels.total_repeaters')} ${totalRepetidoras}`;
    document.getElementById("total-pivos").textContent = `${t('ui.labels.total_pivots')} ${totalPivos}`;
    document.getElementById("fora-cobertura").textContent = `${t('ui.labels.out_of_coverage')} ${foraCobertura}`;
    document.getElementById("template-info").textContent = `🌐 Template: ${AppState.templateSelecionado || '--'}`;
    
    const bombasElemento = document.getElementById("total-bombas");
    bombasElemento.textContent = `${t('ui.labels.pump_houses')} ${totalBombas}`;
    bombasElemento.classList.toggle("hidden", totalBombas === 0);
}


function reposicionarPaineisLaterais() {
    const paineis = [painelDadosDiv, painelRepetidorasDiv];
    let topoAtual = 16; // Corresponde a 'top-16' -> 4rem -> 64px. Assumindo que o container pai dos painéis tem top-16.
    const espacamento = 16; // Corresponde a 'space-y-4'

    paineis.forEach(painel => {
        if (painel) { // Processa mesmo que esteja escondido para manter a ordem
            painel.style.top = `${topoAtual}px`;
            // A altura do painel minimizado é basicamente a altura do seu cabeçalho.
            // A altura total (offsetHeight) reflete o estado atual (minimizado ou expandido).
            topoAtual += painel.offsetHeight + espacamento;
        }
    });
}


// ==========================
// 📂 UPLOAD E TEMPLATE
// ==========================
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
    const isEditing = !AppState.modoEdicaoPivos; 

    const btn = document.getElementById("editar-pivos");
    const btnUndo = document.getElementById("desfazer-edicao");

    // Usa os ícones da biblioteca Lucide
    btn.innerHTML = isEditing ? `<i data-lucide="save" class="w-5 h-5"></i>` : `<i data-lucide="pencil" class="w-5 h-5"></i>`;
    btn.title = isEditing ? t('ui.titles.save_edit') : t('ui.titles.edit_pivots');
    btn.classList.toggle('glass-button-active', isEditing);
    btnUndo.classList.toggle("hidden", !isEditing);
    
    if (isEditing) {
        // ✅ INÍCIO DA CORREÇÃO: Desativa outros modos antes de ativar este
        if (AppState.modoDesenhoPivo) toggleModoDesenhoPivo();
        if (AppState.modoDesenhoPivoSetorial) toggleModoDesenhoPivoSetorial();
        if (AppState.modoDesenhoPivoPacman) toggleModoDesenhoPivoPacman();
        // ✅ FIM DA CORREÇÃO
        
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

    document.querySelectorAll('.panel-toggle-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const panel = e.currentTarget.closest('.panel');
            if (!panel) return;

            panel.classList.toggle('minimized');
            const icon = btn.querySelector('i');

            if (panel.classList.contains('minimized')) {
                icon.setAttribute('data-lucide', 'chevron-down');
            } else {
                icon.setAttribute('data-lucide', 'chevron-up');
            }
            lucide.createIcons();
            
            setTimeout(reposicionarPaineisLaterais, 500); 
        });
    });

    document.getElementById("toggle-legenda").addEventListener("click", () => {
        toggleLegendas(!AppState.legendasAtivas);
    });

    rangeOpacidade.addEventListener("input", () => {
        updateOverlaysOpacity(parseFloat(rangeOpacidade.value));
    });

    templateSelect.addEventListener("change", (e) => {
        AppState.templateSelecionado = e.target.value;
        localStorage.setItem('templateSelecionado', AppState.templateSelecionado);
        atualizarPainelDados();
        updateLegendImage(e.target.value);
        console.log("Template selecionado:", AppState.templateSelecionado);
    });

    document.getElementById("fechar-painel-rep").addEventListener("click", () => {
        painelConfigRepetidoraDiv.classList.add('hidden');
        removePositioningMarker();
    });


    document.getElementById("editar-pivos").addEventListener("click", togglePivoEditing);
    document.getElementById("desfazer-edicao").addEventListener("click", desfazerUltimaAcao);

    document.querySelectorAll('[data-lang]').forEach(button => {
        button.addEventListener('click', (e) => {
            const lang = e.currentTarget.getAttribute('data-lang');
            if (lang) setLanguage(lang);
        });
    });

    lucide.createIcons();
}

/**
 * Garante que todos os painéis laterais estejam expandidos.
 */
function expandAllPanels() {

    document.querySelectorAll('.panel.minimized').forEach(panel => {
 
        panel.classList.remove('minimized');

        const toggleBtn = panel.querySelector('.panel-toggle-btn');
        if (toggleBtn) {
            const icon = toggleBtn.querySelector('i');
            if (icon) {
                icon.setAttribute('data-lucide', 'chevron-up');
            }
        }
    });

    lucide.createIcons();

    setTimeout(reposicionarPaineisLaterais, 500);
}