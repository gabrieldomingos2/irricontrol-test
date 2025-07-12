// assets/js/api.js

const isLocal = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1";
const BACKEND_URL = isLocal ? "http://localhost:8000" : "https://irricontrol-test.onrender.com";
const API_PREFIX = "/api/v1";

/**
 * ✅ NOVO WRAPPER CENTRALIZADO PARA REQUISIÇÕES
 * Esta função lida com toda a lógica comum de chamadas à API:
 * - Monta a URL completa.
 * - Realiza a chamada fetch.
 * - Verifica se a resposta foi bem-sucedida (erros de rede, 4xx, 5xx).
 * - Processa a resposta (JSON ou blob para downloads).
 * - Centraliza o tratamento de erros.
 * @param {string} endpoint - O endpoint da API (ex: '/kmz/processar').
 * @param {object} options - As opções para a chamada fetch (method, headers, body, etc.).
 * @returns {Promise<any>} - A resposta da API, já processada.
 */
async function apiRequest(endpoint, options = {}) {
  try {
    const response = await fetch(`${BACKEND_URL}${API_PREFIX}${endpoint}`, options);

    // Centraliza a verificação de erros HTTP (4xx, 5xx)
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ 
          detail: response.statusText || 'Erro de comunicação com o servidor' 
      }));
      // Lança um erro claro para ser pego pelo .catch() da função chamadora
      throw new Error(`Erro ${response.status}: ${errorData.detail}`);
    }
    
    // Tratamento especial para respostas que não são JSON, como downloads de arquivos
    if (options.responseType === 'blob') {
        return response; // Retorna o objeto de resposta completo para ser tratado
    }

    // Para a maioria dos casos, retorna o JSON já processado
    return await response.json();
  } catch (error) {
    // Loga o erro em baixo nível e o re-lança para que o contexto específico possa tratá-lo
    console.error(`Erro na requisição para ${endpoint}:`, error);
    throw error;
  }
}

// --- Funções da API Refatoradas para Usar o Wrapper ---
// Note como cada função agora é mais curta e focada em seu propósito,
// delegando a lógica de comunicação para o apiRequest.

async function startEmptyJob() {
  return apiRequest('/kmz/iniciar_job_vazio', { method: 'POST' })
    .catch(error => {
      mostrarMensagem(`Não foi possível iniciar uma nova sessão: ${error.message}`, "erro");
      throw error;
    });
}

async function processKmz(formData) {
  return apiRequest('/kmz/processar', { method: 'POST', body: formData })
    .catch(error => {
      mostrarMensagem(`Falha ao carregar KMZ: ${error.message}`, "erro");
      throw error;
    });
}

async function simulateSignal(payload) {
  return apiRequest('/simulation/run_main', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  }).catch(error => {
    mostrarMensagem(`Falha na simulação: ${error.message}`, "erro");
    throw error;
  });
}

async function simulateManual(payload) {
  return apiRequest('/simulation/run_manual', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  }).catch(error => {
    mostrarMensagem(`Falha na simulação manual: ${error.message}`, "erro");
    throw error;
  });
}

async function reevaluatePivots(payload) {
  return apiRequest('/simulation/reevaluate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  }).catch(error => {
    mostrarMensagem(`Falha ao reavaliar cobertura: ${error.message}`, "erro");
    throw error;
  });
}

async function getTemplates() {
  return apiRequest('/simulation/templates')
    .catch(error => {
        mostrarMensagem(`Falha ao buscar templates: ${error.message}`, "erro");
        throw error;
    });
}

async function getElevationProfile(payload) {
  return apiRequest('/simulation/elevation_profile', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  }).catch(error => {
    mostrarMensagem(`Falha no diagnóstico de visada: ${error.message}`, "erro");
    throw error;
  });
}

async function exportKmz(payload) {
  try {
    const response = await apiRequest('/kmz/exportar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      responseType: 'blob' 
    });

    const disposition = response.headers.get('content-disposition');
    let filename = 'estudo-irricontrol.kmz';
    if (disposition?.includes('attachment')) {
      const filenameMatch = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/.exec(disposition);
      if (filenameMatch?.[1]) {
        filename = filenameMatch[1].replace(/['"]/g, '');
      }
    }

    const blob = await response.blob();
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
    mostrarMensagem(`Falha ao exportar KMZ: ${error.message}`, "erro");
    throw error;
  }
}

async function findHighPointsForRepeater(payload) {
  return apiRequest('/simulation/find_repeater_sites', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  }).catch(error => {
    mostrarMensagem(`Falha na busca por locais de repetidora: ${error.message}`, "erro");
    throw error;
  });
}

async function generatePivotInCircle(payload) {
  return apiRequest('/simulation/generate_pivot_in_circle', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  }).catch(error => {
    mostrarMensagem(`Falha ao criar pivô: ${error.message}`, "erro");
    throw error;
  });
}

async function optimizeNetwork(payload) {
  return apiRequest('/simulation/optimize-network', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  }).catch(error => {
    mostrarMensagem(`Falha na otimização da rede: ${error.message}`, "erro"); // Adicionada mensagem de erro
    throw error;
  });
}