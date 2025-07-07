# backend/services/kmz_exporter.py
import html
import simplekml
from pathlib import Path
import logging
import json
from datetime import datetime
import re
from math import log10
from typing import Any, Optional, List, Tuple, Callable
from shutil import copyfile
from geopy.distance import geodesic
from geopy.point import Point

from backend.config import settings
from backend.services.i18n_service import i18n_service

logger = logging.getLogger("irricontrol")
COLOUR_KEY_KML_NAME, LOGO_FILENAME, TORRE_ICON_NAME = "Colour Key", "IRRICONTROL.png", "cloudrf.png"
DEFAULT_ICON_URL = "http://maps.google.com/mapfiles/kml/pushpin/ylw-pushpin.png"

# --- Funções de Geração de Geometria (Sem alterações) ---

def _generate_sector_coords(lat, lon, radius_m, bearing_deg, arc_width_deg, steps=40) -> list:
    """Gera coordenadas para um polígono de setor (fatia de pizza)."""
    coords = [(lon, lat, 0)]
    center_point = Point(latitude=lat, longitude=lon)
    start_angle = bearing_deg - (arc_width_deg / 2)
    for i in range(steps + 1):
        angle = start_angle + (i * arc_width_deg / steps)
        dest = geodesic(meters=radius_m).destination(center_point, angle)
        coords.append((dest.longitude, dest.latitude, 0))
    coords.append((lon, lat, 0)) # Fecha o polígono no centro
    return coords

def _generate_pacman_coords(lat, lon, radius_m, start_angle_deg, end_angle_deg, steps=80) -> list:
    """Gera coordenadas para um polígono de setor invertido (Pac-Man)."""
    coords = [(lon, lat, 0)]
    center_point = Point(latitude=lat, longitude=lon)

    start_angle = start_angle_deg
    end_angle = end_angle_deg
    if end_angle <= start_angle:
        end_angle += 360

    mouth_angle = end_angle - start_angle
    irrigated_angle = 360 - mouth_angle

    for i in range(steps + 1):
        current_angle = end_angle + (i * irrigated_angle / steps)
        dest = geodesic(meters=radius_m).destination(center_point, current_angle)
        coords.append((dest.longitude, dest.latitude, 0))

    coords.append((lon, lat, 0)) # Fecha o polígono de volta ao centro
    return coords


# --- Funções de Criação de Estrutura KML ---

def _create_html_description_table(entity_data: dict, template: Any, file_id_info: str, colour_key_filename: str) -> str:
    txw, txg_dbi = template.transmitter.txw, template.antenna.txg
    tx_power_dbm = 10 * log10(txw * 1000)
    eirp_dbm = tx_power_dbm + txg_dbi
    eirp_w = (10**(eirp_dbm / 10)) / 1000
    erp_dbm = eirp_dbm - 2.15
    erp_w = (10**(erp_dbm / 10)) / 1000
    lat, lon = entity_data.get('lat'), entity_data.get('lon')
    lat_str, lon_str = (f"{lat:.6f}", f"{lon:.6f}") if isinstance(lat, float) else ("N/A", "N/A")
    file_id_info_sanitized = html.escape(file_id_info)
    
    return f"""<div style="font-family: Arial, sans-serif; font-size: 12px;">
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
        <tr><td bgcolor="#f2f2f2"><b>File ID</b></td><td>{file_id_info_sanitized}</td></tr>
        <tr><td bgcolor="#f2f2f2"><b>Colour Key</b></td><td><img src="{colour_key_filename}" alt="Legenda" style="max-width: 120px;"></td></tr>
        <tr><td colspan="2" style="text-align: center;"><img src="{LOGO_FILENAME}" alt="Logo" style="width: 200px;"></td></tr>
    </table></div>"""

def _create_kml_styles() -> Tuple[simplekml.Style, simplekml.Style]:
    torre_style = simplekml.Style(iconstyle=simplekml.IconStyle(icon=simplekml.Icon(href=TORRE_ICON_NAME), scale=1.2), labelstyle=simplekml.LabelStyle(scale=1.1))
    default_point_style = simplekml.Style(iconstyle=simplekml.IconStyle(icon=simplekml.Icon(href=DEFAULT_ICON_URL)))
    return torre_style, default_point_style

def _setup_main_antenna_structure(doc, antena, style, details_name, template, file_id, legend_name, t: Callable) -> simplekml.Folder:
    folder_name = antena.get("nome", t("kml.folders.main_antenna"))
    folder = doc.newfolder(name=folder_name)
    folder.style.liststyle.itemicon.href = TORRE_ICON_NAME
    subfolder = folder.newfolder(name=details_name)
    pnt = subfolder.newpoint(name=folder_name, coords=[(antena["lon"], antena["lat"])])
    pnt.description = _create_html_description_table(antena, template, file_id, legend_name)
    pnt.style = style
    return subfolder

def _add_repeaters(doc, data, style, img_dir, overlay_name, desc_name, template, ts_prefix, overlay_props, t: Callable) -> list:
    files = []
    for i, item in enumerate(data):
        img_name = item.get("imagem")
        if not img_name: continue
        path_img = img_dir / img_name
        path_json = path_img.with_suffix(".json")
        if not path_json.exists(): continue
        with open(path_json) as f:
            bounds = json.load(f).get("bounds")
        if not bounds: continue
        
        altura_repetidora = item.get('altura', 5)
        nome_from_frontend = item.get("nome")

        if nome_from_frontend:
            nome = nome_from_frontend
        else:
            if item.get('sobre_pivo'):
                nome = t("kml.repeaters.solar_pivot_repeater", height=altura_repetidora)
            else:
                nome = t("kml.repeaters.solar_repeater", height=altura_repetidora)

        sub_nome = f"{ts_prefix}_Rep{i+1:02d}_Irricontrol_{template.id}"
        
        folder = doc.newfolder(name=nome)
        folder.style.liststyle.itemicon.href = TORRE_ICON_NAME
        sub = folder.newfolder(name=sub_nome)
        lat, lon = (bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2
        
        pnt = sub.newpoint(name=nome, coords=[(lon, lat)])
        pnt.description = _create_html_description_table({"lat": lat, "lon": lon, "altura": altura_repetidora}, template, f"{ts_prefix}{i+1}_{template.id}", desc_name)
        pnt.style = style
        
        ground = sub.newgroundoverlay(name=t("kml.overlays.coverage_for", name=nome))
        ground.icon.href = img_name
        ground.latlonbox.north, ground.latlonbox.south, ground.latlonbox.east, ground.latlonbox.west = bounds[2], bounds[0], bounds[3], bounds[1]
        files.append((path_img, img_name))
        
        screen_rep = sub.newscreenoverlay(name=COLOUR_KEY_KML_NAME)
        screen_rep.icon.href = overlay_name
        screen_rep.overlayxy = simplekml.OverlayXY(**overlay_props['overlay_xy'])
        screen_rep.screenxy = simplekml.ScreenXY(**overlay_props['screen_xy'])
        screen_rep.size = simplekml.Size(**overlay_props['size'])
        
    return files

def _add_secondary_folders(doc, pivos, ciclos, bombas, style, t: Callable):
    if pivos:
        f_pivos = doc.newfolder(name=t("kml.folders.pivots_markers"))
        for p_data in pivos:
            f_pivos.newpoint(name=p_data["nome"], coords=[(p_data["lon"], p_data["lat"])]).style = style

    f_areas = doc.newfolder(name=t("kml.folders.pivot_areas"))
    nomes_pivos_desenhados_manualmente = set()

    pivos_com_area_manual = [p for p in pivos if p.get('tipo') in ['setorial', 'pacman']]
    if pivos_com_area_manual:
        logger.info(f"Exportando {len(pivos_com_area_manual)} áreas de pivôs desenhados manualmente.")
        for pivo_data in pivos_com_area_manual:
            coords_area = []
            pivo_nome = pivo_data.get('nome', 'Sem Nome')
            pivo_tipo = pivo_data.get('tipo')
            
            try:
                if pivo_tipo == 'setorial':
                    coords_area = _generate_sector_coords(
                        lat=pivo_data['lat'], lon=pivo_data['lon'], radius_m=pivo_data['raio'],
                        bearing_deg=pivo_data['angulo_central'], arc_width_deg=pivo_data['abertura_arco']
                    )
                elif pivo_tipo == 'pacman':
                    coords_area = _generate_pacman_coords(
                        lat=pivo_data['lat'], lon=pivo_data['lon'], radius_m=pivo_data['raio'],
                        start_angle_deg=pivo_data['angulo_inicio'], end_angle_deg=pivo_data['angulo_fim']
                    )
                
                if coords_area:
                    pol = f_areas.newpolygon(name=t("kml.areas.pivot_area", name=pivo_nome))
                    pol.outerboundaryis = coords_area
                    pol.style.polystyle.fill = 0
                    pol.style.linestyle.color = simplekml.Color.red
                    pol.style.linestyle.width = 4
                    nomes_pivos_desenhados_manualmente.add(pivo_nome)
            except KeyError as e:
                logger.warning(f"Dados ausentes para desenhar área do pivô '{pivo_nome}': {e}. Pulando.")

    if ciclos:
        logger.info(f"Exportando {len(ciclos)} áreas de pivôs circulares.")
        for ciclo_data in ciclos:
            coords = ciclo_data.get("coordenadas")
            nome_ciclo = ciclo_data.get("nome_original_circulo", "")
            nome_pivo_associado = nome_ciclo.replace(t("kml.prefixes.cycle"), "").strip()

            if nome_pivo_associado in nomes_pivos_desenhados_manualmente:
                logger.info(f" -> Pulando círculo para '{nome_pivo_associado}', pois já foi desenhado como Setorial/Pac-Man.")
                continue

            if coords and len(coords) > 2:
                nome_area = nome_ciclo.replace(t("kml.prefixes.cycle"), t("kml.prefixes.area")).strip()
                pol = f_areas.newpolygon(name=nome_area)
                pol.outerboundaryis = [(lon, lat, 0) for lat, lon in coords]
                pol.style.polystyle.fill = 0
                pol.style.linestyle.color = simplekml.Color.red
                pol.style.linestyle.width = 4

    if bombas:
        f_bombas = doc.newfolder(name=t("kml.folders.pumps"))
        for i, b_data in enumerate(bombas):
            nome_padronizado = f'{t("entity_names.irripump")} {i+1}'
            f_bombas.newpoint(name=nome_padronizado, coords=[(b_data["lon"], b_data["lat"])]).style = style


def build_kml_document_and_get_image_list(doc, lang: str, pivos_data, ciclos_data, bombas_data, repetidoras_selecionadas_data, generated_images_dir, selected_template, antena_data, imagem_principal_nome_relativo, bounds_principal_data) -> List[Tuple[Path, str]]:
    logger.info(f"Iniciando construção da estrutura KML no idioma: {lang}.")
    t = i18n_service.get_translator(lang)

    torre_style, default_point_style = _create_kml_styles()
    
    key_desc_name = f"{selected_template.col}.key.png"
    key_overlay_name = f"{selected_template.col}.overlay.png"
    original_legend = settings.IMAGENS_DIR_PATH / key_desc_name
    overlay_legend = settings.IMAGENS_DIR_PATH / key_overlay_name
    if original_legend.exists() and not overlay_legend.exists():
        copyfile(original_legend, overlay_legend)
    
    files_for_kmz: List[Tuple[Path, str]] = []
    ts = datetime.now().strftime('%m%d%H%M%S')

    OVERLAY_PROPS = {
        "overlay_xy": {'x': 0, 'y': 1, 'xunits': simplekml.Units.fraction, 'yunits': simplekml.Units.fraction},
        "screen_xy": {'x': 10, 'y': 1, 'xunits': simplekml.Units.pixels, 'yunits': simplekml.Units.fraction},
        "size": {'x': -1, 'y': -1, 'xunits': simplekml.Units.pixels, 'yunits': simplekml.Units.pixels}
    }

    if antena_data and imagem_principal_nome_relativo and bounds_principal_data:
        logger.info(" -> Adicionando estrutura da Antena Principal.")
        nome_antena = antena_data.get("nome", "Antena")
        sub_nome = f"{ts}_{re.sub(r'[^a-zA-Z0-9]', '_', nome_antena)}_{selected_template.id}"
        file_id = f"{ts[4:]}_{nome_antena.replace(' ', '')}_{selected_template.id}"

        folder = _setup_main_antenna_structure(doc, antena_data, torre_style, sub_nome, selected_template, file_id, key_desc_name, t)
        
        ground = folder.newgroundoverlay(name=t("kml.overlays.coverage_freq", freq=selected_template.frq))
        ground.icon.href = imagem_principal_nome_relativo
        b = bounds_principal_data
        ground.latlonbox.north, ground.latlonbox.south, ground.latlonbox.east, ground.latlonbox.west = b[2], b[0], b[3], b[1]
        files_for_kmz.append((generated_images_dir / imagem_principal_nome_relativo, imagem_principal_nome_relativo))
        
        screen = folder.newscreenoverlay(name=COLOUR_KEY_KML_NAME)
        screen.icon.href = key_overlay_name
        screen.overlayxy = simplekml.OverlayXY(**OVERLAY_PROPS['overlay_xy'])
        screen.screenxy = simplekml.ScreenXY(**OVERLAY_PROPS['screen_xy'])
        screen.size = simplekml.Size(**OVERLAY_PROPS['size'])

    repeater_files = _add_repeaters(
        doc, repetidoras_selecionadas_data, torre_style, generated_images_dir,
        overlay_name=key_overlay_name, desc_name=key_desc_name,
        template=selected_template, ts_prefix=ts, overlay_props=OVERLAY_PROPS,
        t=t
    )
    files_for_kmz.extend(repeater_files)
    
    _add_secondary_folders(doc, pivos_data, ciclos_data, bombas_data, default_point_style, t)

    common_files = [(TORRE_ICON_NAME, TORRE_ICON_NAME), (key_desc_name, key_desc_name), (key_overlay_name, key_overlay_name), (LOGO_FILENAME, LOGO_FILENAME)]
    for fname, zip_name in common_files:
        fpath = settings.IMAGENS_DIR_PATH / fname
        if fpath.exists() and not any(item[1] == zip_name for item in files_for_kmz):
            files_for_kmz.append((fpath, zip_name))
            
    logger.info("Construção da estrutura KML concluída.")
    return files_for_kmz