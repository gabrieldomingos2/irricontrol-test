// assets/js/3d_analysis.js

window.Analysis3D = (() => {
const modal         = document.getElementById('modal-3d-analysis');
const mapContainer  = document.getElementById('map-3d-container');
const chartCanvas   = document.getElementById('profile-chart-canvas');

  // SLIDERS (torre e receiver) — suporta vertical novo e fallback antigo
const towerSlider =
    document.getElementById('tower-height-slider-vertical') ||
    document.getElementById('tower-height-slider');

const towerValueEl =
    document.getElementById('tower-height-value-vertical') ||
    document.getElementById('tower-height-value');

const receiverSlider =
    document.getElementById('receiver-height-slider-vertical') ||
    document.getElementById('receiver-height-slider');

const receiverValueEl =
    document.getElementById('receiver-height-value-vertical') ||
    document.getElementById('receiver-height-value');

const closeBtn = document.getElementById('close-3d-modal-btn');

    let map3d, profileChart;
    let terrainData = [];
    let receiverHeight = 3;  // será sobrescrito pelo último estudo no show()
    let towerHeight = 5;     // idem

  // --- Funções Auxiliares (Círculos, etc.) ---
function destination(lat, lon, distance, bearing) {
    const R = 6378137;
    const toRad = (deg) => (deg * Math.PI) / 180;
    const toDeg = (rad) => (rad * 180) / Math.PI;
    const brng = toRad(bearing);
    const lat1 = toRad(lat);
    const lon1 = toRad(lon);
    const lat2 = Math.asin(Math.sin(lat1) * Math.cos(distance / R) + Math.cos(lat1) * Math.sin(distance / R) * Math.cos(brng));
    const lon2 = lon1 + Math.atan2(Math.sin(brng) * Math.sin(distance / R) * Math.cos(lat1), Math.cos(distance / R) - Math.sin(lat1) * Math.sin(lat2));
    return [toDeg(lon2), toDeg(lat2)];
}

function generateCircleCoords(center, radius, points = 64) {
    const coords = [];
    for (let i = 0; i < points; i++) {
    const bearing = (i / points) * 360;
    coords.push(destination(center.lat, center.lon, radius, bearing));
    }
    coords.push(coords[0]);
    return [coords];
}

  // --- Lógica Principal ---
function drawFeaturesOn3DMap(features) {
    if (!map3d || !features) return;
    const circleFeatures = [];
    (features.pivos || []).forEach(pivo => {
    if (pivo.tipo === 'custom' && Array.isArray(pivo.coordenadas)) {
        const coords = pivo.coordenadas.map(c => [c[1], c[0]]);
        circleFeatures.push({ type: 'Feature', geometry: { type: 'Polygon', coordinates: [coords] } });
    } else if (pivo.raio) {
        const center = { lat: pivo.circle_center_lat || pivo.lat, lon: pivo.circle_center_lon || pivo.lon };
        const coordinates = generateCircleCoords(center, pivo.raio);
        circleFeatures.push({ type: 'Feature', geometry: { type: 'Polygon', coordinates } });
    }
    });

    const source = map3d.getSource('pivots-source');
    if (source) {
    source.setData({ type: 'FeatureCollection', features: circleFeatures });
    } else {
    map3d.addSource('pivots-source', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: circleFeatures }
    });
    }

    if (!map3d.getLayer('pivots-layer-line')) {
    map3d.addLayer({
        id: 'pivots-layer-line',
        type: 'line',
        source: 'pivots-source',
        paint: { 'line-color': '#FF4136', 'line-width': 2, 'line-opacity': 0.8 }
    });
    }
}

  function calculateLineOfSight(startHeight /* tower */) {
    const startElev = terrainData[0].elev + startHeight;
    const endElev   = terrainData[terrainData.length - 1].elev + receiverHeight;
    let isBlocked = false;

    const losPoints = terrainData.map((point, index) => {
        const progress = index / (terrainData.length - 1);
        const losElevation = startElev + progress * (endElev - startElev);
        if (point.elev > losElevation) isBlocked = true;
        return losElevation;
    });

    return { points: losPoints, isBlocked };
}

function updateVisualization(newTowerHeight = null) {
    if (newTowerHeight != null) towerHeight = newTowerHeight;

    // Atualiza labels dos sliders se existirem
    if (towerValueEl)    towerValueEl.textContent    = `${Number(towerHeight).toFixed(0)} m`;
    if (receiverValueEl) receiverValueEl.textContent = `${Number(receiverHeight).toFixed(0)} m`;

    // Recalcula a LoS com os valores atuais
    const losData = calculateLineOfSight(Number(towerHeight));

    if (profileChart) {
        profileChart.data.datasets[1].data = losData.points;
        profileChart.data.datasets[1].borderColor = losData.isBlocked ? '#ef4444' : '#22c55e';
        profileChart.update('none');
    }
    if (map3d && map3d.getLayer('los-line-layer')) {
        map3d.setPaintProperty('los-line-layer', 'line-color', losData.isBlocked ? '#ef4444' : '#22c55e');
    }
  }

function initMapbox(initialData, initialLos, featuresToDraw) {
    mapboxgl.accessToken = 'pk.eyJ1IjoiMzYzMzUzMzZnYSIsImEiOiJjbWVsaHZmN2YwaGZvMmxwemtyOHlzczNwIn0.V6Y5GLafCzXd6Bnqjtu89Q';
    map3d = new mapboxgl.Map({
        container: mapContainer,
        style: 'mapbox://styles/mapbox/satellite-streets-v12',
        center: [initialData[0].lon, initialData[0].lat],
        zoom: 14,
    });

    map3d.on('load', () => {
        map3d.addSource('mapbox-dem', { 'type': 'raster-dem', 'url': 'mapbox://mapbox.mapbox-terrain-dem-v1' });
        map3d.setTerrain({ 'source': 'mapbox-dem', 'exaggeration': 1.5 });

        const startPoint = [initialData[0].lon, initialData[0].lat];
        const endPoint   = [initialData[initialData.length - 1].lon, initialData[initialData.length - 1].lat];

        new mapboxgl.Marker({ color: '#22c55e', scale: 0.8 }).setLngLat(startPoint).addTo(map3d);
        new mapboxgl.Marker({ color: '#f87171', scale: 0.8 }).setLngLat(endPoint).addTo(map3d);

    map3d.addSource('los-line-source', {
        'type': 'geojson',
        'data': { 'type': 'Feature', 'geometry': { 'type': 'LineString', 'coordinates': [startPoint, endPoint] } }
    });

    map3d.addLayer({
        'id': 'los-line-layer',
        'type': 'line',
        'source': 'los-line-source',
        'layout': { 'line-join': 'round', 'line-cap': 'round' },
        'paint': {
            'line-color': initialLos.isBlocked ? '#ef4444' : '#22c55e',
            'line-width': 4,
            'line-dasharray': [2, 2]
        }
        });

        drawFeaturesOn3DMap(featuresToDraw);

        const bounds = new mapboxgl.LngLatBounds(startPoint, endPoint);
        map3d.fitBounds(bounds, { padding: { top: 100, bottom: 100, left: 50, right: 50 } });
    });
}

function initChart(initialLos) {
    if (profileChart) profileChart.destroy();

    const startPoint = L.latLng(terrainData[0].lat, terrainData[0].lon);
    const endPoint   = L.latLng(terrainData[terrainData.length - 1].lat, terrainData[terrainData.length - 1].lon);
    const totalDistance = startPoint.distanceTo(endPoint);

    const labels = terrainData.map(p => (p.dist * totalDistance).toFixed(0) + 'm');
    const terrainElevations = terrainData.map(p => p.elev);

    profileChart = new Chart(chartCanvas, {
    type: 'line',
    data: {
        labels,
        datasets: [{
            label: t('ui.chart_labels.terrain'),
            data: terrainElevations,
            borderColor: 'rgba(156, 163, 175, 0.7)',
            backgroundColor: 'rgba(156, 163, 175, 0.3)',
            fill: 'start',
            pointRadius: 0,
            borderWidth: 1.5,
        }, {
            label: t('ui.chart_labels.line_of_sight'),
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
            title: { display: true, text: t('ui.chart_labels.elevation_m'), color: '#9ca3af' }
        },
        x: {
            title: { display: true, text: t('ui.chart_labels.distance_m'), color: '#9ca3af' },
            ticks: { color: '#9ca3af', maxRotation: 45, minRotation: 45 }
        }
        },
        plugins: {
            legend: { labels: { color: '#d1d5db' } }
        }
        }
    });
}

function show(profileData, initialTowerHeight, initialReceiverHeight, featuresToDraw) {
    terrainData = profileData.perfil;

    // Use exatamente os valores vindos do ÚLTIMO ESTUDO
    towerHeight    = Number(initialTowerHeight ?? towerHeight);
    receiverHeight = Number(initialReceiverHeight ?? receiverHeight);

    modal.classList.remove('hidden');

    const initialLos = calculateLineOfSight(towerHeight);

    setTimeout(() => {
        initMapbox(terrainData, initialLos, featuresToDraw);
        initChart(initialLos);
    }, 50);

    // Inicializa sliders/labels a partir do estudo
    if (towerSlider)    towerSlider.value = towerHeight;
    if (towerValueEl)   towerValueEl.textContent = `${towerHeight} m`;

    if (receiverSlider) receiverSlider.value = receiverHeight;
    if (receiverValueEl)receiverValueEl.textContent = `${receiverHeight} m`;
}

  // --- Event Listeners ---
if (towerSlider) {
    towerSlider.addEventListener('input', (e) => {
        const value = parseFloat(e.target.value);
        updateVisualization(value); // atualiza LoS com nova torre
    });
}

if (receiverSlider) {
    receiverSlider.addEventListener('input', (e) => {
      receiverHeight = parseFloat(e.target.value); // atualiza receptor
      updateVisualization();                       // recalcula com torre atual
    });
}

if (closeBtn) {
    closeBtn.addEventListener('click', () => {
    modal.classList.add('hidden');
        if (map3d) {
        map3d.remove();
        map3d = null;
    }
    if (profileChart) {
        profileChart.destroy();
        profileChart = null;
    }
    });
}

return { show };
})();
