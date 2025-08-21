// assets/js/3d_analysis.js

// Envolvemos em um objeto para não poluir o escopo global
window.Analysis3D = (() => {
    // Referências aos elementos do DOM
    const modal = document.getElementById('modal-3d-analysis');
    const mapContainer = document.getElementById('map-3d-container');
    const chartCanvas = document.getElementById('profile-chart-canvas');
    const heightSlider = document.getElementById('tower-height-slider');
    const heightValue = document.getElementById('tower-height-value');
    const closeBtn = document.getElementById('close-3d-modal-btn');

    // Variáveis de estado do módulo
    let map3d, profileChart, terrainData = [], receiverHeight = 3;

    // Função que recalcula a linha de visada (roda 100% no cliente)
    function calculateLineOfSight(startHeight) {
        const startElev = terrainData[0].elev + startHeight;
        const endElev = terrainData[terrainData.length - 1].elev + receiverHeight;
        let isBlocked = false;

        const losPoints = terrainData.map((point, index) => {
            const progress = index / (terrainData.length - 1);
            const losElevation = startElev + progress * (endElev - startElev);
            if (point.elev > losElevation) {
                isBlocked = true;
            }
            return losElevation;
        });
        return { points: losPoints, isBlocked };
    }

    // Função que atualiza as visualizações
    function updateVisualization(newTowerHeight) {
        heightValue.textContent = `${newTowerHeight.toFixed(0)} m`;
        const losData = calculateLineOfSight(newTowerHeight);

        // Atualiza gráfico
        if (profileChart) {
            profileChart.data.datasets[1].data = losData.points;
            profileChart.data.datasets[1].borderColor = losData.isBlocked ? '#ef4444' : '#22c55e';
            profileChart.update('none');
        }

        // NOVO: Atualiza a cor da linha no mapa 3D em tempo real
        if (map3d && map3d.getLayer('los-line-layer')) {
            map3d.setPaintProperty('los-line-layer', 'line-color', losData.isBlocked ? '#ef4444' : '#22c55e');
        }
    }

    // Inicializa o mapa 3D
    function initMapbox(initialData) {
        mapboxgl.accessToken = 'pk.eyJ1IjoiMzYzMzUzMzZnYSIsImEiOiJjbWVsaHZmN2YwaGZvMmxwemtyOHlzczNwIn0.V6Y5GLafCzXd6Bnqjtu89Q';
        map3d = new mapboxgl.Map({
            container: mapContainer,
            style: 'mapbox://styles/mapbox/satellite-streets-v12',
            center: [initialData[0].lon, initialData[0].lat],
            zoom: 14,
        });

        map3d.on('load', () => {
            map3d.addSource('mapbox-dem', {
                'type': 'raster-dem',
                'url': 'mapbox://mapbox.mapbox-terrain-dem-v1',
                'tileSize': 512,
                'maxzoom': 14
            });
            map3d.setTerrain({ 'source': 'mapbox-dem', 'exaggeration': 1.5 });
            
            // NOVO: Desenha a linha e as torres no mapa
            const startPoint = [initialData[0].lon, initialData[0].lat];
            const endPoint = [initialData[initialData.length - 1].lon, initialData[initialData.length - 1].lat];

            // Marcadores para origem e alvo
            new mapboxgl.Marker({ color: '#22c55e', scale: 0.8 }).setLngLat(startPoint).addTo(map3d); // Origem (verde)
            new mapboxgl.Marker({ color: '#f87171', scale: 0.8 }).setLngLat(endPoint).addTo(map3d); // Alvo (vermelho)

            // Fonte de dados GeoJSON para a linha
            map3d.addSource('los-line-source', {
                'type': 'geojson',
                'data': {
                    'type': 'Feature',
                    'properties': {},
                    'geometry': { 'type': 'LineString', 'coordinates': [startPoint, endPoint] }
                }
            });
            
            // Camada (layer) que desenha a linha
            map3d.addLayer({
                'id': 'los-line-layer',
                'type': 'line',
                'source': 'los-line-source',
                'layout': { 'line-join': 'round', 'line-cap': 'round' },
                'paint': {
                    'line-color': '#22c55e', // Cor inicial (será atualizada)
                    'line-width': 4,
                    'line-dasharray': [2, 2] // Linha pontilhada
                }
            });
            
            // Foca o mapa na área de interesse
            const bounds = new mapboxgl.LngLatBounds(startPoint, endPoint);
            map3d.fitBounds(bounds, { padding: { top: 100, bottom: 100, left: 50, right: 50 } });
        });
    }

    // Inicializa o gráfico 2D (já estava correto)
    function initChart(initialTowerHeight) {
    if (profileChart) profileChart.destroy();

    // NOVO: Calcula a distância total em metros entre o ponto inicial e final
    const startPoint = L.latLng(terrainData[0].lat, terrainData[0].lon);
    const endPoint = L.latLng(terrainData[terrainData.length - 1].lat, terrainData[terrainData.length - 1].lon);
    const totalDistance = startPoint.distanceTo(endPoint); // Distância total em metros

    // ALTERADO: Gera as legendas do eixo X em metros
    const labels = terrainData.map(p => (p.dist * totalDistance).toFixed(0) + 'm');
    const terrainElevations = terrainData.map(p => p.elev);
    const initialLos = calculateLineOfSight(initialTowerHeight);

    profileChart = new Chart(chartCanvas, {
        type: 'line',
        data: {
            labels,
            datasets: [{
                label: 'Terreno',
                data: terrainElevations,
                borderColor: 'rgba(156, 163, 175, 0.7)',
                backgroundColor: 'rgba(156, 163, 175, 0.3)',
                fill: 'start',
                pointRadius: 0,
                borderWidth: 1.5,
            }, {
                label: 'Linha de Visada',
                data: initialLos.points,
                borderColor: initialLos.isBlocked ? '#ef4444' : '#22c55e',
                borderWidth: 3,
                pointRadius: 0,
                fill: false,
            }]
        },
        options: {
            maintainAspectRatio: false,
            scales: {
                y: {
                    title: { display: true, text: 'Elevação (m)', color: '#9ca3af' },
                    ticks: { color: '#9ca3af' }
                },
                x: {
                    // ALTERADO: Atualiza o título do eixo X
                    title: { display: true, text: 'Distância do Percurso (m)', color: '#9ca3af' },
                    ticks: { 
                        color: '#9ca3af',
                        maxRotation: 45, // Evita que os textos se sobreponham
                        minRotation: 45
                    }
                }
            },
            plugins: {
                legend: { labels: { color: '#d1d5db' } }
            }
        }
    });
}

    // Função pública para mostrar e inicializar o modal
    function show(profileData, initialTowerHeight, initialReceiverHeight) {
        terrainData = profileData.perfil;
        receiverHeight = initialReceiverHeight;

        modal.classList.remove('hidden');
        
        setTimeout(() => {
            initMapbox(terrainData);
            initChart(initialTowerHeight);
        }, 50);

        heightSlider.value = initialTowerHeight;
        heightValue.textContent = `${initialTowerHeight} m`;
    }

    // Event Listeners internos do módulo
    heightSlider.addEventListener('input', (e) => updateVisualization(parseFloat(e.target.value)));
    closeBtn.addEventListener('click', () => {
        modal.classList.add('hidden');
        if (map3d) {
            // ATUALIZADO: Limpeza completa dos recursos do Mapbox
            if (map3d.getLayer('los-line-layer')) map3d.removeLayer('los-line-layer');
            if (map3d.getSource('los-line-source')) map3d.removeSource('los-line-source');
            map3d.remove();
            map3d = null;
        }
        if (profileChart) {
            profileChart.destroy();
            profileChart = null;
        }
    });

    return { show }; // Expõe apenas a função `show`
})();