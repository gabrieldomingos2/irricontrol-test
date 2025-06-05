import simplekml
from pathlib import Path
import logging
import json

logger = logging.getLogger(__name__)

# Constantes intrínsecas à estrutura KML gerada por este exporter
DETAILS_SUBFOLDER_NAME = "Detalhes da Cobertura"
COLOUR_KEY_KML_NAME = "Colour Key - dBm"

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

def _setup_main_antenna_structure(
    doc: simplekml.Document,
    antena: dict,
    torre_style: simplekml.Style
) -> simplekml.Folder:
    """Cria a pasta principal da antena, a subpasta de detalhes e adiciona o ponto da antena."""
    antena_nome = antena.get("nome", "Antena Principal")
    folder_antena_main = doc.newfolder(name=antena_nome)
    subfolder_details = folder_antena_main.newfolder(name=DETAILS_SUBFOLDER_NAME)
    
    pnt_antena = subfolder_details.newpoint(name=antena_nome, coords=[(antena["lon"], antena["lat"])])
    pnt_antena.description = f"Altura: {antena.get('altura', 'N/A')}m"
    pnt_antena.style = torre_style
    logger.info(f" -> Estrutura de pastas para '{antena_nome}' (com ponto) criada em kmz_exporter.")
    return subfolder_details

def _add_overlays_and_repeater_structures(
    doc: simplekml.Document,
    main_antenna_details_subfolder: simplekml.Folder,
    imagem_principal_nome_kmz: str,
    bounds_principal_data: list,
    repetidora_style: simplekml.Style,
    generated_images_dir: Path, # Diretório onde as imagens (incluindo legenda) estão
    colour_key_filename: str   # Nome do arquivo da legenda
) -> list[tuple[Path, str]]:
    """Adiciona overlays à subpasta da antena principal e cria a estrutura completa para repetidoras."""
    arquivos_a_adicionar_ao_kmz = []

    ground_main = main_antenna_details_subfolder.newgroundoverlay(name="Cobertura Principal")
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
    
    path_colour_key = generated_images_dir / colour_key_filename
    if path_colour_key.exists():
        if not any(item[1] == colour_key_filename for item in arquivos_a_adicionar_ao_kmz):
            arquivos_a_adicionar_ao_kmz.append((path_colour_key, colour_key_filename))
    else:
        logger.warning(f"Arquivo da legenda '{colour_key_filename}' não encontrado em {generated_images_dir} (verificado por kmz_exporter).")
    logger.info(f" -> Overlays para antena principal adicionados à sua subpasta de detalhes em kmz_exporter.")

    logger.info(" -> Adicionando estruturas de repetidoras em kmz_exporter...")
    repeater_counter = 1
    for item_path in generated_images_dir.iterdir():
        if item_path.name.startswith("repetidora_") and item_path.suffix == ".png":
            img_rep_path_servidor = item_path
            json_rep_path_servidor = img_rep_path_servidor.with_suffix(".json")

            if json_rep_path_servidor.exists():
                with open(json_rep_path_servidor, "r") as f_json:
                    bounds_rep_data = json.load(f_json).get("bounds")

                if bounds_rep_data:
                    custom_repeater_name = f"Repetidora Solar {repeater_counter}"
                    folder_rep_main = doc.newfolder(name=custom_repeater_name)
                    subfolder_rep_details = folder_rep_main.newfolder(name=DETAILS_SUBFOLDER_NAME)

                    center_lat = (bounds_rep_data[0] + bounds_rep_data[2]) / 2
                    center_lon = (bounds_rep_data[1] + bounds_rep_data[3]) / 2
                    pnt_rep = subfolder_rep_details.newpoint(name=custom_repeater_name, coords=[(center_lon, center_lat)])
                    pnt_rep.style = repetidora_style

                    ground_rep = subfolder_rep_details.newgroundoverlay(name=f"Cobertura {custom_repeater_name}")
                    ground_rep.icon.href = img_rep_path_servidor.name
                    br = bounds_rep_data
                    ground_rep.latlonbox.north, ground_rep.latlonbox.south = br[2], br[0]
                    ground_rep.latlonbox.east, ground_rep.latlonbox.west = br[3], br[1]
                    ground_rep.color = "ffffffff"
                    arquivos_a_adicionar_ao_kmz.append((img_rep_path_servidor, img_rep_path_servidor.name))

                    screen_rep = subfolder_rep_details.newscreenoverlay(name=COLOUR_KEY_KML_NAME)
                    screen_rep.icon.href = colour_key_filename
                    screen_rep.overlayxy = simplekml.OverlayXY(x=0, y=1, xunits=simplekml.Units.fraction, yunits=simplekml.Units.fraction)
                    screen_rep.screenxy = simplekml.ScreenXY(x=0, y=1, xunits=simplekml.Units.fraction, yunits=simplekml.Units.fraction)
                    screen_rep.size = simplekml.Size(x=0, y=0, xunits=simplekml.Units.fraction, yunits=simplekml.Units.fraction)
                    
                    logger.info(f"     -> Estrutura completa para '{custom_repeater_name}' adicionada em kmz_exporter.")
                    repeater_counter += 1
    return arquivos_a_adicionar_ao_kmz

def _add_secondary_folders(
    doc: simplekml.Document,
    pivos: list, ciclos: list, bombas: list,
    default_point_style: simplekml.Style
):
    """Adiciona pastas de pivôs, ciclos e bombas ao documento KML."""
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
            ciclo_nome = ciclo_data.get("nome", f"Ciclo {i+1}")
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


# Função principal orquestradora neste módulo de serviço
def build_kml_document_and_get_image_list(
    doc: simplekml.Document,
    antena_data: dict,
    pivos_data: list,
    ciclos_data: list,
    bombas_data: list,
    imagem_principal_nome_relativo: str, # Ex: 'cobertura_principal.png'
    bounds_principal_data: list,
    generated_images_dir: Path, # Ex: settings.IMAGENS_DIR_PATH
    torre_icon_name: str,       # Ex: "cloudrf.png"
    default_icon_url: str,    # Ex: "http://..."
    colour_key_filename: str   # Ex: "IRRICONTRO.dBm.key.png"
) -> list[tuple[Path, str]]:
    """
    Constrói a estrutura do documento KML e retorna a lista de arquivos de imagem para o KMZ.
    """
    logger.info("Iniciando construção da estrutura KML em kmz_exporter.")
    torre_style, default_point_style, repetidora_style = _create_kml_styles(
        torre_icon_name, default_icon_url
    )

    main_antenna_details_subfolder = _setup_main_antenna_structure(
        doc,
        antena_data,
        torre_style
    )
    
    # Esta lista conterá os overlays e a legenda.
    image_files_for_kmz = _add_overlays_and_repeater_structures(
        doc, 
        main_antenna_details_subfolder,
        imagem_principal_nome_relativo, 
        bounds_principal_data,
        repetidora_style,
        generated_images_dir,
        colour_key_filename
    )

    _add_secondary_folders(
        doc,
        pivos_data,
        ciclos_data,
        bombas_data,
        default_point_style
    )

    # Adiciona o ícone da torre/repetidora à lista se ele existir e não estiver já lá
    # (embora não seja usado por overlays, é referenciado por estilos)
    path_torre_icon = generated_images_dir / torre_icon_name
    if path_torre_icon.exists():
        if not any(item[1] == torre_icon_name for item in image_files_for_kmz):
            image_files_for_kmz.append((path_torre_icon, torre_icon_name))
            logger.info(f" -> Ícone '{torre_icon_name}' adicionado à lista de arquivos para KMZ por kmz_exporter.")

    logger.info("Construção da estrutura KML concluída em kmz_exporter.")
    return image_files_for_kmz