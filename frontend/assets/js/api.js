// ATENÇÃO AQUI: Verifique se esta URL é EXATAMENTE a URL do seu serviço no Render.
const BACKEND_URL = "https://irricontrol-test.onrender.com";
const API_PREFIX = "/api/v1";


/**
 * ✅ NOVO: Inicia uma sessão de trabalho vazia no backend.
 * Esta é a função que vai "destravar" o aplicativo no início.
 * @returns {Promise<object>} - A resposta da API contendo o 'job_id'.
 */
async function startEmptyJob() {
  try {
    const response = await fetch(`${BACKEND_URL}${API_PREFIX}/kmz/iniciar_job_vazio`, {
      method: "POST",
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Falha ao iniciar sessão' }));
        throw new Error(`Erro ${response.status}: ${errorData.detail || 'Falha ao iniciar sessão'}`);
    }
    return await response.json();
  } catch (error) {
    console.error("Erro ao iniciar job vazio:", error);
    mostrarMensagem(`Não foi possível iniciar uma nova sessão: ${error.message}`, "erro");
    throw error;
  }
}


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
 * ✅ NOVO E CORRIGIDO: Envia os dados via POST para gerar e baixar o arquivo KMZ.
 * @param {object} payload - O objeto contendo todos os dados para a exportação.
 */
async function exportKmz(payload) {
  try {
    const response = await fetch(`${BACKEND_URL}${API_PREFIX}/kmz/exportar`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(`Erro ${response.status}: ${errorData.detail || 'Falha na exportação'}`);
    }

    // Pega o nome do arquivo do header da resposta
    const disposition = response.headers.get('content-disposition');
    let filename = 'estudo-irricontrol.kmz';
    if (disposition && disposition.indexOf('attachment') !== -1) {
      const filenameRegex = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/;
      const matches = filenameRegex.exec(disposition);
      if (matches != null && matches[1]) {
        filename = matches[1].replace(/['"]/g, '');
      }
    }

    // Converte a resposta em um 'blob' (arquivo binário)
    const blob = await response.blob();
    
    // Cria uma URL temporária para o arquivo e simula um clique para iniciar o download
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.style.display = 'none';
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    a.remove();

  } catch (error) {
    console.error("Erro ao exportar KMZ:", error);
    mostrarMensagem(`Falha ao exportar KMZ: ${error.message}`, "erro");
    throw error;
  }
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
 * Envia os dados para gerar um novo pivô no centro de um círculo.
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
