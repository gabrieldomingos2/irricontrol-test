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
    mensagemDiv.textContent = texto;
    mensagemDiv.classList.remove('hidden', 'bg-red-600', 'bg-green-600', 'bg-yellow-500'); // Adicionado amarelo para 'info'
    if (tipo === 'sucesso') {
        mensagemDiv.classList.add('bg-green-600');
    } else if (tipo === 'erro') {
        mensagemDiv.classList.add('bg-red-600');
    } else { // info
        mensagemDiv.classList.add('bg-yellow-500');
    }
    void mensagemDiv.offsetWidth;
    setTimeout(() => {
        mensagemDiv.classList.add('hidden');
    }, 4000);
}

function mostrarLoader(ativo) {
    loaderDiv.classList.toggle('hidden', !ativo);
}

// ==========================
// 📊 ATUALIZAÇÕES DE PAINÉIS
// ==========================
function atualizarPainelDados() {
    const total = Object.keys(pivotsMap).length;
    const fora = Object.values(pivotsMap).filter(m => m.options.fillColor === 'red').length;
    const antena = antenaGlobal || {};
    const bombas = marcadoresBombas || [];

    // Os data-i18n no HTML cuidam dos labels estáticos.
    // Aqui atualizamos apenas os valores dinâmicos.
    document.getElementById("total-pivos").textContent = `${t('ui.labels.total_pivots')} ${total}`;
    document.getElementById("fora-cobertura").textContent = `${t('ui.labels.out_of_coverage')} ${fora}`;
    document.getElementById("altura-antena-info").textContent = `${t('ui.labels.main_antenna')} ${antena.altura || '--'} m`;
    document.getElementById("altura-receiver-info").textContent = `${t('ui.labels.receiver')} ${antena.altura_receiver || '--'} m`;
    document.getElementById("total-repetidoras").textContent = `${t('ui.labels.total_repeaters')} ${repetidoras.length}`;
    document.getElementById("template-info").textContent = `🌐 Template: ${templateSelecionado || '--'}`;

    const bombasElemento = document.getElementById("total-bombas");
    if (bombas.length > 0) {
        bombasElemento.textContent = `${t('ui.labels.pump_houses')} ${bombas.length}`;
        bombasElemento.classList.remove("hidden");
    } else {
        bombasElemento.classList.add("hidden");
    }
}

function reposicionarPaineisLaterais() {
    const paineis = [painelDadosDiv, painelRepetidorasDiv];
    const padding = 16;
    let topoAtual = 16; // Distância do topo da janela de visualização

    paineis.forEach(painel => {
        if (painel && !painel.classList.contains("hidden")) {
            painel.style.top = `${topoAtual}px`;
            topoAtual += painel.offsetHeight + padding;
        }
    });
}

function togglePainel(id) {
    const painel = document.getElementById(id);
    if (painel) {
        painel.classList.toggle("hidden");
        // Atraso para garantir que o DOM foi atualizado antes de recalcular as posições
        setTimeout(reposicionarPaineisLaterais, 50);
    }
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
        templateSelect.innerHTML = '';

        templates.forEach(t => {
            const opt = document.createElement('option');
            opt.value = t;
            opt.textContent = t.includes("Brazil") ? "🇧🇷 " + t :
                              t.includes("Europe") ? "🇪🇺 " + t :
                              "🌐 " + t;
            templateSelect.appendChild(opt);
        });

        const savedTemplate = localStorage.getItem('templateSelecionado');
        templateSelect.value = savedTemplate && templates.includes(savedTemplate)
                             ? savedTemplate
                             : templates[0];

        templateSelect.dispatchEvent(new Event('change'));
    } catch (error) {
        console.error("⚠️ Erro ao carregar templates:", error);
        mostrarMensagem(t('messages.errors.template_load_fail'), "erro");
        templateSelect.dispatchEvent(new Event('change'));
    }
}

// ==========================
// 🧠 TOGGLES INTERATIVOS
// ==========================
function togglePivoEditing() {
    window.modoEdicaoPivos = !window.modoEdicaoPivos;

    const btn = document.getElementById("editar-pivos");
    const btnUndo = document.getElementById("desfazer-edicao");

    // Usa a função `t` para obter os textos corretos
    btn.innerHTML = window.modoEdicaoPivos
        ? `<i data-lucide="save" class="w-5 h-5"></i>`
        : `<i data-lucide="pencil" class="w-5 h-5"></i>`;

    btn.title = window.modoEdicaoPivos ? t('ui.buttons.save_edit') : t('ui.titles.edit_pivots');
    
    if (window.modoEdicaoPivos) {
        btn.classList.add('glass-button-active');
        btnUndo.classList.remove("hidden");
        enablePivoEditingMode();
    } else {
        btn.classList.remove('glass-button-active');
        btnUndo.classList.add("hidden");
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
        toggleLegendas(!legendasAtivas);
    });

    rangeOpacidade.addEventListener("input", () => {
        updateOverlaysOpacity(parseFloat(rangeOpacidade.value));
    });

    arquivoInput.addEventListener("change", updateFileName);

    templateSelect.addEventListener("change", (e) => {
        templateSelecionado = e.target.value;
        localStorage.setItem('templateSelecionado', templateSelecionado);
        atualizarPainelDados();
        console.log("Template selecionado:", templateSelecionado);
    });

    document.getElementById("fechar-painel-rep").addEventListener("click", () => {
        painelConfigRepetidoraDiv.classList.add('hidden');
        if(typeof removePositioningMarker === 'function') {
           removePositioningMarker();
        }
    });

    document.getElementById("editar-pivos").addEventListener("click", togglePivoEditing);
    document.getElementById("desfazer-edicao").addEventListener("click", undoPivoEdits);

    // Adiciona os listeners para os botões de idioma
    document.querySelectorAll('[data-lang]').forEach(button => {
        button.addEventListener('click', (e) => {
            // Sobe para o elemento <button> caso o clique seja na imagem
            const buttonElement = e.target.closest('button');
            const lang = buttonElement.getAttribute('data-lang');
            if (lang) {
                setLanguage(lang); // Chama a função do i18n.js
            }
        });
    });

    lucide.createIcons();
}