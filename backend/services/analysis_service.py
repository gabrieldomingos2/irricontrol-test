import re
from pydantic import BaseModel
from backend.services.i18n_service import i18n_service
from backend.services.kmz_parser import normalizar_nome
from PIL import Image
import httpx
from math import sqrt, radians, sin, cos, atan2, degrees
from typing import List, Dict, Optional, Union, TypedDict, Tuple, Any, Callable
from pathlib import Path
import logging
import asyncio
import hashlib
import json

# Imports para DEM e processamento geoespacial
import rasterio
from rasterio.windows import Window
from rasterio.transform import from_origin
from rasterio.warp import calculate_default_transform, reproject, Resampling
import numpy as np
from scipy.ndimage import maximum_filter
from shapely.geometry import Point, Polygon

from backend.config import settings
from backend.services import cloudrf_service
from fastapi.concurrency import run_in_threadpool

# Configuração do Logger
logger = logging.getLogger("irricontrol")

# --- Tipos Personalizados (sem alterações, mas repetidos para contexto) ---
class PivoInputData(TypedDict, total=False):
    nome: str
    lat: float
    lon: float
    type: str
    fora: Optional[bool]

class OverlayInputData(TypedDict):
    id: Optional[str]
    imagem_path: Union[str, Path]
    bounds: Tuple[float, float, float, float]

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

# NOVO: Tipo para repetidora sugerida
class SuggestedRepeater(TypedDict):
    lat: float
    lon: float
    altura_sugerida: float
    # Você pode adicionar mais campos se a otimização determinar outros atributos
    # Ex: 'expected_coverage_increase': float

# --- Funções Auxiliares (repetidas para contexto) ---

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcula a distância em metros entre dois pontos geográficos."""
    R = 6371000  # Raio da Terra em metros
    phi1, phi2 = radians(lat1), radians(lat2)
    delta_phi = radians(lat2 - lat1)
    delta_lambda = radians(lon2 - lon1)
    a = sin(delta_phi / 2)**2 + cos(phi1) * cos(phi2) * sin(delta_lambda / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c


def _check_coverage_sync(
    entities: List[Dict[str, Any]], 
    overlays_info: List[OverlayInputData],
    signal_sources: List[Dict[str, float]]
) -> List[Dict[str, Any]]:
    """
    Função síncrona que realiza a verificação de cobertura, agora com a "zona de segurança".
    """
    logger.info(f"🔎 (Thread) Verificando cobertura para {len(entities)} entidades com {len(signal_sources)} fontes de sinal.")
    imagens_abertas_cache: Dict[Path, Image.Image] = {}
    entities_atualizadas: List[Dict[str, Any]] = []
    
    PROXIMITY_THRESHOLD_METERS = 20.0 #

    try: 
        for entity_data in entities:
            entity_data_atualizado = entity_data.copy()
            lat, lon = entity_data["lat"], entity_data["lon"]
            coberto_por_algum_overlay = False

            for source in signal_sources:
                distance = haversine(lat, lon, source['lat'], source['lon'])
                if distance < PROXIMITY_THRESHOLD_METERS:
                    coberto_por_algum_overlay = True
                    logger.info(f"  -> 🎯 '{entity_data['nome']}' está na zona de segurança da fonte em ({source['lat']:.4f}, {source['lon']:.4f}). Cobertura garantida.")
                    break
            
            if coberto_por_algum_overlay:
                entity_data_atualizado["fora"] = False
                entities_atualizadas.append(entity_data_atualizado)
                continue

            for overlay_data in overlays_info:
                bounds = overlay_data["bounds"]
                imagem_path_servidor = Path(overlay_data["imagem_path"])

                if not imagem_path_servidor.is_file():
                    logger.warning(f"  -> ⚠️ Imagem não encontrada em: {imagem_path_servidor}. Pulando overlay.")
                    continue

                try:
                    if imagem_path_servidor not in imagens_abertas_cache:
                        imagens_abertas_cache[imagem_path_servidor] = Image.open(imagem_path_servidor).convert("RGBA")

                    pil_image = imagens_abertas_cache[imagem_path_servidor]
                    img_width, img_height = pil_image.size
                    s, w, n, e = bounds

                    if s > n: s, n = n, s
                    if w > e: w, e = e, w

                    delta_lon = e - w
                    delta_lat = n - s

                    if delta_lon == 0 or delta_lat == 0:
                        continue

                    pixel_x = int(((lon - w) / delta_lon) * img_width)
                    pixel_y = int(((n - lat) / delta_lat) * img_height)

                    if 0 <= pixel_x < img_width and 0 <= pixel_y < img_height:
                        _, _, _, alpha_channel = pil_image.getpixel((pixel_x, pixel_y))
                        if alpha_channel > 50:
                            coberto_por_algum_overlay = True
                            break
                except Exception as ex:
                    logger.error(f"  -> ❌ Erro ao analisar overlay para entidade '{entity_data['nome']}': {ex}", exc_info=True)

            entity_data_atualizado["fora"] = not coberto_por_algum_overlay
            entities_atualizadas.append(entity_data_atualizado)
    finally:
        for img_obj in imagens_abertas_cache.values():
            img_obj.close()

    logger.info(f"  -> (Thread) Verificação de cobertura para {len(entities)} entidades concluída.")
    return entities_atualizadas


async def verificar_cobertura_pivos(
    pivos: List[Dict[str, Any]], 
    overlays_info: List[OverlayInputData],
    signal_sources: List[Dict[str, float]]
) -> List[Dict[str, Any]]:
    """
    Verifica a cobertura dos pivôs, delegando o trabalho síncrono para um threadpool.
    """
    logger.info(f"Delegando verificação de cobertura para {len(pivos)} pivôs para o threadpool.")
    pivos_atualizados = await run_in_threadpool(
        _check_coverage_sync, entities=pivos, overlays_info=overlays_info, signal_sources=signal_sources
    )
    return pivos_atualizados

async def verificar_cobertura_bombas(
    bombas: List[Dict], 
    overlays_info: List[OverlayInputData],
    signal_sources: List[Dict[str, float]]
) -> List[Dict]:
    """
    Verifica a cobertura das bombas, delegando o trabalho síncrono para um threadpool.
    """
    logger.info(f"Delegando verificação de cobertura para {len(bombas)} bombas para o threadpool.")
    bombas_atualizadas = await run_in_threadpool(
        _check_coverage_sync, entities=bombas, overlays_info=overlays_info, signal_sources=signal_sources
    )
    return bombas_atualizadas


async def obter_perfil_elevacao(pontos: List[Tuple[float, float]], alt1: float, alt2: float) -> ElevationProfileResult:
    if len(pontos) != 2:
        raise ValueError("São necessários exatamente dois pontos para o perfil de elevação.")

    cache_key_string = f"points:{json.dumps(sorted(pontos))}-alt1:{alt1}-alt2:{alt2}"
    cache_hash = hashlib.sha256(cache_key_string.encode()).hexdigest()
    cache_file_path = settings.ELEVATION_CACHE_PATH / f"{cache_hash}.json"

    if cache_file_path.exists():
        logger.info(f"CACHE HIT: Encontrado perfil de elevação em cache com hash: {cache_hash[:12]}")
        with open(cache_file_path, "r") as f:
            return json.load(f)

    num_passos = 50
    logger.info(f"CACHE MISS: Calculando perfil de elevação ({num_passos} passos) entre {pontos[0]} e {pontos[1]}.")

    pontos_amostrados = [
        (
            pontos[0][0] + (pontos[1][0] - pontos[0][0]) * i / num_passos,
            pontos[0][1] + (pontos[1][1] - pontos[0][1]) * i / num_passos
        )
        for i in range(num_passos + 1)
    ]

    coords_param_str = "|".join([f"{lat:.6f},{lon:.6f}" for lat, lon in pontos_amostrados])
    url_api_elevacao = f"https://api.opentopodata.org/v1/srtm90m?locations={coords_param_str}&interpolation=cubic"
    
    async with await cloudrf_service.get_http_client() as client:
        try:
            response = await client.get(url_api_elevacao)
            response.raise_for_status()
            dados_api = response.json()
        except httpx.HTTPStatusError as e_http:
            logger.error(f"  -> ❌ Erro HTTP ao buscar elevações: Status {e_http.response.status_code}, Resposta: {e_http.response.text}", exc_info=True)
            raise ValueError(f"Falha ao buscar dados de elevação (HTTP {e_http.response.status_code}).")
        except Exception as e_geral:
            logger.error(f"  -> ❌ Erro ao buscar elevações: {e_geral}", exc_info=True)
            raise ValueError(f"Falha na comunicação com a API de elevação: {e_geral}")

    if not dados_api or "results" not in dados_api or not dados_api["results"]:
        raise ValueError("Resposta inválida ou vazia da API de elevação.")

    elevacoes_terreno = [res.get("elevation") for res in dados_api["results"]]
    if any(e is None for e in elevacoes_terreno):
        raise ValueError("Dados de elevação inválidos ou ausentes recebidos da API (valor 'null' encontrado).")
    
    logger.info(f"  -> Elevações recebidas (Min: {min(elevacoes_terreno):.1f}m, Max: {max(elevacoes_terreno):.1f}m)")

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
                    "lat": pontos_amostrados[i][0], "lon": pontos_amostrados[i][1],
                    "elev": float(elev_terreno_atual), "diff": float(diferenca),
                    "dist": i / num_passos
                }

    elev_max_terreno_val = -float('inf')
    idx_elev_max_terreno = 0
    for i, elev_val in enumerate(elevacoes_terreno):
        if elev_val > elev_max_terreno_val:
            elev_max_terreno_val = elev_val
            idx_elev_max_terreno = i
            
    ponto_mais_alto_terreno: Dict[str, Optional[float]] = {
        "lat": pontos_amostrados[idx_elev_max_terreno][0],
        "lon": pontos_amostrados[idx_elev_max_terreno][1],
        "elev": float(elevacoes_terreno[idx_elev_max_terreno])
    }

    perfil_final: List[ElevationPoint] = [
        {
            "lat": pontos_amostrados[i][0], "lon": pontos_amostrados[i][1],
            "elev": float(elevacoes_terreno[i]),
            "dist": i / num_passos
        } for i in range(num_passos + 1)
    ]

    final_result = {"perfil": perfil_final, "bloqueio": ponto_bloqueio, "ponto_mais_alto": ponto_mais_alto_terreno}
    with open(cache_file_path, "w") as f:
        json.dump(final_result, f, indent=4)
    logger.info(f" -> Perfil de elevação salvo no cache em: {cache_file_path.name}")

    return final_result


def _download_and_clip_dem(bounds_dem_wgs84: Tuple[float,float,float,float], output_dem_path: Path) -> None:
    try:
        import elevation
    except ImportError:
        logger.error("A biblioteca 'elevation' não está instalada. Necessária para download automático de DEM.")
        raise NotImplementedError("Biblioteca 'elevation' não encontrada para download de DEM.")
    logger.info(f"    -> (DEM) Baixando/clipando DEM para bounds {bounds_dem_wgs84} -> {output_dem_path}")
    elevation.clip(bounds=bounds_dem_wgs84, output=str(output_dem_path), product='SRTM3')
    logger.info(f"    -> (DEM) Concluído: {output_dem_path}")


async def obter_dem_para_area_geografica(
    lat_central: float, lon_central: float, raio_busca_km: float,
    resolucao_desejada_m: Optional[float] = 90
) -> Tuple[np.ndarray, rasterio.Affine, rasterio.crs.CRS, Optional[Any]]:
    logger.info(f"  -> (DEM) Obtendo DEM para ({lat_central:.4f}, {lon_central:.4f}), raio: {raio_busca_km:.1f}km")
    dem_cache_dir = settings.ARQUIVOS_DIR_PATH / "dem_cache"
    dem_cache_dir.mkdir(parents=True, exist_ok=True)
    raio_busca_m = raio_busca_km * 1000
    graus_lat_por_metro = 1.0 / 111000.0
    graus_lon_por_metro_aprox = 1.0 / (111000.0 * cos(radians(lat_central)))
    offset_lat_graus = raio_busca_m * graus_lat_por_metro
    offset_lon_graus = raio_busca_m * graus_lon_por_metro_aprox
    bounds_dem_wgs84 = (
        lon_central - offset_lon_graus, lat_central - offset_lat_graus,
        lon_central + offset_lon_graus, lat_central + offset_lat_graus
    )
    nome_arquivo_dem = f"dem_clip_lat{lat_central:.4f}_lon{lon_central:.4f}_r{int(raio_busca_m)}m.tif"
    nome_arquivo_dem = nome_arquivo_dem.replace(".", "_").replace("-", "m")
    path_arquivo_dem_local = dem_cache_dir / nome_arquivo_dem
    try:
        if not path_arquivo_dem_local.exists():
            await run_in_threadpool(_download_and_clip_dem, bounds_dem_wgs84, path_arquivo_dem_local)
        else:
            logger.info(f"    -> (DEM) Usando DEM do cache: {path_arquivo_dem_local}")
        def _read_rasterio_dem(path: Path) -> Tuple[np.ndarray, rasterio.Affine, rasterio.crs.CRS, Optional[Any]]:
            with rasterio.open(path) as src:
                dem_array = src.read(1)
                dem_transform = src.transform
                dem_crs = src.crs
                dem_nodata = src.nodata
                return dem_array, dem_transform, dem_crs, dem_nodata
        return await run_in_threadpool(_read_rasterio_dem, path_arquivo_dem_local)
    except (FileNotFoundError, NotImplementedError) as e_dem_specific:
        logger.error(f"  -> ❌ Erro específico ao obter DEM: {e_dem_specific}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"  -> ❌ Erro crítico ao obter/processar DEM: {e}", exc_info=True)
        raise FileNotFoundError(f"Falha crítica ao obter DEM para a área: {e}")


async def encontrar_locais_altos_para_repetidora(
    alvo_lat: float, alvo_lon: float, alvo_nome: str,
    altura_antena_repetidora_proposta: float, altura_receptor_pivo: float,
    active_overlays_data: List[OverlayInputData],
    pivot_polygons_coords_data: Optional[List[List[Tuple[float, float]]]] = None
) -> List[CandidateSite]:

    logger.info(f"🔎 Buscando locais de repetidora para pivô '{alvo_nome}' ({alvo_lat:.5f}, {alvo_lon:.5f})") 
    if not active_overlays_data:
        return []
    shapely_pivot_polygons: List[Polygon] = []
    if pivot_polygons_coords_data:
        for i, poly_coords_list in enumerate(pivot_polygons_coords_data):
            shapely_coords = [(coord_pair[1], coord_pair[0]) for coord_pair in poly_coords_list]
            if len(shapely_coords) >= 3:
                try:
                    shapely_pivot_polygons.append(Polygon(shapely_coords))
                except Exception as e_shapely:
                    logger.warning(f"  -> ⚠️ Erro ao criar polígono Shapely para o ciclo {i+1}: {e_shapely}. Coords: {poly_coords_list}")
            else:
                logger.warning(f"  -> ⚠️ Coordenadas insuficientes ({len(shapely_coords)}) para formar polígono de pivô {i+1}. Pulando.")
    min_s, min_w = float('inf'), float('inf')
    max_n, max_e = float('-inf'), float('-inf')
    for ov_data in active_overlays_data:
        s, w, n, e = ov_data['bounds']
        min_s, min_w = min(min_s, s), min(min_w, w)
        max_n, max_e = max(max_n, n), max(max_e, e)
    if any(val == float('inf') or val == float('-inf') for val in [min_s, max_n, min_w, max_e]):
        raise ValueError("Limites de overlays ativos inválidos para busca de repetidoras.")
    dem_center_lat = (min_s + max_n) / 2
    dem_center_lon = (min_w + max_e) / 2
    dist_diag_width_m = haversine(dem_center_lat, min_w, dem_center_lat, max_e)
    dist_diag_height_m = haversine(min_s, dem_center_lon, max_n, dem_center_lon)
    dem_search_radius_km = (sqrt(dist_diag_width_m**2 + dist_diag_height_m**2) / 2000) + 0.5
    try:
        dem_array, dem_transform, dem_crs, dem_nodata_val = await obter_dem_para_area_geografica(
            dem_center_lat, dem_center_lon, dem_search_radius_km, resolucao_desejada_m=90
        )
    except (FileNotFoundError, NotImplementedError) as e_dem:
        raise
    candidate_sites_list: List[CandidateSite] = []
    imagens_overlay_pil_cache: Dict[Path, Image.Image] = {}
    MAX_DIST_REPETIDORA_ALVO_M = 1800.0
    TAMANHO_FILTRO_PICO_LOCAL = 5
    try:
        dem_para_picos = dem_array.copy().astype(np.float32)
        if dem_nodata_val is not None:
            dem_para_picos[dem_array == dem_nodata_val] = np.nan
        
        valores_picos_locais = maximum_filter(dem_para_picos, size=TAMANHO_FILTRO_PICO_LOCAL, mode='constant', cval=np.nan)
        mascara_picos_locais = (dem_para_picos == valores_picos_locais) & (~np.isnan(dem_para_picos))
        indices_y_picos, indices_x_picos = np.where(mascara_picos_locais)
        coords_x_mapa_picos, coords_y_mapa_picos = rasterio.transform.xy(
            dem_transform, indices_y_picos, indices_x_picos, offset='center'
        )
        
        tasks = []
        candidate_points_data = []
        
        for idx, (peak_lon_crs_dem, peak_lat_crs_dem) in enumerate(zip(coords_x_mapa_picos, coords_y_mapa_picos)):
            elevacao_pico_atual = dem_para_picos[indices_y_picos[idx], indices_x_picos[idx]]
            peak_lon_wgs84, peak_lat_wgs84 = peak_lon_crs_dem, peak_lat_crs_dem
            
            esta_em_area_sinal = False
            for ov_data in active_overlays_data:
                overlay_imagem_path = Path(ov_data['imagem_path'])
                if not overlay_imagem_path.is_file(): continue
                try:
                    if overlay_imagem_path not in imagens_overlay_pil_cache:
                        imagens_overlay_pil_cache[overlay_imagem_path] = Image.open(overlay_imagem_path).convert("RGBA")
                    pil_img_overlay = imagens_overlay_pil_cache[overlay_imagem_path]
                    ov_w, ov_h = pil_img_overlay.size
                    s, w, n, e = ov_data['bounds']
                    if s > n: s, n = n, s
                    if w > e: w, e = e, w
                    ov_delta_lon, ov_delta_lat = e - w, n - s
                    if ov_delta_lon == 0 or ov_delta_lat == 0: continue
                    px = int(((peak_lon_wgs84 - w) / ov_delta_lon) * ov_w)
                    py = int(((n - peak_lat_wgs84) / ov_delta_lat) * ov_h)
                    if 0 <= px < ov_w and 0 <= py < ov_h and pil_img_overlay.getpixel((px, py))[3] > 50:
                        esta_em_area_sinal = True
                        break
                except Exception as e_img_check:
                    logger.warning(f"    -> ❌ Erro ao verificar cobertura do pico no overlay {overlay_imagem_path.name}: {e_img_check}")
            
            if not esta_em_area_sinal: continue
            
            distancia_pico_alvo_m = haversine(alvo_lat, alvo_lon, peak_lat_wgs84, peak_lon_wgs84)
            if distancia_pico_alvo_m > MAX_DIST_REPETIDORA_ALVO_M: continue
            
            if shapely_pivot_polygons:
                ponto_candidato_shapely = Point(peak_lon_wgs84, peak_lat_wgs84)
                if any(piv_poly.contains(ponto_candidato_shapely) for piv_poly in shapely_pivot_polygons):
                    continue
            
            task = obter_perfil_elevacao(
                pontos=[(peak_lat_wgs84, peak_lon_wgs84), (alvo_lat, alvo_lon)],
                alt1=altura_antena_repetidora_proposta,
                alt2=altura_receptor_pivo
            )
            tasks.append(task)
            candidate_points_data.append({
                "lat": float(peak_lat_wgs84),
                "lon": float(peak_lon_wgs84),
                "elevation": float(elevacao_pico_atual),
                "distance_to_target": float(distancia_pico_alvo_m)
            })
        
        if tasks:
            logger.info(f" -> Disparando {len(tasks)} análises de perfil de elevação em paralelo...")
            los_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, result in enumerate(los_results):
                point_data = candidate_points_data[i]
                
                if isinstance(result, Exception):
                    tem_los_para_alvo = False
                    info_ponto_bloqueio = {"error_calculating_los": str(result)}
                    altura_torre_necessaria_m = None
                else:
                    perfil_resultado = result
                    tem_los_para_alvo = perfil_resultado.get("bloqueio") is None
                    info_ponto_bloqueio = perfil_resultado.get("bloqueio")
                    altura_torre_necessaria_m = None
                    if not tem_los_para_alvo and info_ponto_bloqueio and isinstance(info_ponto_bloqueio.get("diff"), (int, float)):
                        altura_torre_necessaria_m = info_ponto_bloqueio["diff"] + 3.0
                
                candidate_sites_list.append({
                    **point_data,
                    "has_los": tem_los_para_alvo,
                    "ponto_bloqueio": info_ponto_bloqueio,
                    "altura_necessaria_torre": altura_torre_necessaria_m
                })
                
    except Exception as e_proc_picos:
        logger.error(f"  -> ❌ Erro durante o processamento dos picos ou LoS: {e_proc_picos}", exc_info=True)
    finally:
        for img_pil in imagens_overlay_pil_cache.values():
            img_pil.close()
    
    candidate_sites_list.sort(key=lambda s: (
        not s["has_los"],
        -(s.get("elevation", -float('inf'))),
        s.get("distance_to_target", float('inf'))
    ))
    MAX_SITES_PARA_RETORNAR = 25
    return candidate_sites_list[:MAX_SITES_PARA_RETORNAR]


def _find_next_pivot_number(pivos: List[PivoInputData]) -> int:
    max_number = 0
    regex = re.compile(r'(\d+)$')

    for pivo in pivos:
        match = regex.search(pivo['nome'])
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
    """
    Gera um novo pivô no ponto central com um nome sequencial único e traduzido.
    """
    logger.info(f"💡 Gerando novo pivô em ({center_lat:.6f}, {center_lon:.6f}) no idioma '{lang}'.")
    
    next_num = _find_next_pivot_number(existing_pivos)
    
    t = i18n_service.get_translator(lang)
    pivot_base_name = t("entity_names.pivot")
    new_pivot_name = f"{pivot_base_name} {next_num}"

    logger.info(f"  -> Nome do novo pivô determinado: '{new_pivot_name}'")

    new_pivot_data: PivoInputData = {
        "nome": new_pivot_name,
        "lat": center_lat,
        "lon": center_lon,
        "type": "pivo",
        "fora": None
    }

    return new_pivot_data

# NOVO: Função para simular a cobertura de uma única fonte para um conjunto de pivôs.
# Isso é um MOCK e deve ser substituído pela sua lógica de simulação real.
async def _simulate_single_source_coverage(
    source_data: Dict[str, Any],
    pivos_to_check: List[Dict[str, Any]],
    template_id: str,
    job_id: str # Adicionado job_id para consistência, embora não usado no mock
) -> List[Dict[str, Any]]:
    """
    MOCK: Simula a cobertura de uma ÚNICA fonte de sinal para um conjunto de pivôs.
    Retorna o status 'fora' para cada pivô.
    Em uma aplicação real, você chamaria cloudrf_service.run_cloudrf_simulation
    para a source_data, obteria o overlay, e então usaria _check_coverage_sync.
    Para a otimização, precisamos de algo mais leve e rápido.
    """
    logger.debug(f"  -> (Mock Sim) Verificando cobertura para {len(pivos_to_check)} pivôs de uma fonte.")

    # MOCK: Apenas para demonstração. O sinal é "bom" se a distância for menor que 2000m.
    # Em um ambiente real, você usaria o CloudRF service ou um modelo interno.
    
    # Se você tiver um mock de overlay para a fonte (source_data), use-o.
    # Caso contrário, simule o "alcance".
    
    # Para o propósito da otimização, precisamos APENAS do status de cobertura (fora: True/False).
    # Uma forma mais robusta seria:
    # 1. Chamar cloudrf_service.run_cloudrf_simulation(source_data...)
    # 2. Obter o `imagem_local_path` e `bounds` do resultado.
    # 3. Chamar _check_coverage_sync com este único overlay.
    
    # Para evitar chamadas CloudRF em loop durante a otimização,
    # vamos usar um modelo de alcance simplificado baseado em distância e altura.
    
    # Parâmetros simplificados para um modelo de "alcance":
    # Estes são arbitrários, mas representam a ideia de que altura e distância influenciam.
    MAX_COVERAGE_DISTANCE_BASE_M = 1500 # Alcance base em metros
    HEIGHT_IMPACT_FACTOR = 50 # Metros adicionais de alcance por metro de altura extra da antena
    
    source_lat = source_data['lat']
    source_lon = source_data['lon']
    source_height = source_data.get('altura', settings.TEMPLATES_DISPONIVEIS[0].antenna.txg) # Altura Tx
    
    # Use a altura do receptor do template, ou um padrão
    # Este é o alt_rx da antena principal ou um valor padrão (3m)
    # Não é o altura_receiver_pivo que pode vir da otimização.
    # Para este mock, usamos um valor padrão ou do template.
    template = settings.obter_template(template_id)
    default_pivot_rx_height = template.receiver.alt

    results = []
    for pivo in pivos_to_check:
        pivot_lat = pivo['lat']
        pivot_lon = pivo['lon']
        
        distance_m = haversine(source_lat, source_lon, pivot_lat, pivot_lon)
        
        # Alcance efetivo: base + impacto da altura da antena Tx
        effective_range = MAX_COVERAGE_DISTANCE_BASE_M + (source_height * HEIGHT_IMPACT_FACTOR)
        
        # Considerar um LOS simples para pontos altos para evitar simulações falsas
        # Isso seria mais preciso com perfil de elevação, mas é um mock.
        # Se a fonte ou o pivô estiver em um ponto alto, aumentar a chance de LoS
        # (Para um mock, ignoramos a elevação real e apenas testamos a distância)
        
        is_covered = distance_m < effective_range
        
        results.append({
            "nome": pivo['nome'],
            "lat": pivo['lat'],
            "lon": pivo['lon'],
            "fora": not is_covered
        })
    return results


async def find_optimal_repeaters(
    job_id: str,
    pivos: List[Dict[str, Any]],
    antena_global: Optional[Dict[str, Any]],
    repetidoras_existentes: List[Dict[str, Any]],
    template_id: str,
    target_pivot_names: List[str],
    optimization_params: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Encontra um conjunto "ótimo" de repetidoras para cobrir os pivôs alvo.
    Utiliza um algoritmo ganancioso.
    """
    logger.info(f"✨ Iniciando algoritmo de otimização para job {job_id}.")
    logger.info(f"  -> Pivôs alvo: {len(target_pivot_names)}")
    logger.info(f"  -> Parâmetros de otimização: {optimization_params}")

    max_repeaters = optimization_params.get('max_repeaters', 3) # Limite de repetidoras a sugerir
    
    # Filtra os pivôs que são alvos e estão FORA de cobertura
    # Assume que 'pivos' já reflete o estado atual de cobertura sem novas repetidoras.
    uncovered_target_pivots = [
        p for p in pivos if p['nome'] in target_pivot_names and p.get('fora', True)
    ]

    if not uncovered_target_pivots:
        logger.info("  -> Todos os pivôs alvo já estão cobertos. Nenhuma otimização necessária.")
        return {
            "new_repeater_suggestions": [],
            "optimized_coverage_status": pivos # Retorna o estado atual
        }

    logger.info(f"  -> {len(uncovered_target_pivots)} pivôs alvo inicialmente sem cobertura.")

    # Lista de repetidoras sugeridas que serão construídas
    suggested_repeaters: List[SuggestedRepeater] = []
    
    # Conjunto de nomes de pivôs alvo que ainda precisam ser cobertos
    pivots_still_uncovered = {p['nome'] for p in uncovered_target_pivots}

    # Fontes de sinal ativas no mapa (antena principal + repetidoras existentes)
    current_active_sources: List[Dict[str, Any]] = []
    if antena_global:
        current_active_sources.append({
            "lat": antena_global['lat'], "lon": antena_global['lon'],
            "altura": antena_global.get('altura', settings.TEMPLATES_DISPONIVEIS[0].antenna.txg), # Altura Tx
            "altura_receiver": antena_global.get('altura_receiver', settings.TEMPLATES_DISPONIVEIS[0].receiver.alt), # Altura Rx
            "type": "main_antenna"
        })
    for rep in repetidoras_existentes:
        current_active_sources.append({
            "lat": rep['lat'], "lon": rep['lon'],
            "altura": rep.get('altura', 5), # Altura Tx
            "altura_receiver": rep.get('altura_receiver', settings.TEMPLATES_DISPONIVEIS[0].receiver.alt), # Altura Rx
            "type": "existing_repeater"
        })

    # Algoritmo Ganancioso: Adiciona a repetidora que cobre o maior número de pivôs não cobertos.
    iteration = 0
    while len(pivots_still_uncovered) > 0 and len(suggested_repeaters) < max_repeaters:
        iteration += 1
        logger.info(f"  -> Iteração {iteration}: {len(pivots_still_uncovered)} pivôs ainda não cobertos.")

        best_candidate_repeater = None
        max_newly_covered_in_this_iteration = -1
        
        # Gerar pontos candidatos próximos aos pivôs ainda não cobertos
        # Para uma otimização mais inteligente, usaríamos DEM aqui.
        candidate_locations_for_iteration: List[Dict[str, float]] = []
        for pivo_name in list(pivots_still_uncovered): # Iterar sobre uma cópia
            pivo_data = next((p for p in pivos if p['nome'] == pivo_name), None)
            if pivo_data:
                # Gerar 3 pontos candidatos aleatórios ao redor de cada pivô descoberto
                # Isso é um mock, na vida real seriam pontos estratégicos (elevação, visada)
                for _ in range(3):
                    lat_offset = (random.random() - 0.5) * 0.01 # +/- 0.005 graus
                    lon_offset = (random.random() - 0.5) * 0.01
                    candidate_locations_for_iteration.append({
                        "lat": pivo_data['lat'] + lat_offset,
                        "lon": pivo_data['lon'] + lon_offset,
                        "altura": 5, # Altura padrão sugerida para novas repetidoras
                        "altura_receiver": settings.TEMPLATES_DISPONIVEIS[0].receiver.alt # Rx alt da repetidora
                    })
        
        if not candidate_locations_for_iteration:
            logger.warning("  -> Não há mais locais candidatos viáveis para esta iteração.")
            break # Não há mais candidatos para adicionar

        for candidate_rep in candidate_locations_for_iteration:
            # Temporariamente adiciona o candidato às fontes de sinal
            temp_sources = current_active_sources + [candidate_rep]
            
            # Avalia quantos pivôs alvo seriam cobertos com este candidato
            # ATENÇÃO: Esta é a parte CRÍTICA do desempenho.
            # `_simulate_single_source_coverage` é um mock.
            # A forma ideal é um "modelo de propagação local" muito rápido
            # ou um cache inteligente de resultados CloudRF.

            # Simula a cobertura de TODAS as fontes (atuais + candidato) para TODOS os pivôs alvo
            # que AINDA estão descobertos.
            pivos_status_with_candidate = await _simulate_single_source_coverage(
                source_data=candidate_rep,
                pivos_to_check=[p for p in pivos if p['nome'] in pivots_still_uncovered],
                template_id=template_id,
                job_id=job_id # Passando job_id para o mock
            )

            newly_covered_count_this_candidate = 0
            for pivo_name in pivots_still_uncovered:
                # Se o pivô já foi coberto por uma fonte existente, não o conta como "novo" aqui.
                # A lógica abaixo é para identificar os pivôs que AGORA estão cobertos
                # considerando APENAS o candidato atual.
                pivo_status = next((p for p in pivos_status_with_candidate if p['nome'] == pivo_name), None)
                if pivo_status and not pivo_status['fora']:
                    # Um pivô é considerado "recém-coberto" por este candidato
                    # se ele estava descoberto e agora estaria coberto.
                    newly_covered_count_this_candidate += 1
            
            # A lógica do greedy é escolher o candidato que COBRE MAIS NOVOS PIVÔS
            if newly_covered_count_this_candidate > max_newly_covered_in_this_iteration:
                max_newly_covered_in_this_iteration = newly_covered_count_this_candidate
                best_candidate_repeater = candidate_rep
        
        if best_candidate_repeater and max_newly_covered_in_this_iteration > 0:
            suggested_repeaters.append({
                "lat": best_candidate_repeater['lat'],
                "lon": best_candidate_repeater['lon'],
                "altura_sugerida": best_candidate_repeater['altura']
            })
            # Adiciona a repetidora sugerida ao conjunto de fontes ativas
            current_active_sources.append({
                "lat": best_candidate_repeater['lat'],
                "lon": best_candidate_repeater['lon'],
                "altura": best_candidate_repeater['altura'],
                "altura_receiver": settings.TEMPLATES_DISPONIVEIS[0].receiver.alt,
                "type": "suggested_repeater"
            })
            
            # Reavalia o status de todos os pivôs que ainda estavam descobertos
            # para atualizar `pivots_still_uncovered` para a próxima iteração.
            
            # Primeiro, simula a cobertura de todas as fontes ATUAIS (existentes + sugeridas)
            # para todos os pivôs alvo
            all_target_pivots_status = []
            for pivo_original in uncovered_target_pivots:
                sim_status = await _simulate_single_source_coverage(
                    source_data={"lat": pivo_original['lat'], "lon": pivo_original['lon'], "altura": 1, "is_target": True}, # Mock source para o target
                    pivos_to_check=[pivo_original],
                    template_id=template_id,
                    job_id=job_id
                )
                all_target_pivots_status.extend(sim_status) # Isso não está usando todas as sources. CORRIGIR.
            
            # CORREÇÃO: Você precisaria de uma função que simulasse a cobertura de *todos* os pivôs alvo
            # contra *todas* as `current_active_sources` acumuladas até agora.
            # O `_simulate_single_source_coverage` não faz isso.
            
            # VAMOS SIMPLIFICAR O MOCK AQUI para o greedy:
            # Após adicionar o best_candidate_repeater,
            # remova de `pivots_still_uncovered` aqueles que seriam cobertos por ELE (best_candidate_repeater)
            # A simulação real para `_simulate_single_source_coverage` deveria refletir o impacto cumulativo.
            
            # Para o mock, vamos apenas remover os pivôs que o "melhor candidato" coberto.
            # Isso é uma aproximação bem simplificada.
            for pivo_status in pivos_status_with_candidate: # pivos_status_with_candidate veio da avaliação do *melhor candidato*
                 if not pivo_status['fora'] and pivo_status['nome'] in pivots_still_uncovered:
                     pivots_still_uncovered.remove(pivo_status['nome'])
        else:
            logger.info("  -> Nenhuma repetidora candidata conseguiu cobrir novos pivôs nesta iteração.")
            break # Não há mais melhorias a fazer

    # Reavaliar o status final de todos os pivôs (não apenas os alvos) com todas as fontes (existentes + sugeridas)
    # Isso precisa ser feito chamando o _check_coverage_sync com todas as imagens/bounds gerados
    # ou usando uma simulação CloudRF completa para cada repetidora sugerida
    # e então verificando os pivôs com todos os overlays.

    # Para simpplicidade do mock de otimização, vamos apenas marcar os pivôs alvo cobertos como 'não fora'.
    # Em um cenário real, você faria uma reavaliação completa como no endpoint `/reevaluate`.

    # MOCK final_pivos_status
    final_pivos_status = []
    for pivo in pivos:
        pivo_copy = pivo.copy()
        if pivo['nome'] in target_pivot_names:
            # Se o pivô alvo foi coberto durante a otimização, marque-o como coberto
            if pivo['nome'] not in pivots_still_uncovered:
                pivo_copy['fora'] = False
            else:
                pivo_copy['fora'] = True # Permanece fora se não foi coberto
        # Senão, mantém o status original (se já coberto ou não alvo)
        final_pivos_status.append(pivo_copy)

    logger.info(f"✨ Otimização finalizada. Total de repetidoras sugeridas: {len(suggested_repeaters)}")
    logger.info(f"  -> Pivôs alvo que permanecem sem cobertura: {len(pivots_still_uncovered)}")

    return {
        "new_repeater_suggestions": suggested_repeaters,
        "optimized_coverage_status": final_pivos_status # Retorna os pivôs com os novos status
    }