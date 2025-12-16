# backend/services/kmz_parser_complex.py

from __future__ import annotations

import logging
import math
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from statistics import mean
from typing import List, Tuple, Dict, Optional, TypedDict, Union

from shapely.geometry import Polygon, Point

from backend.config import settings
from backend.exceptions import FileParseError
from backend.services.i18n_service import i18n_service

logger = logging.getLogger("irricontrol")

KML_NAMESPACE = {"kml": "http://www.opengis.net/kml/2.2"}

DEFAULT_RECEIVER_HEIGHT: int = 3
CIRCLE_CLOSENESS_THRESHOLD: float = 0.0005
HEIGHT_REGEX = re.compile(r"[\s-]*(\d+)\s*(m|metros)\s*$", re.IGNORECASE)


class CoordsDict(TypedDict):
    lat: float
    lon: float


class AntenaData(CoordsDict):
    altura: Optional[int]
    had_height_in_kmz: bool
    altura_receiver: int
    nome: str


class PivoData(CoordsDict):
    nome: str
    type: str
    tipo: Optional[str]
    coordenadas: Optional[List[List[float]]]


class CicloData(TypedDict):
    nome_original_circulo: str
    coordenadas: List[List[float]]


class BombaData(CoordsDict):
    nome: str
    type: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalizar_nome(nome: str) -> str:
    if not nome:
        return ""
    nome_lower = nome.lower()
    nome_sem_especiais = re.sub(r"[^a-z0-9\sÀ-ÖØ-öø-ÿ]", "", nome_lower)
    return re.sub(r"\s+", " ", nome_sem_especiais).strip()


def eh_um_circulo(
    coords_list: List[List[float]], threshold: float = CIRCLE_CLOSENESS_THRESHOLD
) -> bool:
    """Usado só pra decidir se um LineString está fechado."""
    if len(coords_list) < 3:
        return False
    p0 = Point(coords_list[0][1], coords_list[0][0])
    pn = Point(coords_list[-1][1], coords_list[-1][0])
    return p0.distance(pn) < threshold


def _extract_kml_from_zip(caminho_kmz: Path, pasta_extracao: Path) -> Path:
    try:
        pasta_extracao.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(caminho_kmz, "r") as kmz_file:
            kml_file_name = next(
                (f for f in kmz_file.namelist() if f.lower().endswith(".kml")), None
            )
            if not kml_file_name:
                raise FileParseError("Nenhum arquivo .kml encontrado dentro do KMZ.")
            kmz_file.extract(kml_file_name, path=pasta_extracao)
            caminho_kml_extraido = pasta_extracao / kml_file_name
            logger.info(
                "[COMPLEX] Arquivo KML '%s' extraído para '%s'",
                kml_file_name,
                caminho_kml_extraido,
            )
            return caminho_kml_extraido
    except zipfile.BadZipFile:
        raise FileParseError(f"Arquivo KMZ '{caminho_kmz.name}' inválido ou corrompido.")


def _parse_placemark_data(
    placemark_node: ET.Element,
) -> Optional[Dict[str, Union[str, List[List[float]]]]]:
    nome_tag = placemark_node.find("kml:name", KML_NAMESPACE)
    nome_original = nome_tag.text.strip() if nome_tag is not None and nome_tag.text else ""
    data: Dict[str, Union[str, List[List[float]]]] = {"nome_original": nome_original}
    geometry_type: Optional[str] = None
    coords_text: Optional[str] = None

    point = placemark_node.find(".//kml:Point/kml:coordinates", KML_NAMESPACE)
    linestring = placemark_node.find(".//kml:LineString/kml:coordinates", KML_NAMESPACE)
    polygon = placemark_node.find(
        ".//kml:Polygon/kml:outerBoundaryIs/kml:LinearRing/kml:coordinates",
        KML_NAMESPACE,
    )

    if point is not None and point.text:
        coords_text, geometry_type = point.text.strip(), "Point"
    elif linestring is not None and linestring.text:
        coords_text, geometry_type = linestring.text.strip(), "LineString"
    elif polygon is not None and polygon.text:
        coords_text, geometry_type = polygon.text.strip(), "Polygon"

    if not coords_text or not geometry_type:
        return None
    data["geometry_type"] = geometry_type

    try:
        parsed_coords: List[List[float]] = []
        for token in coords_text.split():
            parts = token.split(",")
            if len(parts) >= 2:
                lon = float(parts[0])
                lat = float(parts[1])
                parsed_coords.append([lat, lon])
        if not parsed_coords:
            return None
        data["coordenadas_lista"] = parsed_coords
        return data
    except (ValueError, IndexError):
        logger.warning(
            "[COMPLEX] Não foi possível parsear coordenadas para o placemark '%s'. Texto: '%s'",
            nome_original,
            coords_text,
        )
        return None


# ---------------------------------------------------------------------------
# Filtro de "parece pivô"
# ---------------------------------------------------------------------------

def _shape_parece_pivo(coords: List[List[float]], *, strict: bool = True) -> bool:
    """
    Heurística para decidir se um Polygon/LineString FECHADO parece pivô.

    strict=True  -> filtro agressivo (evita talhão e quadrado)
    strict=False -> filtro mais relaxado (fallback se sumirem pivôs)
    """

    # 1) mínimo de vértices
    min_vertices = 12 if strict else 8
    if len(coords) < min_vertices:
        return False

    try:
        poly = Polygon([(lon, lat) for lat, lon in coords])
        if not poly.is_valid:
            return False
    except Exception:
        return False

    # 2) bounding box: pivô ≈ quadrado, talhão é retângulo esticado
    minx, miny, maxx, maxy = poly.bounds
    width = maxx - minx
    height = maxy - miny
    if width == 0 or height == 0:
        return False

    aspect_ratio = max(width, height) / min(width, height)
    max_aspect = 1.25 if strict else 1.4
    if aspect_ratio > max_aspect:
        return False

    # 3) circularidade: variação do raio em torno do centro
    centroid = poly.centroid
    cx, cy = centroid.x, centroid.y

    radii: List[float] = []
    for lat, lon in coords:
        dx = lon - cx
        dy = lat - cy
        r = math.hypot(dx, dy)
        if r > 0:
            radii.append(r)

    if len(radii) < min_vertices:
        return False

    mean_r = sum(radii) / len(radii)
    if mean_r == 0:
        return False

    var_r = sum((r - mean_r) ** 2 for r in radii) / len(radii)
    std_r = math.sqrt(var_r)
    rel_std = std_r / mean_r

    max_rel_std = 0.20 if strict else 0.30

    return rel_std <= max_rel_std


def _filtrar_ciclos_complex(raw_ciclos: List[CicloData]) -> List[CicloData]:
    """
    2-passos:

    1) tenta com filtro STRICT -> se achar algo, usa só esses
    2) se não achar nada, tenta filtro RELAXED (pra não sumir pivôs
        em arquivos mais “sujo”)
    """
    if not raw_ciclos:
        return []

    strict_ciclos: List[CicloData] = []
    relaxed_ciclos: List[CicloData] = []

    for ciclo in raw_ciclos:
        coords = ciclo["coordenadas"]
        if not coords or len(coords) < 3:
            continue

        if _shape_parece_pivo(coords, strict=True):
            strict_ciclos.append(ciclo)
        elif _shape_parece_pivo(coords, strict=False):
            relaxed_ciclos.append(ciclo)

    if strict_ciclos:
        logger.info(
            "[COMPLEX] Filtro STRICT aplicado: %d shapes aceitos de %d.",
            len(strict_ciclos),
            len(raw_ciclos),
        )
        return strict_ciclos

    if relaxed_ciclos:
        logger.info(
            "[COMPLEX] Nenhum shape passou no STRICT. Usando fallback RELAXED: %d shapes aceitos de %d.",
            len(relaxed_ciclos),
            len(raw_ciclos),
        )
        return relaxed_ciclos

    # Se nada passou, última alternativa: não filtra (melhor ter algo
    # do que sumir pivô por completo)
    logger.warning(
        "[COMPLEX] Nenhum shape passou nos filtros STRICT/RELAXED. Mantendo todos os %d shapes originais.",
        len(raw_ciclos),
    )
    return raw_ciclos


# ---------------------------------------------------------------------------
# Consolidação de pivôs no parser complexo
# ---------------------------------------------------------------------------

def _consolidate_pivos_complex(
    pivos_de_pontos: List[PivoData],
    ciclos_list: List[CicloData],
    nome_base_pivo: str,
) -> List[PivoData]:
    """
    Versão simplificada: não tenta adivinhar tipo, só:
    - associa ponto a shape que o contém;
    - cria pivô no centróide pros shapes órfãos.

    Todos saem como tipo 'custom' com coordenadas completas do polígono/arco.
    """
    final_pivos: List[PivoData] = []
    usados = set()

    # 1) associa pontos a shapes
    for pivo in pivos_de_pontos:
        p_geom = Point(pivo["lon"], pivo["lat"])
        associado_idx = None

        for i, ciclo in enumerate(ciclos_list):
            if i in usados:
                continue
            coords = ciclo["coordenadas"]
            try:
                poly = Polygon([(lon, lat) for lat, lon in coords])
                if not poly.is_valid:
                    continue
            except Exception:
                continue

            if poly.contains(p_geom):
                associado_idx = i
                usados.add(i)
                break

        pivo_final = pivo.copy()
        if associado_idx is not None:
            pivo_final["tipo"] = "custom"
            pivo_final["coordenadas"] = ciclos_list[associado_idx]["coordenadas"]
            logger.info(
                "[COMPLEX] Pivô '%s' associado ao shape '%s'.",
                pivo["nome"],
                ciclos_list[associado_idx]["nome_original_circulo"],
            )
        final_pivos.append(pivo_final)

    # nomes existentes (normalizados) para não duplicar
    nomes_norm = {normalizar_nome(p["nome"]) for p in final_pivos}

    def _gerar_nome() -> str:
        idx = 1
        while True:
            cand = f"{nome_base_pivo} {idx}"
            if normalizar_nome(cand) not in nomes_norm:
                nomes_norm.add(normalizar_nome(cand))
                return cand
            idx += 1

    # 2) cria pivôs pros shapes órfãos
    for i, ciclo in enumerate(ciclos_list):
        if i in usados:
            continue

        coords = ciclo["coordenadas"]
        if not coords:
            continue

        try:
            poly = Polygon([(lon, lat) for lat, lon in coords])
            if poly.is_valid:
                centroid = poly.centroid
                c_lon, c_lat = centroid.x, centroid.y
            else:
                c_lat = mean([c[0] for c in coords])
                c_lon = mean([c[1] for c in coords])
        except Exception:
            c_lat = mean([c[0] for c in coords])
            c_lon = mean([c[1] for c in coords])

        nome_pivo = _gerar_nome()
        final_pivos.append(
            {
                "nome": nome_pivo,
                "lat": c_lat,
                "lon": c_lon,
                "type": "pivo",
                "tipo": "custom",
                "coordenadas": coords,
            }
        )
        logger.info(
            "[COMPLEX] Pivô gerado para shape órfão '%s' como '%s'.",
            ciclo["nome_original_circulo"],
            nome_pivo,
        )

    return final_pivos


# ---------------------------------------------------------------------------
# Parser principal (COMPLEXO)
# ---------------------------------------------------------------------------

def parse_gis_file_complex(
    caminho_gis_str: str, pasta_extracao_str: str, lang: str = "pt-br"
) -> Tuple[List[AntenaData], List[PivoData], List[CicloData], List[BombaData]]:
    """
    Parser COMPLEXO:

    - Junta todos Polygon + LineString FECHADO como shapes crus (raw_ciclos)
    - Passa no filtro em 2 estágios (STRICT -> RELAXED -> fallback total)
    - Só então consolida pivôs
    """
    t = i18n_service.get_translator(lang)
    caminho_gis = Path(caminho_gis_str)
    pasta_extracao = Path(pasta_extracao_str)
    pasta_extracao.mkdir(parents=True, exist_ok=True)

    antenas_list: List[AntenaData] = []
    pivos_de_pontos_list: List[PivoData] = []
    raw_ciclos_list: List[CicloData] = []
    bombas_list: List[BombaData] = []

    caminho_kml_a_ser_lido: Optional[Path] = None
    kml_extraido_path_temp: Optional[Path] = None

    antena_kws = settings.ENTITY_KEYWORDS["ANTENA"]
    pivo_kws = settings.ENTITY_KEYWORDS["PIVO"]
    bomba_kws = settings.ENTITY_KEYWORDS["BOMBA"]

    logger.info("[COMPLEX] Iniciando parser complexo para arquivo: %s", caminho_gis.name)

    try:
        if caminho_gis.suffix.lower() == ".kmz":
            kml_extraido_path_temp = _extract_kml_from_zip(caminho_gis, pasta_extracao)
            caminho_kml_a_ser_lido = kml_extraido_path_temp
        elif caminho_gis.suffix.lower() == ".kml":
            caminho_kml_a_ser_lido = caminho_gis
        else:
            raise FileParseError(
                "[COMPLEX] Formato de arquivo não suportado. Envie um arquivo .kml ou .kmz."
            )

        try:
            tree = ET.parse(str(caminho_kml_a_ser_lido))
        except ET.ParseError as e:
            raise FileParseError(f"[COMPLEX] Arquivo KML mal formatado ou corrompido: {e}")

        root = tree.getroot()

        pivot_num_regex = re.compile(
            r"(?:piv(?:o|ô|ot)?)\s*(\d+)", re.IGNORECASE
        )
        bomba_name_regex = re.compile(
            r"^(casa\s+de\s+bomba|pump\s+house|bomba\s*\d*)$",
            re.IGNORECASE,
        )

        for placemark_node in root.findall(".//kml:Placemark", KML_NAMESPACE):
            parsed_data = _parse_placemark_data(placemark_node)
            if not parsed_data:
                continue

            nome_original = str(parsed_data["nome_original"])
            coords = parsed_data["coordenadas_lista"]
            geo_type = str(parsed_data["geometry_type"])

            match = HEIGHT_REGEX.search(nome_original)
            if match:
                altura = int(match.group(1))
                had_height = True
                nome_limpo_para_keywords = nome_original[: match.start()].strip()
            else:
                altura = None
                had_height = False
                nome_limpo_para_keywords = nome_original

            nome_norm = normalizar_nome(nome_limpo_para_keywords)

            # 1) PONTOS
            if geo_type == "Point" and coords:
                lat, lon = coords[0][0], coords[0][1]

                # ANTENA
                if any(kw in nome_norm for kw in antena_kws):
                    antenas_list.append(
                        {
                            "lat": lat,
                            "lon": lon,
                            "altura": altura,
                            "had_height_in_kmz": had_height,
                            "altura_receiver": DEFAULT_RECEIVER_HEIGHT,
                            "nome": nome_original,
                        }
                    )
                    continue

                # PIVÔ
                if any(kw in nome_norm for kw in pivo_kws) or pivot_num_regex.search(
                    nome_original
                ):
                    final_pivo_name = nome_original
                    match_pivot_num = pivot_num_regex.search(nome_original)
                    if match_pivot_num:
                        pivo_num = match_pivot_num.group(1)
                        final_pivo_name = f"{t('entity_names.pivot')} {pivo_num}"

                    pivos_de_pontos_list.append(
                        {
                            "nome": final_pivo_name,
                            "lat": lat,
                            "lon": lon,
                            "type": "pivo",
                            "tipo": None,
                            "coordenadas": None,
                        }
                    )
                    continue

                # BOMBA
                if any(kw in nome_norm for kw in bomba_kws) or bomba_name_regex.search(
                    nome_original
                ):
                    bombas_list.append(
                        {
                            "nome": t("entity_names.irripump"),
                            "lat": lat,
                            "lon": lon,
                            "type": "bomba",
                        }
                    )
                    continue

            # 2) SHAPES crus (Polygon/LineString fechado) → ainda sem filtro
            if geo_type in ["LineString", "Polygon"] and len(coords) >= 3:
                if geo_type == "LineString" and not eh_um_circulo(coords):
                    logger.debug(
                        "[COMPLEX] LineString ignorado por não fechar como círculo: '%s'",
                        nome_original,
                    )
                    continue

                raw_ciclos_list.append(
                    {
                        "nome_original_circulo": nome_original,
                        "coordenadas": coords,
                    }
                )

        # Filtro 2-passos em cima dos shapes crus
        ciclos_list = _filtrar_ciclos_complex(raw_ciclos_list)

        nome_base_pivo_traduzido = t("entity_names.pivot")
        pivos_finais_list = _consolidate_pivos_complex(
            pivos_de_pontos_list,
            ciclos_list,
            nome_base_pivo_traduzido,
        )

        logger.info(
            "[COMPLEX] Processamento concluído: %d antenas, %d pivôs, %d ciclos, %d bombas.",
            len(antenas_list),
            len(pivos_finais_list),
            len(ciclos_list),
            len(bombas_list),
        )

        return antenas_list, pivos_finais_list, ciclos_list, bombas_list

    finally:
        if kml_extraido_path_temp and kml_extraido_path_temp.exists():
            kml_extraido_path_temp.unlink(missing_ok=True)
