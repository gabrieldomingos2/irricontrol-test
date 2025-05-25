// ATENÇÃO AQUI: Verifique se esta URL é EXATAMENTE a URL do seu serviço no Render.
// Se o seu serviço no Render se chama 'meu-simulador-irrigacao',
// a URL seria 'https://meu-simulador-irrigacao.onrender.com'
const BACKEND_URL = "https://meu-irricontrol-api.onrender.com";

/**
 * Envia o arquivo KMZ para processamento no backend.
 * @param {FormData} formData - O formulário contendo o arquivo.
 * @returns {Promise<object>} - A resposta da API (dados da antena, pivôs, etc.).
 */
async function processKmz(formData) {
  try {
    // A URL final será: BACKEND_URL + "/kmz/processar"
    // Ex: "https://meu-servico.onrender.com/kmz/processar"
    const response = await fetch(`${BACKEND_URL}/kmz/processar`, {
      method: "POST",
      body: formData,
    });
    if (!response.ok) {
        // Se for "Not Found" (404), o erro cairá aqui.
        const errorData = await response.json().catch(() => ({ detail: response.statusText }));
        throw new Error(`Erro ${response.status}: ${errorData.detail || response.statusText}`);
    }
    return await response.json();
  } catch (error) {
    console.error("Erro ao processar KMZ:", error);
    mostrarMensagem(`Falha ao carregar KMZ: ${error.message}`, "erro"); // Adiciona feedback visual
    throw error;
  }
}

/**
 * Envia os dados da antena principal para simular o sinal.
 * @param {object} payload - Dados da antena e pivôs.
 * @returns {Promise<object>} - A resposta da API (imagem, bounds, status pivôs).
 */
async function simulateSignal(payload) {
  try {
    // A URL final será: BACKEND_URL + "/simulation/run_main"
    const response = await fetch(`${BACKEND_URL}/simulation/run_main`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: response.statusText }));
        throw new Error(`Erro ${response.status}: ${errorData.detail || response.statusText}`);
    }
    return await response.json();
  } catch (error) {
    console.error("Erro ao simular sinal:", error);
    mostrarMensagem(`Falha na simulação: ${error.message}`, "erro");
    throw error;
  }
}

/**
 * Envia dados para simular uma repetidora manual.
 * @param {object} payload - Dados da repetidora (lat, lon, altura, pivôs, template).
 * @returns {Promise<object>} - A resposta da API (imagem, bounds, status pivôs).
 */
async function simulateManual(payload) {
  try {
    // A URL final será: BACKEND_URL + "/simulation/run_manual"
    const response = await fetch(`${BACKEND_URL}/simulation/run_manual`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
     if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: response.statusText }));
        throw new Error(`Erro ${response.status}: ${errorData.detail || response.statusText}`);
    }
    return await response.json();
  } catch (error) {
    console.error("Erro ao simular manual:", error);
    mostrarMensagem(`Falha na simulação manual: ${error.message}`, "erro");
    throw error;
  }
}

/**
 * Reavalia os pivôs com base nos overlays visíveis.
 * @param {object} payload - Dados dos pivôs e overlays.
 * @returns {Promise<object>} - A resposta da API (status pivôs atualizado).
 */
async function reevaluatePivots(payload) {
  try {
    // A URL final será: BACKEND_URL + "/simulation/reevaluate"
    const response = await fetch(`${BACKEND_URL}/simulation/reevaluate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
     if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: response.statusText }));
        throw new Error(`Erro ${response.status}: ${errorData.detail || response.statusText}`);
    }
    return await response.json();
  } catch (error) {
    console.error("Erro ao reavaliar pivôs:", error);
    mostrarMensagem(`Falha ao reavaliar cobertura: ${error.message}`, "erro");
    throw error;
  }
}

/**
 * Busca a lista de templates disponíveis no backend.
 * @returns {Promise<Array<string>>} - Um array com os nomes dos templates.
 */
async function getTemplates() {
  try {
    // A URL final será: BACKEND_URL + "/simulation/templates"
    const response = await fetch(`${BACKEND_URL}/simulation/templates`);
    if (!response.ok) {
        // Se o templates não carregar, o erro pode ser aqui.
        throw new Error(`Erro ${response.status}: ${response.statusText} ao buscar templates.`);
    }
    return await response.json();
  } catch (error) {
    console.error("Erro ao buscar templates:", error);
    mostrarMensagem(`Falha ao buscar templates: ${error.message}`, "erro");
    throw error;
  }
}

/**
 * Busca o perfil de elevação entre dois pontos.
 * @param {object} payload - Dados dos pontos e alturas.
 * @returns {Promise<object>} - A resposta da API (ponto de bloqueio, elevações).
 */
async function getElevationProfile(payload) {
  try {
    // A URL final será: BACKEND_URL + "/simulation/elevation_profile"
    const response = await fetch(`${BACKEND_URL}/simulation/elevation_profile`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
     if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: response.statusText }));
        throw new Error(`Erro ${response.status}: ${errorData.detail || response.statusText}`);
    }
    return await response.json();
  } catch (error) {
    console.error("Erro ao buscar perfil de elevação:", error);
    mostrarMensagem(`Falha no diagnóstico de visada: ${error.message}`, "erro");
    throw error;
  }
}

/**
 * Gera a URL para baixar o arquivo KMZ exportado.
 * @param {string} imagem - Nome do arquivo de imagem principal.
 * @param {string} boundsFile - Nome do arquivo JSON de bounds.
 * @returns {string} - A URL completa para download.
 */
function getExportKmzUrl(imagem, boundsFile) {
    // A URL final será: BACKEND_URL + "/kmz/exportar?imagem=...&bounds_file=..."
    return `${BACKEND_URL}/kmz/exportar?imagem=${encodeURIComponent(imagem)}&bounds_file=${encodeURIComponent(boundsFile)}`;
}

function getTowerIconUrl() {
    // A URL final será: BACKEND_URL + "/kmz/icone-torre"
    return `${BACKEND_URL}/kmz/icone-torre`;
}

function getPumpIconUrl() {
    // A URL final será: BACKEND_URL + "/static/imagens/homegardenbusiness.png"
    return `${BACKEND_URL}/static/imagens/homegardenbusiness.png`;
}