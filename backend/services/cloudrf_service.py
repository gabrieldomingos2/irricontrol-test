import httpx
import json
from pathlib import Path
import logging

from backend.config import settings
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# --- Funções Auxiliares (sem alterações) ---

def format_coord(coord: float) -> str:
    """Formata coordenada para nomes de arquivos (igual ao JS)."""
    return f"{coord:.6f}".replace(".", "_").replace("-", "m")

async def get_http_client() -> httpx.AsyncClient:
    """Retorna um cliente HTTP assíncrono com timeout global dos settings."""
    return httpx.AsyncClient(timeout=httpx.Timeout(settings.HTTP_TIMEOUT))

async def download_image(url: str, local_image_path: Path):
    """Baixa uma imagem de uma URL e salva localmente usando pathlib."""
    logger.info(f"  -> Iniciando download da imagem de: {url}")
    try:
        local_image_path.parent.mkdir(parents=True, exist_ok=True)
        async with await get_http_client() as client:
            response = await client.get(url)
            response.raise_for_status()
        with open(local_image_path, "wb") as f:
            f.write(response.content)
        logger.info(f"  -> Imagem salva em: {local_image_path}")
    except httpx.HTTPStatusError as e:
        logger.error(f"  -> ❌ Erro HTTP ao baixar imagem de {url}: {e.response.status_code} - {e.response.text}", exc_info=True)
        raise ValueError(f"Falha ao baixar imagem de sinal. Status {e.response.status_code}")
    except Exception as e:
        logger.error(f"  -> ❌ Erro crítico no download da imagem {url}: {e}", exc_info=True)
        raise ValueError(f"Falha crítica ao baixar imagem: {e}")

def save_bounds(bounds: list, local_image_path: Path):
    """Salva os dados de bounds em um arquivo JSON, com nome derivado do path da imagem."""
    json_path = local_image_path.with_suffix(".json")
    try:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(json_path, "w") as f:
            json.dump({"bounds": bounds}, f, indent=4)
        logger.info(f"  -> Bounds salvos em: {json_path}")
    except Exception as e:
        logger.error(f"  -> ❌ Erro ao salvar bounds em {json_path}: {e}", exc_info=True)

# --- Função Principal de Simulação ---

async def run_cloudrf_simulation(
    # 👇 ALTERADO: A função agora aceita 'job_id' como o primeiro parâmetro.
    job_id: str,
    lat: float,
    lon: float,
    altura: int,
    altura_receiver: Optional[float],
    template_id: str,
    is_repeater: bool = False
) -> dict:
    """
    Executa uma simulação na CloudRF, baixa a imagem, salva os bounds e retorna os dados
    em um diretório específico para o job.
    """
    # 👇 ALTERADO: Log agora inclui o ID do job.
    logger.info(f"📡 Iniciando simulação CloudRF para job {job_id} - Template: {template_id}")
    
    tpl = settings.obter_template(template_id)
    receiver_alt_for_payload = altura_receiver if altura_receiver is not None else tpl.receiver.alt

    payload = {
        "version": "CloudRF-API-v3.24", "site": tpl.site, "network": f"Irricontrol Sim - Job {job_id[:8]}",
        "engine": 2, "coordinates": 1,
        "transmitter": { "lat": lat, "lon": lon, "alt": altura, "frq": tpl.frq, "txw": tpl.transmitter.txw, "bwi": tpl.transmitter.bwi, "powerUnit": "W" },
        "receiver": { "lat": 0, "lon": 0, "alt": receiver_alt_for_payload, "rxg": tpl.receiver.rxg, "rxs": tpl.receiver.rxs },
        "feeder": {"flt": 1, "fll": 0, "fcc": 0},
        "antenna": { "mode": "template", "txg": tpl.antenna.txg, "txl": 0, "ant": 1, "azi": 0, "tlt": 0, "hbw": 360, "vbw": 90, "fbr": tpl.antenna.fbr, "pol": "v" },
        "model": {"pm": 1, "pe": 2, "ked": 4, "rel": 95, "rcs": 1},
        "environment": {"elevation": 1, "landcover": 1, "buildings": 0, "clt": "Minimal.clt"},
        "output": { "units": "m", "col": tpl.col, "out": 2, "ber": 1, "mod": 7, "nf": -120, "res": 30, "rad": 10 }
    }

    if not settings.CLOUDRF_API_KEY:
        logger.error("❌ CLOUDRF_API_KEY não está configurada nas settings.")
        raise ValueError("API Key da CloudRF não configurada.")

    headers = {"key": settings.CLOUDRF_API_KEY, "Content-Type": "application/json"}

    logger.info(f"  -> Enviando payload para CloudRF API URL: {settings.CLOUDRF_API_URL}")
    async with await get_http_client() as client:
        try:
            resposta = await client.post(str(settings.CLOUDRF_API_URL), headers=headers, json=payload)
            resposta.raise_for_status() 
            data = resposta.json()
            logger.info("  -> Resposta recebida da CloudRF.")
        except httpx.HTTPStatusError as e:
            logger.error(f"  -> ❌ Erro HTTP na API CloudRF: {e.response.status_code} - {e.response.text}", exc_info=True)
            error_detail = e.response.text
            try:
                error_json = json.loads(e.response.text)
                if isinstance(error_json, dict) and "error" in error_json: error_detail = error_json["error"]
            except json.JSONDecodeError: pass
            raise ValueError(f"Erro na API CloudRF ({e.response.status_code}): {error_detail}")
        except Exception as e:
            logger.error(f"  -> ❌ Erro ao chamar CloudRF: {e}", exc_info=True)
            raise ValueError(f"Erro de comunicação com a API CloudRF: {e}")

    imagem_url_api = data.get("PNG_WGS84")
    bounds_data = data.get("bounds")

    if not imagem_url_api or not bounds_data:
        logger.error(f"  -> ❌ Resposta inválida da CloudRF (sem PNG_WGS84 ou bounds): {data}")
        raise ValueError("Resposta inválida da API CloudRF (não retornou URL da imagem ou bounds).")

    # 👇 ALTERADO: Lógica de salvamento de arquivos agora usa o job_id para criar o caminho
    lat_str = format_coord(lat)
    lon_str = format_coord(lon)
    prefix = "repetidora" if is_repeater else "principal"
    template_name_safe = tpl.id.lower().replace(" ", "_")
    nome_arquivo_base = f"{prefix}_{template_name_safe}_tx{altura}m_lat{lat_str}_lon{lon_str}.png"
    
    # Cria o caminho para o diretório de imagens do job específico
    job_image_dir = settings.IMAGENS_DIR_PATH / job_id
    caminho_local_imagem: Path = job_image_dir / nome_arquivo_base

    await download_image(imagem_url_api, caminho_local_imagem)
    save_bounds(bounds_data, caminho_local_imagem)

    if not settings.BACKEND_PUBLIC_URL:
        logger.warning("⚠️ settings.BACKEND_PUBLIC_URL não está configurado. A URL da imagem servida pode estar incorreta.")
        backend_url_prefix = ""
    else:
        backend_url_prefix = str(settings.BACKEND_PUBLIC_URL).rstrip('/')

    # 👇 ALTERADO: A URL pública da imagem agora inclui o job_id no caminho
    imagem_servida_url = f"{backend_url_prefix}/{settings.STATIC_DIR_NAME}/{settings.IMAGENS_DIR_NAME}/{job_id}/{nome_arquivo_base}"

    return {
        "imagem_url": imagem_servida_url,
        "imagem_local_path": str(caminho_local_imagem),
        "imagem_filename": nome_arquivo_base,
        "bounds": bounds_data
    }