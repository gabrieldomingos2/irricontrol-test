# Em backend/services/analysis_service.py

from PIL import Image
import httpx
import os
from math import sqrt, radians, sin, cos, atan2, degrees # Adicionado para Haversine
from typing import List, Dict, Optional, Tuple # Adicionado para type hints

# 👇 NOVOS IMPORTS NECESSÁRIOS 👇
import rasterio
from rasterio.windows import Window # Ou outros submódulos que você usar
from rasterio.transform import from_origin # Ou outros submódulos
from rasterio.warp import calculate_default_transform, reproject, Resampling # Se for fazer reprojeção/resampling
import numpy as np
from scipy.ndimage import maximum_filter
# import elevation # Descomente se for usar a biblioteca 'elevation' para baixar DEMs

# Usa imports absolutos
from backend import config
from backend.services import cloudrf_service # cloudrf_service é usado em obter_perfil_elevacao

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
            
            # CORREÇÃO SUGERIDA para caminho da imagem:
            # Assume que imagem_rel_path é algo como 'static/imagens/nome.png'
            # e config.PROJECT_ROOT_DIR é o diretório que contém 'backend', 'static', etc.
            # ou config.BACKEND_DIR é '.../backend' e static está em '../static'
            # A forma mais robusta é usar caminhos absolutos baseados em config.py
            
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

    for img_obj in imagens_abertas.values(): # Renomeado para evitar conflito com módulo Image
        img_obj.close()

    print("   -> Verificação de cobertura concluída.")
    return pivos_atualizados


# --- Análise de Elevação (Função Existente) ---

async def obter_perfil_elevacao(pontos: list, alt1: float, alt2: float) -> dict:
    """
    Busca elevações, calcula bloqueio de visada e retorna também o ponto mais alto da linha.
    """
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
    async with await cloudrf_service.get_http_client() as client: # get_http_client é de cloudrf_service
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
    ponto_de_bloqueio_no_perfil = None

    for i in range(1, steps): # Analisa pontos intermediários
        elev_terreno = elevs[i]
        elev_visada = linha_visada[i]
        
        if elev_terreno > elev_visada:
            diferenca = elev_terreno - elev_visada
            if diferenca > max_diferenca:
                max_diferenca = diferenca
                ponto_de_bloqueio_no_perfil = amostrados[i]
                bloqueio = {
                    "lat": amostrados[i][0],
                    "lon": amostrados[i][1],
                    "elev": float(elev_terreno),
                    "diff": float(diferenca),
                    "dist": i / steps # Distância fracional ao longo do perfil
                }

    if bloqueio:
        print(f"   -> ⛔ Bloqueio detectado! Diferença máx: {max_diferenca:.1f}m")
    else:
        print("   -> ✅ Visada livre!")

    idx_max = elevs.index(max(e for e in elevs if e is not None))
    ponto_mais_alto = {
        "lat": amostrados[idx_max][0],
        "lon": amostrados[idx_max][1],
        "elev": float(elevs[idx_max])
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
        "bloqueio": bloqueio, # Será None se não houver bloqueio
        "ponto_mais_alto": ponto_mais_alto
    }


# --- NOVAS FUNÇÕES PARA BUSCAR LOCAIS DE REPETIDORA ---

# Função auxiliar para calcular distância (Haversine) - Mova para utils se usar em mais lugares
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
    """
    Obtém dados DEM para uma área geográfica.
    Esta é uma implementação de EXEMPLO usando a biblioteca 'elevation'.
    Adapte conforme sua fonte de DEM e estratégia de armazenamento/cache.
    """
    print(f"   -> (DEM) Iniciando obtenção de DEM para área: ({lat_central}, {lon_central}), raio: {raio_busca_m}m")
    
    try:
        import elevation # Tenta importar elevation. Requer instalação.
    except ImportError:
        print("   -> ❌ A biblioteca 'elevation' não está instalada. Necessária para download automático de DEM.")
        raise NotImplementedError("Biblioteca 'elevation' não encontrada. Obtenção de DEM não implementada.")

    # Diretório para armazenar DEMs baixados (cache)
    # Usa ARQUIVOS_DIR_PATH de config.py para um caminho dentro do seu projeto backend
    dem_cache_dir = os.path.join(config.ARQUIVOS_DIR_PATH, "dem_cache")
    os.makedirs(dem_cache_dir, exist_ok=True)

    # Calcular os limites (bounds) da área de busca em graus
    # Aproximação: 1 grau de latitude ~ 111km. Para longitude, depende da latitude.
    # Uma forma mais precisa seria usar bibliotecas geodésicas, mas para o SRTM (global) isso costuma bastar.
    graus_lat_por_metro = 1.0 / 111000.0
    graus_lon_por_metro = 1.0 / (111000.0 * cos(radians(lat_central)))
    
    offset_lat = raio_busca_m * graus_lat_por_metro
    offset_lon = raio_busca_m * graus_lon_por_metro
    
    bounds = ( # west, south, east, north
        lon_central - offset_lon, lat_central - offset_lat,
        lon_central + offset_lon, lat_central + offset_lat
    )
    
    # Nome do arquivo de saída para o DEM (pode ser um .tif temporário ou cacheado)
    # Um nome de cache mais robusto poderia incluir os bounds ou um hash deles.
    output_dem_filename = f"dem_clip_{lat_central:.4f}_{lon_central:.4f}_{int(raio_busca_m)}m.tif"
    output_dem_path = os.path.join(dem_cache_dir, output_dem_filename)

    try:
        # Baixa (se não existir no cache local do 'elevation') e recorta o DEM para os bounds.
        # Produtos: 'SRTM1' (~30m), 'SRTM3' (~90m), 'COP30' (~30m), 'COP90' (~90m)
        # A API OpenTopoData que você usa para perfis é baseada em SRTM90m.
        # Usar SRTM3 (90m) aqui pode ser um bom começo para consistência e velocidade.
        # Se precisar de maior resolução, 'COP30' é uma boa opção.
        if not os.path.exists(output_dem_path): # Só baixa se não existir no nosso cache local
            print(f"      -> DEM não encontrado em cache local: {output_dem_path}. Baixando com 'elevation' (produto SRTM3)...")
            elevation.clip(bounds=bounds, output=output_dem_path, product='SRTM3')
            print(f"      -> DEM baixado e salvo em: {output_dem_path}")
        else:
            print(f"      -> Usando DEM do cache local: {output_dem_path}")

        with rasterio.open(output_dem_path) as src:
            # Se uma resolução desejada for fornecida e for diferente da fonte,
            # você poderia adicionar lógica de resampling aqui usando rasterio.warp.reproject.
            # Por simplicidade, vamos usar a resolução nativa do DEM baixado/cacheado.
            
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
        # Se falhar ao obter DEM, levanta uma exceção que o endpoint pode tratar.
        raise FileNotFoundError(f"Falha crítica ao obter DEM para a área via 'elevation': {e}")


async def encontrar_locais_altos_para_repetidora(
    alvo_lat: float, alvo_lon: float, alvo_nome: str, raio_busca_m: float,
    altura_antena_repetidora_proposta: float, altura_receptor_pivo: float
) -> List[Dict]:
    """
    Encontra pontos altos em um raio ao redor do pivô alvo e verifica LoS.
    """
    print(f"🔎 Iniciando busca por pontos altos para o pivô '{alvo_nome}' em ({alvo_lat:.5f}, {alvo_lon:.5f}), raio {raio_busca_m}m.")

    try:
        # Resolução do DEM: SRTM3 é ~90m. Se usar COP30, seria ~30m.
        # A escolha da resolução afeta o 'tamanho_filtro_maximo'.
        dem_array, dem_transform, dem_crs, dem_nodata = await obter_dem_para_area_geografica(
            alvo_lat, alvo_lon, raio_busca_m, resolucao_desejada_m=90 
        )
    except (FileNotFoundError, NotImplementedError) as e_dem:
        raise e_dem # Re-levanta para ser pego pelo endpoint

    candidate_sites = []

    try:
        # Tamanho do filtro (ímpar) para maximum_filter. Ex: 3 para janela 3x3, 5 para 5x5.
        # Se DEM é 90m, uma janela pequena (ex: 3 ou 5) detecta picos mais locais.
        # Uma janela maior suaviza mais e pega picos mais proeminentes regionalmente.
        tamanho_filtro_maximo = 5 
        print(f"   -> Identificando máximos locais no DEM com filtro de vizinhança {tamanho_filtro_maximo}x{tamanho_filtro_maximo}...")
        
        dem_processado = dem_array.copy().astype(np.float32) # Converte para float para manipulação de NaN
        nodata_original = dem_nodata
        
        if nodata_original is not None:
            dem_processado[dem_array == nodata_original] = np.nan # Usa NaN para facilitar a máscara

        # Aplicar filtro máximo. 'reflect' trata as bordas.
        local_max_values = maximum_filter(dem_processado, size=tamanho_filtro_maximo, mode='reflect', cval=np.nan)
        local_max_mask = (dem_processado == local_max_values) & (~np.isnan(dem_processado)) # Picos são onde o valor é igual ao máximo local e não é NaN
        
        y_pixels, x_pixels = np.where(local_max_mask)
        
        # Converter coordenadas de pixel para coordenadas geográficas (lon, lat do CRS do DEM)
        # A função xy de rasterio espera x (colunas), depois y (linhas)
        map_x_coords, map_y_coords = rasterio.transform.xy(dem_transform, y_pixels, x_pixels, offset='center')
        
        print(f"   -> Encontrados {len(map_x_coords)} picos locais potenciais no DEM.")

        contador_picos_no_raio = 0
        for idx, (peak_lon_dem_crs, peak_lat_dem_crs) in enumerate(zip(map_x_coords, map_y_coords)):
            peak_elev_val = dem_processado[y_pixels[idx], x_pixels[idx]]

            # Aqui, peak_lon_dem_crs e peak_lat_dem_crs estão no CRS do DEM.
            # A função haversine espera WGS84 (lat,lon). Se o DEM não for WGS84, precisa reprojetar.
            # SRTM (usado por 'elevation') é tipicamente WGS84 (EPSG:4326), então a conversão pode não ser necessária.
            # Vamos assumir que dem_crs é EPSG:4326 por enquanto. Se não for, uma etapa de reprojeção é necessária aqui.
            if dem_crs and dem_crs.to_epsg() != 4326:
                print(f"      -> AVISO: CRS do DEM é {dem_crs.to_epsg()}, mas Haversine e LoS esperam WGS84 (EPSG:4326). Reprojeção do ponto seria necessária.")
                # Aqui você precisaria usar pyproj ou similar para converter (peak_lon_dem_crs, peak_lat_dem_crs) para WGS84
                # Por simplicidade, vamos assumir que é WGS84.
                pass

            peak_lat_wgs84, peak_lon_wgs84 = peak_lat_dem_crs, peak_lon_dem_crs

            dist_ao_alvo = haversine(alvo_lat, alvo_lon, peak_lat_wgs84, peak_lon_wgs84)
            
            if dist_ao_alvo > raio_busca_m + 200: # Adiciona uma pequena margem para picos na borda do DEM recortado
                continue
            
            contador_picos_no_raio += 1
            if contador_picos_no_raio % 10 == 0: # Log a cada 10 picos dentro do raio
                 print(f"      -> Analisando LoS do pico {contador_picos_no_raio} ({peak_lat_wgs84:.5f}, {peak_lon_wgs84:.5f}, Elev: {peak_elev_val:.1f}m)...")

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
                    # Estimativa simples: diff + margem (ex: 3m para alguma folga Fresnel ou obstáculos menores)
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
        
        print(f"   -> {len(candidate_sites)} picos dentro do raio de busca e analisados para LoS.")

    except Exception as e_proc:
        print(f"   -> ❌ Erro durante o processamento dos picos ou LoS: {e_proc}")
        import traceback
        traceback.print_exc()
        # Não levanta exceção aqui para permitir que o que foi processado seja retornado.
        # O endpoint pode decidir o que fazer.

    candidate_sites.sort(key=lambda s: (not s["has_los"], -s.get("elevation", 0), s.get("distance_to_target", float('inf'))))

    MAX_SITES_TO_RETURN = 25 # Aumentado um pouco para dar mais opções ao usuário
    print(f"   -> Retornando os {min(len(candidate_sites), MAX_SITES_TO_RETURN)} melhores locais candidatos.")
    return candidate_sites[:MAX_SITES_TO_RETURN]