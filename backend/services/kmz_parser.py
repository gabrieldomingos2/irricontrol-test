import zipfile
# import os # Substituído por pathlib
import re
import xml.etree.ElementTree as ET
from statistics import mean
from shapely.geometry import Polygon, Point
from math import sqrt
from pathlib import Path # Adicionado para manipulação moderna de caminhos
import logging # Adicionado para logging
from typing import List, Tuple, Dict, Optional, TypedDict, Union

# Configuração do Logger
logger = logging.getLogger("irricontrol")

# --- Constantes ---
KML_NAMESPACE = {"kml": "http://www.opengis.net/kml/2.2"}
ANTENA_KEYWORDS = ["central", "antena", "torre", "barracão", "galpão", "silo", "caixa", "repetidora"]
PIVO_KEYWORDS = ["pivô", "pivo"] # Adicionado "pivo" sem acento
BOMBA_KEYWORDS = ["bomba", "irripump"]
PONTA_RETA_KEYWORDS = ["ponta 1 reta", "ponta 2 reta"]
DEFAULT_ANTENA_HEIGHT = 15
DEFAULT_RECEIVER_HEIGHT = 3 # Altura padrão para o receptor na antena
CIRCLE_CLOSENESS_THRESHOLD = 0.0005 # Para eh_um_circulo

# Regex pré-compilado para extrair altura da antena
HEIGHT_REGEX = re.compile(r"(\d{1,3})\s*(m|metros)")

# --- TypedDicts para Estruturas de Dados ---

class CoordsDict(TypedDict):
    lat: float
    lon: float

class AntenaData(CoordsDict):
    altura: int
    altura_receiver: int
    nome: str

class PivoData(CoordsDict):
    nome: str

class CicloData(TypedDict):
    nome_original_circulo: str # Mantido para clareza da origem
    coordenadas: List[List[float]] # Lista de [lat, lon]

class BombaData(CoordsDict):
    nome: str

# --- Funções Auxiliares ---

def normalizar_nome(nome: str) -> str:
    """Normaliza um nome para facilitar comparações: minúsculas, remove caracteres especiais, remove espaços extras."""
    if not nome:
        return ""
    nome_lower = nome.lower()
    # Remove caracteres que não sejam letras (incluindo acentuadas comuns), números ou espaços
    # A-Za-zÀ-ÖØ-öø-ÿ cobre uma gama maior de caracteres acentuados europeus.
    nome_sem_especiais = re.sub(r'[^a-z0-9\sÀ-ÖØ-öø-ÿ]', '', nome_lower)
    nome_normalizado = re.sub(r'\s+', ' ', nome_sem_especiais).strip()
    return nome_normalizado

def calcular_meio_reta(p1: CoordsDict, p2: CoordsDict) -> Tuple[float, float]:
    """Calcula o ponto médio entre duas coordenadas (lat, lon)."""
    meio_lat = (p1["lat"] + p2["lat"]) / 2
    meio_lon = (p1["lon"] + p2["lon"]) / 2
    return meio_lat, meio_lon

def ponto_central_da_reta_maior(coords_list: List[List[float]]) -> Tuple[float, float, List[float], List[float]]:
    """
    Encontra a maior reta entre quaisquer dois pontos em uma lista de coordenadas [lat, lon]
    e retorna o ponto médio dessa reta e os pontos da reta.
    """
    if not coords_list or len(coords_list) < 2:
        raise ValueError("São necessários pelo menos dois pontos para calcular a reta maior.")

    max_dist_sq = 0  # Comparar quadrados evita sqrt repetidos
    ponta1_final, ponta2_final = coords_list[0], coords_list[1] # Inicializa com os dois primeiros

    for i in range(len(coords_list)):
        for j in range(i + 1, len(coords_list)):
            p1 = coords_list[i]  # [lat1, lon1]
            p2 = coords_list[j]  # [lat2, lon2]
            # Distância Euclidiana ao quadrado (mais rápido para comparação)
            # Cuidado: Esta é uma aproximação em coordenadas geográficas.
            dist_sq = (p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2
            if dist_sq > max_dist_sq:
                max_dist_sq = dist_sq
                ponta1_final, ponta2_final = p1, p2

    meio_lat = (ponta1_final[0] + ponta2_final[0]) / 2
    meio_lon = (ponta1_final[1] + ponta2_final[1]) / 2
    return meio_lat, meio_lon, ponta1_final, ponta2_final

def eh_um_circulo(coords_list: List[List[float]], threshold: float = CIRCLE_CLOSENESS_THRESHOLD) -> bool:
    """
    Detecta se um conjunto de pontos [lat, lon] forma uma curva fechada (aproximadamente um círculo)
    verificando a distância entre o primeiro e o último ponto.
    """
    if len(coords_list) < 3: # Um círculo precisa de pelo menos 3 pontos para ser definido por uma LineString
        return False
    # Shapely Point espera (x, y) -> (lon, lat)
    primeiro_ponto = Point(coords_list[0][1], coords_list[0][0])
    ultimo_ponto = Point(coords_list[-1][1], coords_list[-1][0])
    distancia = primeiro_ponto.distance(ultimo_ponto)
    return distancia < threshold


def _extract_kml_from_zip(caminho_kmz: Path, pasta_extracao: Path) -> Path:
    """Extrai o primeiro arquivo .kml de um KMZ para a pasta de extração."""
    try:
        with zipfile.ZipFile(caminho_kmz, 'r') as kmz_file:
            kml_file_name = next((f for f in kmz_file.namelist() if f.lower().endswith('.kml')), None)
            if not kml_file_name:
                raise ValueError("Nenhum arquivo .kml encontrado dentro do KMZ.")
            
            kmz_file.extract(kml_file_name, path=pasta_extracao)
            caminho_kml_extraido = pasta_extracao / kml_file_name
            
            logger.info(f"  -> Arquivo KML '{kml_file_name}' extraído para '{caminho_kml_extraido}'")
            return caminho_kml_extraido
    except zipfile.BadZipFile:
        logger.error(f"Erro: Arquivo '{caminho_kmz}' não é um ZIP válido ou está corrompido.")
        raise ValueError(f"Arquivo KMZ '{caminho_kmz.name}' inválido ou corrompido.")
    except Exception as e:
        logger.error(f"Erro ao extrair KML do KMZ '{caminho_kmz}': {e}", exc_info=True)
        raise


def _parse_placemark_data(placemark_node: ET.Element) -> Optional[Dict[str, Union[str, List[List[float]]]]]:
    """Extrai nome e coordenadas de um Placemark, dependendo do tipo de geometria."""
    nome_tag = placemark_node.find("kml:name", KML_NAMESPACE)
    nome_original = nome_tag.text.strip() if nome_tag is not None and nome_tag.text else ""

    data: Dict[str, Union[str, List[List[float]]]] = {"nome_original": nome_original}
    geometry_type: Optional[str] = None

    point_coords_tag = placemark_node.find(".//kml:Point/kml:coordinates", KML_NAMESPACE)
    linestring_coords_tag = placemark_node.find(".//kml:LineString/kml:coordinates", KML_NAMESPACE)
    polygon_coords_tag = placemark_node.find(".//kml:Polygon/kml:outerBoundaryIs/kml:LinearRing/kml:coordinates", KML_NAMESPACE)

    coords_text: Optional[str] = None
    if point_coords_tag is not None and point_coords_tag.text:
        coords_text = point_coords_tag.text.strip()
        geometry_type = "Point"
    elif linestring_coords_tag is not None and linestring_coords_tag.text:
        coords_text = linestring_coords_tag.text.strip()
        geometry_type = "LineString"
    elif polygon_coords_tag is not None and polygon_coords_tag.text:
        coords_text = polygon_coords_tag.text.strip()
        geometry_type = "Polygon"

    if not coords_text or not geometry_type:
        return None

    data["geometry_type"] = geometry_type
    
    parsed_coords_list: List[List[float]] = []
    for coord_tuple_str in coords_text.split():
        parts = coord_tuple_str.split(',')
        if len(parts) >= 2:
            try:
                lon, lat = float(parts[0]), float(parts[1])
                parsed_coords_list.append([lat, lon])
            except ValueError:
                logger.warning(f"Não foi possível parsear coordenadas '{coord_tuple_str}' para o placemark '{nome_original}'. Pulando.")
                continue
    
    if not parsed_coords_list:
        logger.warning(f"Nenhuma coordenada válida encontrada para o placemark '{nome_original}' após o parsing. Pulando placemark.")
        return None

    data["coordenadas_lista"] = parsed_coords_list
    return data

# --- NOVA FUNÇÃO AUXILIAR PARA NOMEAÇÃO ---
def gerar_nome_pivo_sequencial_unico(lista_de_nomes_existentes_normalizados: set[str], nome_base: str = "Pivô") -> str:
    """
    Gera um nome de pivô sequencial e único no formato "Nome Base X".
    Usa nomes normalizados para a verificação. Retorna o nome não normalizado.
    """
    contador = 1
    while True:
        nome_candidato_para_uso = f"{nome_base} {contador}"
        nome_candidato_normalizado_para_verificacao = normalizar_nome(nome_candidato_para_uso)
        
        if nome_candidato_normalizado_para_verificacao not in lista_de_nomes_existentes_normalizados:
            return nome_candidato_para_uso # Retorna o nome original, não normalizado
        contador += 1

# --- FUNÇÃO _consolidate_pivos CORRIGIDA ---
def _consolidate_pivos(
    pivos_de_pontos: List[PivoData],
    ciclos_parsed: List[CicloData],
    pontas_retas_map: Dict[str, CoordsDict]
) -> List[PivoData]:
    """Consolida pivôs de pontos com pivôs de ciclo (anteriormente virtuais) derivados de ciclos e pontas de retas."""
    final_pivos_list = list(pivos_de_pontos) 
    nomes_pivos_existentes_normalizados = {normalizar_nome(p["nome"]) for p in final_pivos_list}
    pivos_pontos_geometrias = [Point(p['lon'], p['lat']) for p in pivos_de_pontos]
    
    for ciclo_info in ciclos_parsed:
        nome_ciclo_original = ciclo_info["nome_original_circulo"]
        coordenadas_ciclo = ciclo_info["coordenadas"]

        try:
            poligono_ciclo = Polygon([(lon, lat) for lat, lon in coordenadas_ciclo])
            if not poligono_ciclo.is_valid:
                logger.warning(f"Polígono do ciclo '{nome_ciclo_original}' é inválido. Pulando consolidação para este ciclo.")
                continue
        except Exception as e:
            logger.warning(f"Erro ao criar polígono para o ciclo '{nome_ciclo_original}': {e}. Pulando.")
            continue
            
        tem_pivo_existente_dentro = any(poligono_ciclo.contains(p_geom) for p_geom in pivos_pontos_geometrias)

        if tem_pivo_existente_dentro:
            logger.info(f"  -> Ciclo '{nome_ciclo_original}' já contém um pivô de ponto. Não será criado pivô de ciclo.")
            continue

        centro_lat: Optional[float] = None
        centro_lon: Optional[float] = None
        
        nome_ciclo_normalizado = normalizar_nome(nome_ciclo_original)
        ponta1 = pontas_retas_map.get(f"ponta 1 reta {nome_ciclo_normalizado}")
        ponta2 = pontas_retas_map.get(f"ponta 2 reta {nome_ciclo_normalizado}")

        if not (ponta1 and ponta2):
            ponta1 = pontas_retas_map.get("ponta 1 reta")
            ponta2 = pontas_retas_map.get("ponta 2 reta")

        if ponta1 and ponta2:
            centro_lat, centro_lon = calcular_meio_reta(ponta1, ponta2)
            logger.info(f"  -> 📏 Centro para ciclo '{nome_ciclo_original}' determinado pelo meio da reta: ({centro_lat:.6f}, {centro_lon:.6f})")
        elif len(coordenadas_ciclo) >= 2:
            try:
                centro_lat, centro_lon, _, _ = ponto_central_da_reta_maior(coordenadas_ciclo)
                logger.info(f"  -> 📐 Centro para ciclo '{nome_ciclo_original}' determinado pelo centro da reta maior do ciclo: ({centro_lat:.6f}, {centro_lon:.6f})")
            except ValueError:
                if coordenadas_ciclo:
                    centro_lat = mean([lat for lat, lon in coordenadas_ciclo])
                    centro_lon = mean([lon for lat, lon in coordenadas_ciclo])
                    logger.info(f"  -> 🌍 Centro para ciclo '{nome_ciclo_original}' determinado pela média das coordenadas (fallback após reta maior): ({centro_lat:.6f}, {centro_lon:.6f})")
            except Exception as e_reta_maior:
                logger.warning(f"  -> ⚠️ Erro no cálculo da reta maior para '{nome_ciclo_original}': {e_reta_maior}. Tentando média.")
                if coordenadas_ciclo:
                    centro_lat = mean([lat for lat, lon in coordenadas_ciclo])
                    centro_lon = mean([lon for lat, lon in coordenadas_ciclo])
                    logger.info(f"  -> 🌍 Centro para ciclo '{nome_ciclo_original}' determinado pela média das coordenadas (fallback de erro): ({centro_lat:.6f}, {centro_lon:.6f})")
        elif coordenadas_ciclo:
            centro_lat = mean([lat for lat, lon in coordenadas_ciclo])
            centro_lon = mean([lon for lat, lon in coordenadas_ciclo])
            logger.info(f"  -> 🌍 Centro para ciclo '{nome_ciclo_original}' determinado pela média das coordenadas (fallback final): ({centro_lat:.6f}, {centro_lon:.6f})")

        if centro_lat is not None and centro_lon is not None:
            nome_pivo_gerado = gerar_nome_pivo_sequencial_unico(nomes_pivos_existentes_normalizados, "Pivô")
            
            # 👇 ALTERAÇÃO APLICADA AQUI
            final_pivos_list.append({"nome": nome_pivo_gerado, "lat": centro_lat, "lon": centro_lon, "type": "pivo"}) # type: ignore
            nomes_pivos_existentes_normalizados.add(normalizar_nome(nome_pivo_gerado))
            logger.info(f"  -> 🛰️ Pivô (de ciclo) adicionado: {nome_pivo_gerado} ({centro_lat:.6f}, {centro_lon:.6f})")
        else:
            logger.warning(f"  -> ⚠️ Não foi possível determinar o centro para o pivô de ciclo '{nome_ciclo_original}'.")
            
    return final_pivos_list


# --- Função Principal ---

def parse_kmz(
    caminho_kmz_str: str,
    pasta_extracao_str: str
) -> Tuple[List[AntenaData], List[PivoData], List[CicloData], List[BombaData]]:
    """
    Processa um arquivo KMZ, extrai dados de antenas, pivôs, ciclos e bombas.
    Retorna: Tupla contendo (lista_antenas, lista_pivos, lista_ciclos, lista_bombas).
    """
    caminho_kmz = Path(caminho_kmz_str)
    pasta_extracao = Path(pasta_extracao_str)

    antenas_list: List[AntenaData] = []
    pivos_de_pontos_list: List[PivoData] = []
    ciclos_list: List[CicloData] = []
    bombas_list: List[BombaData] = []
    pontas_retas_map: Dict[str, CoordsDict] = {}

    logger.info(f"⚙️ Iniciando processamento do KMZ: {caminho_kmz}")
    
    caminho_kml_extraido: Optional[Path] = None
    try:
        caminho_kml_extraido = _extract_kml_from_zip(caminho_kmz, pasta_extracao)
        
        tree = ET.parse(str(caminho_kml_extraido))
        root = tree.getroot()

        for placemark_node in root.findall(".//kml:Placemark", KML_NAMESPACE):
            parsed_data = _parse_placemark_data(placemark_node)
            if not parsed_data:
                continue

            nome_original = parsed_data["nome_original"]
            nome_normalizado = normalizar_nome(nome_original)
            coordenadas_placemark = parsed_data["coordenadas_lista"] # type: ignore
            geometry_type = parsed_data["geometry_type"]

            if geometry_type == "Point" and coordenadas_placemark:
                lat, lon = coordenadas_placemark[0][0], coordenadas_placemark[0][1]

                if any(keyword in nome_normalizado for keyword in ANTENA_KEYWORDS):
                    match = HEIGHT_REGEX.search(nome_normalizado)
                    altura = int(match.group(1)) if match else DEFAULT_ANTENA_HEIGHT
                    
                    dados_antena_encontrada = {
                        "lat": lat, "lon": lon,
                        "altura": altura, "altura_receiver": DEFAULT_RECEIVER_HEIGHT,
                        "nome": nome_original
                    }
                    antenas_list.append(dados_antena_encontrada)
                    logger.info(f"  -> Antena Candidata encontrada: {nome_original} ({lat:.6f}, {lon:.6f}) Alt: {altura}m")
                
                elif any(keyword in nome_normalizado for keyword in PIVO_KEYWORDS) or re.match(r"p\s?\d+", nome_normalizado):
                    # 👇 ALTERAÇÃO APLICADA AQUI
                    pivos_de_pontos_list.append({"nome": nome_original, "lat": lat, "lon": lon, "type": "pivo"}) # type: ignore
                    logger.info(f"  -> Pivô (Ponto) encontrado: {nome_original} ({lat:.6f}, {lon:.6f})")

                elif any(keyword in nome_normalizado for keyword in BOMBA_KEYWORDS):
                    # 👇 ALTERAÇÃO APLICADA AQUI
                    bombas_list.append({"nome": nome_original, "lat": lat, "lon": lon, "type": "bomba"}) # type: ignore
                    logger.info(f"  -> Bomba encontrada: {nome_original} ({lat:.6f}, {lon:.6f})")
                
                elif any(keyword in nome_normalizado for keyword in PONTA_RETA_KEYWORDS):
                    pontas_retas_map[nome_normalizado] = {"lat": lat, "lon": lon}
                    logger.info(f"  -> Ponta de reta encontrada: {nome_original} ({lat:.6f}, {lon:.6f})")

            elif geometry_type in ["LineString", "Polygon"] and len(coordenadas_placemark) >= 3:
                if eh_um_circulo(coordenadas_placemark) or geometry_type == "Polygon":
                    ciclos_list.append({
                        "nome_original_circulo": nome_original,
                        "coordenadas": coordenadas_placemark
                    })
                    logger.info(f"  -> 🔵 Ciclo (de {geometry_type}) detectado: {nome_original}")
        
        pivos_finais_list = _consolidate_pivos(pivos_de_pontos_list, ciclos_list, pontas_retas_map)

        logger.info(f"✅ Processamento KMZ concluído: {len(antenas_list)} antenas candidatas, {len(pivos_finais_list)} pivôs, {len(bombas_list)} bombas.")
        
        return antenas_list, pivos_finais_list, ciclos_list, bombas_list

    except (ValueError, ET.ParseError) as e_parse:
        logger.error(f"❌ Erro de formato ou valor ao processar KMZ '{caminho_kmz}': {e_parse}", exc_info=True)
        raise
    except Exception as e_geral:
        logger.error(f"❌ Erro inesperado ao processar KMZ '{caminho_kmz}': {e_geral}", exc_info=True)
        raise
    finally:
        if caminho_kml_extraido and caminho_kml_extraido.exists():
            try:
                caminho_kml_extraido.unlink()
                logger.info(f"  -> Arquivo KML temporário '{caminho_kml_extraido}' removido.")
            except OSError as e_remove:
                logger.error(f"  -> ⚠️ Erro ao remover arquivo KML temporário '{caminho_kml_extraido}': {e_remove}")