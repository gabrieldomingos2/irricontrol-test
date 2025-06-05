from fastapi import APIRouter, UploadFile, File, Query, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
# import os # Substituído por pathlib e não mais necessário diretamente em alguns casos
import zipfile
import json
import simplekml # Mantido, pois é a biblioteca principal para KML
from datetime import datetime
from pathlib import Path # Adicionado para manipulação moderna de caminhos
import logging # Adicionado para logging
import shutil # Para operações de arquivo como mover (se necessário) ou remover árvore

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
# Usando Path objects do settings
# Assume-se que ARQUIVOS_DIR_PATH e IMAGENS_DIR_PATH são Path objects em settings
# (conforme definido na revisão de config.py)
_INPUT_KMZ_DIR: Path = settings.ARQUIVOS_DIR_PATH
_GENERATED_IMAGES_DIR: Path = settings.IMAGENS_DIR_PATH

# Nome do arquivo KMZ de entrada.
# ATENÇÃO: Usar um nome fixo "entrada.kmz" implica que o sistema só pode
# processar um KMZ por vez globalmente. Isso pode ser uma limitação séria
# em ambientes com múltiplos usuários ou requisições concorrentes.
# Uma abordagem mais robusta seria usar nomes de arquivo únicos (ex: UUIDs)
# e gerenciar o estado de cada processamento.
# Para esta refatoração, manteremos a lógica de arquivo único, mas com esta ressalva.
_INPUT_KMZ_FILENAME = "entrada.kmz"
INPUT_KMZ_PATH: Path = _INPUT_KMZ_DIR / _INPUT_KMZ_FILENAME

TORRE_ICON_NAME = "cloudrf.png" # Nome do arquivo do ícone
DEFAULT_ICON_URL = "http://maps.google.com/mapfiles/kml/pushpin/ylw-pushpin.png" # URL para ícone padrão

# --- Funções Auxiliares para /exportar (para melhor organização) ---

def _create_kml_styles() -> tuple[simplekml.Style, simplekml.Style, simplekml.Style]:
    """Cria e retorna os estilos KML para torre, ponto padrão e repetidora."""
    torre_style = simplekml.Style()
    torre_style.iconstyle.icon.href = TORRE_ICON_NAME # Referência ao arquivo dentro do KMZ
    torre_style.iconstyle.scale = 1.2
    torre_style.labelstyle.scale = 1.1

    default_point_style = simplekml.Style()
    default_point_style.iconstyle.icon.href = DEFAULT_ICON_URL
    default_point_style.iconstyle.scale = 1.0
    default_point_style.labelstyle.scale = 1.0

    repetidora_style = simplekml.Style()
    repetidora_style.iconstyle.icon.href = TORRE_ICON_NAME # Referência ao arquivo dentro do KMZ
    repetidora_style.iconstyle.scale = 1.1
    repetidora_style.labelstyle.scale = 1.0
    return torre_style, default_point_style, repetidora_style

def _add_placemarks_to_kml_folders(
    doc: simplekml.Document,
    antena: dict, pivos: list, ciclos: list, bombas: list,
    torre_style: simplekml.Style, default_point_style: simplekml.Style
):
    """Adiciona antena, pivôs, ciclos e bombas ao documento KML em suas respectivas pastas."""
    # PASTA TORRE PRINCIPAL
    antena_nome = antena.get("nome", "Antena Principal")
    folder_torre = doc.newfolder(name=antena_nome)
    pnt_antena = folder_torre.newpoint(name=antena_nome, coords=[(antena["lon"], antena["lat"])])
    pnt_antena.description = f"Altura: {antena.get('altura', 'N/A')}m"
    pnt_antena.style = torre_style
    logger.info(f" -> Pasta '{antena_nome}' (ponto) criada.")

    # PASTA PIVÔS
    if pivos:
        folder_pivos = doc.newfolder(name="Pivôs")
        for i, p_data in enumerate(pivos):
            pivo_nome = p_data.get("nome", f"Pivo {i+1}")
            pnt_pivo = folder_pivos.newpoint(name=pivo_nome, coords=[(p_data["lon"], p_data["lat"])])
            pnt_pivo.style = default_point_style
        logger.info(" -> Pasta 'Pivôs' criada.")

    # PASTA CICLOS
    if ciclos:
        folder_ciclos = doc.newfolder(name="Ciclos")
        for i, ciclo_data in enumerate(ciclos):
            ciclo_nome = ciclo_data.get("nome", f"Ciclo {i+1}")
            pol = folder_ciclos.newpolygon(name=ciclo_nome)
            # Coordenadas KML são (lon, lat, opcional_alt)
            pol.outerboundaryis = [(lon, lat) for lat, lon in ciclo_data["coordenadas"]]
            pol.style.polystyle.fill = 0 # Transparente
            pol.style.linestyle.color = simplekml.Color.red
            pol.style.linestyle.width = 4
        logger.info(" -> Pasta 'Ciclos' criada.")

    # PASTA BOMBAS
    if bombas:
        folder_bombas = doc.newfolder(name="Bombas")
        for i, bomba_data in enumerate(bombas):
            bomba_nome = bomba_data.get("nome", f"Bomba {i+1}")
            pnt_bomba = folder_bombas.newpoint(name=bomba_nome, coords=[(bomba_data["lon"], bomba_data["lat"])])
            pnt_bomba.style = default_point_style
        logger.info(" -> Pasta 'Bombas' criada.")

def _add_ground_overlays_to_kml(
    doc: simplekml.Document,
    antena_nome_principal: str, # Nome da pasta da torre principal
    imagem_principal_nome_kmz: str, bounds_principal_data: list,
    repetidora_style: simplekml.Style
) -> list[tuple[Path, str]]:
    """Adiciona overlays de solo (principal e repetidoras) ao KML e retorna lista de arquivos de imagem."""
    arquivos_a_adicionar_ao_kmz = []

    # Overlay Principal (busca a pasta da torre principal pelo nome)
    # O ideal seria passar o objeto folder_torre diretamente se a estrutura permitir
    folder_torre = next((f for f in doc.features if isinstance(f, simplekml.Folder) and f.name == antena_nome_principal), None)
    if not folder_torre: # Fallback se a pasta não for encontrada (improvável se _add_placemarks_to_kml_folders foi chamado)
        folder_torre = doc.newfolder(name=antena_nome_principal)
        logger.warning(f"Pasta da torre principal '{antena_nome_principal}' não encontrada, criando nova para overlay.")


    ground_main = folder_torre.newgroundoverlay(name="Cobertura Principal")
    ground_main.icon.href = imagem_principal_nome_kmz # Nome do arquivo dentro do KMZ
    b = bounds_principal_data
    ground_main.latlonbox.north, ground_main.latlonbox.south = b[2], b[0]
    ground_main.latlonbox.east, ground_main.latlonbox.west = b[3], b[1]
    ground_main.color = "ffffffff" # Opacidade total
    # Adiciona a imagem principal à lista de arquivos para o KMZ
    arquivos_a_adicionar_ao_kmz.append((_GENERATED_IMAGES_DIR / imagem_principal_nome_kmz, imagem_principal_nome_kmz))
    logger.info(f" -> Overlay 'Cobertura Principal' adicionado à pasta '{antena_nome_principal}'.")


    # Overlays e Pontos de Repetidoras
    logger.info(" -> Adicionando repetidoras em pastas individuais...")
    for item_path in _GENERATED_IMAGES_DIR.iterdir():
        if item_path.name.startswith("repetidora_") and item_path.suffix == ".png":
            img_rep_path_servidor = item_path
            json_rep_path_servidor = img_rep_path_servidor.with_suffix(".json")

            if json_rep_path_servidor.exists():
                with open(json_rep_path_servidor, "r") as f:
                    bounds_rep_data = json.load(f).get("bounds")

                if bounds_rep_data:
                    rep_base_name = img_rep_path_servidor.stem # Ex: "repetidora_pivo_1_tx_20m"
                    rep_point_name = rep_base_name.replace('_', ' ').capitalize()

                    folder_rep = doc.newfolder(name=rep_point_name)

                    # Overlay da Repetidora
                    ground_rep = folder_rep.newgroundoverlay(name=f"Cobertura {rep_point_name}")
                    ground_rep.icon.href = img_rep_path_servidor.name # Nome do arquivo dentro do KMZ
                    br = bounds_rep_data
                    ground_rep.latlonbox.north, ground_rep.latlonbox.south = br[2], br[0]
                    ground_rep.latlonbox.east, ground_rep.latlonbox.west = br[3], br[1]
                    ground_rep.color = "ffffffff"
                    arquivos_a_adicionar_ao_kmz.append((img_rep_path_servidor, img_rep_path_servidor.name))

                    # Ponto da Repetidora (centralizado no overlay)
                    center_lat = (br[0] + br[2]) / 2
                    center_lon = (br[1] + br[3]) / 2
                    pnt_rep = folder_rep.newpoint(name=rep_point_name, coords=[(center_lon, center_lat)])
                    pnt_rep.style = repetidora_style
                    logger.info(f"     -> Pasta '{rep_point_name}' (ponto e overlay) adicionada.")
    return arquivos_a_adicionar_ao_kmz


# --- Endpoints ---

@router.post("/processar")
async def processar_kmz_endpoint(file: UploadFile = File(...)):
    """
    Recebe um arquivo KMZ, salva, processa e retorna os dados extraídos.
    Atenção: Este endpoint atualmente sobrescreve 'entrada.kmz' a cada chamada.
    """
    try:
        logger.info("📥 Recebendo arquivo KMZ...")
        conteudo = await file.read()

        # Garante que o diretório de arquivos exista (já deve ter sido criado no startup)
        # _INPUT_KMZ_DIR.mkdir(parents=True, exist_ok=True) # Redundante se settings.initialize_directories() o faz
        with open(INPUT_KMZ_PATH, "wb") as f:
            f.write(conteudo)
        logger.info(f"  -> KMZ salvo em: {INPUT_KMZ_PATH}")

        # Chama o parser
        # Se kmz_parser.parse_kmz for muito demorado, considere FastAPI.run_in_threadpool
        # from fastapi.concurrency import run_in_threadpool
        # antena, pivos, ciclos, bombas = await run_in_threadpool(kmz_parser.parse_kmz, INPUT_KMZ_PATH, _INPUT_KMZ_DIR)
        antena, pivos, ciclos, bombas = kmz_parser.parse_kmz(str(INPUT_KMZ_PATH), str(_INPUT_KMZ_DIR))


        if not antena:
            raise HTTPException(status_code=404, detail="Antena principal (torre, barracão, etc.) não encontrada no KMZ.")

        # TODO: Considerar definir Pydantic models para antena, pivos, etc., para tipagem e validação da resposta.
        return {
            "antena": antena,
            "pivos": pivos,
            "ciclos": ciclos,
            "bombas": bombas
        }

    except ValueError as ve:
        logger.error(f"❌ Erro de Validação KMZ: {ve}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"❌ Erro Interno em /kmz/processar: {e}", exc_info=True) # Adicionado exc_info para traceback
        raise HTTPException(status_code=500, detail=f"Erro interno ao processar KMZ: {type(e).__name__} - {str(e)}")


@router.get("/exportar")
async def exportar_kmz_endpoint( # Alterado para async para usar run_in_threadpool se necessário
    background_tasks: BackgroundTasks, # Adicionado para limpeza de arquivos
    imagem: str = Query(..., description="Nome da imagem PNG principal (ex: 'cobertura_principal.png')."),
    bounds_file: str = Query(..., description="Nome do JSON de bounds principal (ex: 'cobertura_principal.json').")
):
    """
    Gera e retorna um novo arquivo KMZ.
    Combina dados do 'entrada.kmz' com overlays de sinal gerados.
    """
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
        # Re-parse do KMZ original. Considerar cache se for um gargalo e os dados não mudam.
        antena, pivos, ciclos, bombas = kmz_parser.parse_kmz(str(INPUT_KMZ_PATH), str(_INPUT_KMZ_DIR))

        with open(caminho_bounds_principal_servidor, "r") as f:
            bounds_principal = json.load(f).get("bounds")

        # Verificação mais robusta de dados (exemplo)
        # Idealmente, kmz_parser.parse_kmz retornaria um objeto ou TypedDict com estrutura clara
        if not antena or not bounds_principal: # Adicionada verificação de bounds_principal aqui
            logger.warning("⚠️ Dados incompletos para exportar. Antena ou bounds_principal ausentes.")
            raise HTTPException(status_code=500, detail="Dados essenciais (antena, bounds_principal) ausentes para exportar.")
        # pivos, ciclos, bombas podem ser listas vazias, o que é válido.

        kml = simplekml.Kml(name="Estudo de Sinal Irricontrol")
        doc = kml.document # Referência ao documento principal do KML

        # Criação de Estilos
        torre_style, default_point_style, repetidora_style = _create_kml_styles()

        # Adicionando Placemarks (Antena, Pivôs, Ciclos, Bombas)
        _add_placemarks_to_kml_folders(doc, antena, pivos, ciclos, bombas, torre_style, default_point_style)

        # Adicionando Overlays de Solo (Principal e Repetidoras)
        arquivos_de_imagem_para_kmz = _add_ground_overlays_to_kml(
            doc,
            antena_nome_principal=antena.get("nome", "Antena Principal"), # Passa o nome da pasta da antena
            imagem_principal_nome_kmz=imagem, # Nome do arquivo como será no KMZ
            bounds_principal_data=bounds_principal,
            repetidora_style=repetidora_style
        )

        # Salvar KML temporário
        # Usar um diretório temporário do sistema poderia ser mais robusto
        # import tempfile; temp_dir = tempfile.mkdtemp(); caminho_kml_temp = Path(temp_dir) / "estudo_temp.kml"
        caminho_kml_temp = _INPUT_KMZ_DIR / "estudo_temp.kml"
        kml.save(str(caminho_kml_temp))
        logger.info(f"  -> KML temporário salvo em: {caminho_kml_temp}")

        # Criar KMZ final
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        nome_kmz_final = f"estudo-irricontrol-{timestamp}.kmz"
        caminho_kmz_final_servidor = _INPUT_KMZ_DIR / nome_kmz_final

        logger.info(f"  -> Criando KMZ final: {caminho_kmz_final_servidor}")
        with zipfile.ZipFile(str(caminho_kmz_final_servidor), "w", zipfile.ZIP_DEFLATED) as kmz_zip:
            kmz_zip.write(str(caminho_kml_temp), "doc.kml") # Nome padrão dentro do KMZ

            # Adicionar ícone da torre ao KMZ
            caminho_icone_torre_servidor = _GENERATED_IMAGES_DIR / TORRE_ICON_NAME
            if caminho_icone_torre_servidor.exists():
                kmz_zip.write(str(caminho_icone_torre_servidor), TORRE_ICON_NAME) # Adiciona na raiz do KMZ
                logger.info(f"      -> Ícone '{TORRE_ICON_NAME}' adicionado ao KMZ.")
            else:
                logger.warning(f"      -> ⚠️ ATENÇÃO: Ícone da torre '{TORRE_ICON_NAME}' não encontrado em {caminho_icone_torre_servidor}.")

            # Adicionar imagens de overlay (principal e repetidoras)
            for path_origem_img_servidor, nome_destino_img_kmz in arquivos_de_imagem_para_kmz:
                if path_origem_img_servidor.exists():
                    kmz_zip.write(str(path_origem_img_servidor), nome_destino_img_kmz) # Adiciona na raiz
                else:
                    logger.warning(f"      -> ⚠️ Imagem '{path_origem_img_servidor}' não encontrada, não adicionada ao KMZ.")
        
        # Adicionar tarefa em segundo plano para remover arquivos temporários
        # Isso é executado APÓS a resposta ser enviada.
        # Se usar um temp_dir, a limpeza seria 'shutil.rmtree(temp_dir)'
        background_tasks.add_task(Path.unlink, caminho_kml_temp, missing_ok=True)
        # Se INPUT_KMZ_PATH e os arquivos em IMAGENS_DIR_PATH não forem mais necessários
        # após esta exportação, poderiam ser limpos aqui também, mas CUIDADO com a lógica de arquivo único.

        logger.info("  -> Exportação KMZ concluída.")
        return FileResponse(
            str(caminho_kmz_final_servidor),
            media_type="application/vnd.google-earth.kmz",
            filename=nome_kmz_final, # Nome sugerido para download
            background=background_tasks # Passa as tarefas para FileResponse
        )

    except FileNotFoundError as fnfe:
        logger.error(f"❌ Arquivo não encontrado durante a exportação: {fnfe}", exc_info=True)
        raise HTTPException(status_code=404, detail=f"Arquivo necessário não encontrado: {fnfe.filename}")
    except Exception as e:
        logger.error(f"❌ Erro Interno em /kmz/exportar: {e}", exc_info=True)
        # import traceback # traceback é bom para depuração local, mas logger.error com exc_info=True já captura
        # traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao exportar KMZ: {type(e).__name__} - {str(e)}")


@router.get("/icone-torre")
async def get_icone_torre():
    """Serve a imagem do ícone da torre, se existir."""
    caminho_icone = _GENERATED_IMAGES_DIR / TORRE_ICON_NAME
    if caminho_icone.is_file(): # .is_file() é mais específico que .exists() para arquivos
        return FileResponse(str(caminho_icone), media_type="image/png")
    logger.warning(f"Ícone da torre não encontrado em: {caminho_icone}")
    raise HTTPException(status_code=404, detail=f"Ícone '{TORRE_ICON_NAME}' não encontrado.")