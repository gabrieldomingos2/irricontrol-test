from fastapi import APIRouter, UploadFile, File, Query, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import zipfile
import json
import simplekml # Mantido, pois é a biblioteca principal para KML
from datetime import datetime
from pathlib import Path # Adicionado para manipulação moderna de caminhos
import logging # Adicionado para logging
import shutil # Para operações de arquivo como mover (se necessário) ou remover árvore
import re # Adicionado para flexibilidade em futuras lógicas de nomeação

# Usa imports absolutos
from backend.services import kmz_parser
from backend.config import settings # Importando o objeto settings

# Configuração do Logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO) # Configuração básica, pode ser mais elaborada

router = APIRouter(
    prefix="/kmz", # Mantido o prefixo original
    tags=["KMZ Operations"],
)

# --- Constantes e Caminhos Derivados das Configurações ---
_INPUT_KMZ_DIR: Path = settings.ARQUIVOS_DIR_PATH
_GENERATED_IMAGES_DIR: Path = settings.IMAGENS_DIR_PATH
_INPUT_KMZ_FILENAME = "entrada.kmz"
INPUT_KMZ_PATH: Path = _INPUT_KMZ_DIR / _INPUT_KMZ_FILENAME
TORRE_ICON_NAME = "cloudrf.png" # Nome do arquivo do ícone
DEFAULT_ICON_URL = "http://maps.google.com/mapfiles/kml/pushpin/ylw-pushpin.png" # URL para ícone padrão

# --- Funções Auxiliares para /exportar (para melhor organização) ---

def _create_kml_styles() -> tuple[simplekml.Style, simplekml.Style, simplekml.Style, simplekml.Style]:
    """Cria e retorna os estilos KML para torre, ponto padrão, repetidora e ícone de pasta."""
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

    # Estilo para o ícone das Pastas
    folder_icon_style = simplekml.Style()

    # Para alterar o ícone da pasta na lista de "Lugares" (árvore),
    # usamos ListStyle e adicionamos um ItemIcon.
    folder_icon_style.liststyle.add_itemicon(href=TORRE_ICON_NAME)
    # Nota: A propriedade 'scale' de 'iconstyle' não afeta diretamente o tamanho
    # do ícone em 'liststyle'. O ícone (cloudrf.png) será exibido
    # em seu tamanho original ou em um tamanho padrão para ícones de lista do Google Earth.
    # Se o ícone 'cloudrf.png' parecer muito grande ou pequeno como ícone de pasta,
    # você pode precisar de uma versão da imagem com tamanho ajustado especificamente para isso.

    # Manter um IconStyle geral para a pasta pode ser útil para outros contextos
    # ou como fallback, mas ListStyle é o principal para o ícone na lista.
    folder_icon_style.iconstyle.icon.href = TORRE_ICON_NAME # Fallback/geral
    folder_icon_style.iconstyle.scale = 1.0 # Escala para o IconStyle (não para o ListStyle)

    return torre_style, default_point_style, repetidora_style, folder_icon_style

def _add_placemarks_to_kml_folders(
    doc: simplekml.Document,
    antena: dict, pivos: list, ciclos: list, bombas: list,
    torre_style: simplekml.Style, default_point_style: simplekml.Style,
    folder_icon_style: simplekml.Style
):
    """Adiciona antena, pivôs, ciclos e bombas ao documento KML em suas respectivas pastas."""
    antena_nome = antena.get("nome", "Antena Principal")
    folder_torre = doc.newfolder(name=antena_nome)
    folder_torre.style = folder_icon_style
    pnt_antena = folder_torre.newpoint(name=antena_nome, coords=[(antena["lon"], antena["lat"])])
    pnt_antena.description = f"Altura: {antena.get('altura', 'N/A')}m"
    pnt_antena.style = torre_style
    logger.info(f" -> Pasta '{antena_nome}' (ponto e ícone de pasta) criada.")

    if pivos:
        folder_pivos = doc.newfolder(name="Pivôs")
        # folder_pivos.style = folder_icon_style # Descomente se quiser o ícone customizado para esta pasta
        for i, p_data in enumerate(pivos):
            pivo_nome = p_data.get("nome", f"Pivo {i+1}")
            pnt_pivo = folder_pivos.newpoint(name=pivo_nome, coords=[(p_data["lon"], p_data["lat"])])
            pnt_pivo.style = default_point_style
        logger.info(" -> Pasta 'Pivôs' criada.")

    if ciclos:
        folder_ciclos = doc.newfolder(name="Ciclos")
        # folder_ciclos.style = folder_icon_style # Descomente se quiser o ícone customizado para esta pasta
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
        # folder_bombas.style = folder_icon_style # Descomente se quiser o ícone customizado para esta pasta
        for i, bomba_data in enumerate(bombas):
            bomba_nome = bomba_data.get("nome", f"Bomba {i+1}")
            pnt_bomba = folder_bombas.newpoint(name=bomba_nome, coords=[(bomba_data["lon"], bomba_data["lat"])])
            pnt_bomba.style = default_point_style
        logger.info(" -> Pasta 'Bombas' criada.")

def _add_ground_overlays_to_kml(
    doc: simplekml.Document,
    antena_nome_principal: str,
    imagem_principal_nome_kmz: str, bounds_principal_data: list,
    repetidora_style: simplekml.Style,
    folder_icon_style: simplekml.Style
) -> list[tuple[Path, str]]:
    """Adiciona overlays de solo (principal e repetidoras) ao KML e retorna lista de arquivos de imagem."""
    arquivos_a_adicionar_ao_kmz = []

    folder_torre = next((f for f in doc.features if isinstance(f, simplekml.Folder) and f.name == antena_nome_principal), None)
    if not folder_torre:
        folder_torre = doc.newfolder(name=antena_nome_principal)
        folder_torre.style = folder_icon_style # Aplica estilo se a pasta for recriada aqui
        logger.warning(f"Pasta da torre principal '{antena_nome_principal}' não encontrada, criando nova para overlay.")

    ground_main = folder_torre.newgroundoverlay(name="Cobertura Principal")
    ground_main.icon.href = imagem_principal_nome_kmz
    b = bounds_principal_data
    ground_main.latlonbox.north, ground_main.latlonbox.south = b[2], b[0]
    ground_main.latlonbox.east, ground_main.latlonbox.west = b[3], b[1]
    ground_main.color = "ffffffff"
    arquivos_a_adicionar_ao_kmz.append((_GENERATED_IMAGES_DIR / imagem_principal_nome_kmz, imagem_principal_nome_kmz))
    logger.info(f" -> Overlay 'Cobertura Principal' adicionado à pasta '{antena_nome_principal}'.")

    logger.info(" -> Adicionando repetidoras em pastas individuais...")
    repeater_counter = 1
    for item_path in _GENERATED_IMAGES_DIR.iterdir():
        if item_path.name.startswith("repetidora_") and item_path.suffix == ".png":
            img_rep_path_servidor = item_path
            json_rep_path_servidor = img_rep_path_servidor.with_suffix(".json")

            if json_rep_path_servidor.exists():
                with open(json_rep_path_servidor, "r") as f:
                    bounds_rep_data = json.load(f).get("bounds")

                if bounds_rep_data:
                    custom_repeater_name = f"Repetidora Solar {repeater_counter}"
                    folder_rep = doc.newfolder(name=custom_repeater_name)
                    folder_rep.style = folder_icon_style # APLICA ESTILO À PASTA DA REPETIDORA

                    ground_rep = folder_rep.newgroundoverlay(name=f"Cobertura {custom_repeater_name}")
                    ground_rep.icon.href = img_rep_path_servidor.name
                    br = bounds_rep_data
                    ground_rep.latlonbox.north, ground_rep.latlonbox.south = br[2], br[0]
                    ground_rep.latlonbox.east, ground_rep.latlonbox.west = br[3], br[1]
                    ground_rep.color = "ffffffff"
                    arquivos_a_adicionar_ao_kmz.append((img_rep_path_servidor, img_rep_path_servidor.name))

                    center_lat = (br[0] + br[2]) / 2
                    center_lon = (br[1] + br[3]) / 2
                    pnt_rep = folder_rep.newpoint(name=custom_repeater_name, coords=[(center_lon, center_lat)])
                    pnt_rep.style = repetidora_style
                    logger.info(f"     -> Pasta '{custom_repeater_name}' (ponto, overlay e ícone de pasta) adicionada.")
                    
                    repeater_counter += 1
    return arquivos_a_adicionar_ao_kmz

# --- Endpoints ---

@router.post("/processar")
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

        kml = simplekml.Kml(name="Estudo de Sinal Irricontrol")
        doc = kml.document

        torre_style, default_point_style, repetidora_style, folder_icon_style = _create_kml_styles()

        _add_placemarks_to_kml_folders(doc, antena, pivos, ciclos, bombas, torre_style, default_point_style, folder_icon_style)
        
        arquivos_de_imagem_para_kmz = _add_ground_overlays_to_kml(
            doc,
            antena_nome_principal=antena.get("nome", "Antena Principal"),
            imagem_principal_nome_kmz=imagem,
            bounds_principal_data=bounds_principal,
            repetidora_style=repetidora_style,
            folder_icon_style=folder_icon_style
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
            caminho_icone_torre_servidor = _GENERATED_IMAGES_DIR / TORRE_ICON_NAME
            if caminho_icone_torre_servidor.exists():
                kmz_zip.write(str(caminho_icone_torre_servidor), TORRE_ICON_NAME)
                logger.info(f"      -> Ícone '{TORRE_ICON_NAME}' adicionado ao KMZ.")
            else:
                logger.warning(f"      -> ⚠️ ATENÇÃO: Ícone da torre '{TORRE_ICON_NAME}' não encontrado em {caminho_icone_torre_servidor}.")
            for path_origem_img_servidor, nome_destino_img_kmz in arquivos_de_imagem_para_kmz:
                if path_origem_img_servidor.exists():
                    kmz_zip.write(str(path_origem_img_servidor), nome_destino_img_kmz)
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
async def get_icone_torre():
    caminho_icone = _GENERATED_IMAGES_DIR / TORRE_ICON_NAME
    if caminho_icone.is_file():
        return FileResponse(str(caminho_icone), media_type="image/png")
    logger.warning(f"Ícone da torre não encontrado em: {caminho_icone}")
    raise HTTPException(status_code=404, detail=f"Ícone '{TORRE_ICON_NAME}' não encontrado.")