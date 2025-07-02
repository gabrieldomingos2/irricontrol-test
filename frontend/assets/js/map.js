// map.js

let map;
let visadaLayerGroup;
let visadaVisivel = true; // Assumindo que esta variável é usada em toggleVisada

/**
 * Inicializa o mapa Leaflet, adiciona a camada de satélite
 * e o grupo de camadas para a visada.
 */
function initMap() {
    map = L.map('map', {
        zoomControl: false
    }).setView([-15, -55], 5);

    L.tileLayer('https://{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', {
        maxZoom: 20,
        subdomains: ['mt0', 'mt1', 'mt2', 'mt3']
    }).addTo(map);

    visadaLayerGroup = L.layerGroup().addTo(map); // [cite: 1]

    if (!window.candidateRepeaterSitesLayerGroup) {
        window.candidateRepeaterSitesLayerGroup = L.layerGroup().addTo(map); // [cite: 1]
        console.log("candidateRepeaterSitesLayerGroup inicializado e adicionado ao mapa."); // [cite: 1]
    }

    const btnVisada = document.getElementById("btn-visada"); // [cite: 1]
    if (btnVisada) {
        btnVisada.addEventListener("click", toggleVisada); // [cite: 1]
    } else {
        console.error("Botão #btn-visada não encontrado!"); // [cite: 1]
    }

    // --- NOVO: Chamar a função para configurar o listener de remoção ---
    setupCandidateRemovalListener(); // [cite: 1]
    // --- FIM NOVO ---
}

/**
 * Alterna a visibilidade das camadas dentro do visadaLayerGroup.
 */
function toggleVisada() {
    // Supondo que o código original para toggleVisada esteja aqui.
    // Exemplo de como poderia ser, baseado nos seus logs anteriores:
    visadaVisivel = !visadaVisivel; 
    visadaLayerGroup.eachLayer(layer => {
        if (layer.setStyle) {
            layer.setStyle({
                opacity: visadaVisivel ? 1 : 0,
                fillOpacity: visadaVisivel ? (layer.options.fillOpacityOriginal || 0) : 0 // Preserva opacidade original
            });
        } else if (layer.getElement) {
            const element = layer.getElement();
            if(element) {
               element.style.opacity = visadaVisivel ? 1 : 0;
               element.style.pointerEvents = visadaVisivel ? 'auto' : 'none';
            }
        } else if (layer._icon) { // Fallback
             layer._icon.style.opacity = visadaVisivel ? 1 : 0;
             layer._icon.style.pointerEvents = visadaVisivel ? 'auto' : 'none';
        }
        if(layer.options) {
            layer.options.interactive = visadaVisivel;
        }
    });
    // Atualizar botão (exemplo)
    const btnVisadaElement = document.getElementById("btn-visada");
    if(btnVisadaElement) {
       btnVisadaElement.classList.toggle("opacity-50", !visadaVisivel);
    }
    console.log(`Visibilidade da visada: ${visadaVisivel ? 'Ativada' : 'Desativada'}`);
}

// A função setupCandidateRemovalListener() deve estar definida neste arquivo
// ou ser importada/carregada antes de map.js se estiver em outro arquivo.
// Assumindo que está no mesmo arquivo, como na sua última estrutura:
function setupCandidateRemovalListener() {
    if (!map) {
        console.error("Mapa não inicializado ao tentar configurar listener de remoção.");
        return;
    }
    console.log("Configurando listener de remoção de candidatos..."); 

    map.on('click', function(e) {
        const targetElement = e.originalEvent.target;
        // console.log("Clique no mapa capturado. Elemento alvo:", targetElement); 

        if (targetElement.classList.contains('candidate-remove-btn')) {
            console.log("Botão 'X' (candidate-remove-btn) CLICADO. ID do dataset:", targetElement.dataset.markerId); 

            L.DomEvent.stopPropagation(e); 
            L.DomEvent.preventDefault(e);  

            const markerIdToRemove = targetElement.dataset.markerId;
            
            if (window.candidateRepeaterSitesLayerGroup && markerIdToRemove) {
                const layersToRemove = [];
                let foundCount = 0; 
                window.candidateRepeaterSitesLayerGroup.eachLayer(layer => {
                    if (layer.options && layer.options.customId === markerIdToRemove) {
                        layersToRemove.push(layer);
                        foundCount++;
                    }
                });

                console.log(`Encontradas ${foundCount} camadas para remover com ID ${markerIdToRemove}.`); 

                if (layersToRemove.length > 0) {
                    layersToRemove.forEach(layer => {
                        window.candidateRepeaterSitesLayerGroup.removeLayer(layer);
                    });
                    console.log("Candidato e sua linha associada removidos:", markerIdToRemove);
                    if (typeof mostrarMensagem === 'function') { 
                        mostrarMensagem(t('messages.success.repeater_suggestion_removed'), "sucesso");
                    } else {
                        console.log("Sugestão de repetidora removida (mostrarMensagem não disponível em map.js).");
                    }
                } else {
                    console.warn("Nenhuma camada encontrada para remover com o ID:", markerIdToRemove);
                }
            } else {
                console.warn("window.candidateRepeaterSitesLayerGroup não definido ou markerIdToRemove está vazio.");
            }
        }
    });
}