import simplekml
from pathlib import Path
import logging
import json
from datetime import datetime
import re

# 👇 ALTERAÇÃO 1: Importa o objeto 'settings' para termos acesso ao caminho base das imagens.
from backend.config import settings

logger = logging.getLogger(__name__)

COLOUR_KEY_KML_NAME = "Colour Key - dBm"

def _create_kml_styles(
    torre_icon_name: str,
    default_icon_url: str
) -> tuple[simplekml.Style, simplekml.Style, simplekml.Style]:
    # Sem alterações
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

def _setup_main_antenna_structure(
    doc: simplekml.Document,
    antena: dict,
    torre_style: simplekml.Style,
    details_subfolder_actual_name: str,
    torre_icon_name: str 
) -> simplekml.Folder:
    # Sem alterações
    antena_nome = antena.get("nome", "Antena Principal")
    folder_antena_main = doc.newfolder(name=antena_nome)
    folder_antena_main.style.liststyle.itemicon.href = torre_icon_name
    subfolder_details = folder_antena_main.newfolder(name=details_subfolder_actual_name) 
    pnt_antena = subfolder_details.newpoint(name=antena_nome, coords=[(antena["lon"], antena["lat"])])
    pnt_antena.description = f"Altura: {antena.get('altura', 'N/A')}m"
    pnt_antena.style = torre_style
    logger.info(f" -> Estrutura de pastas para '{antena_nome}' (subpasta: '{details_subfolder_actual_name}') criada.")
    return subfolder_details

def _add_overlays_and_repeater_structures(
    doc: simplekml.Document,
    main_antenna_details_subfolder: simplekml.Folder,
    imagem_principal_nome_kmz: str,
    bounds_principal_data: list,
    repetidora_style: simplekml.Style,
    generated_images_dir: Path,
    colour_key_filename: str,
    main_coverage_actual_name: str, 
    template_id: str,
    repetidoras_data: list[dict],
    torre_icon_name: str,
    timestamp_prefix: str
) -> list[tuple[Path, str]]:
    arquivos_a_adicionar_ao_kmz = []
    
    ground_main = main_antenna_details_subfolder.newgroundoverlay(name=main_coverage_actual_name)
    ground_main.icon.href = imagem_principal_nome_kmz
    b = bounds_principal_data
    ground_main.latlonbox.north, ground_main.latlonbox.south = b[2], b[0]
    ground_main.latlonbox.east, ground_main.latlonbox.west = b[3], b[1]
    ground_main.color = "ffffffff"
    arquivos_a_adicionar_ao_kmz.append((generated_images_dir / imagem_principal_nome_kmz, imagem_principal_nome_kmz))
    
    screen_main = main_antenna_details_subfolder.newscreenoverlay(name=COLOUR_KEY_KML_NAME)
    screen_main.icon.href = colour_key_filename
    screen_main.overlayxy = simplekml.OverlayXY(x=0, y=1, xunits=simplekml.Units.fraction, yunits=simplekml.Units.fraction)
    screen_main.screenxy = simplekml.ScreenXY(x=0, y=1, xunits=simplekml.Units.fraction, yunits=simplekml.Units.fraction)
    screen_main.size = simplekml.Size(x=0, y=0, xunits=simplekml.Units.fraction, yunits=simplekml.Units.fraction)
    
    # Procura a legenda no diretório do job
    path_colour_key = generated_images_dir / colour_key_filename
    if path_colour_key.exists():
        if not any(item[1] == colour_key_filename for item in arquivos_a_adicionar_ao_kmz):
            arquivos_a_adicionar_ao_kmz.append((path_colour_key, colour_key_filename))

    logger.info(f" -> Adicionando {len(repetidoras_data)} repetidora(s) selecionada(s)...")
    repeater_counter = 1
    for rep_data in repetidoras_data:
        nome_imagem_rep = rep_data.get("imagem")
        if not nome_imagem_rep or not (nome_imagem_rep.lower().startswith("repetidora_") and nome_imagem_rep.lower().endswith(".png")):
            continue

        img_rep_path_servidor = generated_images_dir / nome_imagem_rep
        json_rep_path_servidor = img_rep_path_servidor.with_suffix(".json")

        if json_rep_path_servidor.exists():
            with open(json_rep_path_servidor, "r") as f_json:
                bounds_rep_data = json.load(f_json).get("bounds")

            if bounds_rep_data:
                altura = rep_data.get("altura", 5)
                is_on_pivot = rep_data.get("sobre_pivo", False)
                custom_repeater_name = f"Repetidora Solar Pivô - {altura}m" if is_on_pivot else f"Repetidora Solar - {altura}m"
                
                repeater_name_part = f"Repetidora_{repeater_counter:02d}"
                dynamic_subfolder_name = f"{timestamp_prefix}_{repeater_name_part}_Irricontrol_{template_id}"

                folder_rep_main = doc.newfolder(name=custom_repeater_name)
                folder_rep_main.style.liststyle.itemicon.href = torre_icon_name
                
                subfolder_rep_details = folder_rep_main.newfolder(name=dynamic_subfolder_name) 

                center_lat = (bounds_rep_data[0] + bounds_rep_data[2]) / 2
                center_lon = (bounds_rep_data[1] + bounds_rep_data[3]) / 2
                pnt_rep = subfolder_rep_details.newpoint(name=custom_repeater_name, coords=[(center_lon, center_lat)])
                pnt_rep.style = repetidora_style
                
                ground_rep = subfolder_rep_details.newgroundoverlay(name=f"Cobertura {custom_repeater_name}") 
                ground_rep.icon.href = img_rep_path_servidor.name
                br = bounds_rep_data
                ground_rep.latlonbox.north, ground_rep.latlonbox.south = br[2], br[0]
                ground_rep.latlonbox.east, ground_rep.latlonbox.west = br[3], br[1]
                arquivos_a_adicionar_ao_kmz.append((img_rep_path_servidor, img_rep_path_servidor.name))

                screen_rep = subfolder_rep_details.newscreenoverlay(name=COLOUR_KEY_KML_NAME)
                screen_rep.icon.href = colour_key_filename
                screen_rep.overlayxy = simplekml.OverlayXY(x=0, y=1, xunits=simplekml.Units.fraction, yunits=simplekml.Units.fraction)
                screen_rep.screenxy = simplekml.ScreenXY(x=0, y=1, xunits=simplekml.Units.fraction, yunits=simplekml.Units.fraction)
                screen_rep.size = simplekml.Size(x=0, y=0, xunits=simplekml.Units.fraction, yunits=simplekml.Units.fraction)
                
                logger.info(f"     -> Estrutura para '{custom_repeater_name}' (subpasta: {dynamic_subfolder_name}) adicionada.")
                repeater_counter += 1
    return arquivos_a_adicionar_ao_kmz

def _add_secondary_folders(
    doc: simplekml.Document,
    pivos: list, ciclos: list, bombas: list,
    default_point_style: simplekml.Style
):
    # Sem alterações
    if pivos:
        folder_pivos = doc.newfolder(name="Pivôs")
        for i, p_data in enumerate(pivos):
            pivo_nome = p_data.get("nome", f"Pivo {i+1}")
            pnt_pivo = folder_pivos.newpoint(name=pivo_nome, coords=[(p_data["lon"], p_data["lat"])])
            pnt_pivo.style = default_point_style
        logger.info(" -> Pasta 'Pivôs' criada.")
    if ciclos:
        folder_ciclos = doc.newfolder(name="Ciclos")
        for i, ciclo_data in enumerate(ciclos):
            ciclo_nome = ciclo_data.get("nome", f"Ciclo {i+1}")
            pol = folder_ciclos.newpolygon(name=ciclo_nome)
            pol.outerboundaryis = [(lon, lat) for lat, lon in ciclo_data["coordenadas"]]
            pol.style.polystyle.fill = 0
            pol.style.linestyle.color = simplekml.Color.red
            pol.style.linestyle.width = 4
        logger.info(" -> Pasta 'Ciclos' criada.")
    if bombas:
        folder_bombas = doc.newfolder(name="Bombas")
        for i, bomba_data in enumerate(bombas):
            bomba_nome = bomba_data.get("nome", f"Bomba {i+1}")
            pnt_bomba = folder_bombas.newpoint(name=bomba_nome, coords=[(bomba_data["lon"], bomba_data["lat"])])
            pnt_bomba.style = default_point_style
        logger.info(" -> Pasta 'Bombas' criada.")

def build_kml_document_and_get_image_list(
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
    template_txw_for_main_coverage: float,
    repetidoras_selecionadas_data: list[dict]
) -> list[tuple[Path, str]]:
    
    logger.info("Iniciando construção da estrutura KML.")
    torre_style, default_point_style, repetidora_style = _create_kml_styles(
        torre_icon_name, default_icon_url
    )

    timestamp_for_name = datetime.now().strftime('%m%d%H%M%S')
    antena_nome_base = antena_data.get("nome", "Antena Principal")
    sanitized_antena_nome = re.sub(r'[\s-]+', '_', antena_nome_base)
    details_subfolder_name = f"{timestamp_for_name}_{sanitized_antena_nome}_Irricontrol_{template_id_for_subfolder}"
    main_coverage_name = f"Cobertura {template_frq_for_main_coverage}MHz {template_txw_for_main_coverage}W"

    main_antenna_details_subfolder = _setup_main_antenna_structure(
        doc, antena_data, torre_style, details_subfolder_name, torre_icon_name
    )
    
    image_files_for_kmz = _add_overlays_and_repeater_structures(
        doc, 
        main_antenna_details_subfolder,
        imagem_principal_nome_relativo, 
        bounds_principal_data,
        repetidora_style,
        generated_images_dir,
        colour_key_filename,
        main_coverage_name, 
        template_id=template_id_for_subfolder,
        repetidoras_data=repetidoras_selecionadas_data,
        torre_icon_name=torre_icon_name,
        timestamp_prefix=timestamp_for_name
    )

    _add_secondary_folders(doc, pivos_data, ciclos_data, bombas_data, default_point_style)

    # 👇 ALTERAÇÃO 2: Procura o ícone da torre no diretório PAI (o 'static/imagens' global)
    # em vez de no diretório específico do job (generated_images_dir).
    path_torre_icon = settings.IMAGENS_DIR_PATH / torre_icon_name
    
    if path_torre_icon.exists():
        if not any(item[1] == torre_icon_name for item in image_files_for_kmz):
            image_files_for_kmz.append((path_torre_icon, torre_icon_name))
            logger.info(f" -> Ícone compartilhado '{torre_icon_name}' encontrado e adicionado à lista de exportação.")
    else:
        logger.warning(f" -> ⚠️ Ícone compartilhado '{torre_icon_name}' não encontrado em '{settings.IMAGENS_DIR_PATH}'.")

    logger.info("Construção da estrutura KML concluída.")
    return image_files_for_kmz