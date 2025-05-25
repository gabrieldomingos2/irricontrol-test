const BACKEND_URL = "https://irricontrol-test.onrender.com"; // Mude se necessário (ex: http://127.0.0.1:8000)

/**
 * Envia o arquivo KMZ para processamento no backend.
 * @param {FormData} formData - O formulário contendo o arquivo.
 * @returns {Promise<object>} - A resposta da API (dados da antena, pivôs, etc.).
 */
async function processKmz(formData) {
  try {
    const response = await fetch(`${BACKEND_URL}/processar_kmz`, {
      method: "POST",
      body: formData,
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(`Erro ${response.status}: ${errorData.erro || response.statusText}`);
    }
    return await response.json();
  } catch (error) {
    console.error("Erro ao processar KMZ:", error);
    throw error; // Re-lança o erro para ser tratado por quem chamou
  }
}

/**
 * Envia os dados da antena principal para simular o sinal.
 * @param {object} payload - Dados da antena e pivôs.
 * @returns {Promise<object>} - A resposta da API (imagem, bounds, status pivôs).
 */
async function simulateSignal(payload) {
  try {
    const response = await fetch(`${BACKEND_URL}/simular_sinal`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(`Erro ${response.status}: ${errorData.erro || response.statusText}`);
    }
    return await response.json();
  } catch (error) {
    console.error("Erro ao simular sinal:", error);
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
    const response = await fetch(`${BACKEND_URL}/simular_manual`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
     if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(`Erro ${response.status}: ${errorData.erro || response.statusText}`);
    }
    return await response.json();
  } catch (error) {
    console.error("Erro ao simular manual:", error);
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
    const response = await fetch(`${BACKEND_URL}/reavaliar_pivos`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
     if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(`Erro ${response.status}: ${errorData.erro || response.statusText}`);
    }
    return await response.json();
  } catch (error) {
    console.error("Erro ao reavaliar pivôs:", error);
    throw error;
  }
}

/**
 * Busca a lista de templates disponíveis no backend.
 * @returns {Promise<Array<string>>} - Um array com os nomes dos templates.
 */
async function getTemplates() {
  try {
    const response = await fetch(`${BACKEND_URL}/templates`);
    if (!response.ok) {
        throw new Error(`Erro ${response.status}: ${response.statusText}`);
    }
    return await response.json();
  } catch (error) {
    console.error("Erro ao buscar templates:", error);
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
    const response = await fetch(`${BACKEND_URL}/perfil_elevacao`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
     if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(`Erro ${response.status}: ${errorData.erro || response.statusText}`);
    }
    return await response.json();
  } catch (error) {
    console.error("Erro ao buscar perfil de elevação:", error);
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
    // A função original formatava aqui, mas agora recebe os nomes prontos.
    // Apenas montamos a URL.
    return `${BACKEND_URL}/exportar_kmz?imagem=${encodeURIComponent(imagem)}&bounds_file=${encodeURIComponent(boundsFile)}`;
}

/**
 * Retorna a URL para o ícone da torre.
 * @returns {string} - URL do ícone.
 */
function getTowerIconUrl() {
    return `${BACKEND_URL}/icone-torre`; // Usava /icone-torre antes
}

/**
 * Retorna a URL para o ícone da bomba.
 * @returns {string} - URL do ícone.
 */
function getPumpIconUrl() {
    return `${BACKEND_URL}/static/imagens/homegardenbusiness.png`;
}