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

# --- Tipos Personalizados (sem alterações) ---
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

# --- Funções Auxiliares ---

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
    
    PROXIMITY_THRESHOLD_METERS = 20.0

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
        (pontos[0][0] + (pontos[1][0] - pontos[0][0]) * i / num_passos,
         pontos[0][1] + (pontos[1][1] - pontos[0][1]) * i / num_passos)
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
    signal_sources_data: List[Dict[str, Any]], # <-- NOVO PARÂMETRO
    pivot_polygons_coords_data: Optional[List[List[Tuple[float, float]]]] = None
) -> List[CandidateSite]:
    """
    Encontra locais de repetidora com uma lógica aprimorada de "Dupla Linha de Visada" e pontuação.
    """
    logger.info(f"🔎 Buscando locais de repetidora para pivô '{alvo_nome}' com lógica aprimorada...")
    if not active_overlays_data or not signal_sources_data:
        logger.warning(" -> ⚠️ Busca cancelada: Não há overlays ativos ou fontes de sinal para a análise.")
        return []

    # --- Lógica para obter DEM e criar polígonos (sem alterações) ---
    shapely_pivot_polygons: List[Polygon] = []
    if pivot_polygons_coords_data:
        for i, poly_coords_list in enumerate(pivot_polygons_coords_data):
            shapely_coords = [(coord_pair[1], coord_pair[0]) for coord_pair in poly_coords_list]
            if len(shapely_coords) >= 3:
                try:
                    shapely_pivot_polygons.append(Polygon(shapely_coords))
                except Exception as e_shapely:
                    logger.warning(f"  -> ⚠️ Erro ao criar polígono Shapely para o ciclo {i+1}: {e_shapely}.")

    min_s, min_w, max_n, max_e = float('inf'), float('inf'), float('-inf'), float('-inf')
    for ov_data in active_overlays_data:
        s, w, n, e = ov_data['bounds']
        min_s, min_w, max_n, max_e = min(min_s, s), min(min_w, w), max(max_n, n), max(max_e, e)
    
    dem_center_lat, dem_center_lon = (min_s + max_n) / 2, (min_w + max_e) / 2
    dist_diag_width_m = haversine(dem_center_lat, min_w, dem_center_lat, max_e)
    dist_diag_height_m = haversine(min_s, dem_center_lon, max_n, dem_center_lon)
    dem_search_radius_km = (sqrt(dist_diag_width_m**2 + dist_diag_height_m**2) / 2000) + 0.5
    
    try:
        dem_array, dem_transform, dem_crs, dem_nodata_val = await obter_dem_para_area_geografica(
            dem_center_lat, dem_center_lon, dem_search_radius_km
        )
    except (FileNotFoundError, NotImplementedError) as e_dem:
        raise

    imagens_overlay_pil_cache: Dict[Path, Image.Image] = {}
    
    try:
        # --- FASE 1: Geração de picos e filtragem inicial ---
        dem_para_picos = dem_array.copy().astype(np.float32)
        if dem_nodata_val is not None:
            dem_para_picos[dem_array == dem_nodata_val] = np.nan
        
        TAMANHO_FILTRO_PICO_LOCAL = 7 # Aumentado para encontrar picos mais significativos
        valores_picos_locais = maximum_filter(dem_para_picos, size=TAMANHO_FILTRO_PICO_LOCAL, mode='constant', cval=np.nan)
        mascara_picos_locais = (dem_para_picos == valores_picos_locais) & (~np.isnan(dem_para_picos))
        indices_y_picos, indices_x_picos = np.where(mascara_picos_locais)
        coords_x_mapa_picos, coords_y_mapa_picos = rasterio.transform.xy(dem_transform, indices_y_picos, indices_x_picos, offset='center')
        
        initial_candidates = []
        MAX_DIST_REPETIDORA_ALVO_M = 2500.0 # Aumentado um pouco
        
        for idx, (peak_lon, peak_lat) in enumerate(zip(coords_x_mapa_picos, coords_y_mapa_picos)):
            # Filtro 1: Distância do Alvo
            distancia_pico_alvo_m = haversine(alvo_lat, alvo_lon, peak_lat, peak_lon)
            if distancia_pico_alvo_m > MAX_DIST_REPETIDORA_ALVO_M: continue
            
            # Filtro 2: Não estar dentro de um pivô
            if shapely_pivot_polygons and any(piv_poly.contains(Point(peak_lon, peak_lat)) for piv_poly in shapely_pivot_polygons): continue
            
            # Filtro 3: Estar em área de cobertura (lógica de imagem)
            esta_em_area_sinal = False
            for ov_data in active_overlays_data:
                try:
                    # ... (lógica de checagem do pixel na imagem PNG, sem alterações)
                    overlay_imagem_path = Path(ov_data['imagem_path'])
                    if not overlay_imagem_path.is_file(): continue
                    if overlay_imagem_path not in imagens_overlay_pil_cache:
                        imagens_overlay_pil_cache[overlay_imagem_path] = Image.open(overlay_imagem_path).convert("RGBA")
                    
                    pil_img = imagens_overlay_pil_cache[overlay_imagem_path]
                    ov_w, ov_h = pil_img.size
                    s, w, n, e = ov_data['bounds']
                    px = int(((peak_lon - w) / (e - w)) * ov_w)
                    py = int(((n - peak_lat) / (n - s)) * ov_h)

                    if 0 <= px < ov_w and 0 <= py < ov_h and pil_img.getpixel((px, py))[3] > 50:
                        esta_em_area_sinal = True
                        break
                except Exception:
                    continue # Ignora erros de imagem
            
            if esta_em_area_sinal:
                initial_candidates.append({
                    "lat": float(peak_lat), "lon": float(peak_lon),
                    "elevation": float(dem_para_picos[indices_y_picos[idx], indices_x_picos[idx]]),
                    "distance_to_target": float(distancia_pico_alvo_m)
                })
        
        logger.info(f" -> Fase 1: {len(initial_candidates)} candidatos iniciais encontrados.")
        if not initial_candidates: return []

        # --- FASE 2: Verificação de LoS para a FONTE DE SINAL ---
        logger.info(" -> Fase 2: Verificando LoS dos candidatos para as fontes de sinal...")
        source_los_tasks_map = {}
        for candidate in initial_candidates:
            # Para cada candidato, cria uma tarefa para cada fonte de sinal
            for source in signal_sources_data:
                task = obter_perfil_elevacao(
                    pontos=[(candidate['lat'], candidate['lon']), (source['lat'], source['lon'])],
                    alt1=altura_antena_repetidora_proposta,
                    alt2=source.get('altura', 15.0)
                )
                source_los_tasks_map[task] = (candidate, source)
        
        tasks = list(source_los_tasks_map.keys())
        results = await asyncio.gather(*tasks, return_exceptions=True)

        candidates_with_source_los = {}
        for i, result in enumerate(results):
            task = tasks[i]
            candidate, source = source_los_tasks_map[task]
            candidate_id = f"{candidate['lat']},{candidate['lon']}"
            
            if isinstance(result, Exception) or result.get("bloqueio") is not None:
                continue

            if candidate_id not in candidates_with_source_los:
                candidate['has_los_to_source'] = True
                candidate['source_connected_to'] = {'lat': source['lat'], 'lon': source['lon'], 'altura': source.get('altura', 15.0)}
                candidates_with_source_los[candidate_id] = candidate
        
        valid_candidates = list(candidates_with_source_los.values())
        logger.info(f" -> Fase 2: {len(valid_candidates)} candidatos com LoS para uma fonte.")
        if not valid_candidates: return []
        
        # --- FASE 3: Verificação de LoS para o ALVO ---
        logger.info(" -> Fase 3: Verificando LoS dos candidatos viáveis para o pivô alvo...")
        target_los_tasks = {
            obter_perfil_elevacao(
                pontos=[(c['lat'], c['lon']), (alvo_lat, alvo_lon)],
                alt1=altura_antena_repetidora_proposta,
                alt2=altura_receptor_pivo
            ): c for c in valid_candidates
        }
        
        tasks = list(target_los_tasks.keys())
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # --- FASE 4: Pontuação e Montagem Final ---
        final_results = []
        for i, result in enumerate(results):
            task = tasks[i]
            candidate = target_los_tasks[task]

            if isinstance(result, Exception) or result.get("bloqueio") is not None:
                continue # Só queremos locais com LoS para o alvo
            
            # Cálculo da Pontuação
            score = 1000  # Base por ter dupla LoS
            score += candidate.get('elevation', 0) * 1.5 # Valoriza mais a elevação
            score -= (candidate.get('distance_to_target', 9999) / 5) # Penaliza mais a distância

            candidate['has_los'] = True
            candidate['ponto_bloqueio'] = None
            candidate['score'] = score
            final_results.append(candidate)
            
        logger.info(f" -> Fases 3 e 4: {len(final_results)} candidatos finais com dupla LoS e pontuados.")

    except Exception as e_proc_picos:
        logger.error(f"  -> ❌ Erro durante o processamento dos picos ou LoS: {e_proc_picos}", exc_info=True)
        final_results = []
    finally:
        for img_pil in imagens_overlay_pil_cache.values():
            img_pil.close()
    
    # --- Ordenação final pela pontuação ---
    final_results.sort(key=lambda s: s.get("score", 0), reverse=True)
    
    MAX_SITES_PARA_RETORNAR = 25
    return final_results[:MAX_SITES_PARA_RETORNAR]


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