// ATENÇÃO AQUI: Verifique se esta URL é EXATAMENTE a URL do seu serviço no Render.
// Se o seu serviço no Render se chama 'meu-simulador-irrigacao',
// a URL seria 'https://meu-simulador-irrigacao.onrender.com'
const BACKEND_URL = "https://irricontrol-test.onrender.com";
const API_PREFIX = "/api/v1"; // Defina o prefixo da sua API aqui

/**
 * Envia o arquivo KMZ para processamento no backend.
 * @param {FormData} formData - O formulário contendo o arquivo.
 * @returns {Promise<object>} - A resposta da API (dados da antena, pivôs, etc.).
 */
async function processKmz(formData) {
  try {
    const response = await fetch(`${BACKEND_URL}${API_PREFIX}/kmz/processar`, {
      method: "POST",
      body: formData,
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: response.statusText }));
        throw new Error(`Erro ${response.status}: ${errorData.detail || response.statusText}`);
    }
    return await response.json();
  } catch (error) {
    console.error("Erro ao processar KMZ:", error);
    mostrarMensagem(`Falha ao carregar KMZ: ${error.message}`, "erro");
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
    const response = await fetch(`${BACKEND_URL}${API_PREFIX}/simulation/run_main`, {
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
    const response = await fetch(`${BACKEND_URL}${API_PREFIX}/simulation/run_manual`, {
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
    const response = await fetch(`${BACKEND_URL}${API_PREFIX}/simulation/reevaluate`, {
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
    const response = await fetch(`${BACKEND_URL}${API_PREFIX}/simulation/templates`);
    if (!response.ok) {
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
    const response = await fetch(`${BACKEND_URL}${API_PREFIX}/simulation/elevation_profile`, {
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
 * @param {Array<object>} [repetidorasData=[]] - Array de objetos com os dados detalhados das repetidoras.
 * @returns {string} - A URL completa para download.
 */
function getExportKmzUrl(imagem, boundsFile, repetidorasData = []) {
    // Constrói a URL base com os parâmetros da imagem principal
    let url = `${BACKEND_URL}${API_PREFIX}/kmz/exportar?imagem=${encodeURIComponent(imagem)}&bounds_file=${encodeURIComponent(boundsFile)}`;

    // Se houver dados de repetidoras, os processa
    if (repetidorasData.length > 0) {
        // Converte o array de objetos para uma string JSON.
        // Ex: [{...}, {...}] -> "[{...},{...}]"
        const jsonString = JSON.stringify(repetidorasData);

        // Adiciona a string JSON à URL como um único parâmetro chamado 'repetidoras_data',
        // que é o nome que o backend espera agora.
        url += `&repetidoras_data=${encodeURIComponent(jsonString)}`;
    }

    return url;
}

/**
 * Busca pontos altos próximos a um pivô alvo para posicionar repetidoras.
 * @param {object} payload - Dados do pivô alvo e parâmetros de busca.
 * @returns {Promise<object>} - A resposta da API (locais candidatos, etc.).
 */
async function findHighPointsForRepeater(payload) {
  try {
    const response = await fetch(`${BACKEND_URL}${API_PREFIX}/simulation/find_repeater_sites`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(`Erro ${response.status}: ${errorData.detail || response.statusText}`);
    }
    return await response.json();
  } catch (error)
 {
    console.error("Erro ao buscar pontos altos para repetidora:", error);
    mostrarMensagem(`Falha na busca por locais de repetidora: ${error.message}`, "erro");
    throw error;
  }
}