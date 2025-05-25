// --- Elementos da UI ---
const mensagemDiv = document.getElementById('mensagem');
const loaderDiv = document.getElementById('loader');
const painelDadosDiv = document.getElementById('painel-dados');
const painelRepetidorasDiv = document.getElementById('painel-repetidoras');
const painelOpacidadeDiv = document.getElementById('painel-opacidade');
const painelConfigRepetidoraDiv = document.getElementById('painel-repetidora');
const rangeOpacidade = document.getElementById("range-opacidade");
const templateSelect = document.getElementById('template-modelo');
const arquivoInput = document.getElementById('arquivo');
const nomeArquivoLabel = document.getElementById('nome-arquivo-label');

// --- Funções da UI ---

/**
 * Mostra uma mensagem temporária na tela.
 * @param {string} texto - O texto da mensagem.
 * @param {string} [tipo='sucesso'] - 'sucesso' (verde) ou 'erro' (vermelho).
 */
function mostrarMensagem(texto, tipo = 'sucesso') {
    mensagemDiv.textContent = texto;
    mensagemDiv.classList.remove('hidden', 'bg-red-600', 'bg-green-600');
    mensagemDiv.classList.add(tipo === 'sucesso' ? 'bg-green-600' : 'bg-red-600');
    // Força reflow para garantir que a transição funcione
    void mensagemDiv.offsetWidth;
    setTimeout(() => {
        mensagemDiv.classList.add('hidden');
    }, 4000);
}

/**
 * Mostra ou esconde o indicador de carregamento (loader).
 * @param {boolean} ativo - True para mostrar, false para esconder.
 */
function mostrarLoader(ativo) {
    loaderDiv.classList.toggle('hidden', !ativo);
}

/**
 * Atualiza as informações no painel de dados da simulação.
 */
function atualizarPainelDados() {
    const total = Object.keys(pivotsMap).length;
    const fora = Object.values(pivotsMap).filter(m => m.options.fillColor === 'red').length;
    const antena = antenaGlobal || {}; // Usa antenaGlobal ou um objeto vazio
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

    // Mostra o painel se estiver escondido (exceto no reset)
    if (total > 0 && painelDadosDiv.classList.contains('hidden')) {
       // painelDadosDiv.classList.remove('hidden'); // Decide-se se deve auto-mostrar
    }
     if (repetidoras.length > 0 && painelRepetidorasDiv.classList.contains('hidden')) {
       // painelRepetidorasDiv.classList.remove('hidden'); // Decide-se se deve auto-mostrar
    }
}


/**
 * Reposiciona os painéis laterais para que não se sobreponham.
 */
function reposicionarPaineisLaterais() {
    const paineis = [painelDadosDiv, painelRepetidorasDiv, painelOpacidadeDiv];
    const padding = 16; // Espaço em pixels entre painéis (equivale a 'space-y-4' do Tailwind)
    const topoBase = 14; // Posição inicial (top-14) + padding
    let topoAtual = topoBase;

    paineis.forEach(painel => {
        if (!painel.classList.contains("hidden")) {
            painel.style.top = `${topoAtual}px`;
            topoAtual += painel.offsetHeight + padding;
        }
    });
}

/**
 * Alterna a visibilidade de um painel e reposiciona os outros.
 * @param {string} id - O ID do painel a ser alternado.
 */
function togglePainel(id) {
    const painel = document.getElementById(id);
    if (painel) {
        painel.classList.toggle("hidden");
        // Dá um pequeno tempo para a classe ser aplicada antes de reposicionar
        setTimeout(reposicionarPaineisLaterais, 50);
    }
}

/**
 * Atualiza o label do botão de upload com o nome do arquivo.
 * @param {Event} e - O evento 'change' do input.
 */
function updateFileName(e) {
    const nome = e.target.files[0]?.name || 'Escolher Arquivo KMZ';
    nomeArquivoLabel.textContent = nome;
    nomeArquivoLabel.title = nome; // Adiciona tooltip para nomes longos
}

/**
 * Busca os templates da API e preenche o seletor <select>.
 */
async function loadAndPopulateTemplates() {
    try {
        const templates = await getTemplates(); // Chama a função da api.js
        templateSelect.innerHTML = ''; // Limpa opções existentes

        templates.forEach(t => {
            const opt = document.createElement('option');
            opt.value = t;
            // Adiciona emojis como no código original
            opt.textContent = t.includes("Brazil") ? "🇧🇷 " + t :
                              t.includes("Europe") ? "🇪🇺 " + t :
                              "🌐 " + t;
            templateSelect.appendChild(opt);
        });

        // Define o template salvo ou o primeiro da lista
        const savedTemplate = localStorage.getItem('templateSelecionado');
        templateSelect.value = savedTemplate && templates.includes(savedTemplate)
                             ? savedTemplate
                             : templates[0];

        // Dispara o evento 'change' para atualizar o estado global
        templateSelect.dispatchEvent(new Event('change'));

    } catch (error) {
        console.error("⚠️ Erro ao carregar templates:", error);
        mostrarMensagem("⚠️ Erro ao carregar templates. Usando padrão.", "erro");
        // Se falhar, usa o que tiver (se houver) e dispara o change
        templateSelect.dispatchEvent(new Event('change'));
    }
}

/**
 * Configura todos os event listeners da interface do usuário.
 */
function setupUIEventListeners() {
    // Botões de Toggle dos Painéis
    document.getElementById("toggle-painel").addEventListener("click", () => togglePainel("painel-dados"));
    document.getElementById("toggle-repetidoras").addEventListener("click", () => togglePainel("painel-repetidoras"));
    document.getElementById("toggle-opacidade").addEventListener("click", () => togglePainel("painel-opacidade"));

    // Botão Toggle Legendas
    document.getElementById("toggle-legenda").addEventListener("click", () => {
        toggleLegendas(!legendasAtivas); // Chama a função de drawing.js
    });

    // Slider de Opacidade
    rangeOpacidade.addEventListener("input", () => {
        updateOverlaysOpacity(parseFloat(rangeOpacidade.value)); // Chama a função de drawing.js
    });

    // Input de Arquivo
    arquivoInput.addEventListener("change", updateFileName);

    // Seletor de Template
    templateSelect.addEventListener("change", (e) => {
        templateSelecionado = e.target.value; // Atualiza a variável global
        localStorage.setItem('templateSelecionado', templateSelecionado);
        atualizarPainelDados(); // Atualiza o painel
        console.log("Template selecionado:", templateSelecionado);
    });

    // Botão Fechar Painel Repetidora
     document.getElementById("fechar-painel-rep").addEventListener("click", () => {
         painelConfigRepetidoraDiv.classList.add('hidden');
         removePositioningMarker(); // Remove o marcador temporário (precisa existir em drawing.js ou main.js)
     });

    // Botões de Edição (Chamam funções que devem existir em main.js ou drawing.js)
    document.getElementById("editar-pivos").addEventListener("click", togglePivoEditing); // Precisa criar togglePivoEditing
    document.getElementById("desfazer-edicao").addEventListener("click", undoPivoEdits); // Precisa criar undoPivoEdits

    // Botões de Ação Principal (Listeners serão adicionados em main.js)
    // #formulario, #simular-btn, #btn-diagnostico, #exportar-btn, #resetar-btn

    // Clique no mapa (Listener será adicionado em main.js)

    // Botão Confirmar Repetidora (Listener será adicionado em main.js)
}

// --- Funções de Edição de Pivôs (Listeners aqui, lógica principal talvez em main/drawing) ---

let modoEdicaoPivos = false;
let backupPosicoesPivos = {};

function togglePivoEditing() {
    modoEdicaoPivos = !modoEdicaoPivos;
    const btn = document.getElementById("editar-pivos");
    const btnUndo = document.getElementById("desfazer-edicao");
    btn.innerHTML = modoEdicaoPivos ? "💾" : "✏️"; // Muda para ícone
    btn.title = modoEdicaoPivos ? "Salvar Edições" : "Editar Pivôs";

    if (modoEdicaoPivos) {
        btn.classList.add('bg-yellow-600', 'hover:bg-yellow-700');
        btnUndo.classList.remove("hidden");
        enablePivoEditingMode(); // Chama a função que ativa a edição (precisa criar)
    } else {
        btn.classList.remove('bg-yellow-600', 'hover:bg-yellow-700');
        btnUndo.classList.add("hidden");
        disablePivoEditingMode(); // Chama a função que desativa e salva (precisa criar)
    }
}

// Nota: As funções enablePivoEditingMode, disablePivoEditingMode, e undoPivoEdits
// precisarão ser criadas, provavelmente em main.js ou drawing.js, pois
// envolverão manipulação pesada de marcadores e estado.
// A função 'removePositioningMarker' também precisa ser criada.