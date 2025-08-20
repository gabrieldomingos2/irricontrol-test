import re
from PIL import Image
import httpx
import requests  # Adicionado para downloads
from math import sqrt, radians, sin, cos, atan2
from typing import List, Dict, Optional, Union, TypedDict, Tuple, Any
from pathlib import Path
import logging
import asyncio
import hashlib
import json

# DEM / geoprocessamento
import rasterio
import rasterio.mask
from rasterio.warp import calculate_default_transform, reproject, Resampling
import numpy as np
from scipy.ndimage import maximum_filter
from shapely.geometry import Point, Polygon, box

from backend.config import settings
from backend.services import cloudrf_service
from backend.services.i18n_service import i18n_service
from fastapi.concurrency import run_in_threadpool

# Configuração do Logger
logger = logging.getLogger("irricontrol")

# ------------------------------ Constantes de ajuste ------------------------------
ALPHA_THRESHOLD = 50         # opacidade mínima do pixel p/ considerar área coberta
ELEVATION_STEPS = 50         # nº de segmentos no perfil (gera 51 amostras)
MAX_LOS_TASKS = 64           # limite de análises LOS por chamada (protege API externa)
# ---------------------------------------------------------------------------------

# --- Tipos Personalizados ---
class PivoInputData(TypedDict, total=False):
    nome: str
    lat: float
    lon: float
    type: str
    fora: Optional[bool]

class OverlayInputData(TypedDict):
    id: Optional[str]
    imagem_path: Union[str, Path]
    bounds: Tuple[float, float, float, float]  # (S, W, N, E)

class ElevationPoint(TypedDict):
    lat: float
    lon: float
    elev: Optional[float]
    dist: float

class BlockageInfo(TypedDict):
    lat: float
    lon: float
    elev: float
    diff: float
    dist: float

class ElevationProfileResult(TypedDict):
    perfil: List[ElevationPoint]
    bloqueio: Optional[BlockageInfo]
    ponto_mais_alto: Dict[str, Optional[float]]

class CandidateSite(TypedDict):
    lat: float
    lon: float
    elevation: float
    has_los: bool
    distance_to_target: float
    ponto_bloqueio: Optional[Union[BlockageInfo, Dict[str, str]]]
    altura_necessaria_torre: Optional[float]


# --- Funções Auxiliares ---
def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distância em metros entre dois pontos geográficos."""
    R = 6371000  # m
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi / 2)**2 + cos(phi1) * cos(phi2) * sin(dlambda / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c


def _check_coverage_sync(
    entities: List[Dict[str, Any]],
    overlays_info: List[OverlayInputData],
    signal_sources: List[Dict[str, float]]
) -> List[Dict[str, Any]]:
    """
    Verifica cobertura usando overlays RGBA (canal alpha) + zona de segurança de proximidade.
    (Síncrona; é rodada no threadpool.)
    """
    logger.info("🔎 (Thread) Verificando cobertura para %d entidades com %d fontes de sinal.",
                len(entities), len(signal_sources))
    imagens_abertas_cache: Dict[Path, Image.Image] = {}
    entities_atualizadas: List[Dict[str, Any]] = []

    PROXIMITY_THRESHOLD_METERS = 20.0

    try:
        for entity_data in entities:
            entity_data_atualizado = entity_data.copy()
            lat, lon = entity_data["lat"], entity_data["lon"]
            coberto = False

            # 1) Zona de segurança (próximo à fonte)
            for source in signal_sources:
                distance = haversine(lat, lon, source['lat'], source['lon'])
                if distance < PROXIMITY_THRESHOLD_METERS:
                    coberto = True
                    logger.info("  -> 🎯 '%s' dentro da zona de segurança (%.1fm).", entity_data.get('nome', '<sem nome>'), distance)
                    break

            if coberto:
                entity_data_atualizado["fora"] = False
                entities_atualizadas.append(entity_data_atualizado)
                continue

            # 2) Teste de cobertura por pixel alpha
            for overlay_data in overlays_info:
                bounds = list(overlay_data["bounds"])
                if len(bounds) != 4:
                    logger.warning("  -> ⚠️ Bounds inválidos para overlay: %s", bounds)
                    continue

                # Normaliza (S,W,N,E)
                s, w, n, e = bounds
                if s > n:
                    s, n = n, s
                if w > e:
                    w, e = e, w

                imagem_path = Path(overlay_data["imagem_path"])

                if not imagem_path.is_file():
                    logger.warning("  -> ⚠️ Imagem não encontrada: %s. Pulando overlay.", imagem_path)
                    continue

                try:
                    if imagem_path not in imagens_abertas_cache:
                        imagens_abertas_cache[imagem_path] = Image.open(imagem_path).convert("RGBA")

                    pil_image = imagens_abertas_cache[imagem_path]
                    img_width, img_height = pil_image.size

                    delta_lon = e - w
                    delta_lat = n - s
                    if delta_lon == 0 or delta_lat == 0:
                        continue

                    pixel_x = int(((lon - w) / delta_lon) * img_width)
                    pixel_y = int(((n - lat) / delta_lat) * img_height)

                    if 0 <= pixel_x < img_width and 0 <= pixel_y < img_height:
                        _, _, _, alpha = pil_image.getpixel((pixel_x, pixel_y))
                        if alpha > ALPHA_THRESHOLD:
                            coberto = True
                            break
                except Exception as ex:
                    logger.error("  -> ❌ Erro ao analisar overlay p/ '%s': %s",
                                entity_data.get('nome', '<sem nome>'), ex, exc_info=True)

            entity_data_atualizado["fora"] = not coberto
            entities_atualizadas.append(entity_data_atualizado)
    finally:
        for img_obj in imagens_abertas_cache.values():
            try:
                img_obj.close()
            except Exception:
                pass

    logger.info("  -> (Thread) Concluída verificação de %d entidades.", len(entities))
    return entities_atualizadas


async def verificar_cobertura_pivos(
    pivos: List[Dict[str, Any]],
    overlays_info: List[OverlayInputData],
    signal_sources: List[Dict[str, float]]
) -> List[Dict[str, Any]]:
    """Verifica cobertura de pivôs no threadpool."""
    logger.info("Delegando verificação de %d pivôs p/ threadpool.", len(pivos))
    return await run_in_threadpool(
        _check_coverage_sync, entities=pivos, overlays_info=overlays_info, signal_sources=signal_sources
    )


async def verificar_cobertura_bombas(
    bombas: List[Dict[str, Any]],
    overlays_info: List[OverlayInputData],
    signal_sources: List[Dict[str, float]]
) -> List[Dict[str, Any]]:
    """Verifica cobertura de bombas no threadpool."""
    logger.info("Delegando verificação de %d bombas p/ threadpool.", len(bombas))
    return await run_in_threadpool(
        _check_coverage_sync, entities=bombas, overlays_info=overlays_info, signal_sources=signal_sources
    )


async def obter_perfil_elevacao(pontos: List[Tuple[float, float]], alt1: float, alt2: float) -> ElevationProfileResult:
    """
    Perfil de elevação entre 2 pontos (ordem importa, pois alt1/alt2 são aplicadas nos extremos).
    Usa cache local para reduzir chamadas à API.
    """
    if len(pontos) != 2:
        raise ValueError("São necessários exatamente dois pontos para o perfil de elevação.")

    # Chave de cache preserva a ORDEM dos pontos
    cache_key_string = (
        f"p1:{pontos[0][0]:.6f},{pontos[0][1]:.6f}|"
        f"p2:{pontos[1][0]:.6f},{pontos[1][1]:.6f}|"
        f"alt1:{alt1}|alt2:{alt2}"
    )
    cache_hash = hashlib.sha256(cache_key_string.encode()).hexdigest()
    cache_dir = settings.ELEVATION_CACHE_PATH
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file_path = cache_dir / f"{cache_hash}.json"

    if cache_file_path.exists():
        logger.info("CACHE HIT: perfil %s", cache_hash[:12])
        with open(cache_file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    num_passos = ELEVATION_STEPS
    logger.info("CACHE MISS: calculando perfil (%d passos) entre %s e %s.",
                num_passos, pontos[0], pontos[1])

    pontos_amostrados = [
        (pontos[0][0] + (pontos[1][0] - pontos[0][0]) * i / num_passos,
         pontos[0][1] + (pontos[1][1] - pontos[0][1]) * i / num_passos)
        for i in range(num_passos + 1)
    ]

    coords_param_str = "|".join([f"{lat:.6f},{lon:.6f}" for lat, lon in pontos_amostrados])
    url_api_elevacao = f"https://api.opentopodata.org/v1/srtm90m?locations={coords_param_str}&interpolation=cubic"

    async with await cloudrf_service.get_http_client() as client:
        try:
            response = await client.get(url_api_elevacao, timeout=20.0)
            response.raise_for_status()
            dados_api = response.json()
        except httpx.HTTPStatusError as e_http:
            logger.error("❌ Falha HTTP elevacao: %s %s", e_http.response.status_code, e_http.response.text, exc_info=True)
            raise ValueError(f"Falha ao buscar dados de elevação (HTTP {e_http.response.status_code}).")
        except httpx.RequestError as e_req:
            logger.error("❌ Erro de rede elevacao: %s", e_req, exc_info=True)
            raise ValueError(f"Falha na comunicação com a API de elevação: {e_req}")
        except Exception as e_geral:
            logger.error("❌ Erro geral elevacao: %s", e_geral, exc_info=True)
            raise ValueError(f"Falha na comunicação com a API de elevação: {e_geral}")

    results = (dados_api or {}).get("results") or []
    if len(results) != len(pontos_amostrados):
        raise ValueError(f"Resposta de elevação inesperada (esperado {len(pontos_amostrados)}, veio {len(results)}).")

    elevacoes_terreno = [res.get("elevation") for res in results]
    if any(e is None for e in elevacoes_terreno):
        raise ValueError("Dados de elevação inválidos (valor 'null' encontrado).")

    logger.info("  -> Elevações (Min: %.1fm, Max: %.1fm)", min(elevacoes_terreno), max(elevacoes_terreno))

    elevacao_total_ponto1 = elevacoes_terreno[0] + alt1
    elevacao_total_ponto2 = elevacoes_terreno[-1] + alt2
    linha_visada_elev = [
        elevacao_total_ponto1 + i * (elevacao_total_ponto2 - elevacao_total_ponto1) / num_passos
        for i in range(num_passos + 1)
    ]

    ponto_bloqueio: Optional[BlockageInfo] = None
    max_diferenca_bloqueio = 0.0

    for i in range(1, num_passos):
        elev_terreno_atual = elevacoes_terreno[i]
        elev_visada_atual = linha_visada_elev[i]
        if elev_terreno_atual > elev_visada_atual:
            diferenca = elev_terreno_atual - elev_visada_atual
            if diferenca > max_diferenca_bloqueio:
                max_diferenca_bloqueio = diferenca
                ponto_bloqueio = {
                    "lat": pontos_amostrados[i][0],
                    "lon": pontos_amostrados[i][1],
                    "elev": float(elev_terreno_atual),
                    "diff": float(diferenca),
                    "dist": i / num_passos
                }

    idx_elev_max = int(np.argmax(elevacoes_terreno))
    ponto_mais_alto: Dict[str, Optional[float]] = {
        "lat": pontos_amostrados[idx_elev_max][0],
        "lon": pontos_amostrados[idx_elev_max][1],
        "elev": float(elevacoes_terreno[idx_elev_max])
    }

    perfil_final: List[ElevationPoint] = [
        {"lat": pontos_amostrados[i][0], "lon": pontos_amostrados[i][1],
            "elev": float(elevacoes_terreno[i]), "dist": i / num_passos}
        for i in range(num_passos + 1)
    ]

    final_result: ElevationProfileResult = {
        "perfil": perfil_final,
        "bloqueio": ponto_bloqueio,
        "ponto_mais_alto": ponto_mais_alto
    }
    with open(cache_file_path, "w", encoding="utf-8") as f:
        json.dump(final_result, f, indent=4)
    logger.info(" -> Perfil salvo no cache: %s", cache_file_path.name)
    return final_result


def _download_file(url: str, output_path: Path) -> None:
    """Faz o download de um arquivo de forma robusta."""
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)  # garante pasta
        with requests.get(url, stream=True, timeout=90) as r:
            r.raise_for_status()
            with open(output_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        logger.info("    -> (DEM) Download concluído: %s", output_path)
    except requests.RequestException as e:
        logger.error("    -> (DEM) ❌ Falha no download de %s: %s", url, e)
        raise IOError(f"Falha ao baixar o arquivo de elevação: {e}")


def _download_and_clip_dem(bounds_dem_wgs84: Tuple[float, float, float, float], output_dem_path: Path) -> None:
    """
    Baixa o DEM de uma fonte pública (AWS) e recorta usando Rasterio.
    Muito mais robusto que a biblioteca 'elevation'.
    """
    min_lon, min_lat, max_lon, max_lat = bounds_dem_wgs84

    # URL do tile de 1 grau de arco SRTM (fonte: https://registry.opendata.aws/terrain-tiles/)
    dem_source_url = "https://s3.amazonaws.com/elevation-tiles-prod/skadi/{N}{W}/{N}{W}.hgt.gz"  # mantido para referência

    # Simplificado: assume que a área está contida num único tile de 1x1 grau.
    # Para áreas maiores, seria necessário um mosaico.
    lat_tile = int(np.floor(min_lat))
    lon_tile = int(np.floor(min_lon))

    N_S = 'N' if lat_tile >= 0 else 'S'
    W_E = 'W' if lon_tile < 0 else 'E'
    lat_str = f"{abs(lat_tile):02d}"
    lon_str = f"{abs(lon_tile):03d}"

    tile_url = f"https://elevation-tiles-prod.s3.amazonaws.com/skadi/{N_S}{lat_str}/{N_S}{lat_str}{W_E}{lon_str}.hgt.gz"

    dem_temp_dir = output_dem_path.parent / "temp"
    dem_temp_dir.mkdir(parents=True, exist_ok=True)
    temp_gz_path = dem_temp_dir / f"{N_S}{lat_str}{W_E}{lon_str}.hgt.gz"

    logger.info("    -> (DEM) Baixando tile de elevação de: %s", tile_url)
    _download_file(tile_url, temp_gz_path)

    try:
        logger.info("    -> (DEM) Recortando tile para os limites da área...")
        geom = box(min_lon, min_lat, max_lon, max_lat)

        with rasterio.open(f"gzip://{temp_gz_path}") as src:
            out_image, out_transform = rasterio.mask.mask(src, [geom], crop=True)
            out_meta = src.meta.copy()

        out_meta.update({
            "driver": "GTiff", "height": out_image.shape[1],
            "width": out_image.shape[2], "transform": out_transform,
            "compress": "deflate"
        })

        with rasterio.open(output_dem_path, "w", **out_meta) as dest:
            dest.write(out_image)

        logger.info("    -> (DEM) Arquivo DEM recortado e salvo em: %s", output_dem_path)

    except Exception as e:
        logger.error("    -> (DEM) ❌ Falha ao recortar o DEM com Rasterio: %s", e, exc_info=True)
        raise IOError(f"Falha ao processar o arquivo DEM: {e}")
    finally:
        # Limpa o arquivo temporário
        try:
            temp_gz_path.unlink(missing_ok=True)
        except Exception:
            pass


async def obter_dem_para_area_geografica(
    lat_central: float, lon_central: float, raio_busca_km: float,
    resolucao_desejada_m: Optional[float] = 90
) -> Tuple[np.ndarray, rasterio.Affine, rasterio.crs.CRS, Optional[Any]]:
    logger.info("  -> (DEM) Obtendo DEM para (%.4f, %.4f), raio: %.1fkm",
                lat_central, lon_central, raio_busca_km)
    dem_cache_dir = settings.ARQUIVOS_DIR_PATH / "dem_cache"
    dem_cache_dir.mkdir(parents=True, exist_ok=True)

    raio_busca_m = raio_busca_km * 1000
    graus_lat_por_metro = 1.0 / 111000.0
    graus_lon_por_metro_aprox = 1.0 / (111000.0 * cos(radians(lat_central)))
    offset_lat = raio_busca_m * graus_lat_por_metro
    offset_lon = raio_busca_m * graus_lon_por_metro_aprox

    bounds_dem_wgs84 = (
        lon_central - offset_lon, lat_central - offset_lat,
        lon_central + offset_lon, lat_central + offset_lat
    )

    nome_arquivo_dem = f"dem_clip_lat{lat_central:.4f}_lon{lon_central:.4f}_r{int(raio_busca_m)}m.tif"
    nome_arquivo_dem = nome_arquivo_dem.replace(".", "_").replace("-", "m")
    path_arquivo_dem_local = dem_cache_dir / nome_arquivo_dem

    try:
        if not path_arquivo_dem_local.exists():
            await run_in_threadpool(_download_and_clip_dem, bounds_dem_wgs84, path_arquivo_dem_local)
        else:
            logger.info("    -> (DEM) Usando DEM do cache: %s", path_arquivo_dem_local)

        def _read_rasterio_dem(path: Path) -> Tuple[np.ndarray, rasterio.Affine, rasterio.crs.CRS, Optional[Any]]:
            with rasterio.open(path) as src:
                dem_array = src.read(1)
                dem_transform = src.transform
                dem_crs = src.crs
                dem_nodata = src.nodata
                return dem_array, dem_transform, dem_crs, dem_nodata

        return await run_in_threadpool(_read_rasterio_dem, path_arquivo_dem_local)
    except (FileNotFoundError, NotImplementedError, IOError) as e_dem_specific:
        logger.error("  -> ❌ Erro específico ao obter DEM: %s", e_dem_specific, exc_info=True)
        raise
    except Exception as e:
        logger.error("  -> ❌ Erro crítico ao obter/processar DEM: %s", e, exc_info=True)
        raise FileNotFoundError(f"Falha crítica ao obter DEM para a área: {e}")


async def encontrar_locais_altos_para_repetidora(
    alvo_lat: float, alvo_lon: float, alvo_nome: str,
    altura_antena_repetidora_proposta: float, altura_receptor_pivo: float,
    active_overlays_data: List[OverlayInputData],
    pivot_polygons_coords_data: Optional[List[List[Tuple[float, float]]]] = None
) -> List[CandidateSite]:

    logger.info("🔎 Buscando locais de repetidora para pivô '%s' (%.5f, %.5f)",
                alvo_nome, alvo_lat, alvo_lon)
    if not active_overlays_data:
        return []

    # Constrói polígonos (se fornecidos) para evitar sugerir pontos dentro dos pivôs existentes
    shapely_pivot_polygons: List[Polygon] = []
    if pivot_polygons_coords_data:
        for i, poly_coords_list in enumerate(pivot_polygons_coords_data):
            # coords recebidas como [(lat, lon), ...] -> shapely usa (lon, lat)
            shapely_coords = [(lon, lat) for (lat, lon) in poly_coords_list]
            if len(shapely_coords) >= 3:
                try:
                    shapely_pivot_polygons.append(Polygon(shapely_coords))
                except Exception as e_shapely:
                    logger.warning("  -> ⚠️ Erro ao criar polígono Shapely p/ ciclo %d: %s", i + 1, e_shapely)
            else:
                logger.warning("  -> ⚠️ Coords insuficientes (%d) p/ formar polígono de pivô %d. Pulando.",
                                len(shapely_coords), i + 1)

    # Bounds totais das imagens ativas (normalizados)
    min_s, min_w = float('inf'), float('inf')
    max_n, max_e = float('-inf'), float('-inf')
    for ov in active_overlays_data:
        s, w, n, e = ov['bounds']
        if s > n:
            s, n = n, s
        if w > e:
            w, e = e, w
        min_s, min_w = min(min_s, s), min(min_w, w)
        max_n, max_e = max(max_n, n), max(max_e, e)
    if any(val in (float('inf'), float('-inf')) for val in [min_s, max_n, min_w, max_e]):
        raise ValueError("Limites de overlays ativos inválidos para busca de repetidoras.")

    dem_center_lat = (min_s + max_n) / 2
    dem_center_lon = (min_w + max_e) / 2
    dist_w = haversine(dem_center_lat, min_w, dem_center_lat, max_e)
    dist_h = haversine(min_s, dem_center_lon, max_n, dem_center_lon)
    dem_search_radius_km = (sqrt(dist_w**2 + dist_h**2) / 2000) + 0.5  # meia diagonal + margem

    try:
        dem_array, dem_transform, dem_crs, dem_nodata_val = await obter_dem_para_area_geografica(
            dem_center_lat, dem_center_lon, dem_search_radius_km, resolucao_desejada_m=90
        )
    except (FileNotFoundError, NotImplementedError, IOError):
        # Propaga — quem chamou decide a mensagem/HTTP
        raise

    candidate_sites_list: List[CandidateSite] = []
    imagens_overlay_pil_cache: Dict[Path, Image.Image] = {}
    MAX_DIST_REPETIDORA_ALVO_M = 1800.0
    TAM_FILTRO_PICO = 5

    try:
        # Picos locais no DEM
        dem_picos = dem_array.copy().astype(np.float32)
        if dem_nodata_val is not None:
            dem_picos[dem_array == dem_nodata_val] = np.nan

        valores_picos = maximum_filter(dem_picos, size=TAM_FILTRO_PICO, mode='constant', cval=np.nan)
        mascara_picos = (dem_picos == valores_picos) & (~np.isnan(dem_picos))
        ys, xs = np.where(mascara_picos)
        xs_lon, ys_lat = rasterio.transform.xy(dem_transform, ys, xs, offset='center')

        tasks = []
        candidate_points_data = []

        for idx, (peak_lon, peak_lat) in enumerate(zip(xs_lon, ys_lat)):
            elev_pico = dem_picos[ys[idx], xs[idx]]

            # Cobertura pela imagem (alpha)
            esta_em_area_sinal = False
            for ov in active_overlays_data:
                overlay_imagem_path = Path(ov['imagem_path'])
                if not overlay_imagem_path.is_file():
                    continue
                try:
                    if overlay_imagem_path not in imagens_overlay_pil_cache:
                        imagens_overlay_pil_cache[overlay_imagem_path] = Image.open(overlay_imagem_path).convert("RGBA")
                    pil_img = imagens_overlay_pil_cache[overlay_imagem_path]
                    ov_w, ov_h = pil_img.size
                    s, w, n, e = ov['bounds']
                    if s > n:
                        s, n = n, s
                    if w > e:
                        w, e = e, w
                    dlon, dlat = e - w, n - s
                    if dlon == 0 or dlat == 0:
                        continue
                    px = int(((peak_lon - w) / dlon) * ov_w)
                    py = int(((n - peak_lat) / dlat) * ov_h)
                    if 0 <= px < ov_w and 0 <= py < ov_h and pil_img.getpixel((px, py))[3] > ALPHA_THRESHOLD:
                        esta_em_area_sinal = True
                        break
                except Exception as e_img:
                    logger.warning("    -> ❌ Erro verif. overlay %s: %s", overlay_imagem_path.name, e_img)

            if not esta_em_area_sinal:
                continue

            dist_alvo_m = haversine(alvo_lat, alvo_lon, peak_lat, peak_lon)
            if dist_alvo_m > MAX_DIST_REPETIDORA_ALVO_M:
                continue

            if shapely_pivot_polygons:
                ponto_shp = Point(peak_lon, peak_lat)
                if any(poly.contains(ponto_shp) for poly in shapely_pivot_polygons):
                    continue

            tasks.append(obter_perfil_elevacao(
                pontos=[(peak_lat, peak_lon), (alvo_lat, alvo_lon)],
                alt1=altura_antena_repetidora_proposta,
                alt2=altura_receptor_pivo
            ))
            candidate_points_data.append({
                "lat": float(peak_lat),
                "lon": float(peak_lon),
                "elevation": float(elev_pico),
                "distance_to_target": float(dist_alvo_m)
            })

        # Limita rajada de chamadas externas
        if len(tasks) > MAX_LOS_TASKS:
            logger.warning(" -> Reduzindo análises de LOS: %d -> %d (cap)", len(tasks), MAX_LOS_TASKS)
            tasks = tasks[:MAX_LOS_TASKS]
            candidate_points_data = candidate_points_data[:MAX_LOS_TASKS]

        if tasks:
            logger.info(" -> Disparando %d análises de perfil/LOS em paralelo...", len(tasks))
            los_results = await asyncio.gather(*tasks, return_exceptions=True)

            for i, result in enumerate(los_results):
                point_data = candidate_points_data[i]
                if isinstance(result, Exception):
                    tem_los = False
                    info_bloq = {"error_calculating_los": str(result)}
                    altura_torre = None
                else:
                    perfil_result = result
                    tem_los = perfil_result.get("bloqueio") is None
                    info_bloq = perfil_result.get("bloqueio")
                    altura_torre = None
                    if not tem_los and info_bloq and isinstance(info_bloq.get("diff"), (int, float)):
                        altura_torre = float(info_bloq["diff"]) + 3.0  # margem

                candidate_sites_list.append({
                    **point_data,
                    "has_los": tem_los,
                    "ponto_bloqueio": info_bloq,
                    "altura_necessaria_torre": altura_torre
                })

    except Exception as e_proc:
        logger.error("  -> ❌ Erro durante processamento dos picos/LOS: %s", e_proc, exc_info=True)
    finally:
        for img in imagens_overlay_pil_cache.values():
            try:
                img.close()
            except Exception:
                pass

    # Ordena: preferir LOS, depois maior elevação, depois menor distância
    candidate_sites_list.sort(key=lambda s: (
        not s["has_los"],
        -(s.get("elevation", -float('inf'))),
        s.get("distance_to_target", float('inf'))
    ))

    return candidate_sites_list[:25]


def _find_next_pivot_number(pivos: List[PivoInputData]) -> int:
    max_number = 0
    regex = re.compile(r'(\d+)$')
    for pivo in pivos:
        match = regex.search(pivo.get('nome', ''))
        if match:
            number = int(match.group(1))
            if number > max_number:
                max_number = number
    return max_number + 1


def generate_pivot_at_center(
    center_lat: float,
    center_lon: float,
    existing_pivos: List[PivoInputData],
    lang: str = 'pt-br'
) -> PivoInputData:
    """Gera um novo pivô no ponto central com nome sequencial traduzido."""
    logger.info("💡 Gerando novo pivô em (%.6f, %.6f) no idioma '%s'.",
                center_lat, center_lon, lang)

    next_num = _find_next_pivot_number(existing_pivos)
    t = i18n_service.get_translator(lang)
    pivot_base_name = t("entity_names.pivot")
    new_pivot_name = f"{pivot_base_name} {next_num}"

    logger.info("  -> Nome do novo pivô: '%s'", new_pivot_name)

    return {
        "nome": new_pivot_name,
        "lat": center_lat,
        "lon": center_lon,
        "type": "pivo",
        "fora": None
    }