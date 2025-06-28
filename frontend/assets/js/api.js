// ATENÇÃO AQUI: Verifique se esta URL é EXATAMENTE a URL do seu serviço no Render.
const BACKEND_URL = "https://irricontrol-test.onrender.com";
const API_PREFIX = "/api/v1";

/**
 * Envia o arquivo KMZ para processamento no backend.
 * @param {FormData} formData - O formulário contendo o arquivo.
 * @returns {Promise<object>} - A resposta da API (incluindo o NOVO 'job_id').
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
 * O payload agora DEVE conter um campo 'job_id'.
 * @param {object} payload - Dados da antena, pivôs, e job_id.
 * @returns {Promise<object>} - A resposta da API.
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
 * O payload agora DEVE conter um campo 'job_id'.
 * @param {object} payload - Dados da repetidora, pivôs, job_id, etc.
 * @returns {Promise<object>} - A resposta da API.
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
 * O payload agora DEVE conter um campo 'job_id'.
 * @param {object} payload - Dados dos pivôs, overlays, e job_id.
 * @returns {Promise<object>} - A resposta da API.
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
 * @returns {Promise<object>} - A resposta da API.
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
 * 👇 ALTERADO: A função agora aceita 'jobId' como o primeiro parâmetro.
 * Gera a URL para baixar o arquivo KMZ exportado.
 * @param {string} jobId - O ID do job atual.
 * @param {string} imagem - Nome do arquivo de imagem principal.
 * @param {string} boundsFile - Nome do arquivo JSON de bounds.
 * @param {Array<object>} [repetidorasData=[]] - Array de objetos com os dados detalhados das repetidoras.
 * @returns {string} - A URL completa para download.
 */
function getExportKmzUrl(jobId, antenaPrincipalData, pivosData, ciclosData, imagem, boundsFile, repetidorasData = []) {
    if (!jobId || !antenaPrincipalData) {
        console.error("Erro fatal: Job ID e dados da antena principal são necessários para exportar.");
        mostrarMensagem("Erro: Dados da sessão ou da antena principal não encontrados para exportação.", "erro");
        return "#";
    }

    // Converte os objetos em strings JSON para enviar pela URL
    const antenaJsonString = JSON.stringify(antenaPrincipalData);
    const pivosJsonString = JSON.stringify(pivosData);
    const ciclosJsonString = JSON.stringify(ciclosData);
    const repetidorasJsonString = JSON.stringify(repetidorasData);

    // Constrói a URL completa com todos os parâmetros
    let url = new URL(`${BACKEND_URL}${API_PREFIX}/kmz/exportar`);
    url.searchParams.append('job_id', jobId);
    url.searchParams.append('imagem', imagem);
    url.searchParams.append('bounds_file', boundsFile);
    url.searchParams.append('antena_principal_data', antenaJsonString);
    url.searchParams.append('pivos_data', pivosJsonString);
    url.searchParams.append('ciclos_data', ciclosJsonString);
    url.searchParams.append('repetidoras_data', repetidorasJsonString);

    return url.toString();
}

/**
 * Busca pontos altos próximos a um pivô alvo para posicionar repetidoras.
 * O payload agora DEVE conter um campo 'job_id'.
 * @param {object} payload - Dados do pivô alvo, job_id, e parâmetros de busca.
 * @returns {Promise<object>} - A resposta da API.
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
  } catch (error) {
    console.error("Erro ao buscar pontos altos para repetidora:", error);
    mostrarMensagem(`Falha na busca por locais de repetidora: ${error.message}`, "erro");
    throw error;
  }
}

/**
 * ✅ NOVO: Envia os dados para gerar um novo pivô no centro de um círculo.
 * @param {object} payload - Contém job_id, as coordenadas do centro e a lista de pivôs atuais.
 * @returns {Promise<object>} - A resposta da API com o novo pivô.
 */
async function generatePivotInCircle(payload) {
  try {
    const response = await fetch(`${BACKEND_URL}${API_PREFIX}/simulation/generate_pivot_in_circle`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: response.statusText }));
        throw new Error(`Erro ${response.status}: ${errorData.detail || 'Erro desconhecido'}`);
    }
    return await response.json();
  } catch (error) {
    console.error("Erro ao gerar novo pivô:", error);
    mostrarMensagem(`Falha ao criar pivô: ${error.message}`, "erro");
    throw error;
  }
}

