from PIL import Image
import httpx # Mantido para cloudrf_service.get_http_client()
# import os # Substituído por pathlib
from math import sqrt, radians, sin, cos, atan2, degrees
from typing import List, Dict, Optional, Union, TypedDict, Tuple, Any
from pathlib import Path # Adicionado
import logging # Adicionado
import asyncio

# Imports para DEM e processamento geoespacial
import rasterio
from rasterio.windows import Window # Mantido, embora não usado diretamente no código fornecido
from rasterio.transform import from_origin # Mantido
from rasterio.warp import calculate_default_transform, reproject, Resampling # Mantido
import numpy as np
from scipy.ndimage import maximum_filter
from shapely.geometry import Point, Polygon

# Opcional: import elevation # A importação real será feita dentro da função

from backend.config import settings # Importando o objeto settings
from backend.services import cloudrf_service # Usado para get_http_client em obter_perfil_elevacao
from fastapi.concurrency import run_in_threadpool # Para executar código síncrono bloqueante

# Configuração do Logger
logger = logging.getLogger(__name__)

# --- Tipos Personalizados (Opcional, mas melhora a clareza) ---
class PivoInputData(TypedDict): # Usando TypedDict para consistência com outros módulos
    nome: str
    lat: float
    lon: float

class OverlayInputData(TypedDict):
    id: Optional[str]
    imagem_path: Union[str, Path] # O router deve passar um Path absoluto aqui
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
    dist: float # Proporção da distância total

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


# --- Análise de Cobertura ---

def verificar_cobertura_pivos(pivos: List[PivoInputData], overlays_info: List[OverlayInputData]) -> List[PivoInputData]:
    """
    Verifica quais pivôs estão cobertos por pelo menos um dos overlays fornecidos.
    Esta função é SÍNCRONA e pode bloquear se chamada de um endpoint async com muitas/grandes imagens.
    Considere executá-la em um threadpool: `await run_in_threadpool(verificar_cobertura_pivos, ...)`
    """
    logger.info(f"🔎 Verificando cobertura para {len(pivos)} pivôs com {len(overlays_info)} overlays.")
    
    imagens_abertas_cache: Dict[Path, Image.Image] = {} # Cache para objetos Image da PIL
    pivos_atualizados: List[PivoInputData] = []

    for pivo_data in pivos:
        lat, lon = pivo_data["lat"], pivo_data["lon"]
        coberto_por_algum_overlay = False

        for overlay_data in overlays_info:
            bounds = overlay_data["bounds"]
            # Espera-se que 'imagem_path' seja um Path absoluto para o arquivo no servidor,
            # já processado pelo router (ex: via _get_image_filepath_for_analysis).
            imagem_path_servidor = Path(overlay_data["imagem_path"])

            if not imagem_path_servidor.is_file():
                logger.warning(f"  -> ⚠️ Imagem não encontrada em: {imagem_path_servidor} (para overlay ID: {overlay_data.get('id', 'N/A')}). Pulando overlay.")
                continue

            try:
                if imagem_path_servidor not in imagens_abertas_cache:
                    logger.debug(f"    -> Abrindo e cacheando imagem: {imagem_path_servidor}")
                    imagens_abertas_cache[imagem_path_servidor] = Image.open(imagem_path_servidor).convert("RGBA")
                
                pil_image = imagens_abertas_cache[imagem_path_servidor]
                img_width, img_height = pil_image.size

                # Normaliza bounds (S, W, N, E)
                s, w, n, e = bounds
                if s > n: s, n = n, s # Garante sul < norte
                if w > e: w, e = e, w # Garante oeste < leste

                delta_lon = e - w
                delta_lat = n - s
                if delta_lon == 0 or delta_lat == 0:
                    logger.warning(f"    -> DeltaLon ou DeltaLat é zero para {imagem_path_servidor}. Pulando cálculo de pixel.")
                    continue

                # Calcula posição do pixel
                # (lon - oeste) / delta_lon dá a proporção horizontal (0 a 1)
                # (norte - lat) / delta_lat dá a proporção vertical (0 a 1, Y invertido)
                pixel_x = int(((lon - w) / delta_lon) * img_width)
                pixel_y = int(((n - lat) / delta_lat) * img_height)

                if 0 <= pixel_x < img_width and 0 <= pixel_y < img_height:
                    _, _, _, alpha_channel = pil_image.getpixel((pixel_x, pixel_y))
                    if alpha_channel > 50: # Limiar de transparência
                        coberto_por_algum_overlay = True
                        logger.debug(f"    -> Pivô '{pivo_data['nome']}' COBERTO pelo overlay {overlay_data.get('id', imagem_path_servidor.name)}.")
                        break # Pivô está coberto, não precisa checar outros overlays para este pivô
                # else:
                # logger.debug(f"    -> Pivô '{pivo_data['nome']}' FORA dos limites do pixel do overlay {overlay_data.get('id', imagem_path_servidor.name)} ({pixel_x}, {pixel_y}).")
            
            except Exception as ex:
                logger.error(f"  -> ❌ Erro ao analisar overlay {overlay_data.get('id', imagem_path_servidor.name)} para pivô '{pivo_data['nome']}': {ex}", exc_info=True)

        pivo_data_atualizado = pivo_data.copy() # Copia para não modificar o original diretamente se for referência
        pivo_data_atualizado["fora"] = not coberto_por_algum_overlay # type: ignore
        pivos_atualizados.append(pivo_data_atualizado) # type: ignore

    # Fecha todas as imagens abertas no cache
    for img_obj in imagens_abertas_cache.values():
        img_obj.close()
    logger.debug("    -> Cache de imagens PIL limpo.")

    logger.info("  -> Verificação de cobertura concluída.")
    return pivos_atualizados # type: ignore


# --- Análise de Elevação ---

async def obter_perfil_elevacao(pontos: List[Tuple[float, float]], alt1: float, alt2: float) -> ElevationProfileResult:
    """Obtém perfil de elevação entre dois pontos usando OpenTopoData."""
    if len(pontos) != 2:
        raise ValueError("São necessários exatamente dois pontos para o perfil de elevação.")

    num_passos = 50 # Número de pontos amostrados ao longo da linha
    logger.info(f"⛰️ Calculando perfil de elevação ({num_passos} passos) entre {pontos[0]} e {pontos[1]}.")

    pontos_amostrados = [
        (pontos[0][0] + (pontos[1][0] - pontos[0][0]) * i / num_passos,
         pontos[0][1] + (pontos[1][1] - pontos[0][1]) * i / num_passos)
        for i in range(num_passos + 1)
    ]

    coords_param_str = "|".join([f"{lat:.6f},{lon:.6f}" for lat, lon in pontos_amostrados])
    # API OpenTopoData SRTM90m (SRTMGL3)
    url_api_elevacao = f"https://api.opentopodata.org/v1/srtm90m?locations={coords_param_str}&interpolation=cubic"
    logger.debug(f"  -> URL da API de Elevação: {url_api_elevacao}")

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
        logger.error(f"  -> Resposta inválida ou vazia da API de elevação: {dados_api}")
        raise ValueError("Resposta inválida ou vazia da API de elevação.")

    elevacoes_terreno = [res.get("elevation") for res in dados_api["results"]]
    if any(e is None for e in elevacoes_terreno): # OpenTopoData pode retornar null para pontos sem dados
        # Substituir None por um valor (ex: 0 ou np.nan) ou levantar erro
        # Por simplicidade, vamos tratar como erro se algum for None, pois afeta cálculos
        logger.error(f"  -> Dados de elevação inválidos (contêm None): {elevacoes_terreno}")
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
    
    for i in range(1, num_passos): # Exclui os pontos inicial e final da checagem de bloqueio
        elev_terreno_atual = elevacoes_terreno[i]
        elev_visada_atual = linha_visada_elev[i]
        
        if elev_terreno_atual > elev_visada_atual:
            diferenca = elev_terreno_atual - elev_visada_atual
            if diferenca > max_diferenca_bloqueio:
                max_diferenca_bloqueio = diferenca
                ponto_bloqueio = {
                    "lat": pontos_amostrados[i][0], "lon": pontos_amostrados[i][1],
                    "elev": float(elev_terreno_atual), "diff": float(diferenca),
                    "dist": i / num_passos # Distância normalizada (0 a 1)
                }

    if ponto_bloqueio:
        logger.info(f"  -> ⛔ Bloqueio detectado! Diferença máx: {max_diferenca_bloqueio:.1f}m")
    else:
        logger.info("  -> ✅ Visada livre!")

    # Encontra o ponto mais alto do terreno ao longo do perfil
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
    logger.info(f"  -> 🏔️ Ponto mais alto no perfil do terreno: {ponto_mais_alto_terreno}")

    perfil_final: List[ElevationPoint] = [
        {
            "lat": pontos_amostrados[i][0], "lon": pontos_amostrados[i][1],
            "elev": float(elevacoes_terreno[i]),
            "dist": i / num_passos
        } for i in range(num_passos + 1)
    ]
    return {"perfil": perfil_final, "bloqueio": ponto_bloqueio, "ponto_mais_alto": ponto_mais_alto_terreno}


# --- NOVAS FUNÇÕES PARA BUSCAR LOCAIS DE REPETIDORA ---

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcula a distância em metros entre duas coordenadas geográficas."""
    R = 6371000  # Raio da Terra em metros
    phi1_rad, phi2_rad = radians(lat1), radians(lat2)
    delta_phi_rad = radians(lat2 - lat1)
    delta_lambda_rad = radians(lon2 - lon1)
    a = sin(delta_phi_rad / 2)**2 + cos(phi1_rad) * cos(phi2_rad) * sin(delta_lambda_rad / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c

def _download_and_clip_dem(bounds_dem_wgs84: Tuple[float,float,float,float], output_dem_path: Path) -> None:
    """Função síncrona para ser executada em threadpool para download de DEM."""
    # Esta função interna é síncrona e será chamada com run_in_threadpool
    try:
        import elevation # Importa aqui para que o erro de importação seja contido
    except ImportError:
        logger.error("A biblioteca 'elevation' não está instalada. Necessária para download automático de DEM.")
        raise NotImplementedError("Biblioteca 'elevation' não encontrada para download de DEM.")
    
    logger.info(f"    -> (DEM) Baixando/clipando DEM para bounds {bounds_dem_wgs84} -> {output_dem_path}")
    # elevation.clip espera (oeste, sul, leste, norte)
    elevation.clip(bounds=bounds_dem_wgs84, output=str(output_dem_path), product='SRTM3') # SRTM3 é ~90m
    # Para maior resolução, poderia usar 'SRTM1' (~30m), mas é mais pesado.
    # Outras opções de produto: 'ALOS_DSM' (pago ou requer registro), 'NASADEM'
    logger.info(f"    -> (DEM) Concluído: {output_dem_path}")


async def obter_dem_para_area_geografica(
    lat_central: float, lon_central: float, raio_busca_km: float, # Raio em km para clareza
    resolucao_desejada_m: Optional[float] = 90 # Resolução de SRTM3 é ~90m
) -> Tuple[np.ndarray, rasterio.Affine, rasterio.crs.CRS, Optional[Any]]:
    """Obtém dados DEM para uma área, usando cache local e baixando se necessário."""
    logger.info(f"  -> (DEM) Obtendo DEM para ({lat_central:.4f}, {lon_central:.4f}), raio: {raio_busca_km:.1f}km")
    
    dem_cache_dir = settings.ARQUIVOS_DIR_PATH / "dem_cache" # Usando settings e pathlib
    dem_cache_dir.mkdir(parents=True, exist_ok=True)

    # Estimativa de graus para o raio (simplificado)
    raio_busca_m = raio_busca_km * 1000
    graus_lat_por_metro = 1.0 / 111000.0 
    graus_lon_por_metro_aprox = 1.0 / (111000.0 * cos(radians(lat_central))) # Aproximação
    
    offset_lat_graus = raio_busca_m * graus_lat_por_metro
    offset_lon_graus = raio_busca_m * graus_lon_por_metro_aprox
    
    # Bounds para elevation.clip: (oeste, sul, leste, norte)
    bounds_dem_wgs84 = ( 
        lon_central - offset_lon_graus, lat_central - offset_lat_graus,
        lon_central + offset_lon_graus, lat_central + offset_lat_graus
    )
    
    # Nome de arquivo mais descritivo e seguro
    nome_arquivo_dem = f"dem_clip_lat{lat_central:.4f}_lon{lon_central:.4f}_r{int(raio_busca_m)}m.tif"
    nome_arquivo_dem = nome_arquivo_dem.replace(".", "_").replace("-", "m") # Sanitiza nome
    path_arquivo_dem_local = dem_cache_dir / nome_arquivo_dem

    try:
        if not path_arquivo_dem_local.exists():
            logger.info(f"    -> (DEM) Cache não encontrado: {path_arquivo_dem_local}. Tentando download.")
            # Executa a função síncrona de download em um threadpool
            await run_in_threadpool(_download_and_clip_dem, bounds_dem_wgs84, path_arquivo_dem_local)
        else:
            logger.info(f"    -> (DEM) Usando DEM do cache: {path_arquivo_dem_local}")

        # Abre o DEM com rasterio (síncrono, executar em threadpool)
        def _read_rasterio_dem(path: Path) -> Tuple[np.ndarray, rasterio.Affine, rasterio.crs.CRS, Optional[Any]]:
            with rasterio.open(path) as src:
                # Poderia adicionar lógica para reamostragem aqui se 'resolucao_desejada_m' for usada
                # para alterar a resolução do DEM lido, mas SRTM3 já tem resolução fixa.
                dem_array = src.read(1) # Lê a primeira banda
                dem_transform = src.transform
                dem_crs = src.crs
                dem_nodata = src.nodata # Valor que indica ausência de dados
                logger.info(f"    -> (DEM) Carregado: Shape={dem_array.shape}, ResXY={src.res}, NoData={dem_nodata}, CRS={dem_crs}")
                return dem_array, dem_transform, dem_crs, dem_nodata
        
        return await run_in_threadpool(_read_rasterio_dem, path_arquivo_dem_local)

    except (FileNotFoundError, NotImplementedError) as e_dem_specific: # Captura erros de _download_and_clip_dem
        logger.error(f"  -> ❌ Erro específico ao obter DEM: {e_dem_specific}", exc_info=True)
        raise # Re-levanta para o chamador (router) tratar como HTTPException
    except Exception as e:
        logger.error(f"  -> ❌ Erro crítico ao obter/processar DEM: {e}", exc_info=True)
        raise FileNotFoundError(f"Falha crítica ao obter DEM para a área: {e}") # Mantém FileNotFoundError ou um erro mais genérico


async def encontrar_locais_altos_para_repetidora(
    alvo_lat: float, alvo_lon: float, alvo_nome: str,
    altura_antena_repetidora_proposta: float, altura_receptor_pivo: float,
    active_overlays_data: List[OverlayInputData], # Espera 'imagem_path' como Path absoluto
    pivot_polygons_coords_data: Optional[List[List[Tuple[float, float]]]] = None
) -> List[CandidateSite]:
    """
    Encontra pontos altos candidatos para repetidoras.
    """
    logger.info(f"🔎 Buscando locais de repetidora para pivô '{alvo_nome}' ({alvo_lat:.5f}, {alvo_lon:.5f})") 
    
    if not active_overlays_data:
        logger.warning("⚠️ Nenhum overlay ativo fornecido. Busca de locais de repetidora não pode continuar.")
        return []

    shapely_pivot_polygons: List[Polygon] = []
    if pivot_polygons_coords_data:
        for i, poly_coords_list in enumerate(pivot_polygons_coords_data):
            shapely_coords = [(coord_pair[1], coord_pair[0]) for coord_pair in poly_coords_list] # (lon, lat)
            if len(shapely_coords) >= 3:
                try:
                    shapely_pivot_polygons.append(Polygon(shapely_coords))
                except Exception as e_shapely:
                    logger.warning(f"  -> ⚠️ Erro ao criar polígono Shapely para o ciclo {i+1}: {e_shapely}. Coords: {poly_coords_list}")
            else:
                logger.warning(f"  -> ⚠️ Coordenadas insuficientes ({len(shapely_coords)}) para formar polígono de pivô {i+1}. Pulando.")
        if shapely_pivot_polygons:
             logger.info(f"  -> {len(shapely_pivot_polygons)} polígonos de pivôs (ciclos) carregados para exclusão de área.")

    # Calcular Bounding Box global dos overlays para determinar área do DEM
    min_s, min_w = float('inf'), float('inf')
    max_n, max_e = float('-inf'), float('-inf')
    for ov_data in active_overlays_data:
        s, w, n, e = ov_data['bounds']
        min_s, min_w = min(min_s, s), min(min_w, w)
        max_n, max_e = max(max_n, n), max(max_e, e)
    
    if any(val == float('inf') or val == float('-inf') for val in [min_s, max_n, min_w, max_e]):
        logger.error("Limites inválidos ou ausentes dos overlays ativos. Não é possível determinar a área do DEM.")
        raise ValueError("Limites de overlays ativos inválidos para busca de repetidoras.")

    dem_center_lat = (min_s + max_n) / 2
    dem_center_lon = (min_w + max_e) / 2
    # Calcula o raio necessário para cobrir a diagonal da bounding box dos overlays + uma margem
    dist_diag_width_m = haversine(dem_center_lat, min_w, dem_center_lat, max_e)
    dist_diag_height_m = haversine(min_s, dem_center_lon, max_n, dem_center_lon)
    dem_search_radius_km = (sqrt(dist_diag_width_m**2 + dist_diag_height_m**2) / 2000) + 0.5 # km, +500m de margem
    
    logger.info(f"  -> Limites globais overlays (SWNE): {min_s:.4f}, {min_w:.4f}, {max_n:.4f}, {max_e:.4f}")
    logger.info(f"  -> Centro para DEM: ({dem_center_lat:.4f}, {dem_center_lon:.4f}), Raio Busca DEM: {dem_search_radius_km:.1f}km")

    try:
        dem_array, dem_transform, dem_crs, dem_nodata_val = await obter_dem_para_area_geografica(
            dem_center_lat, dem_center_lon, dem_search_radius_km, resolucao_desejada_m=90 
        )
    except (FileNotFoundError, NotImplementedError) as e_dem:
        logger.error(f"  -> ❌ Falha crítica ao obter DEM para a área dos overlays: {e_dem}", exc_info=True)
        raise # Propaga o erro para o router (que pode retornar 404 ou 501)

    candidate_sites_list: List[CandidateSite] = []
    imagens_overlay_pil_cache: Dict[Path, Image.Image] = {}
    MAX_DIST_REPETIDORA_ALVO_M = 1800.0 
    TAMANHO_FILTRO_PICO_LOCAL = 5 # Janela NxN para encontrar picos locais
    logger.info(f"  -> Filtros: Dist. Máx do Alvo={MAX_DIST_REPETIDORA_ALVO_M / 1000:.1f}km, Filtro Pico Local={TAMANHO_FILTRO_PICO_LOCAL}x{TAMANHO_FILTRO_PICO_LOCAL}.")

    try:
        dem_para_picos = dem_array.copy().astype(np.float32)
        if dem_nodata_val is not None: # Trata NoData antes do filtro de máximo
            dem_para_picos[dem_array == dem_nodata_val] = np.nan # np.nan é ignorado por maximum_filter com cval=np.nan
        
        valores_picos_locais = maximum_filter(dem_para_picos, size=TAMANHO_FILTRO_PICO_LOCAL, mode='constant', cval=np.nan)
        mascara_picos_locais = (dem_para_picos == valores_picos_locais) & (~np.isnan(dem_para_picos))
        
        indices_y_picos, indices_x_picos = np.where(mascara_picos_locais)
        # Converte índices de pixel para coordenadas geográficas (lon, lat no CRS do DEM)
        coords_x_mapa_picos, coords_y_mapa_picos = rasterio.transform.xy(
            dem_transform, indices_y_picos, indices_x_picos, offset='center'
        )
        logger.info(f"  -> {len(coords_x_mapa_picos)} picos locais potenciais no DEM (antes dos filtros).")

        num_picos_qualificados_antes_los = 0 

        for idx, (peak_lon_crs_dem, peak_lat_crs_dem) in enumerate(zip(coords_x_mapa_picos, coords_y_mapa_picos)):
            elevacao_pico_atual = dem_para_picos[indices_y_picos[idx], indices_x_picos[idx]]
            
            # Assumindo que o DEM (SRTM) está em WGS84 (EPSG:4326)
            # Se não, a reprojeção seria necessária aqui:
            # peak_lon_wgs84, peak_lat_wgs84 = reproject_point(peak_lon_crs_dem, peak_lat_crs_dem, dem_crs, 'EPSG:4326')
            peak_lon_wgs84, peak_lat_wgs84 = peak_lon_crs_dem, peak_lat_crs_dem
            
            # Filtro 1: Pico está em alguma área de sinal dos overlays ativos?
            esta_em_area_sinal = False
            for ov_data in active_overlays_data:
                # 'imagem_path' já é um Path absoluto aqui
                overlay_imagem_path = Path(ov_data['imagem_path'])
                
                if not overlay_imagem_path.is_file(): continue # Imagem não existe mais, pula

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
                        if pil_img_overlay.getpixel((px, py))[3] > 50: # Checa Alpha
                            esta_em_area_sinal = True
                            break 
                except Exception as e_img_check:
                    logger.warning(f"    -> ❌ Erro ao verificar cobertura do pico no overlay {overlay_imagem_path.name}: {e_img_check}")

            if not esta_em_area_sinal:
                continue 
            
            # Filtro 2: Pico está dentro da distância máxima do pivô alvo?
            distancia_pico_alvo_m = haversine(alvo_lat, alvo_lon, peak_lat_wgs84, peak_lon_wgs84)
            if distancia_pico_alvo_m > MAX_DIST_REPETIDORA_ALVO_M:
                continue 

            # Filtro 3: Pico NÃO está dentro de nenhum polígono de pivô existente?
            if shapely_pivot_polygons:
                ponto_candidato_shapely = Point(peak_lon_wgs84, peak_lat_wgs84) # (lon, lat)
                if any(piv_poly.contains(ponto_candidato_shapely) for piv_poly in shapely_pivot_polygons):
                    continue # Pico está dentro de uma área de pivô, descarta

            num_picos_qualificados_antes_los += 1
            
            # Adiciona um pequeno sleep para não sobrecarregar a API de elevação em loops longos
            # e para permitir que outras tarefas asyncio rodem.
            if num_picos_qualificados_antes_los > 1 and num_picos_qualificados_antes_los % 3 == 0 : # A cada 3 LoS checks
                await asyncio.sleep(0.1) # Pequena pausa para não sobrecarregar e permitir I/O

            if num_picos_qualificados_antes_los % 10 == 0 or num_picos_qualificados_antes_los == 1: 
                 logger.info(f"    -> Analisando LoS do candidato #{num_picos_qualificados_antes_los} ({peak_lat_wgs84:.5f}, {peak_lon_wgs84:.5f}, Elev: {elevacao_pico_atual:.1f}m, Dist: {distancia_pico_alvo_m:.0f}m)...")

            # Filtro 4: Pico tem Linha de Visada (LoS) para o pivô alvo?
            try:
                perfil_resultado = await obter_perfil_elevacao(
                    pontos=[(peak_lat_wgs84, peak_lon_wgs84), (alvo_lat, alvo_lon)],
                    alt1=altura_antena_repetidora_proposta, # Altura da antena no pico candidato
                    alt2=altura_receptor_pivo          # Altura do receptor no pivô alvo
                )
                tem_los_para_alvo = perfil_resultado.get("bloqueio") is None
                info_ponto_bloqueio = perfil_resultado.get("bloqueio")
                
                altura_torre_necessaria_m: Optional[float] = None
                if not tem_los_para_alvo and info_ponto_bloqueio and isinstance(info_ponto_bloqueio.get("diff"), (int, float)):
                    # Adiciona uma margem de segurança (ex: 3m) à diferença de bloqueio
                    altura_torre_necessaria_m = info_ponto_bloqueio["diff"] + 3.0 
            
            except ValueError as e_los_val: # Erros específicos de obter_perfil_elevacao
                 logger.warning(f"    -> ⚠️ Erro de valor ao calcular LoS para ({peak_lat_wgs84:.5f}, {peak_lon_wgs84:.5f}): {e_los_val}")
                 tem_los_para_alvo = False 
                 info_ponto_bloqueio = {"error_calculating_los": str(e_los_val)}
                 altura_torre_necessaria_m = None
            except Exception as e_los_geral:
                 logger.error(f"    -> ❌ Erro inesperado ao calcular LoS para ({peak_lat_wgs84:.5f}, {peak_lon_wgs84:.5f}): {e_los_geral}", exc_info=True)
                 tem_los_para_alvo = False 
                 info_ponto_bloqueio = {"error_calculating_los": str(e_los_geral)}
                 altura_torre_necessaria_m = None

            site_candidato_info: CandidateSite = {
                "lat": float(peak_lat_wgs84),
                "lon": float(peak_lon_wgs84),
                "elevation": float(elevacao_pico_atual), # Elevação do terreno no pico
                "has_los": tem_los_para_alvo,
                "distance_to_target": float(distancia_pico_alvo_m),
                "ponto_bloqueio": info_ponto_bloqueio,
                "altura_necessaria_torre": altura_torre_necessaria_m
            }
            candidate_sites_list.append(site_candidato_info)

        logger.info(f"  -> {len(candidate_sites_list)} locais candidatos foram analisados para LoS.")

    except Exception as e_proc_picos:
        logger.error(f"  -> ❌ Erro durante o processamento dos picos ou LoS: {e_proc_picos}", exc_info=True)
    finally:
        for img_pil in imagens_overlay_pil_cache.values():
            img_pil.close()
        logger.debug("    -> Cache de imagens PIL (busca repetidora) limpo.")

    # Ordena os candidatos: com LoS primeiro, depois por maior elevação, depois por menor distância.
    candidate_sites_list.sort(key=lambda s: (
        not s["has_los"], # False (tem LoS) vem antes de True (não tem LoS)
        -(s.get("elevation", -float('inf'))), # Maior elevação primeiro (negativo para ordem decrescente)
        s.get("distance_to_target", float('inf')) # Menor distância primeiro
    ))
    
    MAX_SITES_PARA_RETORNAR = 25 
    logger.info(f"  -> Retornando os {min(len(candidate_sites_list), MAX_SITES_PARA_RETORNAR)} melhores locais candidatos.")
    return candidate_sites_list[:MAX_SITES_PARA_RETORNAR]