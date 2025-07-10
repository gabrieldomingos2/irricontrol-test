// map.js

let map;

/**
 * Inicializa o mapa Leaflet, adiciona a camada de satélite
 * e inicializa as camadas de grupo gerenciadas pelo AppState.
 */
function initMap() {
    map = L.map('map', {
        zoomControl: false
    }).setView([-15, -55], 5);

    L.tileLayer('https://{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', {
        maxZoom: 20,
        subdomains: ['mt0', 'mt1', 'mt2', 'mt3']
    }).addTo(map);

    // Inicializa as camadas de grupo DENTRO do objeto de estado central
    AppState.visadaLayerGroup = L.layerGroup().addTo(map);
    
    // ✅ CORREÇÃO CENTRAL: A camada de candidatas agora é parte do AppState.
    AppState.antenaCandidatesLayerGroup = L.layerGroup().addTo(map);

    if (!window.candidateRepeaterSitesLayerGroup) {
        window.candidateRepeaterSitesLayerGroup = L.layerGroup().addTo(map);
        console.log("candidateRepeaterSitesLayerGroup inicializado e adicionado ao mapa.");
    }

    const btnVisada = document.getElementById("btn-visada");
    if (btnVisada) {
        btnVisada.addEventListener("click", toggleVisada);
    } else {
        console.error("Botão #btn-visada não encontrado!");
    }

    setupCandidateRemovalListener();

    map.on('zoomend', updatePivotIcons);
}

/**
 * Alterna a visibilidade das camadas dentro do visadaLayerGroup.
 */
function toggleVisada() {
    AppState.visadaVisivel = !AppState.visadaVisivel; 
    
    if (AppState.visadaLayerGroup) {
        AppState.visadaLayerGroup.eachLayer(layer => {
            const opacity = AppState.visadaVisivel ? 1 : 0;
            if (layer.setStyle) {
                layer.setStyle({
                    opacity: opacity,
                    fillOpacity: AppState.visadaVisivel ? (layer.options.fillOpacityOriginal || 0) : 0
                });
            } else if (layer.getElement) {
                const element = layer.getElement();
                if(element) {
                   element.style.opacity = opacity;
                   element.style.pointerEvents = AppState.visadaVisivel ? 'auto' : 'none';
                }
            } else if (layer._icon) { // Fallback
                 layer._icon.style.opacity = opacity;
                 layer._icon.style.pointerEvents = AppState.visadaVisivel ? 'auto' : 'none';
            }
            if(layer.options) {
                layer.options.interactive = AppState.visadaVisivel;
            }
        });
    }

    document.getElementById("btn-visada")?.classList.toggle("opacity-50", !AppState.visadaVisivel);
    console.log(`Visibilidade da visada: ${AppState.visadaVisivel ? 'Ativada' : 'Desativada'}`);
}

function setupCandidateRemovalListener() {
    if (!map) {
        console.error("Mapa não inicializado.");
        return;
    }
    
    map.on('click', function(e) {
        const targetElement = e.originalEvent.target;
        if (targetElement.classList.contains('candidate-remove-btn')) {
            console.log("Botão 'X' clicado. ID:", targetElement.dataset.markerId); 
            L.DomEvent.stop(e);

            const markerIdToRemove = targetElement.dataset.markerId;
            if (window.candidateRepeaterSitesLayerGroup && markerIdToRemove) {
                const layersToRemove = [];
                window.candidateRepeaterSitesLayerGroup.eachLayer(layer => {
                    if (layer.options?.customId === markerIdToRemove) {
                        layersToRemove.push(layer);
                    }
                });

                if (layersToRemove.length > 0) {
                    layersToRemove.forEach(layer => window.candidateRepeaterSitesLayerGroup.removeLayer(layer));
                    console.log("Candidato removido:", markerIdToRemove);
                    if (typeof mostrarMensagem === 'function') {
                        mostrarMensagem(t('messages.success.repeater_suggestion_removed'), "sucesso");
                    }
                } else {
                    console.warn("Nenhuma camada encontrada para remover com o ID:", markerIdToRemove);
                }
            }
        }
    });
}