Sim, aqui está o código completo e corrigido para backend/services/kmz_parser.py, que remove as palavras-chave fixas e as substitui pela configuração multilíngue centralizada.

A principal mudança é a remoção das listas ANTENA_KEYWORDS, PIVO_KEYWORDS e BOMBA_KEYWORDS do escopo global e a sua substituição pela importação e uso do objeto settings. Isso torna o parser mais flexível e fácil de manter.

backend/services/kmz_parser.py (Versão Final Corrigida)
Python

# backend/services/kmz_parser.py
import zipfile
import re
import xml.etree.ElementTree as ET
from statistics import mean
from shapely.geometry import Polygon, Point
from pathlib import Path
import logging
from typing import List, Tuple, Dict, Optional, TypedDict, Union

# Importa as configurações centralizadas que agora contêm as keywords
from backend.config import settings

logger = logging.getLogger("irricontrol")

KML_NAMESPACE = {"kml": "http://www.opengis.net/kml/2.2"}

# As listas de keywords foram movidas para config.py para suportar múltiplos idiomas
# e facilitar a manutenção.

# Esta keyword é muito específica da lógica interna e pode ser mantida aqui.
PONTA_RETA_KEYWORDS = ["ponta 1 reta", "ponta 2 reta"]
DEFAULT_ANTENA_HEIGHT = 15
DEFAULT_RECEIVER_HEIGHT = 3
CIRCLE_CLOSENESS_THRESHOLD = 0.0005

HEIGHT_REGEX = re.compile(r"(\d{1,3})\s*(m|metros)")

class CoordsDict(TypedDict):
    lat: float
    lon: float

class AntenaData(CoordsDict):
    altura: int
    altura_receiver: int
    nome: str

class PivoData(CoordsDict):
    nome: str
    type: str

class CicloData(TypedDict):
    nome_original_circulo: str
    coordenadas: List[List[float]]

class BombaData(CoordsDict):
    nome: str
    type: str

def normalizar_nome(nome: str) -> str:
    if not nome: return ""
    # Converte para minúsculas
    nome_lower = nome.lower()
    # Remove caracteres especiais, mantendo letras acentuadas, números e espaços
    nome_sem_especiais = re.sub(r'[^a-z0-9\sÀ-ÖØ-öø-ÿ]', '', nome_lower)
    # Substitui múltiplos espaços por um único espaço e remove espaços no início/fim
    return re.sub(r'\s+', ' ', nome_sem_especiais).strip()

def calcular_meio_reta(p1: CoordsDict, p2: CoordsDict) -> Tuple[float, float]:
    return (p1["lat"] + p2["lat"]) / 2, (p1["lon"] + p2["lon"]) / 2

def ponto_central_da_reta_maior(coords_list: List[List[float]]) -> Tuple[float, float, List[float], List[float]]:
    if not coords_list or len(coords_list) < 2:
        raise ValueError("São necessários pelo menos dois pontos para calcular a reta maior.")
    max_dist_sq = 0
    ponta1_final, ponta2_final = coords_list[0], coords_list[1]
    for i in range(len(coords_list)):
        for j in range(i + 1, len(coords_list)):
            p1, p2 = coords_list[i], coords_list[j]
            dist_sq = (p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2
            if dist_sq > max_dist_sq:
                max_dist_sq, ponta1_final, ponta2_final = dist_sq, p1, p2
    return (ponta1_final[0] + ponta2_final[0]) / 2, (ponta1_final[1] + ponta2_final[1]) / 2, ponta1_final, ponta2_final

def eh_um_circulo(coords_list: List[List[float]], threshold: float = CIRCLE_CLOSENESS_THRESHOLD) -> bool:
    if len(coords_list) < 3: return False
    # Compara a distância entre o primeiro e o último ponto
    return Point(coords_list[0][1], coords_list[0][0]).distance(Point(coords_list[-1][1], coords_list[-1][0])) < threshold


def _extract_kml_from_zip(caminho_kmz: Path, pasta_extracao: Path) -> Path:
    try:
        with zipfile.ZipFile(caminho_kmz, 'r') as kmz_file:
            kml_file_name = next((f for f in kmz_file.namelist() if f.lower().endswith('.kml')), None)
            if not kml_file_name: raise ValueError("Nenhum arquivo .kml encontrado dentro do KMZ.")
            kmz_file.extract(kml_file_name, path=pasta_extracao)
            caminho_kml_extraido = pasta_extracao / kml_file_name
            logger.info(f"  -> Arquivo KML '{kml_file_name}' extraído para '{caminho_kml_extraido}'")
            return caminho_kml_extraido
    except zipfile.BadZipFile:
        raise ValueError(f"Arquivo KMZ '{caminho_kmz.name}' inválido ou corrompido.")

def _parse_placemark_data(placemark_node: ET.Element) -> Optional[Dict[str, Union[str, List[List[float]]]]]:
    nome_tag = placemark_node.find("kml:name", KML_NAMESPACE)
    nome_original = nome_tag.text.strip() if nome_tag is not None and nome_tag.text else ""
    data: Dict[str, Union[str, List[List[float]]]] = {"nome_original": nome_original}
    geometry_type: Optional[str] = None
    coords_text: Optional[str] = None

    point = placemark_node.find(".//kml:Point/kml:coordinates", KML_NAMESPACE)
    linestring = placemark_node.find(".//kml:LineString/kml:coordinates", KML_NAMESPACE)
    polygon = placemark_node.find(".//kml:Polygon/kml:outerBoundaryIs/kml:LinearRing/kml:coordinates", KML_NAMESPACE)

    if point is not None and point.text:
        coords_text, geometry_type = point.text.strip(), "Point"
    elif linestring is not None and linestring.text:
        coords_text, geometry_type = linestring.text.strip(), "LineString"
    elif polygon is not None and polygon.text:
        coords_text, geometry_type = polygon.text.strip(), "Polygon"
    
    if not coords_text or not geometry_type: return None
    data["geometry_type"] = geometry_type
    
    parsed_coords = [[float(p.split(',')[1]), float(p.split(',')[0])] for p in coords_text.split() if len(p.split(',')) >= 2]
    if not parsed_coords: return None
    data["coordenadas_lista"] = parsed_coords
    return data

def gerar_nome_pivo_sequencial_unico(lista_de_nomes_existentes_normalizados: set[str], nome_base: str = "Pivô") -> str:
    contador = 1
    while True:
        nome_candidato = f"{nome_base} {contador}"
        if normalizar_nome(nome_candidato) not in lista_de_nomes_existentes_normalizados:
            return nome_candidato
        contador += 1

def _consolidate_pivos(
    pivos_de_pontos: List[PivoData],
    ciclos_parsed: List[CicloData],
    pontas_retas_map: Dict[str, CoordsDict]
) -> List[PivoData]:
    final_pivos_list = list(pivos_de_pontos) 
    nomes_pivos_existentes_normalizados = {normalizar_nome(p["nome"]) for p in final_pivos_list}
    pivos_pontos_geometrias = [Point(p['lon'], p['lat']) for p in pivos_de_pontos]
    
    for ciclo_info in ciclos_parsed:
        nome_ciclo_original = ciclo_info["nome_original_circulo"]
        coordenadas_ciclo = ciclo_info["coordenadas"]
        
        try:
            poligono_ciclo = Polygon([(lon, lat) for lat, lon in coordenadas_ciclo])
            if not poligono_ciclo.is_valid: continue
        except Exception: continue
            
        if any(poligono_ciclo.contains(p_geom) for p_geom in pivos_pontos_geometrias):
            continue

        centro_lat: Optional[float] = None
        centro_lon: Optional[float] = None
        
        nome_ciclo_norm = normalizar_nome(nome_ciclo_original)
        ponta1 = pontas_retas_map.get(f"ponta 1 reta {nome_ciclo_norm}")
        ponta2 = pontas_retas_map.get(f"ponta 2 reta {nome_ciclo_norm}")
        if not (ponta1 and ponta2):
            ponta1 = pontas_retas_map.get("ponta 1 reta")
            ponta2 = pontas_retas_map.get("ponta 2 reta")

        if ponta1 and ponta2:
            centro_lat, centro_lon = calcular_meio_reta(ponta1, ponta2)
        elif len(coordenadas_ciclo) >= 2:
            try:
                centro_lat, centro_lon, _, _ = ponto_central_da_reta_maior(coordenadas_ciclo)
            except (ValueError, Exception):
                 if coordenadas_ciclo:
                    centro_lat, centro_lon = mean([c[0] for c in coordenadas_ciclo]), mean([c[1] for c in coordenadas_ciclo])

        if centro_lat is not None and centro_lon is not None:
            nome_pivo_gerado = gerar_nome_pivo_sequencial_unico(nomes_pivos_existentes_normalizados, "Pivô")
            final_pivos_list.append({"nome": nome_pivo_gerado, "lat": centro_lat, "lon": centro_lon, "type": "pivo"}) # type: ignore
            nomes_pivos_existentes_normalizados.add(normalizar_nome(nome_pivo_gerado))
            
            ciclo_info['nome_original_circulo'] = f"Ciclo {nome_pivo_gerado}"
            logger.info(f"  -> 🛰️ Pivô de ciclo adicionado como '{nome_pivo_gerado}'. Nome do ciclo atualizado para '{ciclo_info['nome_original_circulo']}'.")
            
    return final_pivos_list

def parse_gis_file(caminho_gis_str: str, pasta_extracao_str: str) -> Tuple[List[AntenaData], List[PivoData], List[CicloData], List[BombaData]]:
    """
    Processa um arquivo KML ou KMZ, extrai os dados relevantes e os retorna,
    usando as keywords multilíngues da configuração.
    """
    caminho_gis = Path(caminho_gis_str)
    pasta_extracao = Path(pasta_extracao_str)
    
    antenas_list: List[AntenaData] = []
    pivos_de_pontos_list: List[PivoData] = []
    ciclos_list: List[CicloData] = []
    bombas_list: List[BombaData] = []
    pontas_retas_map: Dict[str, CoordsDict] = {}

    caminho_kml_a_ser_lido: Optional[Path] = None
    kml_extraido_path_temp: Optional[Path] = None

    # Pega as listas de keywords consolidadas da configuração
    antena_kws = settings.ENTITY_KEYWORDS['ANTENA']
    pivo_kws = settings.ENTITY_KEYWORDS['PIVO']
    bomba_kws = settings.ENTITY_KEYWORDS['BOMBA']
    
    logger.info(f"Usando keywords para Antenas: {antena_kws}")
    logger.info(f"Usando keywords para Pivôs: {pivo_kws}")
    logger.info(f"Usando keywords para Bombas: {bomba_kws}")

    try:
        # Lógica para decidir como obter o arquivo KML
        if caminho_gis.suffix.lower() == ".kmz":
            logger.info(f"Processando arquivo KMZ: {caminho_gis.name}")
            kml_extraido_path_temp = _extract_kml_from_zip(caminho_gis, pasta_extracao)
            caminho_kml_a_ser_lido = kml_extraido_path_temp
        elif caminho_gis.suffix.lower() == ".kml":
            logger.info(f"Processando arquivo KML direto: {caminho_gis.name}")
            caminho_kml_a_ser_lido = caminho_gis
        else:
            raise ValueError("Formato de arquivo não suportado. Envie um arquivo .kml ou .kmz.")

        tree = ET.parse(str(caminho_kml_a_ser_lido))
        root = tree.getroot()

        for placemark_node in root.findall(".//kml:Placemark", KML_NAMESPACE):
            parsed_data = _parse_placemark_data(placemark_node)
            if not parsed_data: continue

            nome_original = parsed_data["nome_original"]
            nome_norm = normalizar_nome(nome_original)
            coords, geo_type = parsed_data["coordenadas_lista"], parsed_data["geometry_type"] # type: ignore

            if geo_type == "Point" and coords:
                lat, lon = coords[0][0], coords[0][1]
                
                # A lógica de verificação agora usa as listas da configuração
                if any(kw in nome_norm for kw in antena_kws):
                    match = HEIGHT_REGEX.search(nome_norm)
                    altura = int(match.group(1)) if match else DEFAULT_ANTENA_HEIGHT
                    antenas_list.append({"lat": lat, "lon": lon, "altura": altura, "altura_receiver": DEFAULT_RECEIVER_HEIGHT, "nome": nome_original})
                
                elif any(kw in nome_norm for kw in pivo_kws) or re.match(r"p\s?\d+", nome_norm):
                    pivos_de_pontos_list.append({"nome": nome_original, "lat": lat, "lon": lon, "type": "pivo"}) # type: ignore
                
                elif any(kw in nome_norm for kw in bomba_kws):
                    bombas_list.append({"nome": nome_original, "lat": lat, "lon": lon, "type": "bomba"}) # type: ignore
                
                elif any(kw in nome_norm for kw in PONTA_RETA_KEYWORDS):
                    pontas_retas_map[nome_norm] = {"lat": lat, "lon": lon}
                    
            elif geo_type in ["LineString", "Polygon"] and len(coords) >= 3: # type: ignore
                if eh_um_circulo(coords) or geo_type == "Polygon": # type: ignore
                    ciclos_list.append({"nome_original_circulo": nome_original, "coordenadas": coords}) # type: ignore
        
        pivos_finais_list = _consolidate_pivos(pivos_de_pontos_list, ciclos_list, pontas_retas_map)
        logger.info(f"✅ Processamento do arquivo concluído: {len(antenas_list)} antenas, {len(pivos_finais_list)} pivôs, {len(bombas_list)} bombas.")
        return antenas_list, pivos_finais_list, ciclos_list, bombas_list
    finally:
        # Garante que o KML extraído temporariamente seja excluído
        if kml_extraido_path_temp and kml_extraido_path_temp.exists():
            kml_extraido_path_temp.unlink(missing_ok=True)