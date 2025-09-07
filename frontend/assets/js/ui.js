/* global t, getTemplates, updateLegendsVisibility, updateOverlaysOpacity, removePositioningMarker, lucide */

// =========================
//  Refs principais do DOM
// =========================
const mensagemDiv = document.getElementById("mensagem");
const loaderDiv = document.getElementById("loader");
const painelDadosDiv = document.getElementById("painel-dados");
const painelRepetidorasDiv = document.getElementById("painel-repetidoras");
const painelConfigRepetidoraDiv = document.getElementById("painel-repetidora");
const rangeOpacidade = document.getElementById("range-opacidade");
const templateSelect = document.getElementById("template-modelo");
const arquivoInput = document.getElementById("arquivo");
const nomeArquivoLabel = document.getElementById("nome-arquivo-label");
const legendContainer = document.getElementById("legend-container");
const legendImage = document.getElementById("legend-image");
const customConfirmOverlay = document.getElementById("custom-confirm-overlay");
const customConfirmBox = document.getElementById("custom-confirm-box");
const customConfirmTitle = document.getElementById("custom-confirm-title");
const customConfirmMessage = document.getElementById("custom-confirm-message");
const customConfirmOkBtn = document.getElementById("custom-confirm-ok-btn");
const customConfirmCancelBtn = document.getElementById("custom-confirm-cancel-btn");
const btnMoverPivoSemCirculo = document.getElementById("btn-mover-pivo-sem-circulo");

let dicaLoaderInterval = null;
let _hideMsgTimer = null;

// ===================================================
// Overlay helpers (evita conflito 'hidden' x 'flex')
// ===================================================
function showOverlay(el, { column = false, center = true } = {}) {
    if (!el) return;
    el.classList.remove("hidden");
    el.classList.add("flex");
    if (column) el.classList.add("flex-col");
    if (center) el.classList.add("items-center", "justify-center");
    }
    function hideOverlay(el) {
    if (!el) return;
    el.classList.add("hidden");
    el.classList.remove("flex", "flex-col", "items-center", "justify-center");
}

// ====================
// Utils: AppState
// ====================
function ensureAppState() {
    if (!window.AppState) window.AppState = {};
    const st = window.AppState;
    st.lastPivosDataDrawn ??= [];
    st.lastBombasDataDrawn ??= [];
    st.repetidoras ??= [];
    st.templateSelecionado ??= "";
    st.legendasAtivas ??= true;
    st.antenaLegendasAtivas ??= true;
    st.modoEdicaoPivos ??= false;
}

// ===============================
// Modal de Confirmação (custom)
// ===============================
/**
 * Exibe um modal de confirmação e resolve com true/false.
 * @param {string} message
 * @param {string} [title=t('ui.titles.confirm_needed')]
 * @returns {Promise<boolean>}
 */
function showCustomConfirm(message, title = t("ui.titles.confirm_needed")) {
    if (!customConfirmOverlay) return Promise.resolve(false);

    customConfirmTitle.innerHTML = `<i data-lucide="shield-question" class="w-6 h-6"></i> ${title}`;
    lucide?.createIcons?.();

    customConfirmMessage.textContent = message;
    // Abre com helpers (sem conflitar hidden/flex)
    showOverlay(customConfirmOverlay);

    return new Promise((resolve) => {
        let resolved = false;

        const handleResolution = (val) => {
        if (resolved) return;
        resolved = true;
        hideOverlay(customConfirmOverlay);
        customConfirmOkBtn?.removeEventListener("click", okListener);
        customConfirmCancelBtn?.removeEventListener("click", cancelListener);
        customConfirmOverlay?.removeEventListener("click", overlayListener);
        document.removeEventListener("keydown", keyListener);
        resolve(val);
        };

        const okListener = () => handleResolution(true);
        const cancelListener = () => handleResolution(false);
        const overlayListener = (e) => {
        if (e.target === customConfirmOverlay) handleResolution(false);
        };
        const keyListener = (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            handleResolution(true);
        } else if (e.key === "Escape") {
            e.preventDefault();
            handleResolution(false);
        }
        };

        customConfirmOkBtn?.addEventListener("click", okListener);
        customConfirmCancelBtn?.addEventListener("click", cancelListener);
        customConfirmOverlay?.addEventListener("click", overlayListener);
        document.addEventListener("keydown", keyListener);
    });
}

// =======================
// Toast / Mensagens
// =======================
function mostrarMensagem(texto, tipo = "sucesso") {
    if (!mensagemDiv) return;

    // limpa timer anterior para não esconder a nova msg cedo demais
    if (_hideMsgTimer) {
        clearTimeout(_hideMsgTimer);
        _hideMsgTimer = null;
    }

    // base limpa
    mensagemDiv.className =
        "fixed bottom-16 left-1/2 -translate-x-1/2 flex items-center gap-x-3 text-white px-4 py-3 rounded-lg shadow-lg border-l-4 bg-gray-800/90 z-[10000]";
    mensagemDiv.removeAttribute("hidden");
    mensagemDiv.classList.remove("hidden");

    // ARIA para leitura por screen readers
    mensagemDiv.setAttribute("role", "status");
    mensagemDiv.setAttribute("aria-live", "polite");

    let icon = "";
    let border = "";

    if (tipo === "sucesso") {
        icon = `<i data-lucide="check-circle-2" class="w-5 h-5 text-green-400"></i>`;
        border = "border-green-400";
    } else if (tipo === "erro") {
        icon = `<i data-lucide="alert-triangle" class="w-5 h-5 text-red-500"></i>`;
        border = "border-red-500";
    } else {
        icon = `<i data-lucide="info" class="w-5 h-5 text-yellow-400"></i>`;
        border = "border-yellow-400";
    }

    mensagemDiv.classList.add(border);
    mensagemDiv.innerHTML = `${icon}<span>${texto}</span>`;
    lucide?.createIcons?.();

    _hideMsgTimer = setTimeout(() => {
        mensagemDiv.classList.add("hidden");
    }, 4000);
}

// ==============
// Loader
// ==============
function mostrarLoader(ativo, textoOuDicas = "") {
    if (!loaderDiv) return;

    // limpa dicas anteriores
    if (dicaLoaderInterval) {
        clearInterval(dicaLoaderInterval);
        dicaLoaderInterval = null;
    }

    // abrir/fechar sem conflito de classes
    if (ativo) showOverlay(loaderDiv, { column: true });
    else hideOverlay(loaderDiv);

    // feedback de cursor
    document.body.style.cursor = ativo ? "progress" : "";

    const processingTextSpan = loaderDiv.querySelector(
        'span[data-i18n="ui.labels.processing"]'
    );
    if (!processingTextSpan) return;

    processingTextSpan.style.transition = "opacity 0.4s ease-in-out";

    if (ativo) {
        if (Array.isArray(textoOuDicas) && textoOuDicas.length) {
        let i = 0;
        processingTextSpan.textContent = textoOuDicas[i];
        processingTextSpan.style.opacity = 1;

        dicaLoaderInterval = setInterval(() => {
            i = (i + 1) % textoOuDicas.length;
            processingTextSpan.style.opacity = 0;
            setTimeout(() => {
            processingTextSpan.textContent = textoOuDicas[i];
            processingTextSpan.style.opacity = 1;
            }, 400);
        }, 6500);
        } else if (typeof textoOuDicas === "string" && textoOuDicas) {
        processingTextSpan.textContent = textoOuDicas;
        processingTextSpan.style.opacity = 1;
        } else {
        processingTextSpan.textContent = t("ui.labels.processing");
        processingTextSpan.style.opacity = 1;
        }
    } else {
        processingTextSpan.textContent = t("ui.labels.processing");
        processingTextSpan.style.opacity = 1;
    }
}

// ========================
// Legenda (imagem)
// ========================
function updateLegendImage(templateName) {
    if (!legendContainer || !legendImage || !templateName) return;

    const normalized = String(templateName).toLowerCase();

    // ajuste aqui conforme seus assets reais
    const MAP = [
        { test: /brazil[_-\s]?v6[_-\s]?100dbm/i, path: "assets/images/IRRICONTRO.dBm.key.png" },
        { test: /brazil[_-\s]?v6[_-\s]?90dbm/i, path: "assets/images/CONTROL90.dBm.key.png" },
        { test: /europe[_-\s]?v6/i, path: "assets/images/IRRIEUROPE.dBm.key.png" },
    ];

    const match = MAP.find((m) => m.test.test(normalized));
    if (!match) {
        legendContainer.classList.add("hidden");
        legendImage.removeAttribute("src");
        return;
    }

    legendImage.onerror = () => {
        // se a imagem não existir, apenas esconda para não quebrar UI
        legendContainer.classList.add("hidden");
    };
    legendImage.onload = () => {
        legendContainer.classList.remove("hidden");
    };
    legendImage.src = match.path;
}

// ========================
// Painel de dados
// ========================
function atualizarPainelDados() {
    ensureAppState();

    const pivos = Array.isArray(AppState.lastPivosDataDrawn)
        ? AppState.lastPivosDataDrawn
        : [];
    const bombas = Array.isArray(AppState.lastBombasDataDrawn)
        ? AppState.lastBombasDataDrawn
        : [];
    const reps = Array.isArray(AppState.repetidoras) ? AppState.repetidoras : [];

    const totalPivos = pivos.length;
    const foraCobertura = pivos.filter((p) => p?.fora).length;

    let totalRepetidoras = 0;
    let totalCentrais = 0;

    if (AppState.antenaGlobal) {
        const tipo = AppState.antenaGlobal.type; // (corrigido) não usar 't'
        if (tipo === "central") totalCentrais++;
        else if (tipo === "central_repeater_combined") {
        totalCentrais++;
        totalRepetidoras++;
        } else totalRepetidoras++;
    }

    reps.forEach((r) => {
        const tipo = r?.type; // (corrigido) não usar 't'
        if (tipo === "central") totalCentrais++;
        else if (tipo === "central_repeater_combined") {
        totalCentrais++;
        totalRepetidoras++;
        } else totalRepetidoras++;
    });

    const elTotalPivos = document.getElementById("total-pivos");
    const elFora = document.getElementById("fora-cobertura");
    const elTpl = document.getElementById("template-info");
    const elTotalRep = document.getElementById("total-repetidoras");
    const elCentrais = document.getElementById("total-centrais");
    const elCentraisVal = document.getElementById("central-count-value");
    const elBombas = document.getElementById("total-bombas");

    if (elTotalPivos)
        elTotalPivos.textContent = `${t("ui.labels.total_pivots")} ${totalPivos}`;
    if (elFora)
        elFora.textContent = `${t("ui.labels.out_of_coverage")} ${foraCobertura}`;
    if (elTpl)
        elTpl.textContent = `🌐 Template: ${AppState.templateSelecionado || "--"}`;
    if (elTotalRep)
        elTotalRep.textContent = `${t("ui.labels.total_repeaters")} ${totalRepetidoras}`;

    if (elCentrais && elCentraisVal) {
        elCentraisVal.textContent = totalCentrais;
        elCentrais.classList.toggle("hidden", totalCentrais === 0);
    }
    if (elBombas) {
        elBombas.textContent = `${t("ui.labels.pump_houses")} ${bombas.length}`;
        elBombas.classList.toggle("hidden", bombas.length === 0);
    }
}

// ==================================
// Stack/posição dos painéis direitos
// ==================================
function reposicionarPaineisLaterais() {
    const paineis = [painelDadosDiv, painelRepetidorasDiv].filter(Boolean);
    let topo = 16; // px
    const gap = 16;

    paineis.forEach((p) => {
        p.style.top = `${topo}px`;
        topo += p.offsetHeight + gap;
    });
}

// ===================
// Templates (select)
// ===================
async function loadAndPopulateTemplates() {
    try {
        const templates = await getTemplates();
        const arr = Array.isArray(templates) ? templates.slice() : [];
        if (!arr.length) throw new Error("Lista de templates vazia");

        // remove duplicados
        const uniq = [...new Set(arr)];
        templateSelect.innerHTML = uniq
        .map((tname) => {
            const prefix = /brazil/i.test(tname)
            ? "🇧🇷 "
            : /europe/i.test(tname)
            ? "🇪🇺 "
            : "🌐 ";
            return `<option value="${tname}">${prefix}${tname}</option>`;
        })
        .join("");

        const saved = localStorage.getItem("templateSelecionado");
        const hasSaved = saved && uniq.includes(saved);
        templateSelect.value = hasSaved ? saved : uniq[0];
        templateSelect.dispatchEvent(new Event("change"));
    } catch (err) {
        console.error("⚠️ Erro ao carregar templates:", err);
        mostrarMensagem(t("messages.errors.template_load_fail"), "erro");
    }
}

// ===================
// Edição de Pivôs
// ===================
function togglePivoEditing() {
    ensureAppState();

    const novo = !AppState.modoEdicaoPivos;
    AppState.modoEdicaoPivos = novo;

    const btn = document.getElementById("editar-pivos");
    const btnUndo = document.getElementById("desfazer-edicao");

    if (btn) {
        btn.innerHTML = novo
        ? `<i data-lucide="save" class="w-5 h-5"></i>`
        : `<i data-lucide="pencil" class="w-5 h-5"></i>`;
        btn.title = novo ? t("ui.titles.save_edit") : t("ui.titles.edit_pivots");
        btn.classList.toggle("glass-button-active", novo);
    }
    btnUndo?.classList.toggle("hidden", !novo);
    btnMoverPivoSemCirculo?.classList.toggle("hidden", !novo);

    // Desliga outros modos se existirem
    if (novo) {
        typeof AppState.modoDesenhoPivo !== "undefined" &&
        AppState.modoDesenhoPivo &&
        typeof toggleModoDesenhoPivo === "function" &&
        toggleModoDesenhoPivo();

        typeof AppState.modoDesenhoPivoSetorial !== "undefined" &&
        AppState.modoDesenhoPivoSetorial &&
        typeof toggleModoDesenhoPivoSetorial === "function" &&
        toggleModoDesenhoPivoSetorial();

        typeof AppState.modoDesenhoPivoPacman !== "undefined" &&
        AppState.modoDesenhoPivoPacman &&
        typeof toggleModoDesenhoPivoPacman === "function" &&
        toggleModoDesenhoPivoPacman();

        typeof AppState.modoDesenhoIrripump !== "undefined" &&
        AppState.modoDesenhoIrripump &&
        typeof toggleModoDesenhoIrripump === "function" &&
        toggleModoDesenhoIrripump();

        typeof AppState.modoLoSPivotAPivot !== "undefined" &&
        AppState.modoLoSPivotAPivot &&
        typeof toggleLoSPivotAPivotMode === "function" &&
        toggleLoSPivotAPivotMode();

        typeof AppState.modoBuscaLocalRepetidora !== "undefined" &&
        AppState.modoBuscaLocalRepetidora &&
        typeof handleBuscarLocaisRepetidoraActivation === "function" &&
        handleBuscarLocaisRepetidoraActivation();

        // Liga edição
        if (typeof enablePivoEditingMode === "function") enablePivoEditingMode();
    } else {
        if (AppState.modoMoverPivoSemCirculo && typeof toggleModoMoverPivoSemCirculo === "function") {
        toggleModoMoverPivoSemCirculo();
        }
        if (typeof disablePivoEditingMode === "function") disablePivoEditingMode();
    }

    lucide?.createIcons?.();
}

// ======================
// Listeners de UI
// ======================
function setupUIEventListeners() {
  // evita duplo bind se função for chamada mais de uma vez
    if (document.body.dataset.uiBound === "1") return;
    document.body.dataset.uiBound = "1";

    // botões de minimizar dos painéis
    document.querySelectorAll(".panel-toggle-btn").forEach((btn) => {
        btn.addEventListener("click", (e) => {
        const panel = e.currentTarget.closest(".panel");
        if (!panel) return;
        panel.classList.toggle("minimized");
        const icon = btn.querySelector("i");
        if (icon) {
            icon.setAttribute(
            "data-lucide",
            panel.classList.contains("minimized") ? "chevron-down" : "chevron-up"
            );
        }
        lucide?.createIcons?.();
        setTimeout(reposicionarPaineisLaterais, 500);
        });
    });

    // legenda geral (mapa)
    const btnLegenda = document.getElementById("toggle-legenda");
    if (btnLegenda && !btnLegenda.dataset.bound) {
        btnLegenda.dataset.bound = "1";
        btnLegenda.addEventListener("click", () => {
        ensureAppState();
        AppState.legendasAtivas = !AppState.legendasAtivas;

        btnLegenda.classList.toggle("glass-button-active", !AppState.legendasAtivas);
        const icon = btnLegenda.querySelector(".sidebar-icon");
        const iconPath = AppState.legendasAtivas
            ? "assets/images/captions.svg"
            : "assets/images/captions-off.svg";
        if (icon) {
            icon.style.webkitMaskImage = `url(${iconPath})`;
            icon.style.maskImage = `url(${iconPath})`;
        }
        if (typeof updateLegendsVisibility === "function") updateLegendsVisibility();
        });
    }

    // legendas de antena
    const btnAntLeg = document.getElementById("toggle-antenas-legendas");
    if (btnAntLeg && !btnAntLeg.dataset.bound) {
        btnAntLeg.dataset.bound = "1";
        btnAntLeg.addEventListener("click", () => {
        ensureAppState();
        AppState.antenaLegendasAtivas = !AppState.antenaLegendasAtivas;

        // botão ativo quando as legendas estiverem INATIVAS
        btnAntLeg.classList.toggle("glass-button-active", !AppState.antenaLegendasAtivas);

        const icon = btnAntLeg.querySelector(".sidebar-icon");
        if (icon) {
            const iconPath = AppState.antenaLegendasAtivas
            ? "assets/images/radio.svg"
            : "assets/images/radio-off.svg"; // forneça esse asset
            icon.style.webkitMaskImage = `url('${iconPath}')`;
            icon.style.maskImage = `url('${iconPath}')`;
        }

        if (typeof updateLegendsVisibility === "function") updateLegendsVisibility();
        });
    }

    // range de opacidade
    if (rangeOpacidade && !rangeOpacidade.dataset.bound) {
        rangeOpacidade.dataset.bound = "1";
        rangeOpacidade.addEventListener("input", () => {
        const val = parseFloat(rangeOpacidade.value);
        if (typeof updateOverlaysOpacity === "function") updateOverlaysOpacity(val);
        });
    }

    // select de template
    if (templateSelect && !templateSelect.dataset.bound) {
        templateSelect.dataset.bound = "1";
        templateSelect.addEventListener("change", (e) => {
        ensureAppState();
        AppState.templateSelecionado = e.target.value;
        localStorage.setItem("templateSelecionado", AppState.templateSelecionado);
        atualizarPainelDados();
        updateLegendImage(e.target.value);
        console.log("Template selecionado:", AppState.templateSelecionado);
        });
    }

    // fechar painel repetidora
    const fecharPainelRep = document.getElementById("fechar-painel-rep");
    if (fecharPainelRep && !fecharPainelRep.dataset.bound) {
        fecharPainelRep.dataset.bound = "1";
        fecharPainelRep.addEventListener("click", () => {
        painelConfigRepetidoraDiv?.classList.add("hidden");
        if (typeof removePositioningMarker === "function") removePositioningMarker();
        });
    }

    // editar / desfazer
    const btnEditar = document.getElementById("editar-pivos");
    if (btnEditar && !btnEditar.dataset.bound) {
        btnEditar.dataset.bound = "1";
        btnEditar.addEventListener("click", togglePivoEditing);
    }
    const btnUndo = document.getElementById("desfazer-edicao");
    if (btnUndo && !btnUndo.dataset.bound) {
        btnUndo.dataset.bound = "1";
        btnUndo.addEventListener("click", () => {
        if (typeof desfazerUltimaAcao === "function") desfazerUltimaAcao();
        });
    }

    // troca de idioma
    document.querySelectorAll("[data-lang]").forEach((button) => {
        if (button.dataset.bound) return;
        button.dataset.bound = "1";
        button.addEventListener("click", (e) => {
        const lang = e.currentTarget.getAttribute("data-lang");
        if (lang && typeof setLanguage === "function") setLanguage(lang);
        });
    });

    lucide?.createIcons?.();
}

// ==============================
// Painéis: expandir tudo
// ==============================
function expandAllPanels() {
    document.querySelectorAll(".panel.minimized").forEach((panel) => {
        panel.classList.remove("minimized");
        const toggleBtn = panel.querySelector(".panel-toggle-btn");
        const icon = toggleBtn?.querySelector("i");
        if (icon) icon.setAttribute("data-lucide", "chevron-up");
    });
    lucide?.createIcons?.();
    setTimeout(reposicionarPaineisLaterais, 500);
}

// ==============================
// Tooltips de desenho
// ==============================
function updateDrawingTooltip(mapInstance, mouseEvent, textContent) {
    if (!mapInstance || !mouseEvent) return;
    const container = mapInstance.getContainer?.();
    if (!container) return;

    let tooltip = container.querySelector(".drawing-tooltip");
    if (!tooltip) {
        tooltip = document.createElement("div");
        tooltip.className = "drawing-tooltip";
        container.appendChild(tooltip);
    }
    tooltip.innerHTML = textContent;

    const x = mouseEvent.containerPoint.x + 15;
    const y = mouseEvent.containerPoint.y + 15;
    tooltip.style.left = `${x}px`;
    tooltip.style.top = `${y}px`;
    tooltip.style.opacity = 1;
}

function removeDrawingTooltip(mapInstance) {
    const container = mapInstance?.getContainer?.();
    const tooltip = container?.querySelector(".drawing-tooltip");
    if (tooltip) {
        tooltip.style.opacity = 0;
        setTimeout(() => tooltip.remove(), 100);
    }
}

// ==================
// Exports globais
// ==================
window.showCustomConfirm = showCustomConfirm;
window.mostrarMensagem = mostrarMensagem;
window.mostrarLoader = mostrarLoader;
window.updateLegendImage = updateLegendImage;
window.atualizarPainelDados = atualizarPainelDados;
window.reposicionarPaineisLaterais = reposicionarPaineisLaterais;
window.loadAndPopulateTemplates = loadAndPopulateTemplates;
window.togglePivoEditing = togglePivoEditing;
window.setupUIEventListeners = setupUIEventListeners;
window.expandAllPanels = expandAllPanels;
window.updateDrawingTooltip = updateDrawingTooltip;
window.removeDrawingTooltip = removeDrawingTooltip;
window.ensureAppState = ensureAppState;
window.showOverlay = showOverlay;
window.hideOverlay = hideOverlay;
