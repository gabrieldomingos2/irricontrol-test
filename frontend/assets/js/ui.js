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
const customConfirmOverlay = document.getElementById('custom-confirm-overlay');
const customConfirmBox = document.getElementById('custom-confirm-box');
const customConfirmTitle = document.getElementById('custom-confirm-title');
const customConfirmMessage = document.getElementById('custom-confirm-message');
const customConfirmOkBtn = document.getElementById('custom-confirm-ok-btn');
const customConfirmCancelBtn = document.getElementById('custom-confirm-cancel-btn');
const btnMoverPivoSemCirculo = document.getElementById('btn-mover-pivo-sem-circulo');

let dicaLoaderInterval = null;


/**
 * Exibe um modal de confirmação customizado e retorna uma Promise.
 * @param {string} message A mensagem a ser exibida no corpo do modal.
 * @param {string} [title='Confirmação Necessária'] O título do modal.
 * @returns {Promise<boolean>} Resolve como `true` se o usuário confirmar, `false` caso contrário.
 */
function showCustomConfirm(message, title = t('ui.titles.confirm_needed')) {
    customConfirmTitle.innerHTML = `<i data-lucide="shield-question" class="w-6 h-6"></i> ${title}`;
    lucide.createIcons();

    customConfirmMessage.textContent = message;
    customConfirmOverlay.classList.remove('hidden');

    return new Promise(resolve => {
        let resolved = false;

        const keyboardListener = (event) => {
            if (event.key === 'Enter') {
                event.preventDefault();
                handleResolution(true);
            } else if (event.key === 'Escape') {
                event.preventDefault();
                handleResolution(false);
            }
        };

        const handleResolution = (value) => {
            if (resolved) return;
            resolved = true;
            
            customConfirmOverlay.classList.add('hidden');
            customConfirmOkBtn.removeEventListener('click', okListener);
            customConfirmCancelBtn.removeEventListener('click', cancelListener);
            customConfirmOverlay.removeEventListener('click', overlayListener);
            document.removeEventListener('keydown', keyboardListener);
            
            resolve(value);
        };

        const okListener = () => handleResolution(true);
        const cancelListener = () => handleResolution(false);
        const overlayListener = (e) => {
            if (e.target === customConfirmOverlay) {
                handleResolution(false);
            }
        };
        
        customConfirmOkBtn.addEventListener('click', okListener);
        customConfirmCancelBtn.addEventListener('click', cancelListener);
        customConfirmOverlay.addEventListener('click', overlayListener);
        document.addEventListener('keydown', keyboardListener);
    });
}


function mostrarMensagem(texto, tipo = 'sucesso') {
    const mensagemDiv = document.getElementById('mensagem');
    mensagemDiv.className = 'fixed bottom-16 left-[calc(50%-180px)] transform -translate-x-1/2 flex items-center gap-x-3 text-white px-4 py-3 rounded-lg shadow-lg border-l-4 bg-gray-800/90 z-[10000]';

    let iconeHtml = '';
    let borderClass = '';

    if (tipo === 'sucesso') {
        iconeHtml = `<i data-lucide="check-circle-2" class="w-5 h-5 text-green-400"></i>`;
        borderClass = 'border-green-400';
    } else if (tipo === 'erro') {
        iconeHtml = `<i data-lucide="alert-triangle" class="w-5 h-5 text-red-500"></i>`;
        borderClass = 'border-red-500';
    } else {
        iconeHtml = `<i data-lucide="info" class="w-5 h-5 text-yellow-400"></i>`;
        borderClass = 'border-yellow-400';
    }

    mensagemDiv.classList.add(borderClass);
    mensagemDiv.innerHTML = `${iconeHtml}<span>${texto}</span>`;
    lucide.createIcons();
    
    setTimeout(() => mensagemDiv.classList.add('hidden'), 4000);
}

function mostrarLoader(ativo, textoOuDicas = '') {
    if (dicaLoaderInterval) {
        clearInterval(dicaLoaderInterval);
        dicaLoaderInterval = null;
    }

    loaderDiv.classList.toggle('hidden', !ativo);
    const processingTextSpan = loaderDiv.querySelector('span[data-i18n="ui.labels.processing"]');
    
    if (!processingTextSpan) return;

    processingTextSpan.style.transition = 'opacity 0.4s ease-in-out';

    if (ativo) {
        if (Array.isArray(textoOuDicas) && textoOuDicas.length > 0) {
            let currentIndex = 0;
            processingTextSpan.textContent = textoOuDicas[currentIndex];
            processingTextSpan.style.opacity = 1;

            dicaLoaderInterval = setInterval(() => {
                currentIndex = (currentIndex + 1) % textoOuDicas.length;
                
                processingTextSpan.style.opacity = 0;

                setTimeout(() => {
                    processingTextSpan.textContent = textoOuDicas[currentIndex];
                    processingTextSpan.style.opacity = 1;
                }, 400);

            }, 6500);

        } else if (typeof textoOuDicas === 'string' && textoOuDicas) {
            processingTextSpan.textContent = textoOuDicas;
            processingTextSpan.style.opacity = 1;
        } else {
            processingTextSpan.textContent = t('ui.labels.processing');
            processingTextSpan.style.opacity = 1;
        }
    } else {
        processingTextSpan.textContent = t('ui.labels.processing');
        processingTextSpan.style.opacity = 1;
    }
}

function updateLegendImage(templateName) {
    if (!legendContainer || !legendImage) return;

    let imagePath = null;
    const normalizedName = templateName.toLowerCase();

    if (normalizedName.includes("brazil_v6")) {
        imagePath = "assets/images/IRRICONTRO.dBm.key.png";
    } else if (normalizedName.includes("europe") && normalizedName.includes("v6")) {
        imagePath = "assets/images/IRRIEUROPE.dBm.key.png";
    }

    if (imagePath) {
        legendImage.src = imagePath;
        legendContainer.classList.remove('hidden');
    } else {
        legendContainer.classList.add('hidden');
    }
}

function atualizarPainelDados() {
    const totalPivos = AppState.lastPivosDataDrawn.length;
    const foraCobertura = AppState.lastPivosDataDrawn.filter(p => p.fora).length;
    const totalBombas = AppState.lastBombasDataDrawn.length;

    let totalRepetidorasContagem = 0;
    let totalCentraisContagem = 0;

    if (AppState.antenaGlobal) {
        const antennaType = AppState.antenaGlobal.type;
        if (antennaType === 'central') {
            totalCentraisContagem++;
        } else if (antennaType === 'central_repeater_combined') {
            totalCentraisContagem++;
            totalRepetidorasContagem++;
        } else {
            totalRepetidorasContagem++;
        }
    }

    AppState.repetidoras.forEach(rep => {
        const repType = rep.type;
        if (repType === 'central') {
            totalCentraisContagem++;
        } else if (repType === 'central_repeater_combined') {
            totalCentraisContagem++;
            totalRepetidorasContagem++;
        } else {
            totalRepetidorasContagem++;
        }
    });


    document.getElementById("total-pivos").textContent = `${t('ui.labels.total_pivots')} ${totalPivos}`;
    document.getElementById("fora-cobertura").textContent = `${t('ui.labels.out_of_coverage')} ${foraCobertura}`;
    document.getElementById("template-info").textContent = `🌐 Template: ${AppState.templateSelecionado || '--'}`;
    
    document.getElementById("total-repetidoras").textContent = `${t('ui.labels.total_repeaters')} ${totalRepetidorasContagem}`;

    const centralCountElement = document.getElementById('total-centrais');
    const centralCountValueElement = document.getElementById('central-count-value');
    if (centralCountElement && centralCountValueElement) {
        centralCountValueElement.textContent = totalCentraisContagem;
        centralCountElement.classList.toggle("hidden", totalCentraisContagem === 0);
    }
    
    const bombasElemento = document.getElementById("total-bombas");
    bombasElemento.textContent = `${t('ui.labels.pump_houses')} ${totalBombas}`;
    bombasElemento.classList.toggle("hidden", totalBombas === 0);
}


function reposicionarPaineisLaterais() {
    const paineis = [painelDadosDiv, painelRepetidorasDiv];
    let topoAtual = 16;
    const espacamento = 16;

    paineis.forEach(painel => {
        if (painel) {
            painel.style.top = `${topoAtual}px`;
            topoAtual += painel.offsetHeight + espacamento;
        }
    });
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

function togglePivoEditing() {
    const novoEstadoDeEdicao = !AppState.modoEdicaoPivos;
    AppState.modoEdicaoPivos = novoEstadoDeEdicao;

    const btn = document.getElementById("editar-pivos");
    const btnUndo = document.getElementById("desfazer-edicao");
    const btnMoverPivo = document.getElementById("btn-mover-pivo-sem-circulo");

    btn.innerHTML = novoEstadoDeEdicao ? `<i data-lucide="save" class="w-5 h-5"></i>` : `<i data-lucide="pencil" class="w-5 h-5"></i>`;
    btn.title = novoEstadoDeEdicao ? t('ui.titles.save_edit') : t('ui.titles.edit_pivots');
    btn.classList.toggle('glass-button-active', novoEstadoDeEdicao);
    btnUndo.classList.toggle("hidden", !novoEstadoDeEdicao);
    btnMoverPivo.classList.toggle("hidden", !novoEstadoDeEdicao);

    if (novoEstadoDeEdicao) {
        if (AppState.modoDesenhoPivo) toggleModoDesenhoPivo();
        if (AppState.modoDesenhoPivoSetorial) toggleModoDesenhoPivoSetorial();
        if (AppState.modoDesenhoPivoPacman) toggleModoDesenhoPivoPacman();
        if (AppState.modoDesenhoIrripump) toggleModoDesenhoIrripump();
        if (AppState.modoLoSPivotAPivot) toggleLoSPivotAPivotMode();
        if (AppState.modoBuscaLocalRepetidora) handleBuscarLocaisRepetidoraActivation();
        
        enablePivoEditingMode();
    } else {
        if (AppState.modoMoverPivoSemCirculo) {
            toggleModoMoverPivoSemCirculo();
        }
        disablePivoEditingMode();
    }

    lucide.createIcons();
}

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
        AppState.legendasAtivas = !AppState.legendasAtivas;
        const btn = document.getElementById("toggle-legenda");
        btn.classList.toggle("glass-button-active", !AppState.legendasAtivas);

        const icon = btn.querySelector('.sidebar-icon');
        const iconPath = AppState.legendasAtivas ? 'assets/images/captions.svg' : 'assets/images/captions-off.svg';
        if(icon) {
            icon.style.webkitMaskImage = `url(${iconPath})`;
            icon.style.maskImage = `url(${iconPath})`;
        }
        
        updateLegendsVisibility();
    });

    document.getElementById("toggle-antenas-legendas").addEventListener("click", () => {
        AppState.antenaLegendasAtivas = !AppState.antenaLegendasAtivas;
        const btn = document.getElementById("toggle-antenas-legendas");
        btn.classList.toggle("glass-button-active", !AppState.antenaLegendasAtivas);

        const icon = btn.querySelector('.sidebar-icon');
        
        if(icon) {
            icon.style.webkitMaskImage = `url('assets/images/radio.svg')`;
            icon.style.maskImage = `url('assets/images/radio.svg')`;
        }

        updateLegendsVisibility();
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

/**
 * Cria ou atualiza um tooltip que segue o mouse.
 * @param {L.Map} mapInstance - A instância do mapa Leaflet.
 * @param {MouseEvent} mouseEvent - O evento do mouse para obter a posição.
 * @param {string} textContent - O texto a ser exibido no tooltip.
 */
function updateDrawingTooltip(mapInstance, mouseEvent, textContent) {
    const container = mapInstance.getContainer();
    let tooltip = container.querySelector('.drawing-tooltip');

    // Cria o tooltip se ele não existir
    if (!tooltip) {
        tooltip = document.createElement('div');
        tooltip.className = 'drawing-tooltip';
        container.appendChild(tooltip);
    }

    // Atualiza o texto
    tooltip.innerHTML = textContent;

    // Posiciona o tooltip um pouco abaixo e à direita do cursor
    const x = mouseEvent.containerPoint.x + 15;
    const y = mouseEvent.containerPoint.y + 15;

    tooltip.style.left = `${x}px`;
    tooltip.style.top = `${y}px`;
    tooltip.style.opacity = 1;
}

/**
 * Remove o tooltip de desenho do mapa.
 * @param {L.Map} mapInstance - A instância do mapa Leaflet.
 */
function removeDrawingTooltip(mapInstance) {
    const container = mapInstance.getContainer();
    const tooltip = container.querySelector('.drawing-tooltip');
    if (tooltip) {
        tooltip.style.opacity = 0;
        // Remove o elemento após a transição para suavizar o desaparecimento
        setTimeout(() => tooltip.remove(), 100);
    }
}