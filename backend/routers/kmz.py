from fastapi import APIRouter, UploadFile, File, Query, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import zipfile
import json 
import simplekml 
from datetime import datetime 
from pathlib import Path
import logging

from backend.services import kmz_parser
from backend.services import kmz_exporter 
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

@router.post("/processar")
async def processar_kmz_endpoint(file: UploadFile = File(...)):
    try:
        logger.info("📥 Recebendo arquivo KMZ...")
        conteudo = await file.read()
        _INPUT_KMZ_DIR.mkdir(parents=True, exist_ok=True)
        with open(INPUT_KMZ_PATH, "wb") as f:
            f.write(conteudo)
        antena, pivos, ciclos, bombas = kmz_parser.parse_kmz(str(INPUT_KMZ_PATH), str(_INPUT_KMZ_DIR))
        if not antena:
            raise HTTPException(status_code=404, detail="Antena principal não encontrada no KMZ.")
        return {"antena": antena, "pivos": pivos, "ciclos": ciclos, "bombas": bombas}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/exportar")
async def exportar_kmz_endpoint(
    background_tasks: BackgroundTasks,
    imagem: str = Query(..., description="Nome da imagem PNG principal."),
    bounds_file: str = Query(..., description="Nome do JSON de bounds principal.")
):
    logger.info("📦 Iniciando exportação KMZ...")
    if not INPUT_KMZ_PATH.exists():
        raise HTTPException(status_code=400, detail="Nenhum KMZ foi processado ainda.")
    
    caminho_imagem_principal_servidor = _GENERATED_IMAGES_DIR / imagem
    caminho_bounds_principal_servidor = _GENERATED_IMAGES_DIR / bounds_file

    if not caminho_imagem_principal_servidor.exists() or not caminho_bounds_principal_servidor.exists():
        raise HTTPException(status_code=404, detail="Imagem principal ou arquivo de bounds não encontrados.")

    try:
        # Lógica de template
        image_name_base = imagem.lower()
        if not image_name_base.startswith("principal_"):
            raise HTTPException(status_code=400, detail=f"Formato de nome de imagem inválido: {imagem}")
        image_name_suffix = image_name_base.replace("principal_", "")

        selected_template = None
        for t_config in sorted(settings.TEMPLATES_DISPONIVEIS, key=lambda t: len(t.id), reverse=True):
            if image_name_suffix.startswith(t_config.id.lower()):
                selected_template = t_config
                break
        if not selected_template:
            raise HTTPException(status_code=404, detail=f"Template não encontrado para imagem '{imagem}'.")

        if not (hasattr(selected_template, 'col') and selected_template.col):
            raise HTTPException(status_code=500, detail=f"Configuração da legenda (col) ausente para o template {selected_template.id}")
        
        # **ALTERAÇÃO AQUI**: Deriva o nome da pasta interna do nome do arquivo da imagem
        internal_folder_name = imagem.replace("principal_", "").replace(".png", "")
        logger.info(f"Nome da pasta interna definido como: '{internal_folder_name}'")

        # Busca os dados
        antena_data, pivos_data, ciclos_data, bombas_data = kmz_parser.parse_kmz(str(INPUT_KMZ_PATH), str(_INPUT_KMZ_DIR))
        with open(caminho_bounds_principal_servidor, "r") as f:
            bounds_principal_data = json.load(f).get("bounds")

        if not antena_data or not bounds_principal_data:
            raise HTTPException(status_code=500, detail="Dados essenciais ausentes para exportar.")

        kml = simplekml.Kml(name="Estudo de Sinal Irricontrol") 
        doc = kml.document 

        sub_kmz_files_to_add = kmz_exporter.build_main_kml_and_sub_kmzs(
            doc=doc,
            antena_data=antena_data,
            pivos_data=pivos_data,
            ciclos_data=ciclos_data,
            bombas_data=bombas_data,
            imagem_principal_nome_relativo=imagem, 
            bounds_principal_data=bounds_principal_data,
            generated_images_dir=_GENERATED_IMAGES_DIR,
            torre_icon_name=TORRE_ICON_NAME,
            default_icon_url=DEFAULT_ICON_URL,
            colour_key_filename=f"{selected_template.col}.key.png", 
            internal_folder_name=internal_folder_name, # Passa o novo nome da pasta
            template_frq_for_main_coverage=selected_template.frq,
            template_txw_for_main_coverage=selected_template.transmitter.txw
        )

        caminho_kml_temp = _INPUT_KMZ_DIR / "estudo_temp.kml"
        kml.save(str(caminho_kml_temp))

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        nome_kmz_final = f"estudo-irricontrol-{timestamp}.kmz"
        caminho_kmz_final_servidor = _INPUT_KMZ_DIR / nome_kmz_final

        with zipfile.ZipFile(str(caminho_kmz_final_servidor), "w", zipfile.ZIP_DEFLATED) as kmz_zip:
            kmz_zip.write(str(caminho_kml_temp), "doc.kml") 
            for path_sub_kmz in sub_kmz_files_to_add:
                if path_sub_kmz.exists():
                    kmz_zip.write(str(path_sub_kmz), path_sub_kmz.name)
        
        background_tasks.add_task(Path.unlink, caminho_kml_temp, missing_ok=True)
        for path_sub_kmz in sub_kmz_files_to_add:
            background_tasks.add_task(Path.unlink, path_sub_kmz, missing_ok=True)

        return FileResponse(
            str(caminho_kmz_final_servidor),
            media_type="application/vnd.google-earth.kmz",
            filename=nome_kmz_final
        )
    except Exception as e:
        logger.error(f"❌ Erro Interno em /kmz/exportar: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro ao exportar KMZ: {type(e).__name__} - {str(e)}")