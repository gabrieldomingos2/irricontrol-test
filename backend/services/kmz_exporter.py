# backend/services/kmz_exporter.py
import simplekml
from pathlib import Path
import logging
import json
from datetime import datetime
import re
from math import log10
from typing import Any, Optional, List, Tuple
from shutil import copyfile
from geopy.distance import geodesic
from geopy.point import Point

from backend.config import settings

logger = logging.getLogger("irricontrol")
COLOUR_KEY_KML_NAME, LOGO_FILENAME, TORRE_ICON_NAME = "Colour Key", "IRRICONTROL.png", "cloudrf.png"
DEFAULT_ICON_URL = "http://maps.google.com/mapfiles/kml/pushpin/ylw-pushpin.png"

def _create_html_description_table(entity_data: dict, template: Any, file_id_info: str, colour_key_filename: str) -> str:
    txw, txg_dbi = template.transmitter.txw, template.antenna.txg
    tx_power_dbm = 10 * log10(txw * 1000)
    eirp_dbm = tx_power_dbm + txg_dbi
    eirp_w = (10**(eirp_dbm / 10)) / 1000
    erp_dbm = eirp_dbm - 2.15
    erp_w = (10**(erp_dbm / 10)) / 1000
    lat, lon = entity_data.get('lat'), entity_data.get('lon')
    lat_str, lon_str = (f"{lat:.6f}", f"{lon:.6f}") if isinstance(lat, float) else ("N/A", "N/A")
    
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
        <tr><td bgcolor="#f2f2f2"><b>File ID</b></td><td>{file_id_info}</td></tr>
        <tr><td bgcolor="#f2f2f2"><b>Colour Key</b></td><td><img src="{colour_key_filename}" alt="Legenda" style="max-width: 120px;"></td></tr>
        <tr><td colspan="2" style="text-align: center;"><img src="{LOGO_FILENAME}" alt="Logo" style="width: 200px;"></td></tr>
    </table></div>"""

def _create_kml_styles() -> Tuple[simplekml.Style, simplekml.Style]:
    torre_style = simplekml.Style(iconstyle=simplekml.IconStyle(icon=simplekml.Icon(href=TORRE_ICON_NAME), scale=1.2), labelstyle=simplekml.LabelStyle(scale=1.1))
    default_point_style = simplekml.Style(iconstyle=simplekml.IconStyle(icon=simplekml.Icon(href=DEFAULT_ICON_URL)))
    return torre_style, default_point_style

def _setup_main_antenna_structure(doc, antena, style, details_name, template, file_id, legend_name) -> simplekml.Folder:
    folder = doc.newfolder(name=antena.get("nome", "Antena Principal")); folder.style.liststyle.itemicon.href = TORRE_ICON_NAME
    subfolder = folder.newfolder(name=details_name)
    pnt = subfolder.newpoint(name=antena.get("nome", "Antena"), coords=[(antena["lon"], antena["lat"])])
    pnt.description = _create_html_description_table(antena, template, file_id, legend_name); pnt.style = style
    return subfolder


def _add_repeaters(doc, data, style, img_dir, overlay_name, desc_name, template, ts_prefix, overlay_props) -> list:
    files = []
    for i, item in enumerate(data):
        img_name = item.get("imagem")
        if not img_name: continue
        path_img = img_dir / img_name
        path_json = path_img.with_suffix(".json")
        if not path_json.exists(): continue
        with open(path_json) as f: bounds = json.load(f).get("bounds")
        if not bounds: continue
        
        altura_repetidora = item.get('altura', 5)

        if item.get('sobre_pivo'):
            nome = f"Repetidora Solar Pivô - {altura_repetidora}m"
        else:
            nome = f"Repetidora Solar - {altura_repetidora}m"
            
        sub_nome = f"{ts_prefix}_Rep{i+1:02d}_Irricontrol_{template.id}"
        
        folder = doc.newfolder(name=nome); folder.style.liststyle.itemicon.href = TORRE_ICON_NAME
        sub = folder.newfolder(name=sub_nome)
        lat, lon = (bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2
        
        pnt = sub.newpoint(name=nome, coords=[(lon, lat)])
        
        pnt.description = _create_html_description_table({"lat": lat, "lon": lon, "altura": altura_repetidora}, template, f"{ts_prefix}{i+1}_{template.id}", desc_name)
        pnt.style = style
        
        ground = sub.newgroundoverlay(name=f"Cobertura {nome}"); ground.icon.href = img_name
        ground.latlonbox.north, ground.latlonbox.south, ground.latlonbox.east, ground.latlonbox.west = bounds[2], bounds[0], bounds[3], bounds[1]
        files.append((path_img, img_name))
        
        screen_rep = sub.newscreenoverlay(name=COLOUR_KEY_KML_NAME)
        screen_rep.icon.href = overlay_name
        screen_rep.overlayxy = simplekml.OverlayXY(**overlay_props['overlay_xy'])
        screen_rep.screenxy = simplekml.ScreenXY(**overlay_props['screen_xy'])
        screen_rep.size = simplekml.Size(**overlay_props['size'])
        
    return files

def _add_secondary_folders(doc, pivos, ciclos, bombas, style):
    if pivos:
        f_pivos = doc.newfolder(name="Pivôs (Marcadores)")
        for p_data in pivos: f_pivos.newpoint(name=p_data["nome"], coords=[(p_data["lon"], p_data["lat"])]).style = style
    
    if (ciclos and any(c.get("coordenadas") for c in ciclos)) or any(p.get('tipo') == 'setorial' for p in pivos):
        f_areas = doc.newfolder(name="Áreas de Pivôs")
        pivos_setoriais = [p for p in pivos if p.get('tipo') == 'setorial']
        for pivo_data in pivos_setoriais:
            try:
                coords_area = _generate_sector_coords(
                    lat=pivo_data['lat'], lon=pivo_data['lon'], radius_m=pivo_data['raio'],
                    bearing_deg=pivo_data['angulo_central'], arc_width_deg=pivo_data['abertura_arco']
                )
                if coords_area:
                    pol = f_areas.newpolygon(name=f"Área {pivo_data['nome']}")
                    pol.outerboundaryis = coords_area
                    pol.style.polystyle.fill = 0
                    pol.style.linestyle.color = simplekml.Color.red
                    pol.style.linestyle.width = 4
            except KeyError as e:
                logger.warning(f"Dados ausentes para desenhar setor '{pivo_data.get('nome')}': {e}. Pulando.")
        if ciclos:
            for ciclo_data in ciclos:
                coords = ciclo_data.get("coordenadas")
                if coords and len(coords) > 2:
                    nome_area = ciclo_data.get("nome_original_circulo", "Área").replace("Ciclo", "Área")
                    pol = f_areas.newpolygon(name=nome_area)
                    pol.outerboundaryis = [(lon, lat, 0) for lat, lon in coords]
                    pol.style.polystyle.fill = 0
                    pol.style.linestyle.color = simplekml.Color.red
                    pol.style.linestyle.width = 4

    if bombas:
        f_bombas = doc.newfolder(name="Bombas")
        for i, b_data in enumerate(bombas): f_bombas.newpoint(name=b_data.get("nome", f"Bomba {i+1}"), coords=[(b_data["lon"], b_data["lat"])]).style = style

def build_kml_document_and_get_image_list(doc, pivos_data, ciclos_data, bombas_data, repetidoras_selecionadas_data, generated_images_dir, selected_template, antena_data, imagem_principal_nome_relativo, bounds_principal_data) -> List[Tuple[Path, str]]:
    logger.info("Iniciando construção da estrutura KML.")
    torre_style, default_point_style = _create_kml_styles()
    
    key_desc_name = f"{selected_template.col}.key.png"
    key_overlay_name = f"{selected_template.col}.overlay.png"
    original_legend, overlay_legend = settings.IMAGENS_DIR_PATH/key_desc_name, settings.IMAGENS_DIR_PATH/key_overlay_name
    if original_legend.exists() and not overlay_legend.exists(): copyfile(original_legend, overlay_legend)
    
    files_for_kmz: List[Tuple[Path, str]] = []
    ts = datetime.now().strftime('%m%d%H%M%S')

    # ✅ 1. Definir as propriedades da legenda de cores EM UM SÓ LUGAR
    # Usar x=-1 e y=-1 diz ao Google Earth para usar o tamanho original da imagem.
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

        folder = _setup_main_antenna_structure(doc, antena_data, torre_style, sub_nome, selected_template, file_id, key_desc_name)
        
        ground = folder.newgroundoverlay(name=f"Cobertura {selected_template.frq}MHz"); ground.icon.href = imagem_principal_nome_relativo
        b = bounds_principal_data; ground.latlonbox.north, ground.latlonbox.south, ground.latlonbox.east, ground.latlonbox.west = b[2], b[0], b[3], b[1]
        files_for_kmz.append((generated_images_dir / imagem_principal_nome_relativo, imagem_principal_nome_relativo))
        
        # ✅ 2. Usa as propriedades padronizadas
        screen = folder.newscreenoverlay(name=COLOUR_KEY_KML_NAME)
        screen.icon.href = key_overlay_name
        screen.overlayxy = simplekml.OverlayXY(**OVERLAY_PROPS['overlay_xy'])
        screen.screenxy = simplekml.ScreenXY(**OVERLAY_PROPS['screen_xy'])
        screen.size = simplekml.Size(**OVERLAY_PROPS['size']) # Aplica o tamanho aqui

    # ✅ 3. Passa as propriedades padronizadas para a função das repetidoras
    repeater_files = _add_repeaters(
        doc, repetidoras_selecionadas_data, torre_style, generated_images_dir,
        overlay_name=key_overlay_name, desc_name=key_desc_name,
        template=selected_template, ts_prefix=ts, overlay_props=OVERLAY_PROPS
    )
    files_for_kmz.extend(repeater_files)
    
    _add_secondary_folders(doc, pivos_data, ciclos_data, bombas_data, default_point_style)

    common_files = [(TORRE_ICON_NAME, TORRE_ICON_NAME), (key_desc_name, key_desc_name), (key_overlay_name, key_overlay_name), (LOGO_FILENAME, LOGO_FILENAME)]
    for fname, zip_name in common_files:
        fpath = settings.IMAGENS_DIR_PATH / fname
        if fpath.exists() and not any(item[1] == zip_name for item in files_for_kmz):
            files_for_kmz.append((fpath, zip_name))
            
    logger.info("Construção da estrutura KML concluída.")
    return files_for_kmz

def _generate_sector_coords(lat, lon, radius_m, bearing_deg, arc_width_deg, steps=40) -> list:
    coords = [(lon, lat, 0)]
    start_angle = bearing_deg - (arc_width_deg / 2)
    for i in range(steps + 1):
        angle = start_angle + (i * arc_width_deg / steps)
        dest = geodesic(meters=radius_m).destination(Point(lat, lon), angle)
        coords.append((dest.longitude, dest.latitude, 0))
    coords.append((lon, lat, 0))
    return coords