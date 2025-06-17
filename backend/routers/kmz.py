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

logger = logging.getLogger("irricontrol")

router = APIRouter(
    prefix="/kmz",
    tags=["KMZ Operations"],
)

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
        
        antenas, pivos, ciclos, bombas = kmz_parser.parse_kmz(str(input_kmz_path), str(job_input_dir))
        parsed_data_path = job_input_dir / "parsed_data.json"
        parsed_content = {

            "antenas": antenas,
            "pivos": pivos,
            "ciclos": ciclos,
            "bombas": bombas
        }
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

@router.get("/exportar")
async def exportar_kmz_endpoint(
    background_tasks: BackgroundTasks,
    job_id: str = Query(..., description="O ID único do job retornado pelo endpoint /processar."),
    imagem: str = Query(..., description="Nome do arquivo da imagem PNG principal."),
    bounds_file: str = Query(..., description="Nome do arquivo JSON de bounds principal."),
    # 👇 ALTERAÇÃO 1: Adicionar um novo parâmetro para receber os dados da antena principal como uma string JSON.
    antena_principal_data: str = Query(..., description="String JSON com os dados da antena principal selecionada."),
    repetidoras_data: str = Query('[]', description="String JSON com os dados das repetidoras selecionadas.")
):
    logger.info(f"📦 Iniciando exportação KMZ para o job: {job_id}")

    job_input_dir = settings.ARQUIVOS_DIR_PATH / job_id
    job_images_dir = settings.IMAGENS_DIR_PATH / job_id
    
    caminho_imagem_principal_servidor = job_images_dir / imagem
    caminho_bounds_principal_servidor = job_images_dir / bounds_file

    if not caminho_imagem_principal_servidor.exists():
        raise HTTPException(status_code=404, detail=f"Imagem principal '{imagem}' não encontrada no job '{job_id}'.")
    if not caminho_bounds_principal_servidor.exists():
        raise HTTPException(status_code=404, detail=f"Bounds '{bounds_file}' não encontrados no job '{job_id}'.")

    try:
        lista_repetidoras_selecionadas = json.loads(repetidoras_data)
        if not isinstance(lista_repetidoras_selecionadas, list):
            raise ValueError("O JSON das repetidoras deve ser uma lista de objetos.")

        metadata_path = job_input_dir / "job_metadata.json"
        if not metadata_path.exists():
            raise HTTPException(status_code=404, detail=f"Metadados do job '{job_id}' não encontrados.")

        with open(metadata_path, "r") as f:
            metadata = json.load(f)
        
        template_id_do_job = metadata.get("template_id")
        if not template_id_do_job:
            raise HTTPException(status_code=500, detail=f"O arquivo de metadados do job '{job_id}' não contém um 'template_id'.")

        selected_template = settings.obter_template(template_id_do_job)
        if not selected_template:
            raise HTTPException(status_code=404, detail=f"O template com ID '{template_id_do_job}' não foi encontrado.")

        logger.info(f"Template '{selected_template.id}' lido dos metadados do job.")
        
        study_date_str = datetime.now().strftime('%Y-%m-%d')
        
        parsed_data_path = job_input_dir / "parsed_data.json"
        if not parsed_data_path.exists():
            raise HTTPException(status_code=404, detail=f"Dados processados para o job '{job_id}' não encontrados.")
        
        logger.info(f"  -> Lendo dados parseados de: {parsed_data_path}")
        with open(parsed_data_path, "r", encoding="utf-8") as f:
            parsed_data = json.load(f)
        
        # 👇 ALTERAÇÃO 2: Carregar os dados da antena a partir do novo parâmetro da URL,
        # em vez de tentar ler do arquivo JSON, que não tem mais a chave 'antena'.
        antena_data = json.loads(antena_principal_data)
        
        # O resto dos dados continua vindo do arquivo parseado.
        pivos_data = parsed_data.get("pivos", [])
        ciclos_data = parsed_data.get("ciclos", [])
        bombas_data = parsed_data.get("bombas", [])

        with open(caminho_bounds_principal_servidor, "r") as f:
            bounds_principal_data = json.load(f).get("bounds")

        # Esta verificação agora funcionará corretamente.
        if not antena_data or not bounds_principal_data:
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
            selected_template=selected_template,
            study_date_str_for_subfolder=study_date_str,
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
        raise HTTPException(status_code=404, detail=f"Arquivo necessário não encontrado: {str(fnfe)}")
    except Exception as e:
        logger.error(f"❌ Erro Interno em /kmz/exportar (job: {job_id}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro ao exportar KMZ: {type(e).__name__} - {str(e)}")

@router.get("/icone-torre")
async def get_icone_torre():
    caminho_icone = settings.IMAGENS_DIR_PATH / "cloudrf.png" # Usando o nome diretamente
    if caminho_icone.is_file():
        return FileResponse(str(caminho_icone), media_type="image/png")
    logger.warning(f"Ícone da torre não encontrado no caminho base: {caminho_icone}")
    raise HTTPException(status_code=404, detail="Ícone 'cloudrf.png' não encontrado.")