from fastapi import APIRouter, UploadFile, File, Query, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import zipfile
import json
import simplekml
from datetime import datetime
from pathlib import Path
import logging
import shutil
import re

from backend.services import kmz_parser
from backend.config import settings

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

router = APIRouter(
    prefix="/kmz",
    tags=["KMZ Operations"],
)

_INPUT_KMZ_DIR: Path = settings.ARQUIVOS_DIR_PATH
_GENERATED_IMAGES_DIR: Path = settings.IMAGENS_DIR_PATH
_INPUT_KMZ_FILENAME = "entrada.kmz"
INPUT_KMZ_PATH: Path = _INPUT_KMZ_DIR / _INPUT_KMZ_FILENAME
TORRE_ICON_NAME = "cloudrf.png"
DEFAULT_ICON_URL = "http://maps.google.com/mapfiles/kml/pushpin/ylw-pushpin.png"
COLOUR_KEY_FILENAME = "IRRICONTRO.dBm.key.png" # Nome do arquivo da legenda
COLOUR_KEY_KML_NAME = "Colour Key - dBm"    # Nome da legenda no KML
DETAILS_SUBFOLDER_NAME = "Detalhes da Cobertura" # Nome da subpasta

def _create_kml_styles() -> tuple[simplekml.Style, simplekml.Style, simplekml.Style]:
    """Cria e retorna os estilos KML para os pontos da torre e repetidora."""
    torre_style = simplekml.Style()
    torre_style.iconstyle.icon.href = TORRE_ICON_NAME
    torre_style.iconstyle.scale = 1.2
    torre_style.labelstyle.scale = 1.1

    default_point_style = simplekml.Style() # Para pivos e bombas
    default_point_style.iconstyle.icon.href = DEFAULT_ICON_URL
    default_point_style.iconstyle.scale = 1.0
    default_point_style.labelstyle.scale = 1.0

    repetidora_style = simplekml.Style()
    repetidora_style.iconstyle.icon.href = TORRE_ICON_NAME # Mesmo ícone da torre para pontos de repetidora
    repetidora_style.iconstyle.scale = 1.1
    repetidora_style.labelstyle.scale = 1.0

    return torre_style, default_point_style, repetidora_style

def _setup_main_antenna_structure(
    doc: simplekml.Document,
    antena: dict,
    torre_style: simplekml.Style
) -> simplekml.Folder: # Retorna a subpasta de detalhes
    """Cria a pasta principal da antena, a subpasta de detalhes e adiciona o ponto da antena."""
    antena_nome = antena.get("nome", "Antena Principal")
    
    folder_antena_main = doc.newfolder(name=antena_nome) # Ícone de pasta padrão
    
    subfolder_details = folder_antena_main.newfolder(name=DETAILS_SUBFOLDER_NAME) # Ícone de pasta padrão
    
    pnt_antena = subfolder_details.newpoint(name=antena_nome, coords=[(antena["lon"], antena["lat"])])
    pnt_antena.description = f"Altura: {antena.get('altura', 'N/A')}m"
    pnt_antena.style = torre_style
    logger.info(f" -> Estrutura de pastas para '{antena_nome}' (com ponto) criada.")
    return subfolder_details

def _add_overlays_and_repeater_structures(
    doc: simplekml.Document, # Documento KML principal para adicionar pastas de repetidoras
    main_antenna_details_subfolder: simplekml.Folder,
    imagem_principal_nome_kmz: str, 
    bounds_principal_data: list,
    repetidora_style: simplekml.Style # Para os pontos das repetidoras
) -> list[tuple[Path, str]]:
    """Adiciona overlays à subpasta da antena principal e cria a estrutura completa para repetidoras."""
    arquivos_a_adicionar_ao_kmz = []

    # Adiciona overlay principal à subpasta da antena
    ground_main = main_antenna_details_subfolder.newgroundoverlay(name="Cobertura Principal")
    ground_main.icon.href = imagem_principal_nome_kmz
    b = bounds_principal_data
    ground_main.latlonbox.north, ground_main.latlonbox.south = b[2], b[0]
    ground_main.latlonbox.east, ground_main.latlonbox.west = b[3], b[1]
    ground_main.color = "ffffffff"
    arquivos_a_adicionar_ao_kmz.append((_GENERATED_IMAGES_DIR / imagem_principal_nome_kmz, imagem_principal_nome_kmz))

    # Adiciona ScreenOverlay da legenda à subpasta da antena
    screen_main = main_antenna_details_subfolder.newscreenoverlay(name=COLOUR_KEY_KML_NAME)
    screen_main.icon.href = COLOUR_KEY_FILENAME
    screen_main.overlayxy = simplekml.OverlayXY(x=0, y=1, xunits=simplekml.Units.fraction, yunits=simplekml.Units.fraction)
    screen_main.screenxy = simplekml.ScreenXY(x=0, y=1, xunits=simplekml.Units.fraction, yunits=simplekml.Units.fraction)
    screen_main.size = simplekml.Size(x=0, y=0, xunits=simplekml.Units.fraction, yunits=simplekml.Units.fraction) # Tamanho original
    
    path_colour_key = _GENERATED_IMAGES_DIR / COLOUR_KEY_FILENAME
    if path_colour_key.exists():
        # Adiciona apenas uma vez à lista, mesmo se usado em múltiplas repetidoras
        if not any(item[1] == COLOUR_KEY_FILENAME for item in arquivos_a_adicionar_ao_kmz):
            arquivos_a_adicionar_ao_kmz.append((path_colour_key, COLOUR_KEY_FILENAME))
    else:
        logger.warning(f"Arquivo da legenda '{COLOUR_KEY_FILENAME}' não encontrado em {_GENERATED_IMAGES_DIR}.")
    logger.info(f" -> Overlays para antena principal adicionados à sua subpasta de detalhes.")

    # Estrutura para Repetidoras
    logger.info(" -> Adicionando estruturas de repetidoras...")
    repeater_counter = 1
    for item_path in _GENERATED_IMAGES_DIR.iterdir():
        if item_path.name.startswith("repetidora_") and item_path.suffix == ".png":
            img_rep_path_servidor = item_path
            json_rep_path_servidor = img_rep_path_servidor.with_suffix(".json")

            if json_rep_path_servidor.exists():
                with open(json_rep_path_servidor, "r") as f_json:
                    bounds_rep_data = json.load(f_json).get("bounds")

                if bounds_rep_data:
                    custom_repeater_name = f"Repetidora Solar {repeater_counter}"
                    
                    folder_rep_main = doc.newfolder(name=custom_repeater_name) # Pasta principal da repetidora
                    subfolder_rep_details = folder_rep_main.newfolder(name=DETAILS_SUBFOLDER_NAME) # Subpasta de detalhes

                    # Ponto da Repetidora na subpasta de detalhes
                    center_lat = (bounds_rep_data[0] + bounds_rep_data[2]) / 2
                    center_lon = (bounds_rep_data[1] + bounds_rep_data[3]) / 2
                    pnt_rep = subfolder_rep_details.newpoint(name=custom_repeater_name, coords=[(center_lon, center_lat)])
                    pnt_rep.style = repetidora_style

                    # GroundOverlay da Repetidora na subpasta de detalhes
                    ground_rep = subfolder_rep_details.newgroundoverlay(name=f"Cobertura {custom_repeater_name}")
                    ground_rep.icon.href = img_rep_path_servidor.name
                    br = bounds_rep_data
                    ground_rep.latlonbox.north, ground_rep.latlonbox.south = br[2], br[0]
                    ground_rep.latlonbox.east, ground_rep.latlonbox.west = br[3], br[1]
                    ground_rep.color = "ffffffff"
                    arquivos_a_adicionar_ao_kmz.append((img_rep_path_servidor, img_rep_path_servidor.name))

                    # ScreenOverlay da legenda na subpasta de detalhes da repetidora
                    screen_rep = subfolder_rep_details.newscreenoverlay(name=COLOUR_KEY_KML_NAME)
                    screen_rep.icon.href = COLOUR_KEY_FILENAME
                    screen_rep.overlayxy = simplekml.OverlayXY(x=0, y=1, xunits=simplekml.Units.fraction, yunits=simplekml.Units.fraction)
                    screen_rep.screenxy = simplekml.ScreenXY(x=0, y=1, xunits=simplekml.Units.fraction, yunits=simplekml.Units.fraction)
                    screen_rep.size = simplekml.Size(x=0, y=0, xunits=simplekml.Units.fraction, yunits=simplekml.Units.fraction)
                    
                    logger.info(f"     -> Estrutura completa para '{custom_repeater_name}' adicionada.")
                    repeater_counter += 1
    return arquivos_a_adicionar_ao_kmz

def _add_secondary_folders(
    doc: simplekml.Document,
    pivos: list, ciclos: list, bombas: list,
    default_point_style: simplekml.Style
):
    """Adiciona pastas de pivôs, ciclos e bombas ao documento KML."""
    if pivos:
        folder_pivos = doc.newfolder(name="Pivôs") # Ícone de pasta padrão
        for i, p_data in enumerate(pivos):
            pivo_nome = p_data.get("nome", f"Pivo {i+1}")
            pnt_pivo = folder_pivos.newpoint(name=pivo_nome, coords=[(p_data["lon"], p_data["lat"])])
            pnt_pivo.style = default_point_style
        logger.info(" -> Pasta 'Pivôs' criada.")

    if ciclos:
        folder_ciclos = doc.newfolder(name="Ciclos") # Ícone de pasta padrão
        for i, ciclo_data in enumerate(ciclos):
            ciclo_nome = ciclo_data.get("nome", f"Ciclo {i+1}")
            pol = folder_ciclos.newpolygon(name=ciclo_nome)
            pol.outerboundaryis = [(lon, lat) for lat, lon in ciclo_data["coordenadas"]]
            pol.style.polystyle.fill = 0
            pol.style.linestyle.color = simplekml.Color.red
            pol.style.linestyle.width = 4
        logger.info(" -> Pasta 'Ciclos' criada.")

    if bombas:
        folder_bombas = doc.newfolder(name="Bombas") # Ícone de pasta padrão
        for i, bomba_data in enumerate(bombas):
            bomba_nome = bomba_data.get("nome", f"Bomba {i+1}")
            pnt_bomba = folder_bombas.newpoint(name=bomba_nome, coords=[(bomba_data["lon"], bomba_data["lat"])])
            pnt_bomba.style = default_point_style
        logger.info(" -> Pasta 'Bombas' criada.")

# --- Endpoints ---
@router.post("/processar")
# ... (código do endpoint /processar permanece o mesmo) ...
async def processar_kmz_endpoint(file: UploadFile = File(...)):
    try:
        logger.info("📥 Recebendo arquivo KMZ...")
        conteudo = await file.read()
        with open(INPUT_KMZ_PATH, "wb") as f:
            f.write(conteudo)
        logger.info(f"  -> KMZ salvo em: {INPUT_KMZ_PATH}")
        antena, pivos, ciclos, bombas = kmz_parser.parse_kmz(str(INPUT_KMZ_PATH), str(_INPUT_KMZ_DIR))
        if not antena:
            raise HTTPException(status_code=404, detail="Antena principal (torre, barracão, etc.) não encontrada no KMZ.")
        return {"antena": antena, "pivos": pivos, "ciclos": ciclos, "bombas": bombas}
    except ValueError as ve:
        logger.error(f"❌ Erro de Validação KMZ: {ve}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"❌ Erro Interno em /kmz/processar: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro interno ao processar KMZ: {type(e).__name__} - {str(e)}")


@router.get("/exportar")
async def exportar_kmz_endpoint(
    background_tasks: BackgroundTasks,
    imagem: str = Query(..., description="Nome da imagem PNG principal (ex: 'cobertura_principal.png')."),
    bounds_file: str = Query(..., description="Nome do JSON de bounds principal (ex: 'cobertura_principal.json').")
):
    logger.info("📦 Iniciando exportação KMZ...")
    if not INPUT_KMZ_PATH.exists():
        raise HTTPException(status_code=400, detail=f"Nenhum KMZ foi processado ainda ({_INPUT_KMZ_FILENAME}). Faça o upload primeiro.")
    caminho_imagem_principal_servidor = _GENERATED_IMAGES_DIR / imagem
    caminho_bounds_principal_servidor = _GENERATED_IMAGES_DIR / bounds_file
    if not caminho_imagem_principal_servidor.exists():
        raise HTTPException(status_code=404, detail=f"Imagem principal '{imagem}' não encontrada em {_GENERATED_IMAGES_DIR}.")
    if not caminho_bounds_principal_servidor.exists():
        raise HTTPException(status_code=404, detail=f"Bounds '{bounds_file}' não encontrados em {_GENERATED_IMAGES_DIR}.")

    try:
        antena, pivos, ciclos, bombas = kmz_parser.parse_kmz(str(INPUT_KMZ_PATH), str(_INPUT_KMZ_DIR))
        with open(caminho_bounds_principal_servidor, "r") as f:
            bounds_principal = json.load(f).get("bounds")
        if not antena or not bounds_principal:
            logger.warning("⚠️ Dados incompletos para exportar. Antena ou bounds_principal ausentes.")
            raise HTTPException(status_code=500, detail="Dados essenciais (antena, bounds_principal) ausentes para exportar.")

        kml = simplekml.Kml(name="Estudo de Sinal Irricontrol") # Nome do documento KML
        doc = kml.document

        torre_style, default_point_style, repetidora_style = _create_kml_styles()

        # 1. Configura a estrutura da antena principal (pasta principal, subpasta de detalhes, ponto)
        main_antenna_details_subfolder = _setup_main_antenna_structure(
            doc,
            antena,
            torre_style
        )
        
        # 2. Adiciona overlays à antena principal e cria estruturas completas para repetidoras
        arquivos_de_imagem_para_kmz = _add_overlays_and_repeater_structures(
            doc, # Documento KML principal
            main_antenna_details_subfolder,
            imagem, # Nome do arquivo da imagem principal
            bounds_principal,
            repetidora_style
        )

        # 3. Adiciona as demais pastas (Pivôs, Ciclos, Bombas)
        _add_secondary_folders(
            doc,
            pivos,
            ciclos,
            bombas,
            default_point_style
        )

        caminho_kml_temp = _INPUT_KMZ_DIR / "estudo_temp.kml"
        kml.save(str(caminho_kml_temp))
        logger.info(f"  -> KML temporário salvo em: {caminho_kml_temp}")

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        nome_kmz_final = f"estudo-irricontrol-{timestamp}.kmz"
        caminho_kmz_final_servidor = _INPUT_KMZ_DIR / nome_kmz_final

        logger.info(f"  -> Criando KMZ final: {caminho_kmz_final_servidor}")
        with zipfile.ZipFile(str(caminho_kmz_final_servidor), "w", zipfile.ZIP_DEFLATED) as kmz_zip:
            kmz_zip.write(str(caminho_kml_temp), "doc.kml")
            
            # Adiciona o ícone da torre/repetidora ao KMZ (usado pelos pontos)
            caminho_icone_torre_servidor = _GENERATED_IMAGES_DIR / TORRE_ICON_NAME
            if caminho_icone_torre_servidor.exists():
                # Adiciona apenas uma vez, mesmo se usado por múltiplos estilos
                if not any(item[1] == TORRE_ICON_NAME for item in arquivos_de_imagem_para_kmz):
                     arquivos_a_adicionar_ao_kmz.append((caminho_icone_torre_servidor, TORRE_ICON_NAME))
                logger.info(f"      -> Ícone '{TORRE_ICON_NAME}' preparado para o KMZ.")
            else:
                logger.warning(f"      -> ⚠️ ATENÇÃO: Ícone da torre '{TORRE_ICON_NAME}' não encontrado em {caminho_icone_torre_servidor}.")

            # Adicionar todas as imagens necessárias (overlays, legenda, ícone da torre)
            # A lista agora é construída em _add_overlays_and_repeater_structures e acima para TORRE_ICON_NAME
            added_to_zip = set() # Para evitar adicionar o mesmo arquivo (ex: legenda) múltiplas vezes
            for path_origem_img_servidor, nome_destino_img_kmz in arquivos_a_adicionar_ao_kmz:
                if nome_destino_img_kmz not in added_to_zip:
                    if path_origem_img_servidor.exists():
                        kmz_zip.write(str(path_origem_img_servidor), nome_destino_img_kmz)
                        added_to_zip.add(nome_destino_img_kmz)
                        logger.info(f"      -> Arquivo '{nome_destino_img_kmz}' adicionado ao KMZ.")
                    else:
                        logger.warning(f"      -> ⚠️ Imagem '{path_origem_img_servidor}' não encontrada, não adicionada ao KMZ.")
        
        background_tasks.add_task(Path.unlink, caminho_kml_temp, missing_ok=True)
        logger.info("  -> Exportação KMZ concluída.")
        return FileResponse(
            str(caminho_kmz_final_servidor),
            media_type="application/vnd.google-earth.kmz",
            filename=nome_kmz_final,
            background=background_tasks
        )
    except FileNotFoundError as fnfe:
        logger.error(f"❌ Arquivo não encontrado durante a exportação: {fnfe}", exc_info=True)
        raise HTTPException(status_code=404, detail=f"Arquivo necessário não encontrado: {fnfe.filename}")
    except Exception as e:
        logger.error(f"❌ Erro Interno em /kmz/exportar: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro ao exportar KMZ: {type(e).__name__} - {str(e)}")

@router.get("/icone-torre")
# ... (código do endpoint /icone-torre permanece o mesmo) ...
async def get_icone_torre():
    caminho_icone = _GENERATED_IMAGES_DIR / TORRE_ICON_NAME
    if caminho_icone.is_file():
        return FileResponse(str(caminho_icone), media_type="image/png")
    logger.warning(f"Ícone da torre não encontrado em: {caminho_icone}")
    raise HTTPException(status_code=404, detail=f"Ícone '{TORRE_ICON_NAME}' não encontrado.")