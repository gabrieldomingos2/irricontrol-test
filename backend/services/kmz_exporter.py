import simplekml
from pathlib import Path
import logging
import json
from datetime import datetime
import re
from math import log10
from typing import Any
from shutil import copyfile

from backend.config import settings # type: ignore

logger = logging.getLogger("irricontrol")

# --- Constantes ---
COLOUR_KEY_KML_NAME = "Colour Key"
LOGO_FILENAME = "IRRICONTROL.png"
TORRE_ICON_NAME = "cloudrf.png"
DEFAULT_ICON_URL = "http://maps.google.com/mapfiles/kml/pushpin/ylw-pushpin.png"

def _create_html_description_table(
    sim_type: str, entity_data: dict, template: Any,
    file_id_info: str, colour_key_filename: str
) -> str:
    txw = template.transmitter.txw
    txg_dbi = template.antenna.txg
    tx_power_dbm = 10 * log10(txw * 1000)
    eirp_dbm = tx_power_dbm + txg_dbi
    eirp_w = (10**(eirp_dbm / 10)) / 1000
    erp_dbm = eirp_dbm - 2.15
    erp_w = (10**(erp_dbm / 10)) / 1000
    
    lat = entity_data.get('lat')
    lon = entity_data.get('lon')
    lat_str = f"{lat:.6f}" if isinstance(lat, float) else "N/A"
    lon_str = f"{lon:.6f}" if isinstance(lon, float) else "N/A"
    
    html = f"""
    <div style="font-family: Arial, sans-serif; font-size: 12px;">
    <table border="1" cellpadding="4" cellspacing="0" style="border-collapse: collapse; width: 350px;">
        <tr><td bgcolor="#f2f2f2" style="width: 120px;"><b>Frequency</b></td><td>{template.frq} MHz</td></tr>
        <tr><td bgcolor="#f2f2f2"><b>RF Power</b></td><td>{txw} W</td></tr>
        <tr><td bgcolor="#f2f2f2"><b>Tx Gain</b></td><td>{txg_dbi} dBi</td></tr>
        <tr><td bgcolor="#f2f2f2"><b>ERP</b></td><td>{erp_w:.3f} W / {erp_dbm:.3f} dBm</td></tr>
        <tr><td bgcolor="#f2f2f2"><b>EIRP</b></td><td>{eirp_w:.3f} W / {eirp_dbm:.3f} dBm</td></tr>
        <tr><td bgcolor="#f2f2f2"><b>Tx Lat/Lon</b></td><td>{lat_str}, {lon_str}</td></tr>
        <tr><td bgcolor="#f2f2f2"><b>Tx Height</b></td><td>{entity_data.get('altura', 'N/A')}m</td></tr>
        <tr><td bgcolor="#f2f2f2"><b>Tx Antenna</b></td><td>Pattern: DIPOLE.ANT<br>Azimuth: 0°<br>Tilt: 0°<br>Polarisation: v<br>Gain: {txg_dbi} dBi</td></tr>
        <tr><td bgcolor="#f2f2f2"><b>Rx Height</b></td><td>{template.receiver.alt}m</td></tr>
        <tr><td bgcolor="#f2f2f2"><b>Rx Sensitivity</b></td><td>{template.rxs}dBm</td></tr>
        <tr><td bgcolor="#f2f2f2"><b>Rx Gain</b></td><td>{template.receiver.rxg} dBi</td></tr>
        <tr><td bgcolor="#f2f2f2"><b>Modulation</b></td><td>CW</td></tr>
        <tr><td bgcolor="#f2f2f2"><b>Bandwidth</b></td><td>{template.transmitter.bwi} MHz</td></tr>
        <tr><td bgcolor="#f2f2f2"><b>RF Model</b></td><td>1-2-4</td></tr>
        <tr><td bgcolor="#f2f2f2"><b>Resolution</b></td><td>30m</td></tr>
        <tr><td bgcolor="#f2f2f2"><b>Radius</b></td><td>10Km</td></tr>
        <tr><td bgcolor="#f2f2f2"><b>Area</b></td><td>8.79217</td></tr>
        <tr><td bgcolor="#f2f2f2"><b>Coverage</b></td><td>3</td></tr>
        <tr><td bgcolor="#f2f2f2"><b>File ID</b></td><td>{file_id_info}</td></tr>
        <tr><td bgcolor="#f2f2f2"><b>Colour Key</b></td><td><img src="{colour_key_filename}" alt="Legenda de Cores" style="max-width: 120px; height: auto;"></td></tr>
        <tr>
            <td colspan="2" style="text-align: center; background-color: #ffffff; padding: 2px;">
                <img src="{LOGO_FILENAME}" alt="Logo Irricontrol" style="width: 200px;">
            </td>
        </tr>
    </table>
    </div>
    """
    return html

def _create_kml_styles() -> tuple[simplekml.Style, simplekml.Style, simplekml.Style]:
    torre_style = simplekml.Style()
    torre_style.iconstyle.icon.href = TORRE_ICON_NAME
    torre_style.iconstyle.scale = 1.2
    torre_style.labelstyle.scale = 1.1
    default_point_style = simplekml.Style()
    default_point_style.iconstyle.icon.href = DEFAULT_ICON_URL
    default_point_style.iconstyle.scale = 1.0
    default_point_style.labelstyle.scale = 1.0
    repetidora_style = simplekml.Style()
    repetidora_style.iconstyle.icon.href = TORRE_ICON_NAME
    repetidora_style.iconstyle.scale = 1.1
    repetidora_style.labelstyle.scale = 1.0
    return torre_style, default_point_style, repetidora_style

def _setup_main_antenna_structure(
    doc: simplekml.Document, antena: dict, torre_style: simplekml.Style,
    details_subfolder_name: str, template: Any,
    file_id_str: str, colour_key_desc_filename: str
) -> simplekml.Folder:
    antena_nome = antena.get("nome", "Antena Principal")
    folder_antena_main = doc.newfolder(name=antena_nome)
    folder_antena_main.style.liststyle.itemicon.href = TORRE_ICON_NAME
    subfolder_details = folder_antena_main.newfolder(name=details_subfolder_name)
    pnt_antena = subfolder_details.newpoint(name=antena_nome, coords=[(antena["lon"], antena["lat"])])
    pnt_antena.description = _create_html_description_table(
        sim_type='Antena Principal', entity_data=antena, template=template,
        file_id_info=file_id_str, colour_key_filename=colour_key_desc_filename
    )
    pnt_antena.style = torre_style
    logger.info(f" -> Estrutura de pastas para '{antena_nome}' criada.")
    return subfolder_details

def _add_overlays_and_repeater_structures(
    doc: simplekml.Document, main_folder: simplekml.Folder,
    image_name: str, bounds_data: list, repetidora_style: simplekml.Style,
    images_dir: Path, overlay_legend_name: str, desc_legend_name: str,
    coverage_name: str, template: Any, repeaters_data: list[dict],
    timestamp_prefix: str
) -> list[tuple[Path, str]]:
    files_to_add = []
    ground = main_folder.newgroundoverlay(name=coverage_name)
    ground.icon.href = image_name
    b = bounds_data
    ground.latlonbox.north, ground.latlonbox.south, ground.latlonbox.east, ground.latlonbox.west = b[2], b[0], b[3], b[1]
    ground.color = "ffffffff"
    files_to_add.append((images_dir / image_name, image_name))
    
    screen = main_folder.newscreenoverlay(name=COLOUR_KEY_KML_NAME)
    screen.icon.href = overlay_legend_name
    screen.overlayxy = simplekml.OverlayXY(x=0, y=1, xunits=simplekml.Units.fraction, yunits=simplekml.Units.fraction)
    screen.screenxy = simplekml.ScreenXY(x=10, y=1, xunits=simplekml.Units.pixels, yunits=simplekml.Units.fraction)
    screen.size = simplekml.Size(x=40, y=70, xunits=simplekml.Units.pixels, yunits=simplekml.Units.pixels)

    for i, rep_data in enumerate(repeaters_data):
        nome_img_rep = rep_data.get("imagem")
        if not nome_img_rep or not nome_img_rep.lower().endswith(".png"):
            continue
        path_img_rep = images_dir / nome_img_rep
        path_json_rep = path_img_rep.with_suffix(".json")
        if not path_json_rep.exists():
            continue
        with open(path_json_rep, "r") as f:
            bounds = json.load(f).get("bounds")
        if not bounds:
            continue
        altura = rep_data.get("altura", 5)
        sobre_pivo = rep_data.get("sobre_pivo", False)
        nome_personalizado = f"Repetidora Solar Pivô - {altura}m" if sobre_pivo else f"Repetidora Solar - {altura}m"
        nome_repetidora_id = f"Repetidora_{i+1:02d}"
        subpasta_nome = f"{timestamp_prefix}_{nome_repetidora_id}_Irricontrol_{template.id}"
        folder_rep = doc.newfolder(name=nome_personalizado)
        folder_rep.style.liststyle.itemicon.href = TORRE_ICON_NAME
        subfolder = folder_rep.newfolder(name=subpasta_nome)
        centro_lat = (bounds[0] + bounds[2]) / 2
        centro_lon = (bounds[1] + bounds[3]) / 2
        ponto = subfolder.newpoint(name=nome_personalizado, coords=[(centro_lon, centro_lat)])
        ponto.description = _create_html_description_table(
            sim_type="Repetidora",
            entity_data={"nome": nome_personalizado, "lat": centro_lat, "lon": centro_lon, "altura": altura},
            template=template,
            file_id_info=f"{timestamp_prefix}{nome_repetidora_id}_{template.id}",
            colour_key_filename=desc_legend_name
        )
        ponto.style = repetidora_style
        ground_rep = subfolder.newgroundoverlay(name=f"Cobertura {nome_personalizado}")
        ground_rep.icon.href = nome_img_rep
        ground_rep.latlonbox.north, ground_rep.latlonbox.south, ground_rep.latlonbox.east, ground_rep.latlonbox.west = bounds[2], bounds[0], bounds[3], bounds[1]
        files_to_add.append((path_img_rep, nome_img_rep))
        
        screen_rep = subfolder.newscreenoverlay(name=COLOUR_KEY_KML_NAME)
        screen_rep.icon.href = overlay_legend_name
        screen_rep.overlayxy = simplekml.OverlayXY(x=0, y=1, xunits=simplekml.Units.fraction, yunits=simplekml.Units.fraction)
        screen_rep.screenxy = simplekml.ScreenXY(x=10, y=1, xunits=simplekml.Units.pixels, yunits=simplekml.Units.fraction)
        screen_rep.size = simplekml.Size(x=40, y=70, xunits=simplekml.Units.pixels, yunits=simplekml.Units.pixels)
        
        logger.info(f" -> Repetidora '{nome_personalizado}' adicionada com overlay e descrição.")
    return files_to_add

def _add_secondary_folders(
    doc: simplekml.Document, pivos: list, ciclos: list, bombas: list,
    default_point_style: simplekml.Style
):
    if pivos:
        folder_pivos = doc.newfolder(name="Pivôs")
        folder_pivos.visibility = 0  # ✅ NOVO: Define a pasta para estar desmarcada por padrão
        for i, p_data in enumerate(pivos):
            pnt_pivo = folder_pivos.newpoint(name=p_data["nome"], coords=[(p_data["lon"], p_data["lat"])])
            pnt_pivo.style = default_point_style
        logger.info(" -> Pasta 'Pivôs' criada e configurada como invisível por padrão.")
    if ciclos:
        folder_ciclos = doc.newfolder(name="Ciclos")
        for i, ciclo_data in enumerate(ciclos):
            ciclo_nome = ciclo_data.get("nome_original_circulo", f"Ciclo {i+1}")
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
    doc: simplekml.Document, antena_data: dict, pivos_data: list,
    ciclos_data: list, bombas_data: list, imagem_principal_nome_relativo: str,
    bounds_principal_data: list, generated_images_dir: Path, selected_template: Any,
    study_date_str_for_subfolder: str, repetidoras_selecionadas_data: list[dict]
) -> list[tuple[Path, str]]:
    
    logger.info("Iniciando construção da estrutura KML.")
    torre_style, default_point_style, repetidora_style = _create_kml_styles()
    
    base_col_name = selected_template.col
    colour_key_desc_filename = f"{base_col_name}.key.png"
    colour_key_overlay_filename = f"{base_col_name}.overlay.png"
    original_legend_path = settings.IMAGENS_DIR_PATH / colour_key_desc_filename
    overlay_legend_path = settings.IMAGENS_DIR_PATH / colour_key_overlay_filename

    if original_legend_path.exists() and not overlay_legend_path.exists():
        try:
            copyfile(original_legend_path, overlay_legend_path)
            logger.info(f" -> Copiada imagem de legenda para overlay: {overlay_legend_path.name}")
        except Exception as e:
            logger.error(f" -> ❌ Falha ao copiar arquivo de legenda: {e}")
    
    timestamp_for_name = datetime.now().strftime('%m%d%H%M%S')
    antena_nome_base = antena_data.get("nome", "Antena Principal")
    sanitized_antena_nome = re.sub(r'[\s-]+', '_', antena_nome_base)
    details_subfolder_name = f"{timestamp_for_name}_{sanitized_antena_nome}_Irricontrol_{selected_template.id}"
    main_coverage_name = f"Cobertura {selected_template.frq}MHz {selected_template.transmitter.txw}W"
    
    file_id_principal = f"{timestamp_for_name[4:]}_{antena_nome_base.replace(' ', '')}_{selected_template.id}"
    main_antenna_details_subfolder = _setup_main_antenna_structure(
        doc, antena_data, torre_style, details_subfolder_name,
        template=selected_template, file_id_str=file_id_principal,
        colour_key_desc_filename=colour_key_desc_filename
    )
    
    image_files_for_kmz = _add_overlays_and_repeater_structures(
        doc, main_antenna_details_subfolder, imagem_principal_nome_relativo,
        bounds_principal_data, repetidora_style, generated_images_dir,
        overlay_legend_name=colour_key_overlay_filename,
        desc_legend_name=colour_key_desc_filename,
        coverage_name=main_coverage_name, template=selected_template,
        repeaters_data=repetidoras_selecionadas_data,
        timestamp_prefix=timestamp_for_name
    )
    
    _add_secondary_folders(doc, pivos_data, ciclos_data, bombas_data, default_point_style)

    arquivos_a_incluir = [
        (settings.IMAGENS_DIR_PATH / TORRE_ICON_NAME, TORRE_ICON_NAME),
        (original_legend_path, colour_key_desc_filename),
        (overlay_legend_path, colour_key_overlay_filename),
        (settings.IMAGENS_DIR_PATH / LOGO_FILENAME, LOGO_FILENAME)
    ]

    for path_arquivo, nome_no_zip in arquivos_a_incluir:
        if path_arquivo.exists():
            if not any(item[1] == nome_no_zip for item in image_files_for_kmz):
                image_files_for_kmz.append((path_arquivo, nome_no_zip))
                logger.info(f" -> Arquivo compartilhado '{nome_no_zip}' adicionado ao KMZ.")
        else:
            logger.warning(f" -> ⚠️ Arquivo compartilhado '{path_arquivo}' não encontrado.")

    logger.info("Construção da estrutura KML concluída.")
    return image_files_for_kmz