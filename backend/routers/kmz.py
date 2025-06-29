# backend/routers/kmz.py

from fastapi import APIRouter, UploadFile, File, Query, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse # ✅ ESTA LINHA CORRIGE O ERRO
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import zipfile
import json 
import simplekml 
from datetime import datetime 
from pathlib import Path
import logging
import uuid

from backend.services import kmz_parser
from backend.services import kmz_exporter 
from backend.config import settings

logger = logging.getLogger("irricontrol")

router = APIRouter(
    prefix="/kmz",
    tags=["KMZ Operations"],
)

@router.post("/iniciar_job_vazio")
async def iniciar_job_vazio_endpoint():
    job_id = str(uuid.uuid4())
    logger.info(f"🆕 Novo job VAZIO iniciado com ID: {job_id}")
    job_input_dir = settings.ARQUIVOS_DIR_PATH / job_id
    job_images_dir = settings.IMAGENS_DIR_PATH / job_id
    job_input_dir.mkdir(parents=True, exist_ok=True)
    job_images_dir.mkdir(parents=True, exist_ok=True)
    parsed_data_path = job_input_dir / "parsed_data.json"
    parsed_content_vazio = {"antenas": [], "pivos": [], "ciclos": [], "bombas": []}
    with open(parsed_data_path, "w", encoding="utf-8") as f:
        json.dump(parsed_content_vazio, f, ensure_ascii=False, indent=4)
    logger.info(f"  -> Estrutura de diretórios para job vazio '{job_id}' criada.")
    return {"job_id": job_id}


@router.post("/processar")
async def processar_kmz_endpoint(file: UploadFile = File(...)):
    job_id = str(uuid.uuid4())
    logger.info(f"🆕 Novo job de processamento com KMZ iniciado com ID: {job_id}")
    job_input_dir = settings.ARQUIVOS_DIR_PATH / job_id
    job_images_dir = settings.IMAGENS_DIR_PATH / job_id
    job_input_dir.mkdir(parents=True, exist_ok=True)
    job_images_dir.mkdir(parents=True, exist_ok=True)
    input_kmz_path = job_input_dir / "entrada.kmz" 
    try:
        conteudo = await file.read()
        with open(input_kmz_path, "wb") as f:
            f.write(conteudo)
        logger.info(f"  -> KMZ salvo em: {input_kmz_path}")
        antenas, pivos, ciclos, bombas = kmz_parser.parse_kmz(str(input_kmz_path), str(job_input_dir))
        parsed_data_path = job_input_dir / "parsed_data.json"
        parsed_content = {"antenas": antenas, "pivos": pivos, "ciclos": ciclos, "bombas": bombas}
        with open(parsed_data_path, "w", encoding="utf-8") as f:
            json.dump(parsed_content, f, ensure_ascii=False, indent=4)
        logger.info(f"  -> Dados parseados salvos para o job em: {parsed_data_path}")
        return {"job_id": job_id, "antenas": antenas, "pivos": pivos, "ciclos": ciclos, "bombas": bombas}
    except ValueError as ve:
        logger.error(f"❌ Erro de Validação KMZ (job: {job_id}): {ve}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"❌ Erro Interno em /kmz/processar (job: {job_id}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro interno ao processar KMZ: {type(e).__name__} - {str(e)}")


class ExportPayload(BaseModel):
    job_id: str
    template_id: str
    antena_principal_data: Optional[Dict[str, Any]] = None
    imagem: Optional[str] = None
    bounds_file: Optional[str] = None
    pivos_data: List[Dict[str, Any]]
    ciclos_data: List[Dict[str, Any]]
    bombas_data: List[Dict[str, Any]]
    repetidoras_data: List[Dict[str, Any]]


@router.post("/exportar")
async def exportar_kmz_endpoint(payload: ExportPayload, background_tasks: BackgroundTasks):
    logger.info(f"📦 Iniciando exportação KMZ via POST para o job: {payload.job_id}")

    job_input_dir = settings.ARQUIVOS_DIR_PATH / payload.job_id
    job_images_dir = settings.IMAGENS_DIR_PATH / payload.job_id
    
    bounds_principal_data = None
    
    if payload.antena_principal_data and payload.imagem and payload.bounds_file:
        logger.info(" -> Antena principal detectada no payload. Verificando arquivos...")
        caminho_imagem_principal_servidor = job_images_dir / payload.imagem
        caminho_bounds_principal_servidor = job_images_dir / payload.bounds_file
        if not caminho_imagem_principal_servidor.exists():
            raise HTTPException(status_code=404, detail=f"Imagem principal '{payload.imagem}' não encontrada no job '{payload.job_id}'.")
        if not caminho_bounds_principal_servidor.exists():
            raise HTTPException(status_code=404, detail=f"Bounds '{payload.bounds_file}' não encontrados no job '{payload.job_id}'.")
        with open(caminho_bounds_principal_servidor, "r") as f:
            bounds_principal_data = json.load(f).get("bounds")
    else:
        logger.info(" -> Nenhuma antena principal no payload. Exportando sem ela.")

    try:
        selected_template = settings.obter_template(payload.template_id)
        if not selected_template:
            raise HTTPException(status_code=404, detail=f"O template com ID '{payload.template_id}' não foi encontrado.")
        logger.info(f"  -> Usando template '{selected_template.id}' do payload.")

        kml = simplekml.Kml(name="Estudo de Sinal Irricontrol")
        doc = kml.document
        
        arquivos_de_imagem_para_kmz = kmz_exporter.build_kml_document_and_get_image_list(
            doc=doc,
            antena_data=payload.antena_principal_data,
            pivos_data=payload.pivos_data,
            ciclos_data=payload.ciclos_data,
            bombas_data=payload.bombas_data,
            imagem_principal_nome_relativo=payload.imagem, 
            bounds_principal_data=bounds_principal_data,
            generated_images_dir=job_images_dir,
            selected_template=selected_template,
            repetidoras_selecionadas_data=payload.repetidoras_data
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
        logger.error(f"❌ Arquivo não encontrado durante a exportação (job: {payload.job_id}): {fnfe}", exc_info=True)
        raise HTTPException(status_code=404, detail=f"Arquivo necessário não encontrado: {str(fnfe)}")
    except Exception as e:
        logger.error(f"❌ Erro Interno em /kmz/exportar (job: {payload.job_id}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro ao exportar KMZ: {type(e).__name__} - {str(e)}")


@router.get("/icone-torre")
async def get_icone_torre():
    caminho_icone = settings.IMAGENS_DIR_PATH / "cloudrf.png"
    if caminho_icone.is_file():
        return FileResponse(str(caminho_icone), media_type="image/png")
    logger.warning(f"Ícone da torre não encontrado no caminho base: {caminho_icone}")
    raise HTTPException(status_code=404, detail="Ícone 'cloudrf.png' não encontrado.")
