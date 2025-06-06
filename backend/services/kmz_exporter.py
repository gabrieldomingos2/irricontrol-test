import simplekml
from pathlib import Path
import logging
import json
import zipfile
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)

COLOUR_KEY_KML_NAME = "Colour Key - dBm" # Nome fixo da legenda no KML

def _create_kml_styles(
    torre_icon_name: str,
    default_icon_url: str
) -> tuple[simplekml.Style, simplekml.Style, simplekml.Style]:
    """Cria e retorna os estilos KML para os pontos da torre e repetidora."""
    torre_style = simplekml.Style()
    torre_style.iconstyle.icon.href = torre_icon_name
    torre_style.iconstyle.scale = 1.2
    torre_style.labelstyle.scale = 1.1

    default_point_style = simplekml.Style()
    default_point_style.iconstyle.icon.href = default_icon_url
    default_point_style.iconstyle.scale = 1.0
    default_point_style.labelstyle.scale = 1.0

    repetidora_style = simplekml.Style()
    repetidora_style.iconstyle.icon.href = torre_icon_name
    repetidora_style.iconstyle.scale = 1.1
    repetidora_style.labelstyle.scale = 1.0

    return torre_style, default_point_style, repetidora_style

def _add_secondary_folders(
    doc: simplekml.Document,
    pivos: list, ciclos: list, bombas: list,
    default_point_style: simplekml.Style
):
    """Adiciona pastas de dados secundários (Pivôs, Ciclos, Bombas) ao documento KML principal."""
    if pivos:
        folder_pivos = doc.newfolder(name="Pivôs")
        for i, p_data in enumerate(pivos):
            pivo_nome = p_data.get("nome", f"Pivo {i+1}")
            pnt_pivo = folder_pivos.newpoint(name=pivo_nome, coords=[(p_data["lon"], p_data["lat"])])
            pnt_pivo.style = default_point_style
        logger.info(" -> Pasta 'Pivôs' criada em kmz_exporter.")

    if ciclos:
        folder_ciclos = doc.newfolder(name="Ciclos")
        for i, ciclo_data in enumerate(ciclos):
            ciclo_nome = ciclo_data.get("nome_original_circulo", f"Ciclo {i+1}")
            pol = folder_ciclos.newpolygon(name=ciclo_nome)
            pol.outerboundaryis = [(lon, lat) for lat, lon in ciclo_data["coordenadas"]]
            pol.style.polystyle.fill = 0
            pol.style.linestyle.color = simplekml.Color.red
            pol.style.linestyle.width = 4
        logger.info(" -> Pasta 'Ciclos' criada em kmz_exporter.")

    if bombas:
        folder_bombas = doc.newfolder(name="Bombas")
        for i, bomba_data in enumerate(bombas):
            bomba_nome = bomba_data.get("nome", f"Bomba {i+1}")
            pnt_bomba = folder_bombas.newpoint(name=bomba_nome, coords=[(bomba_data["lon"], bomba_data["lat"])])
            pnt_bomba.style = default_point_style
        logger.info(" -> Pasta 'Bombas' criada em kmz_exporter.")

def _create_coverage_kmz(
    entity_name: str,
    entity_coords: List[Tuple[float, float]],
    entity_style: simplekml.Style,
    coverage_name: str,
    coverage_image_path: Path,
    coverage_bounds: List[float],
    colour_key_path: Path,
    torre_icon_path: Path,
    output_dir: Path,
    details_subfolder_name: str,
    is_main_antenna: bool = False
) -> Path:
    """
    Cria um arquivo KMZ auto-contido para uma única entidade de cobertura (antena ou repetidora).
    Retorna o caminho para o arquivo KMZ gerado.
    """
    logger.info(f"   -> 🏭 Criando KMZ individual para: '{entity_name}'")
    kml_sub = simplekml.Kml()
    
    # Estrutura de pastas interna do sub-KMZ
    folder_main = kml_sub.newfolder(name=entity_name)
    subfolder_details = folder_main.newfolder(name=details_subfolder_name)

    # Ponto da antena/repetidora
    pnt = subfolder_details.newpoint(name=entity_name, coords=entity_coords)
    pnt.style = entity_style
    if is_main_antenna and isinstance(pnt.style, simplekml.Style):
         pnt.description = f"Altura: {entity_style.extendeddata.elements[0].value}m"

    # Ground Overlay (mapa de cobertura)
    ground = subfolder_details.newgroundoverlay(name=coverage_name)
    ground.icon.href = coverage_image_path.name
    b = coverage_bounds
    ground.latlonbox.north, ground.latlonbox.south = b[2], b[0]
    ground.latlonbox.east, ground.latlonbox.west = b[3], b[1]
    ground.color = "ffffffff"

    # Screen Overlay (legenda)
    screen = subfolder_details.newscreenoverlay(name=COLOUR_KEY_KML_NAME)
    screen.icon.href = colour_key_path.name
    screen.overlayxy = simplekml.OverlayXY(x=0, y=1, xunits=simplekml.Units.fraction, yunits=simplekml.Units.fraction)
    screen.screenxy = simplekml.ScreenXY(x=0, y=1, xunits=simplekml.Units.fraction, yunits=simplekml.Units.fraction)
    screen.size = simplekml.Size(x=0, y=0, xunits=simplekml.Units.fraction, yunits=simplekml.Units.fraction)

    # Salvar e empacotar o sub-KMZ
    sub_kml_filename = f"sub_{entity_name.replace(' ', '_').lower()}.kml"
    sub_kmz_filename = f"sub_{entity_name.replace(' ', '_').lower()}.kmz"
    
    path_kml_temp = output_dir / sub_kml_filename
    path_kmz_final = output_dir / sub_kmz_filename
    
    kml_sub.save(str(path_kml_temp))

    with zipfile.ZipFile(str(path_kmz_final), "w", zipfile.ZIP_DEFLATED) as kmz_zip:
        kmz_zip.write(str(path_kml_temp), "doc.kml")
        kmz_zip.write(str(coverage_image_path), coverage_image_path.name)
        kmz_zip.write(str(colour_key_path), colour_key_path.name)
        if torre_icon_path.exists():
            kmz_zip.write(str(torre_icon_path), torre_icon_path.name)

    path_kml_temp.unlink() # Limpa o KML temporário
    logger.info(f"   -> ✅ KMZ individual '{path_kmz_final.name}' criado com sucesso.")
    return path_kmz_final

def build_main_kml_and_sub_kmzs(
    doc: simplekml.Document,
    antena_data: dict,
    pivos_data: list,
    ciclos_data: list,
    bombas_data: list,
    imagem_principal_nome_relativo: str,
    bounds_principal_data: list,
    generated_images_dir: Path,
    torre_icon_name: str,
    default_icon_url: str,
    colour_key_filename: str,
    template_id_for_subfolder: str,
    study_date_str_for_subfolder: str,
    template_frq_for_main_coverage: int,
    template_txw_for_main_coverage: float
) -> List[Path]:
    """
    Constrói o KML principal com NetworkLinks e gera os sub-KMZs para cada cobertura.
    Retorna a lista de caminhos para os sub-KMZs gerados.
    """
    logger.info("Iniciando construção da estrutura KML principal e sub-KMZs.")
    sub_kmz_paths_to_add = []
    
    torre_style, default_point_style, repetidora_style = _create_kml_styles(
        torre_icon_name, default_icon_url
    )
    # Adiciona a altura da antena aos dados do estilo para uso posterior
    torre_style.extendeddata.add_data(antena_data.get('altura', 'N/A'))


    details_subfolder_name = f"{template_id_for_subfolder} ({study_date_str_for_subfolder})"
    main_coverage_name = f"Cobertura {template_frq_for_main_coverage}MHz {template_txw_for_main_coverage}W"
    
    # --- 1. Criar o KMZ da Antena Principal ---
    antena_nome = antena_data.get("nome", "Antena Principal")
    path_imagem_principal = generated_images_dir / imagem_principal_nome_relativo
    path_colour_key = generated_images_dir / colour_key_filename
    path_torre_icon = generated_images_dir / torre_icon_name

    if path_imagem_principal.exists() and path_colour_key.exists():
        sub_kmz_antena_path = _create_coverage_kmz(
            entity_name=antena_nome,
            entity_coords=[(antena_data["lon"], antena_data["lat"])],
            entity_style=torre_style,
            coverage_name=main_coverage_name,
            coverage_image_path=path_imagem_principal,
            coverage_bounds=bounds_principal_data,
            colour_key_path=path_colour_key,
            torre_icon_path=path_torre_icon,
            output_dir=generated_images_dir,
            details_subfolder_name=details_subfolder_name,
            is_main_antenna=True
        )
        sub_kmz_paths_to_add.append(sub_kmz_antena_path)
        
        # Adicionar NetworkLink ao KML principal
        nl_antena = doc.newnetworklink(name=antena_nome)
        nl_antena.link.href = sub_kmz_antena_path.name
        logger.info(f" -> 🔗 NetworkLink para '{antena_nome}' adicionado ao KML principal.")
    else:
        logger.error(f"Erro: Imagem principal '{path_imagem_principal}' ou legenda '{path_colour_key}' não encontrada. KMZ da antena principal não pode ser criado.")

    # --- 2. Criar KMZs para cada Repetidora ---
    logger.info(" -> Procurando e criando KMZs para repetidoras...")
    repeater_counter = 1
    for item_path in generated_images_dir.iterdir():
        if item_path.name.startswith("repetidora_") and item_path.suffix == ".png":
            img_rep_path = item_path
            json_rep_path = img_rep_path.with_suffix(".json")

            if json_rep_path.exists():
                with open(json_rep_path, "r") as f_json:
                    bounds_rep_data = json.load(f_json).get("bounds")

                if bounds_rep_data:
                    rep_name = f"Repetidora Solar {repeater_counter}"
                    center_lat = (bounds_rep_data[0] + bounds_rep_data[2]) / 2
                    center_lon = (bounds_rep_data[1] + bounds_rep_data[3]) / 2
                    
                    sub_kmz_rep_path = _create_coverage_kmz(
                        entity_name=rep_name,
                        entity_coords=[(center_lon, center_lat)],
                        entity_style=repetidora_style,
                        coverage_name=f"Cobertura {rep_name}",
                        coverage_image_path=img_rep_path,
                        coverage_bounds=bounds_rep_data,
                        colour_key_path=path_colour_key, # Reusa a mesma legenda
                        torre_icon_path=path_torre_icon, # Reusa o mesmo ícone
                        output_dir=generated_images_dir,
                        details_subfolder_name=details_subfolder_name
                    )
                    sub_kmz_paths_to_add.append(sub_kmz_rep_path)
                    
                    # Adicionar NetworkLink ao KML principal
                    nl_rep = doc.newnetworklink(name=rep_name)
                    nl_rep.link.href = sub_kmz_rep_path.name
                    logger.info(f" -> 🔗 NetworkLink para '{rep_name}' adicionado ao KML principal.")
                    repeater_counter += 1

    # --- 3. Adicionar Pastas Secundárias ao KML Principal ---
    _add_secondary_folders(
        doc,
        pivos_data,
        ciclos_data,
        bombas_data,
        default_point_style
    )

    logger.info("Construção da estrutura KML principal e sub-KMZs concluída.")
    return sub_kmz_paths_to_add