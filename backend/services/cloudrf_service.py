# backend/services/cloudrf_service.py

import os
import asyncio
import random
import httpx
import json
from pathlib import Path
import logging
import hashlib
from typing import Dict, Optional, Any

from backend.config import settings

logger = logging.getLogger("irricontrol")

# ---------------------- Helpers de HTTP (timeout/limites/retry) ----------------------

def _build_timeout() -> httpx.Timeout:
    """
    Constrói um httpx.Timeout a partir de settings.HTTP_TIMEOUT.
    Aceita:
        - número único (segundos)
        - dict com keys: connect/read/write/pool
        - tuple/list [connect, read, write, pool]
    Fallback: 30s global.
    """
    t = getattr(settings, "HTTP_TIMEOUT", 30.0)
    try:
        if isinstance(t, (int, float)):
            return httpx.Timeout(float(t))
        if isinstance(t, dict):
            return httpx.Timeout(
                connect=float(t.get("connect", 10.0)),
                read=float(t.get("read", 30.0)),
                write=float(t.get("write", 30.0)),
                pool=float(t.get("pool", 30.0)),
            )
        if isinstance(t, (list, tuple)):
            vals = list(t) + [30.0, 30.0, 30.0, 30.0]  # pad
            return httpx.Timeout(connect=float(vals[0]), read=float(vals[1]), write=float(vals[2]), pool=float(vals[3]))
    except Exception:
        pass
    return httpx.Timeout(30.0)

def _build_limits() -> httpx.Limits:
    max_conns = int(getattr(settings, "HTTP_MAX_CONNECTIONS", 100))
    max_keepalive = int(getattr(settings, "HTTP_MAX_KEEPALIVE", 20))
    return httpx.Limits(max_connections=max_conns, max_keepalive_connections=max_keepalive)

async def get_http_client() -> httpx.AsyncClient:
    """
    Mantém a mesma assinatura usada no projeto (é 'async' e retorna um AsyncClient).
    """
    return httpx.AsyncClient(timeout=_build_timeout(), limits=_build_limits(), http2=bool(getattr(settings, "HTTP_HTTP2", True)))

async def _request_with_retries(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    json_payload: Optional[Dict[str, Any]] = None,
    expected_ok: int | tuple = (200,),
    retries: int = 3,
    backoff_base: float = 0.35,
    **kwargs,
) -> httpx.Response:
    """
    Requisição com retry exponencial e jitter. Re-tenta em 5xx/429 e erros de rede.
    """
    if isinstance(expected_ok, int):
        expected_ok = (expected_ok,)

    for attempt in range(retries + 1):
        try:
            resp = await client.request(method.upper(), url, json=json_payload, **kwargs)
            if resp.status_code in expected_ok:
                return resp
            # HTTP status não-ok: decide se vale retry
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < retries:
                delay = backoff_base * (2 ** attempt) + random.uniform(0, 0.2)
                logger.warning("Retry %d/%d %s %s -> %s; esperando %.2fs", attempt + 1, retries, method, url, resp.status_code, delay)
                await asyncio.sleep(delay)
                continue
            resp.raise_for_status()
            return resp
        except httpx.RequestError as e:
            if attempt >= retries:
                logger.error("Falha de rede definitiva em %s %s: %s", method, url, e, exc_info=True)
                raise
            delay = backoff_base * (2 ** attempt) + random.uniform(0, 0.2)
            logger.warning("Rede falhou (%s). Tentando novamente em %.2fs (%d/%d)", type(e).__name__, delay, attempt + 1, retries)
            await asyncio.sleep(delay)
    # nunca chega aqui
    raise RuntimeError("Exaustão de tentativas em _request_with_retries")

# ----------------------------- Funções Auxiliares do Serviço -----------------------------

def format_coord(coord: float) -> str:
    """Formata uma coordenada para ser usada em nomes de arquivo."""
    return f"{coord:.6f}".replace(".", "_").replace("-", "m")

async def download_image(url: str, local_image_path: Path):
    """
    Baixa uma imagem de uma URL e salva localmente (com retry e escrita atômica).
    """
    logger.info("  -> Iniciando download da imagem: %s", url)
    tmp_path = local_image_path.with_suffix(local_image_path.suffix + ".tmp")
    try:
        local_image_path.parent.mkdir(parents=True, exist_ok=True)
        async with await get_http_client() as client:
            resp = await _request_with_retries(client, "GET", url, expected_ok=(200,), retries=3)
            content = resp.content
        # grava de forma atômica
        with open(tmp_path, "wb") as f:
            f.write(content)
        os.replace(tmp_path, local_image_path)
        logger.info("  -> Imagem salva em: %s", local_image_path)
    except Exception as e:
        # limpa temporário
        try:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
        if isinstance(e, httpx.HTTPStatusError):
            logger.error("  -> ❌ Erro HTTP ao baixar imagem %s: %s - %s", url, e.response.status_code, e.response.text, exc_info=True)
            raise ValueError(f"Falha ao baixar imagem de sinal. Status {e.response.status_code}")
        logger.error("  -> ❌ Erro no download da imagem %s: %s", url, e, exc_info=True)
        raise ValueError(f"Falha crítica ao baixar imagem: {e}")

def save_bounds(bounds: list, local_image_path: Path):
    """
    Salva os dados de 'bounds' em um arquivo .json associado à imagem (escrita atômica).
    """
    json_path = local_image_path.with_suffix(".json")
    tmp_json = json_path.with_suffix(".json.tmp")
    try:
        if not (isinstance(bounds, (list, tuple)) and len(bounds) == 4):
            raise ValueError(f"Bounds inválidos: {bounds}")
        json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp_json, "w", encoding="utf-8") as f:
            json.dump({"bounds": list(bounds)}, f, indent=4)
        os.replace(tmp_json, json_path)
        logger.info("  -> Bounds salvos em: %s", json_path)
    except Exception as e:
        try:
            if tmp_json.exists():
                tmp_json.unlink(missing_ok=True)
        except Exception:
            pass
        logger.error("  -> ❌ Erro ao salvar bounds em %s: %s", json_path, e, exc_info=True)

# --------------------------------- Lógica de Simulação/Cache ---------------------------------

async def run_cloudrf_simulation(
    lat: float,
    lon: float,
    altura: int,
    altura_receiver: Optional[float],
    template_id: str,
    is_repeater: bool = False
) -> dict:
    """
    Executa simulação de cobertura (CloudRF) com cache canônico.
    Não usa job_id aqui; apenas cache por parâmetros.
    """
    tpl = settings.obter_template(template_id)
    receiver_alt_for_payload = altura_receiver if altura_receiver is not None else tpl.receiver.alt

    # chave de cache
    cache_key_string = f"lat:{lat:.6f}-lon:{lon:.6f}-alt:{altura}-rx_alt:{receiver_alt_for_payload}-tpl:{template_id}"
    cache_hash = hashlib.sha256(cache_key_string.encode()).hexdigest()
    cache_dir = settings.SIMULATIONS_CACHE_PATH
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file_path = cache_dir / f"{cache_hash}.json"

    # CACHE HIT
    if cache_file_path.exists():
        logger.info("CACHE HIT: %s", cache_hash[:12])
        try:
            with open(cache_file_path, "r", encoding="utf-8") as f:
                cached_result = json.load(f)
            cached_image_path = Path(cached_result["imagem_local_path"])
            if cached_image_path.exists() and cached_image_path.with_suffix(".json").exists():
                logger.info(" -> Retornando dados do cache. Imagem: %s", cached_image_path.name)
                return cached_result
            logger.warning("CACHE HIT, mas arquivos físicos ausentes (%s). Re-simulando.", cached_image_path.name)
        except Exception as e:
            logger.warning("CACHE CORROMPIDO (%s). Re-simulando. Motivo: %s", cache_file_path.name, e)

    # CACHE MISS
    return await _perform_simulation_and_save_to_cache(
        lat, lon, altura, receiver_alt_for_payload, template_id, is_repeater, tpl, cache_file_path
    )

async def _perform_simulation_and_save_to_cache(
    lat: float, lon: float, altura: int, receiver_alt: Optional[float],
    template_id: str, is_repeater: bool, tpl: Any, cache_file_path: Path
) -> dict:
    """
    Chama a API CloudRF e persiste resultado no cache (imagem + bounds + json do cache).
    """
    logger.info("CACHE MISS: Simulação CloudRF (tpl=%s, lat=%.6f, lon=%.6f, alt=%dm, rx=%.2f)",
                template_id, lat, lon, altura, float(receiver_alt or 0))

    if not settings.CLOUDRF_API_KEY:
        logger.error("❌ CLOUDRF_API_KEY não está configurada nas settings.")
        raise ValueError("API Key da CloudRF não configurada.")

    payload = {
        "version": "CloudRF-API-v3.24",
        "site": tpl.site,
        "network": "Irricontrol Signal Simulation",
        "engine": 2,
        "coordinates": 1,
        "transmitter": {
            "lat": lat,
            "lon": lon,
            "alt": altura,
            "frq": tpl.frq,
            "txw": tpl.transmitter.txw,
            "bwi": tpl.transmitter.bwi,
            "powerUnit": "W"
        },
        "receiver": {
            "lat": 0, "lon": 0,
            "alt": receiver_alt,
            "rxg": tpl.receiver.rxg,
            "rxs": tpl.receiver.rxs
        },
        "feeder": {"flt": 1, "fll": 0, "fcc": 0},
        "antenna": {
            "mode": "template",
            "txg": tpl.antenna.txg,
            "txl": 0,
            "ant": 1,
            "azi": 0,
            "tlt": 0,
            "hbw": 360,
            "vbw": 90,
            "fbr": tpl.antenna.fbr,
            "pol": "v"
        },
        "model": {"pm": 1, "pe": 2, "ked": 4, "rel": 95, "rcs": 1},
        "environment": {"elevation": 1, "landcover": 1, "buildings": 0, "clt": "Minimal.clt"},
        "output": {"units": "m", "col": tpl.col, "out": 2, "ber": 1, "mod": 7, "nf": -120, "res": 30, "rad": 7}
    }

    headers = {"key": settings.CLOUDRF_API_KEY, "Content-Type": "application/json"}

    async with await get_http_client() as client:
        try:
            resp = await _request_with_retries(
                client, "POST", str(settings.CLOUDRF_API_URL),
                json_payload=payload, expected_ok=(200,), retries=3
            )
            data = resp.json()
        except httpx.HTTPStatusError as e:
            logger.error("  -> ❌ Erro HTTP CloudRF: %s - %s", e.response.status_code, e.response.text, exc_info=True)
            raise ValueError(f"Erro na API CloudRF ({e.response.status_code}): {e.response.text}")
        except Exception as e:
            logger.error("  -> ❌ Erro ao chamar CloudRF: %s", e, exc_info=True)
            raise ValueError(f"Erro de comunicação com a API CloudRF: {e}")

    imagem_url_api = data.get("PNG_WGS84")
    bounds_data = data.get("bounds")
    if not imagem_url_api or not bounds_data:
        raise ValueError("Resposta inválida da API CloudRF (sem URL da imagem ou bounds).")

    # filename descritivo/único
    lat_str = format_coord(lat)
    lon_str = format_coord(lon)
    prefix = "repetidora" if is_repeater else "principal"
    template_name_safe = str(tpl.id).lower().replace(" ", "_")
    nome_arquivo_base = f"{prefix}_{template_name_safe}_tx{altura}m_lat{lat_str}_lon{lon_str}.png"

    caminho_local_imagem: Path = settings.SIMULATIONS_CACHE_PATH / nome_arquivo_base

    await download_image(imagem_url_api, caminho_local_imagem)
    save_bounds(bounds_data, caminho_local_imagem)

    result_to_cache = {
        "imagem_local_path": str(caminho_local_imagem),
        "imagem_filename": nome_arquivo_base,
        "bounds": bounds_data
    }

    # grava cache JSON de forma atômica
    tmp_cache = cache_file_path.with_suffix(cache_file_path.suffix + ".tmp")
    try:
        with open(tmp_cache, "w", encoding="utf-8") as f:
            json.dump(result_to_cache, f, indent=4)
        os.replace(tmp_cache, cache_file_path)
        logger.info(" -> Resultado salvo no cache: %s", cache_file_path.name)
    except Exception as e:
        try:
            if tmp_cache.exists():
                tmp_cache.unlink(missing_ok=True)
        except Exception:
            pass
        logger.warning(" -> Não consegui escrever cache (%s): %s", cache_file_path, e)

    return result_to_cache