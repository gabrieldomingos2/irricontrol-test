// assets/js/map.js

/* global L, AppState, mostrarMensagem, t */

let map;

/**
 * Garante que AppState exista com as chaves usadas aqui.
 */
function ensureAppState() {
    if (!window.AppState) window.AppState = {};
    const st = window.AppState;
    if (!("visadaVisivel" in st)) st.visadaVisivel = true;
    if (!("visadaLayerGroup" in st)) st.visadaLayerGroup = null;
    if (!("antenaCandidatesLayerGroup" in st)) st.antenaCandidatesLayerGroup = null;
}

/**
 * Inicializa o mapa Leaflet, camada de satélite e grupos.
 * Pode ser chamado mais de uma vez com segurança (faz cleanup do mapa anterior).
 */
function initMap() {
    ensureAppState();

// Destroi mapa anterior (se existir) para evitar listeners duplicados/erro de container já inicializado
    if (map && map.remove) {
        try {
        map.off();
        map.remove();
    } catch (_) {}
    map = null;
}

const container = document.getElementById("map");
    if (!container) {
    console.error("Elemento #map não encontrado.");
    return;
}

map = L.map(container, {
    zoomControl: false,
    preferCanvas: true, // melhora performance com muitos vetores
}).setView([-15, -55], 5);

// Camada de satélite (Google). Observação: respeite os termos de uso do provedor.
const tiles = L.tileLayer("https://{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}", {
    maxZoom: 20,
    subdomains: ["mt0", "mt1", "mt2", "mt3"],
    attribution: "",
}).addTo(map);

  tiles.on("tileerror", (/* e */) => {
    // Silencioso por padrão; descomente para depurar:
    // console.warn("Falha ao carregar tile:", e);
});

// Grupos
AppState.visadaLayerGroup = L.layerGroup().addTo(map);
AppState.antenaCandidatesLayerGroup = L.layerGroup().addTo(map);

if (!window.candidateRepeaterSitesLayerGroup) {
    window.candidateRepeaterSitesLayerGroup = L.layerGroup().addTo(map);
    console.log("candidateRepeaterSitesLayerGroup inicializado e adicionado ao mapa.");
}

// Botão Visada
const btnVisada = document.getElementById("btn-visada");
if (btnVisada) {
    btnVisada.addEventListener("click", toggleVisada);
    // estado inicial coerente
    btnVisada.classList.toggle("glass-button-active", AppState.visadaVisivel);
    btnVisada.setAttribute("aria-pressed", String(AppState.visadaVisivel));
} else {
    console.error("Botão #btn-visada não encontrado!");
}

setupCandidateRemovalListener();

// Atualização de ícones em zoom, se a função existir
map.on("zoomend", () => {
    if (typeof updatePivotIcons === "function") {
        try {
        updatePivotIcons();
        } catch (e) {
        console.warn("updatePivotIcons lançou erro:", e);
        }
    }
});

// Ajusta mapa ao redimensionar janela
window.addEventListener("resize", () => {
    if (map && map.invalidateSize) map.invalidateSize();
});

// Aplica visibilidade inicial
applyVisadaVisibility();
}

/**
 * Define explicitamente a visibilidade de tudo que está em visadaLayerGroup.
 * @param {boolean} visible
 */
function setVisadaVisible(visible) {
    ensureAppState();
    AppState.visadaVisivel = !!visible;
    applyVisadaVisibility();

// Sincroniza botão/aria
const btnVisada = document.getElementById("btn-visada");
    if (btnVisada) {
        btnVisada.classList.toggle("glass-button-active", AppState.visadaVisivel);
        btnVisada.setAttribute("aria-pressed", String(AppState.visadaVisivel));
    }
}

/**
 * Aplica o estado atual AppState.visadaVisivel às camadas do grupo.
 * Suporta vetores, markers, ImageOverlay, TileLayer e grupos aninhados.
 */
function applyVisadaVisibility() {
    const group = AppState.visadaLayerGroup;
    if (!group) return;

    const visible = !!AppState.visadaVisivel;

    const applyToLayer = (layer) => {
    const targetOpacity = visible ? 1 : 0;

// Grupos aninhados (LayerGroup/FeatureGroup)
    if (layer && typeof layer.getLayers === "function") {
        layer.getLayers().forEach(applyToLayer);
        return;
    }

    // Raster (ImageOverlay / TileLayer)
    if (typeof layer.setOpacity === "function") {
        try {
            layer.setOpacity(targetOpacity);
        } catch (_) {}
        // Tenta também mexer em eventos
        if (layer._image) {
        layer._image.style.pointerEvents = visible ? "auto" : "none";
    }
    return;
    }

    // Vetores (Polyline/Polygon/Circle/GeoJSON)
    if (typeof layer.setStyle === "function") {
      // Guarda fillOpacity original (apenas 1x)
        if (layer.options && typeof layer.options.__fillOpacityOriginal === "undefined") {
        const orig =
            typeof layer.options.fillOpacity === "number" ? layer.options.fillOpacity : 0.5;
        layer.options.__fillOpacityOriginal = orig;
    }
    const baseFill =
        layer.options?.__fillOpacityOriginal !== undefined
            ? layer.options.__fillOpacityOriginal
            : 0.5;

    try {
        layer.setStyle({
            opacity: targetOpacity,
            fillOpacity: visible ? baseFill : 0,
        });
    } catch (_) {}

      // pointer-events em SVG path
        if (layer._path) {
            layer._path.style.pointerEvents = visible ? "auto" : "none";
    }
    return;
}

    // Markers com elemento DOM (DivIcon / default)
    if (layer && typeof layer.getElement === "function") {
        const el = layer.getElement();
        if (el) {
        el.style.opacity = targetOpacity;
        el.style.pointerEvents = visible ? "auto" : "none";
        }
    return;
    }

    // Fallback direto no _icon (alguns tipos de marker)
    if (layer && layer._icon) {
        layer._icon.style.opacity = targetOpacity;
        layer._icon.style.pointerEvents = visible ? "auto" : "none";
    }
};

group.eachLayer(applyToLayer);

console.log(`Visada: ${visible ? "Ativada" : "Desativada"}`);
}

/**
 * Alterna a visibilidade das camadas dentro de visadaLayerGroup.
 */
function toggleVisada() {
    setVisadaVisible(!AppState.visadaVisivel);
}

/**
 * Clique no mapa para capturar botão "X" (remover candidato a repetidora).
 * Usa delegação para não precisar adicionar listeners por marker.
 */
function setupCandidateRemovalListener() {
    if (!map) {
    console.error("Mapa não inicializado.");
    return;
}

map.on("click", function (e) {
    const target = e.originalEvent?.target;
    if (!target || !target.classList) return;

    if (target.classList.contains("candidate-remove-btn")) {
        const markerIdToRemove = target.dataset.markerId;
        if (!markerIdToRemove) return;

    // Evita que o click no "X" seja interpretado como clique no mapa
        L.DomEvent.stop(e);

    if (window.candidateRepeaterSitesLayerGroup) {
        const toRemove = [];
        window.candidateRepeaterSitesLayerGroup.eachLayer((layer) => {
            if (layer?.options?.customId === markerIdToRemove) {
            toRemove.push(layer);
            }
        });

        if (toRemove.length) {
            toRemove.forEach((l) => window.candidateRepeaterSitesLayerGroup.removeLayer(l));
            console.log("Candidato removido:", markerIdToRemove);
            if (typeof mostrarMensagem === "function") {
            mostrarMensagem(t("messages.success.repeater_suggestion_removed"), "sucesso");
            }
        } else {
            console.warn("Nenhuma camada encontrada para remover:", markerIdToRemove);
        }
    }
    }
});
}

// Exponha initMap/setVisadaVisible globalmente (se usado por outros arquivos)
window.initMap = initMap;
window.setVisadaVisible = setVisadaVisible;