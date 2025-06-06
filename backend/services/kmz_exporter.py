import simplekml
from pathlib import Path
import logging
import json
import zipfile
from typing import List, Dict, Tuple, Optional

logger = logging.getLogger(__name__)

COLOUR_KEY_KML_NAME = "Colour Key - dBm"

def _create_kml_styles(
    torre_icon_name: str,
    default_icon_url: str
) -> tuple[simplekml.Style, simplekml.Style, simplekml.Style]:
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
    if pivos:
        folder_pivos = doc.newfolder(name="Pivôs")
        for p_data in pivos:
            pnt_pivo = folder_pivos.newpoint(name=p_data.get("nome"), coords=[(p_data["lon"], p_data["lat"])])
            pnt_pivo.style = default_point_style
    if ciclos:
        folder_ciclos = doc.newfolder(name="Ciclos")
        for ciclo_data in ciclos:
            pol = folder_ciclos.newpolygon(name=ciclo_data.get("nome_original_circulo"))
            pol.outerboundaryis = [(lon, lat) for lat, lon in ciclo_data["coordenadas"]]
            pol.style.polystyle.fill = 0
            pol.style.linestyle.color = simplekml.Color.red
            pol.style.linestyle.width = 4
    if bombas:
        folder_bombas = doc.newfolder(name="Bombas")
        for bomba_data in bombas:
            pnt_bomba = folder_bombas.newpoint(name=bomba_data.get("nome"), coords=[(bomba_data["lon"], bomba_data["lat"])])
            pnt_bomba.style = default_point_style

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
    internal_folder_name: str, # NOME DA PASTA INTERNA AJUSTADO
    entity_description: Optional[str] = None
) -> Path:
    logger.info(f"   -> 🏭 Criando KMZ individual para: '{entity_name}'")
    kml_sub = simplekml.Kml()
    
    # **ALTERAÇÃO AQUI**: Cria a pasta interna com o nome derivado do arquivo de simulação
    details_folder = kml_sub.newfolder(name=internal_folder_name)

    # Adiciona os itens dentro desta pasta
    pnt = details_folder.newpoint(name=entity_name, coords=entity_coords)
    pnt.style = entity_style
    if entity_description:
        pnt.description = entity_description

    ground = details_folder.newgroundoverlay(name=coverage_name)
    ground.icon.href = coverage_image_path.name
    b = coverage_bounds
    ground.latlonbox.north, ground.latlonbox.south = b[2], b[0]
    ground.latlonbox.east, ground.latlonbox.west = b[3], b[1]

    screen = details_folder.newscreenoverlay(name=COLOUR_KEY_KML_NAME)
    screen.icon.href = colour_key_path.name
    screen.overlayxy = simplekml.OverlayXY(x=0, y=1, xunits=simplekml.Units.fraction, yunits=simplekml.Units.fraction)
    screen.screenxy = simplekml.ScreenXY(x=0, y=1, xunits=simplekml.Units.fraction, yunits=simplekml.Units.fraction)
    screen.size = simplekml.Size(x=0, y=0, xunits=simplekml.Units.fraction, yunits=simplekml.Units.fraction)

    safe_name = "".join(c for c in entity_name if c.isalnum() or c in (' ', '_')).rstrip()
    sub_kmz_filename = f"sub_{safe_name.replace(' ', '_').lower()}.kmz"
    path_kmz_final = output_dir / sub_kmz_filename
    
    # Salva diretamente no KMZ sem um KML intermediário explícito
    kml_sub.savekmz(str(path_kmz_final), files_to_add=[
        (str(coverage_image_path), coverage_image_path.name),
        (str(colour_key_path), colour_key_path.name),
        (str(torre_icon_path), torre_icon_path.name)
    ])

    logger.info(f"   -> ✅ KMZ individual '{path_kmz_final.name}' criado.")
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
    internal_folder_name: str, # Parâmetro novo para o nome da pasta
    template_frq_for_main_coverage: int,
    template_txw_for_main_coverage: float
) -> List[Path]:
    logger.info("Iniciando construção de KML com NetworkLinks.")
    sub_kmz_paths_to_add = []
    
    torre_style, default_point_style, repetidora_style = _create_kml_styles(
        torre_icon_name, default_icon_url
    )
    
    # **ALTERAÇÃO AQUI**: Nome da cobertura sem o prefixo "Cobertura"
    main_coverage_name = f"{template_frq_for_main_coverage}MHz {template_txw_for_main_coverage}W"
    
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
            internal_folder_name=internal_folder_name, # Passa o nome correto
            entity_description=f"Altura: {antena_data.get('altura', 'N/A')}m"
        )
        sub_kmz_paths_to_add.append(sub_kmz_antena_path)
        
        nl_antena = doc.newnetworklink(name=antena_nome)
        nl_antena.link.href = sub_kmz_antena_path.name
        logger.info(f" -> 🌐 NetworkLink para '{antena_nome}' adicionado.")

    repeater_counter = 1
    for item_path in generated_images_dir.iterdir():
        if item_path.name.startswith("repetidora_") and item_path.suffix == ".png":
            json_rep_path = item_path.with_suffix(".json")
            if json_rep_path.exists():
                with open(json_rep_path, "r") as f_json:
                    bounds_rep_data = json.load(f_json).get("bounds")
                if bounds_rep_data:
                    rep_name = f"Repetidora Solar {repeater_counter}"
                    # Usa o nome do arquivo da repetidora para a pasta interna
                    rep_internal_folder_name = item_path.name.replace(".png", "")
                    
                    sub_kmz_rep_path = _create_coverage_kmz(
                        entity_name=rep_name, # O nome do ponto pode ser diferente do link
                        entity_coords=[(center_lon, center_lat) for center_lon, center_lat in [( (bounds_rep_data[1] + bounds_rep_data[3]) / 2, (bounds_rep_data[0] + bounds_rep_data[2]) / 2 )]],
                        entity_style=repetidora_style,
                        coverage_name=main_coverage_name, # Reusa os mesmos dados técnicos
                        coverage_image_path=item_path,
                        coverage_bounds=bounds_rep_data,
                        colour_key_path=path_colour_key,
                        torre_icon_path=path_torre_icon,
                        output_dir=generated_images_dir,
                        internal_folder_name=rep_internal_folder_name
                    )
                    sub_kmz_paths_to_add.append(sub_kmz_rep_path)
                    
                    nl_rep = doc.newnetworklink(name=rep_name) # O nome do link principal
                    nl_rep.link.href = sub_kmz_rep_path.name
                    logger.info(f" -> 🌐 NetworkLink para '{rep_name}' adicionado.")
                    repeater_counter += 1

    _add_secondary_folders(
        doc, pivos_data, ciclos_data, bombas_data, default_point_style
    )

    return sub_kmz_paths_to_add