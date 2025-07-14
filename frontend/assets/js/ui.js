// Mantenha estas constantes no topo, pois são referencias a IDs fixos no HTML
const mensagemDiv = document.getElementById('mensagem');
const loaderDiv = document.getElementById('loader');
const painelDadosDiv = document.getElementById('painel-dados');
const painelRepetidorasDiv = document.getElementById('painel-repetidoras');
const painelRepetidoraSetupDiv = document.getElementById('painel-repetidora-setup'); // Painel de setup de nova repetidora
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

// Referências para as sidebars e seus botões de toggle
const leftSidebar = document.getElementById('left-sidebar');
const toggleLeftSidebarBtn = document.getElementById('toggle-left-sidebar');
const toggleRightPanelsBtn = document.getElementById('toggle-right-panels'); 
const rightSidebar = document.getElementById('right-sidebar'); 
const toggleRightSidebarBtn = document.getElementById('toggle-right-sidebar'); 

// As referências para os botões internos dos painéis serão inicializadas dentro de setupUIEventListeners
let painelDadosMinimizarBtn = null; 
let painelRepetidorasToggleBtn = null;


/**
 * Exibe um modal de confirmação customizado e retorna uma Promise.
 * @param {string} message A mensagem a ser exibida no corpo do modal.
 * @param {string} [title='Confirmação Necessária'] O título do modal.
 * @returns {Promise<boolean>} Resolve como `true` se o usuário confirmar, `false` caso contrário.
 */
function showCustomConfirm(message, title = 'Confirmação Necessária') {
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
    mensagemDiv.className = 'fixed bottom-16 flex items-center gap-x-3 text-white px-4 py-3 rounded-lg shadow-lg border-l-4 bg-gray-800/90 z-[10000]';

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
    
    mensagemDiv.classList.remove('hidden');
    setTimeout(() => mensagemDiv.classList.add('hidden'), 4000);
}

function mostrarLoader(ativo, textoAdicional = '') {
    loaderDiv.classList.toggle('hidden', !ativo);
    const processingTextSpan = loaderDiv.querySelector('span[data-i18n="ui.labels.processing"]');
    if (processingTextSpan) {
        if (ativo && textoAdicional) {
            processingTextSpan.textContent = textoAdicional;
        } else {
            processingTextSpan.textContent = t('ui.labels.processing');
        }
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

    // Ajusta o texto do botão de exportar PDF no painel de dados
    const exportPdfBtnText = document.querySelector('#exportar-pdf-btn span');
    if (exportPdfBtnText) {
        exportPdfBtnText.textContent = t('ui.buttons.export_pdf_report');
    }
}


function reposicionarPaineisLaterais() {
    if (window.innerWidth >= 768) { // Apenas para telas desktop (md e acima)
        const espacamento = 16; // 1rem em pixels, espaçamento entre os painéis
        const headerHeight = 56; // Altura do cabeçalho (h-14) em pixels

        const topInicialNaColuna = headerHeight + espacamento;
        const rightPos = '6.5rem'; 
        
        // Garante que os painéis estão visíveis antes de calcular offsetHeight
        painelDadosDiv.classList.remove('hidden');
        painelRepetidorasDiv.classList.remove('hidden');
        
        const painelDadosMinimizado = painelDadosDiv.classList.contains('minimized');

        // --- Lógica para o Painel de Dados ---
        if (painelDadosMinimizado) { 
            // Painel de Dados minimizado: invisível e não interativo, mas no lugar para o Repetidoras subir
            painelDadosDiv.style.opacity = '0'; 
            painelDadosDiv.style.pointerEvents = 'none'; 
            painelDadosDiv.style.top = `${topInicialNaColuna}px`; 
            painelDadosDiv.style.right = rightPos; 

            // Painel de Repetidoras sobe para a posição do Painel de Dados
            painelRepetidorasDiv.style.top = `${topInicialNaColuna}px`;
            painelRepetidorasDiv.style.right = rightPos;
            painelRepetidorasDiv.style.opacity = '1';
            painelRepetidorasDiv.style.pointerEvents = 'auto';

            // ATUALIZA O ÍCONE DO BOTÃO DE MINIMIZAR DO PAINEL DE DADOS PARA 'CHEVRON-DOWN' (MAXIMIZAR)
            // E GARANTE SUA VISIBILIDADE
            if (painelDadosMinimizarBtn) { 
                painelDadosMinimizarBtn.classList.remove('hidden'); 
                const icon = painelDadosMinimizarBtn.querySelector('i'); 
                if (icon) { 
                    icon.setAttribute('data-lucide', 'chevron-down'); 
                    lucide.createIcons(); 
                }
            }

        } else {
            // Painel de Dados expandido: visível e interativo
            painelDadosDiv.style.opacity = '1';
            painelDadosDiv.style.pointerEvents = 'auto';
            painelDadosDiv.style.top = `${topInicialNaColuna}px`;
            painelDadosDiv.style.right = rightPos;

            // Painel de Repetidoras fica abaixo do Painel de Dados expandido
            // Força o browser a recalcular o layout para garantir offsetHeight correto
            void painelDadosDiv.offsetHeight; 
            const topoPainelRepetidoras = painelDadosDiv.offsetTop + painelDadosDiv.offsetHeight + espacamento;
            painelRepetidorasDiv.style.top = `${topoPainelRepetidoras}px`;
            painelRepetidorasDiv.style.right = rightPos;
            painelRepetidorasDiv.style.opacity = '1';
            painelRepetidorasDiv.style.pointerEvents = 'auto';

            // ATUALIZA O ÍCONE DO BOTÃO DE MINIMIZAR DO PAINEL DE DADOS PARA 'CHEVRON-UP' (MINIMIZAR)
            // E GARANTE SUA VISIBILIDADE (se o painel não está minimizado, o botão de minimizar é visível)
            if (painelDadosMinimizarBtn) { 
                painelDadosMinimizarBtn.classList.remove('hidden'); 
                const icon = painelDadosMinimizarBtn.querySelector('i'); 
                if (icon) { 
                    icon.setAttribute('data-lucide', 'chevron-up'); 
                    lucide.createIcons(); 
                }
            }
        }

        // --- Lógica para o botão de toggle do Painel de Repetidoras ---
        if (painelRepetidorasToggleBtn) { 
            painelRepetidorasToggleBtn.classList.remove('hidden'); 
            // Posiciona o botão no canto superior direito do PRÓPRIO PAINEL
            painelRepetidorasToggleBtn.style.position = 'absolute'; // Já deve estar, mas garante
            painelRepetidorasToggleBtn.style.top = '0.5rem'; // Ajuste conforme padding interno do painel
            painelRepetidorasToggleBtn.style.right = '0.5rem'; // Ajuste conforme padding interno do painel
            
            const icon = painelRepetidorasToggleBtn.querySelector('i');
            if (icon) { 
                if (painelRepetidorasDiv.classList.contains('minimized')) { 
                    icon.setAttribute('data-lucide', 'chevron-down'); // Seta para baixo se minimizado
                } else { 
                    icon.setAttribute('data-lucide', 'chevron-up'); // Seta para cima se expandido
                }
                lucide.createIcons();
            }
        }

    } else { // Para telas menores que 768px (mobile), os painéis são escondidos
        painelDadosDiv.classList.add('hidden');
        painelRepetidorasDiv.classList.add('hidden');
        painelDadosDiv.style.opacity = '';
        painelDadosDiv.style.pointerEvents = '';
        painelRepetidorasDiv.style.opacity = '';
        painelRepetidorasDiv.style.pointerEvents = '';

        // Oculta todos os botões de toggle de painéis flutuantes em mobile
        if (painelDadosMinimizarBtn) painelDadosMinimizarBtn.classList.add('hidden');
        if (painelRepetidorasToggleBtn) painelRepetidorasToggleBtn.classList.add('hidden');
        
        // Garante que os botões de sidebar (left e right) apareçam em mobile
        if (toggleLeftSidebarBtn) toggleLeftSidebarBtn.classList.remove('hidden');
        if (toggleRightSidebarBtn) toggleRightSidebarBtn.classList.remove('hidden');
        if (toggleRightPanelsBtn) toggleRightPanelsBtn.classList.remove('hidden');
    }
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
    btn.innerHTML = novoEstadoDeEdicao ? `<i data-lucide="save" class="w-5 h-5"></i>` : `<i data-lucide="pencil" class="w-5 h-5"></i>`;
    btn.title = novoEstadoDeEdicao ? t('ui.titles.save_edit') : t('ui.titles.edit_pivots');
    btn.classList.toggle('glass-button-active', novoEstadoDeEdicao);
    btnUndo.classList.toggle("hidden", !novoEstadoDeEdicao);
    
    if (novoEstadoDeEdicao) {
        if (AppState.modoDesenhoPivo) toggleModoDesenhoPivo();
        if (AppState.modoDesenhoPivoSetorial) toggleModoDesenhoPivoSetorial();
        if (AppState.modoDesenhoPivoPacman) toggleModoDesenhoPivoPacman();
        if (AppState.modoDesenhoIrripump) toggleModoDesenhoIrripump();
        
        enablePivoEditingMode();
    } else {
        disablePivoEditingMode();
    }

    lucide.createIcons();
}

function setupUIEventListeners() {
    // Inicialize as referências dos botões internos aqui, após o DOM estar carregado.
    painelDadosMinimizarBtn = document.getElementById('painel-dados-minimizar-btn');
    painelRepetidorasToggleBtn = document.getElementById('toggle-painel-repetidoras-btn');

    // Listener para o botão de MINIMIZAR/MAXIMIZAR do PAINEL DE DADOS (agora um só botão)
    if (painelDadosMinimizarBtn) { 
        painelDadosMinimizarBtn.addEventListener('click', () => { 
            painelDadosDiv.classList.toggle('minimized'); // Alterna a classe 'minimized'
            
            // A visibilidade e o ícone são controlados por reposicionarPaineisLaterais()
            if (window.innerWidth >= 768) { 
                setTimeout(reposicionarPaineisLaterais, 50); // Curto delay para CSS aplicar
            }
        });
    }

    // Listener para o botão de TOGGLE do PAINEL DE REPETIDORAS (dentro do painel)
    if (painelRepetidorasToggleBtn) { 
        painelRepetidorasToggleBtn.addEventListener('click', () => { 
            // Se o Painel de Dados estiver minimizado, expande-o primeiro E GARANTE REPETIDORAS EXPANDIDA
            if (painelDadosDiv.classList.contains('minimized')) { 
                painelDadosDiv.classList.remove('minimized'); // Expande Painel de Dados
                painelRepetidorasDiv.classList.remove('minimized'); // Expande Painel de Repetidoras também!

                if (window.innerWidth >= 768) { 
                    setTimeout(reposicionarPaineisLaterais, 600); // Dá tempo para o Painel de Dados expandir
                }
            } else {
                // Se o Painel de Dados NÃO estiver minimizado, então minimiza/maximiza APENAS o Painel de Repetidoras
                painelRepetidorasDiv.classList.toggle('minimized');
                if (window.innerWidth >= 768) { 
                    setTimeout(reposicionarPaineisLaterais, 50); // Curto delay para CSS aplicar
                }
            }
        });
    }

    // Este loop document.querySelectorAll('.panel-toggle-btn') agora é redundante para
    // os botões que têm IDs específicos e listeners dedicados.
    // Mantenho-o por segurança para outros painéis que usam a classe genérica.
    document.querySelectorAll('.panel-toggle-btn').forEach(btn => {
        // Verifica se o botão já tem um listener específico pelo ID
        if (btn.id === 'painel-dados-minimizar-btn' || btn.id === 'toggle-painel-repetidoras-btn') {
            return; // Já tratado por listeners específicos.
        }

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
            
            if (window.innerWidth >= 768) {
                setTimeout(reposicionarPaineisLaterais, 500); 
            }
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
        btn.classList.toggle("glass-button-active", !AppState.antendasLegendasAtivas);
        
        const icon = btn.querySelector('.sidebar-icon');
        
        if(icon) {
            icon.style.webkitMaskImage = `url('assets/images/radio.svg')`;
            icon.style.maskImage = `url('assets/images/radio.svg')`;
            icon.style.opacity = AppState.antenaLegendasAtivas ? '1' : '0.5';
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

    document.getElementById("fechar-painel-rep-setup").addEventListener("click", () => {
        painelRepetidoraSetupDiv.classList.add('hidden');
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

    if (toggleLeftSidebarBtn) {
        toggleLeftSidebarBtn.addEventListener('click', () => {
            leftSidebar.classList.toggle('-translate-x-full');
            const icon = toggleLeftSidebarBtn.querySelector('i');
            if (icon) {
                icon.setAttribute('data-lucide', leftSidebar.classList.contains('-translate-x-full') ? 'chevrons-right' : 'chevrons-left');
                lucide.createIcons();
            }
            if (window.innerWidth < 768) {
                if (!painelDadosDiv.classList.contains('hidden')) {
                    painelDadosDiv.classList.add('hidden');
                    painelRepetidorasDiv.classList.add('hidden');
                    const rightPanelsIcon = toggleRightPanelsBtn.querySelector('i');
                    if (rightPanelsIcon) {
                        rightPanelsIcon.setAttribute('data-lucide', 'panel-left-open'); 
                        lucide.createIcons();
                    }
                }
                if (!rightSidebar.classList.contains('translate-x-full')) { 
                    rightSidebar.classList.add('translate-x-full'); 
                    const rightSidebarIcon = toggleRightSidebarBtn.querySelector('i'); 
                    if (rightSidebarIcon) { 
                        rightSidebarIcon.setAttribute('data-lucide', 'chevrons-left'); 
                        lucide.createIcons(); 
                    }
                }
            }
        });
    }

    if (toggleRightSidebarBtn) { 
        toggleRightSidebarBtn.addEventListener('click', () => { 
            rightSidebar.classList.toggle('translate-x-full'); 
            const icon = toggleRightSidebarBtn.querySelector('i'); 
            if (icon) { 
                icon.setAttribute('data-lucide', rightSidebar.classList.contains('translate-x-full') ? 'chevrons-left' : 'chevrons-right'); 
                lucide.createIcons(); 
            }
            if (window.innerWidth < 768) {
                if (!leftSidebar.classList.contains('-translate-x-full')) {
                    leftSidebar.classList.add('-translate-x-full');
                    const leftIcon = toggleLeftSidebarBtn.querySelector('i');
                    if (leftIcon) {
                        leftIcon.setAttribute('data-lucide', 'chevrons-right');
                        lucide.createIcons();
                    }
                }
                if (!painelDadosDiv.classList.contains('hidden')) {
                    painelDadosDiv.classList.add('hidden');
                    painelRepetidorasDiv.classList.add('hidden');
                    const rightPanelsIcon = toggleRightPanelsBtn.querySelector('i');
                    if (rightPanelsIcon) {
                        rightPanelsIcon.setAttribute('data-lucide', 'panel-left-open');
                        lucide.createIcons();
                    }
                }
            }
        });
    }

    if (toggleRightPanelsBtn) {
        toggleRightPanelsBtn.addEventListener('click', () => {
            const arePanelsHidden = painelDadosDiv.classList.contains('hidden');
            painelDadosDiv.classList.toggle('hidden', !arePanelsHidden);
            painelRepetidorasDiv.classList.toggle('hidden', !arePanelsHidden);

            const icon = toggleRightPanelsBtn.querySelector('i');
            if (icon) {
                icon.setAttribute('data-lucide', arePanelsHidden ? 'panel-right-close' : 'panel-left-open');
                lucide.createIcons();
            }
            if (window.innerWidth < 768) {
                if (!leftSidebar.classList.contains('-translate-x-full')) {
                    leftSidebar.classList.add('-translate-x-full');
                    const leftIcon = toggleLeftSidebarBtn.querySelector('i');
                    if (leftIcon) {
                        leftIcon.setAttribute('data-lucide', 'chevrons-right');
                        lucide.createIcons();
                    }
                }
                if (!rightSidebar.classList.contains('translate-x-full')) { 
                    rightSidebar.classList.add('translate-x-full'); 
                    const rightSidebarIcon = toggleRightSidebarBtn.querySelector('i'); 
                    if (rightSidebarIcon) { 
                        rightSidebarIcon.setAttribute('data-lucide', 'chevrons-left'); 
                        lucide.createIcons(); 
                    }
                }
            }
        });
    }

    window.addEventListener('resize', () => { 
        if (window.innerWidth >= 768) { 
            leftSidebar.classList.remove('-translate-x-full'); 
            if (toggleLeftSidebarBtn) toggleLeftSidebarBtn.classList.add('hidden'); 

            rightSidebar.classList.remove('translate-x-full'); 
            if (toggleRightSidebarBtn) toggleRightSidebarBtn.classList.add('hidden'); 

            reposicionarPaineisLaterais(); 
            if (toggleRightPanelsBtn) toggleRightPanelsBtn.classList.add('hidden'); 

        } else { 
            if (toggleLeftSidebarBtn) toggleLeftSidebarBtn.classList.remove('hidden'); 
            if (toggleRightPanelsBtn) toggleRightPanelsBtn.classList.remove('hidden'); 
            if (toggleRightSidebarBtn) toggleRightSidebarBtn.classList.remove('hidden'); 
            
            leftSidebar.classList.add('-translate-x-full');
            rightSidebar.classList.add('translate-x-full');
            painelDadosDiv.classList.add('hidden');
            painelRepetidorasDiv.classList.add('hidden');
            if (painelDadosMinimizarBtn) painelDadosMinimizarBtn.classList.add('hidden');
            if (painelRepetidorasToggleBtn) painelRepetidorasToggleBtn.classList.add('hidden');
        }
    });

    window.dispatchEvent(new Event('resize')); 

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
    if (window.innerWidth >= 768) {
        setTimeout(reposicionarPaineisLaterais, 500); 
    }
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

    if (!tooltip) {
        tooltip = document.createElement('div');
        tooltip.className = 'drawing-tooltip';
        container.appendChild(tooltip);
    }

    tooltip.innerHTML = textContent;

    const x = mouseEvent.containerPoint.x + 5; 
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
        setTimeout(() => tooltip.remove(), 100);
    }
}