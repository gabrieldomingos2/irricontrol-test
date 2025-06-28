import re
from pydantic import BaseModel
from backend.services.kmz_parser import normalizar_nome
from PIL import Image
import httpx
from math import sqrt, radians, sin, cos, atan2, degrees
from typing import List, Dict, Optional, Union, TypedDict, Tuple, Any
from pathlib import Path
import logging
import asyncio
import hashlib  # Adicionado para gerar o hash do cache
import json     # Adicionado para serializar dados para a chave de cache

# Imports para DEM e processamento geoespacial
import rasterio
from rasterio.windows import Window
from rasterio.transform import from_origin
from rasterio.warp import calculate_default_transform, reproject, Resampling
import numpy as np
from scipy.ndimage import maximum_filter
from shapely.geometry import Point, Polygon

# Opcional: import elevation

from backend.config import settings
from backend.services import cloudrf_service
from fastapi.concurrency import run_in_threadpool

# Configuração do Logger
logger = logging.getLogger("irricontrol")

# --- Tipos Personalizados (sem alterações) ---
class PivoInputData(TypedDict):
    nome: str
    lat: float
    lon: float

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

# --- Análise de Cobertura (sem alterações) ---
def verificar_cobertura_pivos(pivos: List[PivoInputData], overlays_info: List[OverlayInputData]) -> List[PivoInputData]:
    # (código da função sem alterações)
    logger.info(f"🔎 Verificando cobertura para {len(pivos)} pivôs com {len(overlays_info)} overlays.")
    imagens_abertas_cache: Dict[Path, Image.Image] = {}
    pivos_atualizados: List[PivoInputData] = []
    for pivo_data in pivos:
        lat, lon = pivo_data["lat"], pivo_data["lon"]
        coberto_por_algum_overlay = False
        for overlay_data in overlays_info:
            bounds = overlay_data["bounds"]
            imagem_path_servidor = Path(overlay_data["imagem_path"])
            if not imagem_path_servidor.is_file():
                logger.warning(f"  -> ⚠️ Imagem não encontrada em: {imagem_path_servidor} (para overlay ID: {overlay_data.get('id', 'N/A')}). Pulando overlay.")
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
                logger.error(f"  -> ❌ Erro ao analisar overlay {overlay_data.get('id', imagem_path_servidor.name)} para pivô '{pivo_data['nome']}': {ex}", exc_info=True)
        pivo_data_atualizado = pivo_data.copy()
        pivo_data_atualizado["fora"] = not coberto_por_algum_overlay # type: ignore
        pivos_atualizados.append(pivo_data_atualizado) # type: ignore
    for img_obj in imagens_abertas_cache.values():
        img_obj.close()
    logger.info("  -> Verificação de cobertura concluída.")
    return pivos_atualizados # type: ignore

# ✅ NOVA FUNÇÃO PARA VERIFICAR COBERTURA DAS BOMBAS
def verificar_cobertura_bombas(bombas: List[Dict], overlays_info: List[OverlayInputData]) -> List[Dict]:
    """
    Verifica se as casas de bomba estão dentro da área de cobertura dos overlays.
    Esta função é uma cópia adaptada da lógica dos pivôs.
    """
    logger.info(f"🔎 Verificando cobertura para {len(bombas)} casas de bomba com {len(overlays_info)} overlays.")
    imagens_abertas_cache: Dict[Path, Image.Image] = {}
    bombas_atualizadas: List[Dict] = []

    for bomba_data in bombas:
        lat, lon = bomba_data["lat"], bomba_data["lon"]
        coberto_por_algum_overlay = False

        for overlay_data in overlays_info:
            bounds = overlay_data["bounds"]
            imagem_path_servidor = Path(overlay_data["imagem_path"])

            if not imagem_path_servidor.is_file():
                logger.warning(f"  -> ⚠️ Imagem não encontrada em: {imagem_path_servidor} (para overlay ID: {overlay_data.get('id', 'N/A')}). Pulando overlay.")
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
                logger.error(f"  -> ❌ Erro ao analisar overlay {overlay_data.get('id', imagem_path_servidor.name)} para bomba '{bomba_data['nome']}': {ex}", exc_info=True)

        bomba_data_atualizada = bomba_data.copy()
        bomba_data_atualizada["fora"] = not coberto_por_algum_overlay
        bombas_atualizadas.append(bomba_data_atualizada)

    for img_obj in imagens_abertas_cache.values():
        img_obj.close()
        
    logger.info("  -> Verificação de cobertura das bombas concluída.")
    return bombas_atualizadas


# --- Análise de Elevação com Cache ---

async def obter_perfil_elevacao(pontos: List[Tuple[float, float]], alt1: float, alt2: float) -> ElevationProfileResult:
    """Obtém perfil de elevação entre dois pontos, usando cache para evitar requisições repetidas."""
    if len(pontos) != 2:
        raise ValueError("São necessários exatamente dois pontos para o perfil de elevação.")

    # --- LÓGICA DE CACHE (VERIFICAÇÃO) ---
    # 1. Criar chave única para os parâmetros. Usamos json.dumps para serializar a lista de pontos.
    #    A ordenação 'sorted(pontos)' garante que a ordem dos pontos não afete a chave de cache.
    cache_key_string = f"points:{json.dumps(sorted(pontos))}-alt1:{alt1}-alt2:{alt2}"
    cache_hash = hashlib.sha256(cache_key_string.encode()).hexdigest()
    cache_file_path = settings.ELEVATION_CACHE_PATH / f"{cache_hash}.json"

    # 2. Verificar se o resultado já existe no cache.
    if cache_file_path.exists():
        logger.info(f"CACHE HIT: Encontrado perfil de elevação em cache com hash: {cache_hash[:12]}")
        with open(cache_file_path, "r") as f:
            return json.load(f)
    # --- FIM DA VERIFICAÇÃO DE CACHE ---

    # CACHE MISS: Se não encontrou, executa a busca na API.
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

    # --- LÓGICA DE CACHE (SALVAR) ---
    # 3. Salvar o resultado obtido no cache para uso futuro.
    final_result = {"perfil": perfil_final, "bloqueio": ponto_bloqueio, "ponto_mais_alto": ponto_mais_alto_terreno}
    with open(cache_file_path, "w") as f:
        json.dump(final_result, f, indent=4)
    logger.info(f" -> Perfil de elevação salvo no cache em: {cache_file_path.name}")
    # --- FIM DO SALVAMENTO NO CACHE ---

    return final_result


# --- Funções de Busca por Repetidora (sem alterações) ---

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    # (código da função sem alterações)
    R = 6371000
    phi1_rad, phi2_rad = radians(lat1), radians(lat2)
    delta_phi_rad = radians(lat2 - lat1)
    delta_lambda_rad = radians(lon2 - lon1)
    a = sin(delta_phi_rad / 2)**2 + cos(phi1_rad) * cos(phi2_rad) * sin(delta_lambda_rad / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c

def _download_and_clip_dem(bounds_dem_wgs84: Tuple[float,float,float,float], output_dem_path: Path) -> None:
    # (código da função sem alterações)
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
    # (código da função sem alterações)
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
    # (Esta função usará o cache de 'obter_perfil_elevacao' automaticamente em seu loop)
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
        num_picos_qualificados_antes_los = 0 
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
                    if 0 <= px < ov_w and 0 <= py < ov_h:
                        if pil_img_overlay.getpixel((px, py))[3] > 50:
                            esta_em_area_sinal = True
                            break 
                except Exception as e_img_check:
                    logger.warning(f"    -> ❌ Erro ao verificar cobertura do pico no overlay {overlay_imagem_path.name}: {e_img_check}")
            if not esta_em_area_sinal:
                continue 
            distancia_pico_alvo_m = haversine(alvo_lat, alvo_lon, peak_lat_wgs84, peak_lon_wgs84)
            if distancia_pico_alvo_m > MAX_DIST_REPETIDORA_ALVO_M:
                continue 
            if shapely_pivot_polygons:
                ponto_candidato_shapely = Point(peak_lon_wgs84, peak_lat_wgs84)
                if any(piv_poly.contains(ponto_candidato_shapely) for piv_poly in shapely_pivot_polygons):
                    continue
            num_picos_qualificados_antes_los += 1
            if num_picos_qualificados_antes_los > 1 and num_picos_qualificados_antes_los % 3 == 0 :
                await asyncio.sleep(0.1)
            try:
                perfil_resultado = await obter_perfil_elevacao(
                    pontos=[(peak_lat_wgs84, peak_lon_wgs84), (alvo_lat, alvo_lon)],
                    alt1=altura_antena_repetidora_proposta,
                    alt2=altura_receptor_pivo
                )
                tem_los_para_alvo = perfil_resultado.get("bloqueio") is None
                info_ponto_bloqueio = perfil_resultado.get("bloqueio")
                altura_torre_necessaria_m: Optional[float] = None
                if not tem_los_para_alvo and info_ponto_bloqueio and isinstance(info_ponto_bloqueio.get("diff"), (int, float)):
                    altura_torre_necessaria_m = info_ponto_bloqueio["diff"] + 3.0 
            except ValueError as e_los_val:
                 tem_los_para_alvo = False 
                 info_ponto_bloqueio = {"error_calculating_los": str(e_los_val)}
                 altura_torre_necessaria_m = None
            except Exception as e_los_geral:
                 tem_los_para_alvo = False 
                 info_ponto_bloqueio = {"error_calculating_los": str(e_los_geral)}
                 altura_torre_necessaria_m = None
            site_candidato_info: CandidateSite = {
                "lat": float(peak_lat_wgs84),
                "lon": float(peak_lon_wgs84),
                "elevation": float(elevacao_pico_atual),
                "has_los": tem_los_para_alvo,
                "distance_to_target": float(distancia_pico_alvo_m),
                "ponto_bloqueio": info_ponto_bloqueio,
                "altura_necessaria_torre": altura_torre_necessaria_m
            }
            candidate_sites_list.append(site_candidato_info)
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
    """
    Analisa os nomes dos pivôs existentes e encontra o próximo número sequencial.
    Ex: Se "Pivô 3", "Pivô Teste 5" existem, retorna 6.
    """
    max_number = 0
    # Regex para encontrar um ou mais dígitos no final do nome, opcionalmente precedido por espaço.
    regex = re.compile(r'(\d+)$') 

    for pivo in pivos:
        nome_norm = normalizar_nome(pivo['nome'])
        match = regex.search(nome_norm)
        if match:
            number = int(match.group(1))
            if number > max_number:
                max_number = number
    
    return max_number + 1

def generate_pivot_at_center(
    center_lat: float, 
    center_lon: float, 
    existing_pivos: List[PivoInputData]
) -> PivoInputData:
    """
    Gera um novo pivô no ponto central com um nome sequencial único.

    Retorna:
        Um dicionário contendo os dados do novo pivô criado.
    """
    logger.info(f"💡 Gerando novo pivô em ({center_lat:.6f}, {center_lon:.6f}).")
    
    # 1. Encontrar o próximo número de pivô disponível
    next_num = _find_next_pivot_number(existing_pivos)
    new_pivot_name = f"Pivô {next_num}"

    logger.info(f"  -> Nome do novo pivô determinado: '{new_pivot_name}'")

    # 2. Criar o objeto do novo pivô
    new_pivot_data: PivoInputData = {
        "nome": new_pivot_name,
        "lat": center_lat,
        "lon": center_lon,
        "type": "pivo",
        "fora": None # O status de cobertura será definido posteriormente
    }

    return new_pivot_data
