# backend/routers/kmz.py

from fastapi import APIRouter, UploadFile, File, Query, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import zipfile
import json 
import simplekml 
from datetime import datetime 
from pathlib import Path
import logging
from typing import List
import uuid

from backend.services import kmz_parser
from backend.services import kmz_exporter 
from backend.config import settings

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO) 

router = APIRouter(
    prefix="/kmz",
    tags=["KMZ Operations"],
)

TORRE_ICON_NAME = "cloudrf.png"
DEFAULT_ICON_URL = "http://maps.google.com/mapfiles/kml/pushpin/ylw-pushpin.png"

@router.post("/processar")
async def processar_kmz_endpoint(file: UploadFile = File(...)):

    job_id = str(uuid.uuid4())
    logger.info(f"🆕 Novo job de processamento iniciado com ID: {job_id}")
    job_input_dir = settings.ARQUIVOS_DIR_PATH / job_id
    job_images_dir = settings.IMAGENS_DIR_PATH / job_id
    job_input_dir.mkdir(parents=True, exist_ok=True)
    job_images_dir.mkdir(parents=True, exist_ok=True)

    input_kmz_path = job_input_dir / "entrada.kmz" 

    try:
        logger.info(f"📥 Recebendo arquivo KMZ para o job {job_id}...")
        conteudo = await file.read()
        with open(input_kmz_path, "wb") as f:
            f.write(conteudo)
        logger.info(f"  -> KMZ salvo em: {input_kmz_path}")
        
        antena, pivos, ciclos, bombas = kmz_parser.parse_kmz(str(input_kmz_path), str(job_input_dir))
        
        if not antena:
            raise HTTPException(status_code=404, detail="Antena principal (torre, barracão, etc.) não encontrada no KMZ.")
        
        return {"job_id": job_id, "antena": antena, "pivos": pivos, "ciclos": ciclos, "bombas": bombas}
    except ValueError as ve:
        logger.error(f"❌ Erro de Validação KMZ (job: {job_id}): {ve}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"❌ Erro Interno em /kmz/processar (job: {job_id}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro interno ao processar KMZ: {type(e).__name__} - {str(e)}")

@router.get("/exportar")
async def exportar_kmz_endpoint(
    background_tasks: BackgroundTasks,

    job_id: str = Query(..., description="O ID único do job retornado pelo endpoint /processar."),
    imagem: str = Query(..., description="Nome do arquivo da imagem PNG principal (ex: 'principal_...png')."),
    bounds_file: str = Query(..., description="Nome do arquivo JSON de bounds principal (ex: 'principal_...json')."),
    repetidoras_data: str = Query('[]', description="String JSON com os dados das repetidoras (imagem, altura, sobre_pivo).")
):
    logger.info(f"📦 Iniciando exportação KMZ para o job: {job_id}")

    job_input_dir = settings.ARQUIVOS_DIR_PATH / job_id
    job_images_dir = settings.IMAGENS_DIR_PATH / job_id
    input_kmz_path = job_input_dir / "entrada.kmz"

    if not input_kmz_path.exists():
        raise HTTPException(status_code=400, detail=f"Nenhum KMZ foi processado para o job '{job_id}'. Faça o upload primeiro.")
    
    caminho_imagem_principal_servidor = job_images_dir / imagem
    caminho_bounds_principal_servidor = job_images_dir / bounds_file

    if not caminho_imagem_principal_servidor.exists():
        raise HTTPException(status_code=404, detail=f"Imagem principal '{imagem}' não encontrada no job '{job_id}'.")
    if not caminho_bounds_principal_servidor.exists():
        raise HTTPException(status_code=404, detail=f"Bounds '{bounds_file}' não encontrados no job '{job_id}'.")

    try:
        try:
            lista_repetidoras_selecionadas = json.loads(repetidoras_data)
            if not isinstance(lista_repetidoras_selecionadas, list):
                raise ValueError("O JSON das repetidoras deve ser uma lista de objetos.")
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Erro ao decodificar JSON de repetidoras: {repetidoras_data}. Erro: {e}")
            raise HTTPException(status_code=400, detail=f"Formato de JSON inválido para o parâmetro 'repetidoras_data'. Detalhe: {e}")

        image_name_base = imagem.lower()
        if image_name_base.startswith("principal_"):
            image_name_suffix = image_name_base[len("principal_"):]
        else:
            logger.error(f"Nome da imagem '{imagem}' não começa com 'principal_'.")
            raise HTTPException(status_code=400, detail=f"Formato de nome de imagem inválido: {imagem}")

        selected_template = None
        sorted_templates = sorted(settings.TEMPLATES_DISPONIVEIS, key=lambda t: len(t.id), reverse=True)

        for t_config in sorted_templates:
            template_id_config_lower = t_config.id.lower()
            if image_name_suffix.startswith(template_id_config_lower):
                if (len(image_name_suffix) == len(template_id_config_lower) or 
                   (len(image_name_suffix) > len(template_id_config_lower) and 
                    image_name_suffix[len(template_id_config_lower)] == '_')):
                    selected_template = t_config
                    logger.info(f"Template correspondente encontrado: ID '{t_config.id}' para imagem '{imagem}'")
                    break
        
        if not selected_template:
            parts = image_name_suffix.split('_')
            guessed_id_parts = []
            for part in parts:
                if not (part.startswith("tx") or part.startswith("lat") or part.startswith("lon") or part.startswith("bwi") or part.isdigit() or "mhz" in part):
                    guessed_id_parts.append(part)
                else:
                    break
            
            if guessed_id_parts:
                attempted_extracted_id_for_error = "_".join(guessed_id_parts)
            else:
                 attempted_extracted_id_for_error = image_name_suffix.split('_')[0] if '_' in image_name_suffix else image_name_suffix

            logger.error(f"Nenhum template correspondente encontrado para o nome base da imagem: '{image_name_suffix}' (derivado de '{imagem}')")
            raise HTTPException(status_code=404, detail=f"Template com ID derivado '{attempted_extracted_id_for_error}' não encontrado nas configurações.")

        template_id_for_name = selected_template.id
        template_frq = selected_template.frq
        template_txw = selected_template.transmitter.txw
        
        study_date_str = datetime.now().strftime('%Y-%m-%d')

        if hasattr(selected_template, 'col') and selected_template.col:
            dynamic_colour_key_filename = f"{selected_template.col}.key.png"
            logger.info(f"Usando legenda específica do template: {dynamic_colour_key_filename}")
        else:
            logger.error(f"Atributo 'col' da legenda não encontrado ou vazio no template '{selected_template.id}'. Verifique as configurações do template.")
            raise HTTPException(status_code=500, detail=f"Configuração da legenda (col) ausente para o template {selected_template.id}")

        antena_data, pivos_data, ciclos_data, bombas_data = kmz_parser.parse_kmz(str(input_kmz_path), str(job_input_dir))

        with open(caminho_bounds_principal_servidor, "r") as f:
            bounds_principal_data = json.load(f).get("bounds")

        if not antena_data or not bounds_principal_data:
            logger.warning("⚠️ Dados incompletos para exportar. Antena ou bounds_principal ausentes.")
            raise HTTPException(status_code=500, detail="Dados essenciais (antena, bounds_principal) ausentes para exportar.")

        kml = simplekml.Kml(name="Estudo de Sinal Irricontrol")
        doc = kml.document

        
        arquivos_de_imagem_para_kmz = kmz_exporter.build_kml_document_and_get_image_list(
            doc=doc,
            antena_data=antena_data,
            pivos_data=pivos_data,
            ciclos_data=ciclos_data,
            bombas_data=bombas_data,
            imagem_principal_nome_relativo=imagem, 
            bounds_principal_data=bounds_principal_data,
            generated_images_dir=job_images_dir,
            torre_icon_name=TORRE_ICON_NAME,
            default_icon_url=DEFAULT_ICON_URL,
            colour_key_filename=dynamic_colour_key_filename, 
            template_id_for_subfolder=template_id_for_name,
            study_date_str_for_subfolder=study_date_str,
            template_frq_for_main_coverage=template_frq,
            template_txw_for_main_coverage=template_txw,
            repetidoras_selecionadas_data=lista_repetidoras_selecionadas
        )

        caminho_kml_temp = job_input_dir / "estudo_temp.kml"
        kml.save(str(caminho_kml_temp))
        logger.info(f"  -> KML temporário salvo em: {caminho_kml_temp}")

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        nome_kmz_final = f"estudo-irricontrol-{timestamp}.kmz"
        caminho_kmz_final_servidor = job_input_dir / nome_kmz_final

        logger.info(f"  -> Criando KMZ final: {caminho_kmz_final_servidor}")
        with zipfile.ZipFile(str(caminho_kmz_final_servidor), "w", zipfile.ZIP_DEFLATED) as kmz_zip:
            kmz_zip.write(str(caminho_kml_temp), "doc.kml")
            
            added_to_zip = set()
            for path_origem_img_servidor, nome_destino_img_kmz in arquivos_de_imagem_para_kmz:
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
        logger.error(f"❌ Arquivo não encontrado durante a exportação (job: {job_id}): {fnfe}", exc_info=True)
        raise HTTPException(status_code=404, detail=f"Arquivo necessário não encontrado: {fnfe.filename}")
    except Exception as e:
        logger.error(f"❌ Erro Interno em /kmz/exportar (job: {job_id}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro ao exportar KMZ: {type(e).__name__} - {str(e)}")

@router.get("/icone-torre")
async def get_icone_torre():

    caminho_icone = settings.IMAGENS_DIR_PATH / TORRE_ICON_NAME
    if caminho_icone.is_file():
        return FileResponse(str(caminho_icone), media_type="image/png")
    logger.warning(f"Ícone da torre não encontrado no caminho base: {caminho_icone}")
    raise HTTPException(status_code=404, detail=f"Ícone '{TORRE_ICON_NAME}' não encontrado.")