# Em backend/services/analysis_service.py

from PIL import Image
import httpx
import os
from math import sqrt, radians, sin, cos, atan2, degrees
from typing import List, Dict, Optional, Tuple

import asyncio
import rasterio
from rasterio.windows import Window
from rasterio.transform import from_origin
from rasterio.warp import calculate_default_transform, reproject, Resampling
import numpy as np
from scipy.ndimage import maximum_filter
from shapely.geometry import Point, Polygon
# import elevation # Descomente se for usar a biblioteca 'elevation' para baixar DEMs

from backend import config
from backend.services import cloudrf_service # Usado para get_http_client em obter_perfil_elevacao

# --- Análise de Cobertura ---

def verificar_cobertura_pivos(pivos: list, overlays_info: list) -> list:
    """
    Verifica quais pivôs estão cobertos por pelo menos um dos overlays fornecidos.
    """
    print(f"🔎 Verificando cobertura para {len(pivos)} pivôs com {len(overlays_info)} overlays.")
    
    imagens_abertas = {}
    pivos_atualizados = []

    for pivo in pivos:
        lat, lon = pivo["lat"], pivo["lon"]
        coberto = False

        for overlay in overlays_info:
            bounds = overlay["bounds"]
            imagem_rel_path = overlay["imagem"] # Ex: 'static/imagens/nome_imagem.png'
            
            nome_base_imagem = os.path.basename(imagem_rel_path.split('?')[0])
            imagem_full_path = os.path.join(config.IMAGENS_DIR_PATH, nome_base_imagem)

            if not os.path.exists(imagem_full_path):
                print(f"   -> ⚠️ Imagem não encontrada em: {imagem_full_path} (original path: {imagem_rel_path})")
                continue

            try:
                if imagem_full_path not in imagens_abertas:
                    imagens_abertas[imagem_full_path] = Image.open(imagem_full_path).convert("RGBA")
                
                img = imagens_abertas[imagem_full_path]
                largura, altura_img = img.size

                sul, oeste, norte, leste = bounds
                if sul > norte: sul, norte = norte, sul
                if oeste > leste: oeste, leste = leste, oeste

                delta_lon = leste - oeste
                delta_lat = norte - sul
                if delta_lon == 0 or delta_lat == 0: continue

                x = int((lon - oeste) / delta_lon * largura)
                y = int((norte - lat) / delta_lat * altura_img)

                if 0 <= x < largura and 0 <= y < altura_img:
                    _, _, _, a = img.getpixel((x, y))
                    if a > 50: # Limiar de transparência
                        coberto = True
                        break 
            except Exception as e:
                print(f"   -> ❌ Erro ao analisar overlay {imagem_rel_path} para {pivo['nome']}: {e}")

        pivo["fora"] = not coberto
        pivos_atualizados.append(pivo)

    for img_obj in imagens_abertas.values():
        img_obj.close()

    print("   -> Verificação de cobertura concluída.")
    return pivos_atualizados


# --- Análise de Elevação (Função Existente) ---

async def obter_perfil_elevacao(pontos: list, alt1: float, alt2: float) -> dict:
    if len(pontos) != 2:
        raise ValueError("São necessários exatamente dois pontos.")

    steps = 50
    print(f"⛰️  Calculando perfil de elevação com {steps} passos...")

    amostrados = [
        (pontos[0][0] + (pontos[1][0] - pontos[0][0]) * i / steps,
         pontos[0][1] + (pontos[1][1] - pontos[0][1]) * i / steps)
        for i in range(steps + 1)
    ]

    coords_param = "|".join([f"{lat:.6f},{lon:.6f}" for lat, lon in amostrados])
    url = f"https://api.opentopodata.org/v1/srtm90m?locations={coords_param}"

    print("   -> Buscando elevações na OpenTopoData...")
    async with await cloudrf_service.get_http_client() as client: 
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            dados = resp.json()
        except Exception as e:
            print(f"   -> ❌ Erro ao buscar elevações: {e}")
            raise ValueError(f"Falha ao buscar dados de elevação: {e}")

    if not dados or "results" not in dados or not dados["results"]:
        raise ValueError("Resposta inválida ou vazia da API de elevação.")

    elevs = [r["elevation"] for r in dados["results"]]
    if not elevs or any(e is None for e in elevs):
        raise ValueError("Dados de elevação inválidos ou ausentes recebidos da API.")
        
    print(f"   -> Elevações recebidas (Min: {min(e for e in elevs if e is not None):.1f}m, Max: {max(e for e in elevs if e is not None):.1f}m)")

    elev1_total = elevs[0] + alt1
    elev2_total = elevs[-1] + alt2
    linha_visada = [
        elev1_total + i * (elev2_total - elev1_total) / steps
        for i in range(steps + 1)
    ]

    bloqueio = None
    max_diferenca = 0
    
    for i in range(1, steps): 
        elev_terreno = elevs[i]
        elev_visada = linha_visada[i]
        
        if elev_terreno > elev_visada:
            diferenca = elev_terreno - elev_visada
            if diferenca > max_diferenca:
                max_diferenca = diferenca
                bloqueio = {
                    "lat": amostrados[i][0],
                    "lon": amostrados[i][1],
                    "elev": float(elev_terreno),
                    "diff": float(diferenca),
                    "dist": i / steps 
                }

    if bloqueio:
        print(f"   -> ⛔ Bloqueio detectado! Diferença máx: {max_diferenca:.1f}m")
    else:
        print("   -> ✅ Visada livre!")

    idx_max_val = -float('inf')
    idx_max_idx = 0
    for i, e_val in enumerate(elevs):
        if e_val is not None and e_val > idx_max_val:
            idx_max_val = e_val
            idx_max_idx = i
            
    ponto_mais_alto = {
        "lat": amostrados[idx_max_idx][0],
        "lon": amostrados[idx_max_idx][1],
        "elev": float(elevs[idx_max_idx]) if elevs[idx_max_idx] is not None else None
    }

    print(f"   -> 🏔️ Ponto mais alto na linha: {ponto_mais_alto}")

    return {
        "perfil": [
            {
                "lat": amostrados[i][0],
                "lon": amostrados[i][1],
                "elev": float(elevs[i]) if elevs[i] is not None else None,
                "dist": i * (1 / steps)
            }
            for i in range(steps + 1)
        ],
        "bloqueio": bloqueio,
        "ponto_mais_alto": ponto_mais_alto
    }


# --- NOVAS FUNÇÕES PARA BUSCAR LOCAIS DE REPETIDORA ---

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000  # Raio da Terra em metros
    phi1, phi2 = radians(lat1), radians(lat2)
    delta_phi = radians(lat2 - lat1)
    delta_lambda = radians(lon2 - lon1)
    a = sin(delta_phi / 2)**2 + cos(phi1) * cos(phi2) * sin(delta_lambda / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c

async def obter_dem_para_area_geografica(
    lat_central: float, lon_central: float, raio_busca_m: float,
    resolucao_desejada_m: Optional[float] = None 
) -> Tuple[np.ndarray, rasterio.Affine, rasterio.crs.CRS, Optional[float]]:
    print(f"   -> (DEM) Iniciando obtenção de DEM para área: ({lat_central}, {lon_central}), raio: {raio_busca_m}m")
    
    try:
        import elevation 
    except ImportError:
        print("   -> ❌ A biblioteca 'elevation' não está instalada. Necessária para download automático de DEM.")
        raise NotImplementedError("Biblioteca 'elevation' não encontrada. Obtenção de DEM não implementada.")

    dem_cache_dir = os.path.join(config.ARQUIVOS_DIR_PATH, "dem_cache")
    os.makedirs(dem_cache_dir, exist_ok=True)

    graus_lat_por_metro = 1.0 / 111000.0
    graus_lon_por_metro = 1.0 / (111000.0 * cos(radians(lat_central)))
    
    offset_lat = raio_busca_m * graus_lat_por_metro
    offset_lon = raio_busca_m * graus_lon_por_metro
    
    bounds_dem = ( 
        lon_central - offset_lon, lat_central - offset_lat,
        lon_central + offset_lon, lat_central + offset_lat
    )
    
    output_dem_filename = f"dem_clip_{lat_central:.4f}_{lon_central:.4f}_{int(raio_busca_m)}m.tif"
    output_dem_path = os.path.join(dem_cache_dir, output_dem_filename)

    try:
        if not os.path.exists(output_dem_path):
            print(f"      -> DEM não encontrado em cache local: {output_dem_path}. Baixando com 'elevation' (produto SRTM3)...")
            elevation.clip(bounds=bounds_dem, output=output_dem_path, product='SRTM3')
            print(f"      -> DEM baixado e salvo em: {output_dem_path}")
        else:
            print(f"      -> Usando DEM do cache local: {output_dem_path}")

        with rasterio.open(output_dem_path) as src:
            dem_array = src.read(1)
            dem_transform = src.transform
            dem_crs = src.crs
            dem_nodata = src.nodata
            print(f"      -> DEM carregado: Forma={dem_array.shape}, Resolução Nativa XY={src.res}, NoData={dem_nodata}, CRS={dem_crs}")
            return dem_array, dem_transform, dem_crs, dem_nodata

    except Exception as e:
        print(f"   -> ❌ Erro ao obter/processar DEM com 'elevation': {e}")
        import traceback
        traceback.print_exc()
        raise FileNotFoundError(f"Falha crítica ao obter DEM para a área via 'elevation': {e}")


async def encontrar_locais_altos_para_repetidora(
    alvo_lat: float, alvo_lon: float, alvo_nome: str,
    altura_antena_repetidora_proposta: float, altura_receptor_pivo: float,
    active_overlays_data: List[Dict],
    pivot_polygons_coords_data: Optional[List[List[Tuple[float, float]]]] = None # <--- NOVO PARÂMETRO
) -> List[Dict]:
    """
    Encontra pontos altos DENTRO DAS ÁREAS DE COBERTURA (active_overlays_data),
    FORA DOS POLÍGONOS DE PIVÔS (pivot_polygons_coords_data),
    a uma DISTÂNCIA MÁXIMA (1.8km) do pivô alvo, e verifica LoS para o pivô alvo.
    """
    print(f"🔎 Iniciando busca por pontos altos para pivô '{alvo_nome}' ({alvo_lat:.5f}, {alvo_lon:.5f})") 
    
    if not active_overlays_data:
        print("⚠️ Nenhum overlay ativo fornecido. Não é possível buscar locais.")
        return []

    # --- NOVO: Preparar polígonos de pivôs para verificação ---
    shapely_pivot_polygons = []
    if pivot_polygons_coords_data:
        for poly_coords_list in pivot_polygons_coords_data:
            # O frontend envia coordenadas como [lat, lon]. Shapely Polygon espera (lon, lat).
            shapely_coords = [(coord_pair[1], coord_pair[0]) for coord_pair in poly_coords_list]
            if len(shapely_coords) >= 3: # Um polígono precisa de pelo menos 3 pontos
                try:
                    shapely_pivot_polygons.append(Polygon(shapely_coords))
                except Exception as e_shapely:
                    print(f"      -> ⚠️ Erro ao criar polígono Shapely para um ciclo: {e_shapely}. Coords: {poly_coords_list}")
            else:
                print(f"      -> ⚠️ Coordenadas insuficientes para formar polígono de pivô: {poly_coords_list}")
        
        if shapely_pivot_polygons:
            print(f"   -> {len(shapely_pivot_polygons)} polígonos de pivôs (ciclos) carregados para exclusão de área.")
    # --- FIM NOVO ---

    # (Lógica para determinar Bounding Box do DEM e obter DEM permanece a mesma)
    min_overall_lat = float('inf')
    # ... (código para calcular dem_center_lat, dem_center_lon, dem_effective_radius_m) ...
    max_overall_lat = float('-inf')
    min_overall_lon = float('inf')
    max_overall_lon = float('-inf')
    for ov_data in active_overlays_data:
        s, w, n, e = ov_data['bounds'] 
        min_overall_lat = min(min_overall_lat, s)
        max_overall_lat = max(max_overall_lat, n)
        min_overall_lon = min(min_overall_lon, w)
        max_overall_lon = max(max_overall_lon, e)
    if any(val == float('inf') or val == float('-inf') for val in [min_overall_lat, max_overall_lat, min_overall_lon, max_overall_lon]):
        raise ValueError("Limites inválidos ou ausentes dos overlays ativos.")
    dem_center_lat = (min_overall_lat + max_overall_lat) / 2
    dem_center_lon = (min_overall_lon + max_overall_lon) / 2
    width_m = haversine(dem_center_lat, min_overall_lon, dem_center_lat, max_overall_lon)
    height_m = haversine(min_overall_lat, dem_center_lon, max_overall_lat, dem_center_lon)
    dem_effective_radius_m = (sqrt(width_m**2 + height_m**2) / 2) + 500 
    print(f"   -> Limites globais dos overlays: S={min_overall_lat:.4f}, W={min_overall_lon:.4f}, N={max_overall_lat:.4f}, E={max_overall_lon:.4f}")
    print(f"   -> Centro para busca DEM: ({dem_center_lat:.4f}, {dem_center_lon:.4f}), Raio Efetivo para DEM: {dem_effective_radius_m:.0f}m")
    try:
        dem_array, dem_transform, dem_crs, dem_nodata = await obter_dem_para_area_geografica(
            dem_center_lat, dem_center_lon, dem_effective_radius_m, resolucao_desejada_m=90 
        )
    except (FileNotFoundError, NotImplementedError) as e_dem:
        print(f"   -> ❌ Falha ao obter DEM para a área dos overlays: {e_dem}")
        raise e_dem

    candidate_sites = []
    imagens_overlay_cache = {}
    MAX_DISTANCIA_DO_PIVO_ALVO_M = 1800.0 
    print(f"   -> Restrição de distância: locais candidatos devem estar a no máximo {MAX_DISTANCIA_DO_PIVO_ALVO_M / 1000:.1f} km do pivô alvo.")
    tamanho_filtro_maximo = 5
    print(f"   -> Usando filtro de vizinhança {tamanho_filtro_maximo}x{tamanho_filtro_maximo} para identificar picos.")

    try:
        # (Lógica de identificação de picos no DEM permanece a mesma)
        dem_processado = dem_array.copy().astype(np.float32)
        # ... (código para local_max_mask, y_pixels, x_pixels, map_x_coords, map_y_coords) ...
        nodata_original = dem_nodata
        if nodata_original is not None:
            dem_processado[dem_array == nodata_original] = np.nan
        local_max_values = maximum_filter(dem_processado, size=tamanho_filtro_maximo, mode='reflect', cval=np.nan)
        local_max_mask = (dem_processado == local_max_values) & (~np.isnan(dem_processado))
        y_pixels, x_pixels = np.where(local_max_mask)
        map_x_coords, map_y_coords = rasterio.transform.xy(dem_transform, y_pixels, x_pixels, offset='center')
        print(f"   -> Encontrados {len(map_x_coords)} picos locais potenciais no DEM (antes dos filtros).")

        contador_picos_validos = 0 

        for idx, (peak_lon_dem_crs, peak_lat_dem_crs) in enumerate(zip(map_x_coords, map_y_coords)):
            peak_elev_val = dem_processado[y_pixels[idx], x_pixels[idx]]
            peak_lat_wgs84, peak_lon_wgs84 = peak_lat_dem_crs, peak_lon_dem_crs
            if dem_crs and dem_crs.to_epsg() != 4326:
                # Implementar reprojeção se CRS do DEM não for WGS84 (EPSG:4326)
                pass 
            
            # Filtro 1: Pico em área de sinal
            # (Lógica para peak_in_signal_area permanece a mesma)
            peak_in_signal_area = False
            # ... (código para verificar peak_in_signal_area) ...
            for ov_data_inner in active_overlays_data: # Renomeado para evitar conflito
                ov_bounds = ov_data_inner['bounds']
                ov_image_rel_path = ov_data_inner['imagem']
                ov_nome_base_imagem = os.path.basename(ov_image_rel_path.split('?')[0])
                ov_imagem_full_path = os.path.join(config.IMAGENS_DIR_PATH, ov_nome_base_imagem)
                if not os.path.exists(ov_imagem_full_path): continue
                try:
                    if ov_imagem_full_path not in imagens_overlay_cache:
                        imagens_overlay_cache[ov_imagem_full_path] = Image.open(ov_imagem_full_path).convert("RGBA")
                    img_overlay_pil = imagens_overlay_cache[ov_imagem_full_path]
                    ov_img_width, ov_img_height = img_overlay_pil.size
                    ov_sul_b, ov_oeste_b, ov_norte_b, ov_leste_b = ov_bounds # Renomeado para evitar conflito de escopo
                    if ov_sul_b > ov_norte_b: ov_sul_b, ov_norte_b = ov_norte_b, ov_sul_b
                    if ov_oeste_b > ov_leste_b: ov_oeste_b, ov_leste_b = ov_leste_b, ov_oeste_b
                    ov_delta_lon_b, ov_delta_lat_b = ov_leste_b - ov_oeste_b, ov_norte_b - ov_sul_b
                    if ov_delta_lon_b == 0 or ov_delta_lat_b == 0: continue
                    px_in_ov = int((peak_lon_wgs84 - ov_oeste_b) / ov_delta_lon_b * ov_img_width)
                    py_in_ov = int((ov_norte_b - peak_lat_wgs84) / ov_delta_lat_b * ov_img_height)
                    if 0 <= px_in_ov < ov_img_width and 0 <= py_in_ov < ov_img_height:
                        if img_overlay_pil.getpixel((px_in_ov, py_in_ov))[3] > 50:
                            peak_in_signal_area = True
                            break 
                except Exception as e_img_check:
                    print(f"      -> ❌ Erro ao verificar cobertura do pico no overlay {ov_image_rel_path}: {e_img_check}")

            if not peak_in_signal_area:
                continue 
            
            # Filtro 2: Pico dentro da distância máxima do pivô alvo
            dist_ao_alvo = haversine(alvo_lat, alvo_lon, peak_lat_wgs84, peak_lon_wgs84)
            if dist_ao_alvo > MAX_DISTANCIA_DO_PIVO_ALVO_M:
                continue 

            # --- NOVO FILTRO 3: Verificar se o pico está DENTRO de algum polígono de pivô ---
            if shapely_pivot_polygons:
                candidate_point_shapely = Point(peak_lon_wgs84, peak_lat_wgs84) # Point(lon, lat)
                is_inside_a_pivot_area = False
                for pivot_poly in shapely_pivot_polygons:
                    if pivot_poly.contains(candidate_point_shapely):
                        is_inside_a_pivot_area = True
                        break 
                if is_inside_a_pivot_area:
                    # print(f"      -> Descartado: Pico ({peak_lat_wgs84:.4f}, {peak_lon_wgs84:.4f}) está dentro de um polígono de pivô.") # Opcional
                    continue # Pula este pico
            # --- FIM NOVO FILTRO 3 ---
            
            contador_picos_validos +=1 
            
            if contador_picos_validos > 1:
                await asyncio.sleep(0.3) 

            if contador_picos_validos % 5 == 0 or contador_picos_validos == 1: 
                 print(f"      -> Analisando LoS do candidato #{contador_picos_validos} ({peak_lat_wgs84:.5f}, {peak_lon_wgs84:.5f}, Elev: {peak_elev_val:.1f}m, Dist: {dist_ao_alvo:.0f}m)...")

            # (Lógica de cálculo de LoS e armazenamento de site_info permanece a mesma)
            # ...
            try:
                perfil_data = await obter_perfil_elevacao(
                    pontos=[[peak_lat_wgs84, peak_lon_wgs84], [alvo_lat, alvo_lon]],
                    alt1=altura_antena_repetidora_proposta,
                    alt2=altura_receptor_pivo
                )
                has_los_to_target = perfil_data.get("bloqueio") is None
                ponto_bloqueio_info = perfil_data.get("bloqueio")
                altura_torre_necessaria = None
                if not has_los_to_target and ponto_bloqueio_info and isinstance(ponto_bloqueio_info.get("diff"), (int, float)):
                    altura_torre_necessaria = ponto_bloqueio_info.get("diff", 0) + 3.0
            except Exception as e_los:
                print(f"      -> ⚠️ Erro ao calcular LoS para ({peak_lat_wgs84:.5f}, {peak_lon_wgs84:.5f}): {e_los}")
                has_los_to_target = False 
                ponto_bloqueio_info = {"error_calculating_los": str(e_los)}
                altura_torre_necessaria = None

            site_info = {
                "lat": float(peak_lat_wgs84),
                "lon": float(peak_lon_wgs84),
                "elevation": float(peak_elev_val),
                "has_los": has_los_to_target,
                "distance_to_target": float(dist_ao_alvo),
                "ponto_bloqueio": ponto_bloqueio_info,
                "altura_necessaria_torre": float(altura_torre_necessaria) if altura_torre_necessaria is not None else None
            }
            candidate_sites.append(site_info)

        print(f"   -> {len(candidate_sites)} locais candidatos (em cobertura, fora dos pivôs, dentro de {MAX_DISTANCIA_DO_PIVO_ALVO_M/1000:.1f}km) foram analisados para LoS.")

    # (Bloco except Exception e finally permanecem os mesmos)
    except Exception as e_proc: # ...
        print(f"   -> ❌ Erro durante o processamento dos picos ou LoS: {e_proc}")
        import traceback
        traceback.print_exc()
    finally: # ...
        for img_pil_cached_inner in imagens_overlay_cache.values(): # Renomeado para evitar conflito
            img_pil_cached_inner.close()
        if 'imagens_overlay_cache' in locals(): 
            del imagens_overlay_cache

    # (Ordenação e retorno dos candidate_sites permanecem os mesmos)
    candidate_sites.sort(key=lambda s: (not s["has_los"], -s.get("elevation", 0), s.get("distance_to_target", float('inf')))) # ...
    MAX_SITES_TO_RETURN = 25 
    print(f"   -> Retornando os {min(len(candidate_sites), MAX_SITES_TO_RETURN)} melhores locais candidatos.")
    return candidate_sites[:MAX_SITES_TO_RETURN]