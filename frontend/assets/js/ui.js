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
    mensagemDiv.classList.remove('hidden', 'bg-red-600', 'bg-green-600');
    mensagemDiv.classList.add(tipo === 'sucesso' ? 'bg-green-600' : 'bg-red-600');
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

    document.getElementById("total-pivos").textContent = `Pivôs: ${total}`;
    document.getElementById("fora-cobertura").textContent = `Fora da cobertura: ${fora}`;
    document.getElementById("altura-antena-info").textContent = `Antena principal: ${antena.altura || '--'} m`;
    document.getElementById("altura-receiver-info").textContent = `Receiver: ${antena.altura_receiver || '--'} m`;
    document.getElementById("total-repetidoras").textContent = `Total Repetidoras: ${repetidoras.length}`;
    document.getElementById("template-info").textContent = `🌐 Template: ${templateSelecionado || '--'}`;

    const bombasElemento = document.getElementById("total-bombas");
    if (bombas.length > 0) {
        bombasElemento.textContent = `Casas de bomba: ${bombas.length}`;
        bombasElemento.classList.remove("hidden");
    } else {
        bombasElemento.classList.add("hidden");
    }
}

function reposicionarPaineisLaterais() {
    const paineis = [painelDadosDiv, painelRepetidorasDiv];
    const padding = 16;
    const topoBase = 14;
    let topoAtual = topoBase;

    paineis.forEach(painel => {
        if (!painel.classList.contains("hidden")) {
            painel.style.top = `${topoAtual}px`;
            topoAtual += painel.offsetHeight + padding;
        }
    });
}

function togglePainel(id) {
    const painel = document.getElementById(id);
    if (painel) {
        painel.classList.toggle("hidden");
        setTimeout(reposicionarPaineisLaterais, 50);
    }
}

// ==========================
// 📂 UPLOAD E TEMPLATE
// ==========================
function updateFileName(e) {
    const nome = e.target.files[0]?.name || 'Escolher Arquivo KMZ';
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
        mostrarMensagem("⚠️ Erro ao carregar templates. Usando padrão.", "erro");
        templateSelect.dispatchEvent(new Event('change'));
    }
}

// ==========================
// 🧠 TOGGLES INTERATIVOS
// ==========================
function toggleLegenda() {
    const btn = document.getElementById('toggle-legenda');
    btn.classList.toggle('glass-button-active');
}

function togglePivoEditing() {
    modoEdicaoPivos = !modoEdicaoPivos;

    const btn = document.getElementById("editar-pivos");
    const btnUndo = document.getElementById("desfazer-edicao");

    btn.innerHTML = modoEdicaoPivos
        ? `<i data-lucide="save" class="w-5 h-5"></i> <span class="text-xs">Salvar Edição</span>`
        : `<i data-lucide="pencil" class="w-5 h-5"></i>`;

    btn.title = modoEdicaoPivos ? "Salvar Edições" : "Editar";

    if (modoEdicaoPivos) {
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
        removePositioningMarker(); // Função de main.js
    });

    document.getElementById("editar-pivos").addEventListener("click", togglePivoEditing); // Função de ui.js
    document.getElementById("desfazer-edicao").addEventListener("click", undoPivoEdits); // Função de main.js

    // Garante que os ícones Lucide sejam renderizados
    lucide.createIcons();
}
