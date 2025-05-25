// Variáveis globais relacionadas ao mapa
let map;
let visadaLayerGroup;
let visadaVisivel = true;

/**
 * Inicializa o mapa Leaflet, adiciona a camada de satélite
 * e o grupo de camadas para a visada.
 */
function initMap() {
    // Cria o mapa na div #map, sem o controle de zoom padrão
    map = L.map('map', {
        zoomControl: false
    }).setView([-15, -55], 5); // Centralizado no Brasil

    // Adiciona a camada de satélite do Google
    L.tileLayer('https://{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', {
        maxZoom: 20,
        subdomains: ['mt0', 'mt1', 'mt2', 'mt3']
    }).addTo(map);

    // Cria um grupo de camadas para adicionar/remover
    // elementos de visada (linhas, marcadores de bloqueio)
    visadaLayerGroup = L.layerGroup().addTo(map);

    // Adiciona o listener para o botão de visada
    const btnVisada = document.getElementById("btn-visada");
    if (btnVisada) {
        btnVisada.addEventListener("click", toggleVisada);
    } else {
        console.error("Botão #btn-visada não encontrado!");
    }
}

/**
 * Alterna a visibilidade das camadas dentro do visadaLayerGroup.
 */
function toggleVisada() {
    visadaVisivel = !visadaVisivel; // Inverte o estado

    // Percorre cada camada no grupo
    visadaLayerGroup.eachLayer(layer => {
        // Se a camada tem a função setStyle (linhas, polígonos)
        if (layer.setStyle) {
            layer.setStyle({
                opacity: visadaVisivel ? 1 : 0,
                fillOpacity: visadaVisivel ? layer.options.fillOpacity : 0 // Também esconde preenchimento se houver
            });
        }
        // Se a camada tem um ícone (marcadores)
        else if (layer.getElement) { // Método mais moderno para obter o elemento HTML
            const element = layer.getElement();
            if(element) {
               element.style.opacity = visadaVisivel ? 1 : 0;
               // Impede que o usuário interaja com marcadores escondidos
               element.style.pointerEvents = visadaVisivel ? 'auto' : 'none';
            }
        }
        // Fallback para versões mais antigas ou tipos diferentes
        else if (layer._icon) {
             layer._icon.style.opacity = visadaVisivel ? 1 : 0;
             layer._icon.style.pointerEvents = visadaVisivel ? 'auto' : 'none';
        }

        // Tenta tornar as camadas não interativas quando escondidas
        if(layer.options) {
            layer.options.interactive = visadaVisivel;
        }
    });

    // Atualiza a aparência do botão para refletir o estado
    document.getElementById("btn-visada").classList.toggle("opacity-50", !visadaVisivel);
    console.log(`Visibilidade da visada: ${visadaVisivel ? 'Ativada' : 'Desativada'}`);
}

// Nota: A função initMap() será chamada em main.js quando o DOM estiver pronto.