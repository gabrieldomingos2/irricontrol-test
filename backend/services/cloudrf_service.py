# backend/services/cloudrf_service.py

import httpx
import json
from pathlib import Path
import logging
import hashlib
from typing import Dict, Optional, Any

from backend.config import settings

logger = logging.getLogger("irricontrol")

# --- Funções Auxiliares ---

def format_coord(coord: float) -> str:
    """Formata uma coordenada para ser usada em nomes de arquivo."""
    return f"{coord:.6f}".replace(".", "_").replace("-", "m")

async def get_http_client() -> httpx.AsyncClient:
    """Retorna um cliente HTTP assíncrono com timeout padrão."""
    return httpx.AsyncClient(timeout=httpx.Timeout(settings.HTTP_TIMEOUT))

async def download_image(url: str, local_image_path: Path):
    """
    Baixa uma imagem de uma URL e a salva em um caminho local.
    """
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
    """
    Salva os dados de 'bounds' em um arquivo .json associado à imagem.
    """
    json_path = local_image_path.with_suffix(".json")
    try:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump({"bounds": bounds}, f, indent=4)
        logger.info(f"  -> Bounds salvos em: {json_path}")
    except Exception as e:
        logger.error(f"  -> ❌ Erro ao salvar bounds em {json_path}: {e}", exc_info=True)


# --- Lógica Principal de Simulação e Cache ---

async def run_cloudrf_simulation(
    lat: float,
    lon: float,
    altura: int,
    altura_receiver: Optional[float],
    template_id: str,
    is_repeater: bool = False
) -> dict:
    """
    Executa uma simulação de cobertura, utilizando um sistema de cache para evitar requisições repetidas.
    O serviço é agnóstico ao 'job_id', operando apenas com o cache canônico.
    """
    tpl = settings.obter_template(template_id)
    receiver_alt_for_payload = altura_receiver if altura_receiver is not None else tpl.receiver.alt

    # Gera uma chave de cache única baseada nos parâmetros da simulação.
    cache_key_string = f"lat:{lat:.6f}-lon:{lon:.6f}-alt:{altura}-rx_alt:{receiver_alt_for_payload}-tpl:{template_id}"
    cache_hash = hashlib.sha256(cache_key_string.encode()).hexdigest()
    cache_file_path = settings.SIMULATIONS_CACHE_PATH / f"{cache_hash}.json"

    # CACHE HIT: Verifica se o resultado já existe no cache.
    if cache_file_path.exists():
        logger.info(f"CACHE HIT: Encontrado resultado em cache com hash: {cache_hash[:12]}")
        with open(cache_file_path, "r", encoding="utf-8") as f:
            cached_result = json.load(f)
        
        # Validação de integridade do cache: verifica se os arquivos físicos existem.
        cached_image_path = Path(cached_result["imagem_local_path"])
        if cached_image_path.exists() and cached_image_path.with_suffix(".json").exists():
            logger.info(f" -> Retornando dados do cache. Imagem canônica: {cached_image_path}")
            return cached_result
        else:
            logger.warning(f"CACHE HIT, mas arquivos físicos ('{cached_image_path.name}') não encontrados. Forçando nova simulação.")
            # Se os arquivos não existem, o cache está corrompido e uma nova simulação será executada.

    # CACHE MISS: Se não encontrou no cache ou estava corrompido, executa a simulação.
    return await _perform_simulation_and_save_to_cache(
        lat, lon, altura, receiver_alt_for_payload, template_id, is_repeater, tpl, cache_file_path
    )


async def _perform_simulation_and_save_to_cache(
    lat: float, lon: float, altura: int, receiver_alt: Optional[float],
    template_id: str, is_repeater: bool, tpl: Any, cache_file_path: Path
) -> dict:
    """
    Função auxiliar que executa a simulação na API CloudRF e salva o resultado no cache.
    """
    logger.info(f"CACHE MISS: Iniciando simulação CloudRF - Template: {template_id}")
    
    # Payload para a API CloudRF com um nome de rede genérico.
    payload = {
        "version": "CloudRF-API-v3.24", "site": tpl.site, "network": "Irricontrol Signal Simulation",
        "engine": 2, "coordinates": 1,
        "transmitter": { "lat": lat, "lon": lon, "alt": altura, "frq": tpl.frq, "txw": tpl.transmitter.txw, "bwi": tpl.transmitter.bwi, "powerUnit": "W" },
        "receiver": { "lat": 0, "lon": 0, "alt": receiver_alt, "rxg": tpl.receiver.rxg, "rxs": tpl.receiver.rxs },
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
    async with await get_http_client() as client:
        try:
            resposta = await client.post(str(settings.CLOUDRF_API_URL), headers=headers, json=payload)
            resposta.raise_for_status() 
            data = resposta.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"  -> ❌ Erro HTTP na API CloudRF: {e.response.status_code} - {e.response.text}", exc_info=True)
            raise ValueError(f"Erro na API CloudRF ({e.response.status_code}): {e.response.text}")
        except Exception as e:
            logger.error(f"  -> ❌ Erro ao chamar CloudRF: {e}", exc_info=True)
            raise ValueError(f"Erro de comunicação com a API CloudRF: {e}")

    imagem_url_api = data.get("PNG_WGS84")
    bounds_data = data.get("bounds")
    if not imagem_url_api or not bounds_data:
        raise ValueError("Resposta inválida da API CloudRF (não retornou URL da imagem ou bounds).")

    # Gera um nome de arquivo descritivo e único para os parâmetros da simulação.
    lat_str = format_coord(lat)
    lon_str = format_coord(lon)
    prefix = "repetidora" if is_repeater else "principal"
    template_name_safe = tpl.id.lower().replace(" ", "_")
    nome_arquivo_base = f"{prefix}_{template_name_safe}_tx{altura}m_lat{lat_str}_lon{lon_str}.png"
    
    # Salva a imagem e os bounds diretamente no diretório de cache.
    caminho_local_imagem: Path = settings.SIMULATIONS_CACHE_PATH / nome_arquivo_base

    await download_image(imagem_url_api, caminho_local_imagem)
    save_bounds(bounds_data, caminho_local_imagem)
    
    # O dicionário de resultado salvo no cache contém apenas informações agnósticas.
    result_to_cache = {
        "imagem_local_path": str(caminho_local_imagem),
        "imagem_filename": nome_arquivo_base,
        "bounds": bounds_data
    }
    
    with open(cache_file_path, "w", encoding="utf-8") as f:
        json.dump(result_to_cache, f, indent=4)
    logger.info(f" -> Resultado da simulação salvo no cache em: {cache_file_path.name}")

    return result_to_cache
