# backend/routers/kmz.py

from fastapi import APIRouter, UploadFile, File, Query, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Dict, Any
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

# ✅ NOVO ENDPOINT: Este é o "botão de iniciar" que destrava o aplicativo.
# O frontend deve chamar este endpoint assim que a página carregar.
@router.post("/iniciar_job_vazio")
async def iniciar_job_vazio_endpoint():
    """
    Cria um novo job (sessão de trabalho) sem a necessidade de um upload de KMZ.
    Isto permite que a aplicação inicie em um estado "em branco", pronta para uso.
    Retorna o job_id para o frontend, que o usará em todas as chamadas futuras.
    """
    job_id = str(uuid.uuid4())
    logger.info(f"🆕 Novo job VAZIO iniciado com ID: {job_id}")
    
    job_input_dir = settings.ARQUIVOS_DIR_PATH / job_id
    job_images_dir = settings.IMAGENS_DIR_PATH / job_id
    job_input_dir.mkdir(parents=True, exist_ok=True)
    job_images_dir.mkdir(parents=True, exist_ok=True)

    # Cria um arquivo 'parsed_data.json' vazio para garantir a compatibilidade com outras partes do sistema.
    parsed_data_path = job_input_dir / "parsed_data.json"
    parsed_content_vazio = {
        "antenas": [], "pivos": [], "ciclos": [], "bombas": []
    }
    with open(parsed_data_path, "w", encoding="utf-8") as f:
        json.dump(parsed_content_vazio, f, ensure_ascii=False, indent=4)
    
    logger.info(f"  -> Estrutura de diretórios e 'parsed_data.json' vazio criados para o job {job_id}.")
    
    # Retorna o job_id para o frontend, desbloqueando a aplicação.
    return {"job_id": job_id}


@router.post("/processar")
async def processar_kmz_endpoint(file: UploadFile = File(...)):
    """Este endpoint (a "fechadura com chave KMZ") continua a funcionar como antes."""
    job_id = str(uuid.uuid4())
    logger.info(f"🆕 Novo job de processamento com KMZ iniciado com ID: {job_id}")
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
            "antenas": antenas, "pivos": pivos, "ciclos": ciclos, "bombas": bombas
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


# ✅ ALTERADO: Modelo de dados para a exportação.
# É importante que ele receba todos os dados (incluindo bombas) do frontend.
class ExportPayload(BaseModel):
    job_id: str
    imagem: str
    bounds_file: str
    antena_principal_data: Dict[str, Any]
    pivos_data: List[Dict[str, Any]]
    ciclos_data: List[Dict[str, Any]]
    bombas_data: List[Dict[str, Any]] # Adicionado para garantir que bombas desenhadas sejam exportadas
    repetidoras_data: List[Dict[str, Any]]


# ✅ ALTERADO: O endpoint de exportação agora é mais robusto
@router.post("/exportar")
async def exportar_kmz_endpoint(payload: ExportPayload, background_tasks: BackgroundTasks):
    logger.info(f"📦 Iniciando exportação KMZ via POST para o job: {payload.job_id}")

    job_input_dir = settings.ARQUIVOS_DIR_PATH / payload.job_id
    job_images_dir = settings.IMAGENS_DIR_PATH / payload.job_id
    
    caminho_imagem_principal_servidor = job_images_dir / payload.imagem
    caminho_bounds_principal_servidor = job_images_dir / payload.bounds_file

    if not caminho_imagem_principal_servidor.exists():
        raise HTTPException(status_code=404, detail=f"Imagem principal '{payload.imagem}' não encontrada no job '{payload.job_id}'.")
    if not caminho_bounds_principal_servidor.exists():
        raise HTTPException(status_code=404, detail=f"Bounds '{payload.bounds_file}' não encontrados no job '{payload.job_id}'.")

    try:
        # Carrega os dados diretamente do payload Pydantic, que reflete o estado atual do mapa.
        lista_repetidoras_selecionadas = payload.repetidoras_data
        antena_data = payload.antena_principal_data
        pivos_data_list = payload.pivos_data
        ciclos_data_list = payload.ciclos_data
        bombas_data_list = payload.bombas_data # Usa a lista de bombas do payload
        
        metadata_path = job_input_dir / "job_metadata.json"
        if not metadata_path.exists():
            raise HTTPException(status_code=404, detail=f"Metadados do job '{payload.job_id}' não encontrados. Execute a simulação da antena principal primeiro.")

        with open(metadata_path, "r") as f:
            metadata = json.load(f)
        
        template_id_do_job = metadata.get("template_id")
        if not template_id_do_job:
            raise HTTPException(status_code=500, detail=f"O arquivo de metadados do job '{payload.job_id}' não contém um 'template_id'.")

        selected_template = settings.obter_template(template_id_do_job)
        if not selected_template:
            raise HTTPException(status_code=404, detail=f"O template com ID '{template_id_do_job}' não foi encontrado.")

        logger.info(f"  -> Template '{selected_template.id}' lido dos metadados do job.")
        
        with open(caminho_bounds_principal_servidor, "r") as f:
            bounds_principal_data = json.load(f).get("bounds")
        
        if not antena_data or not bounds_principal_data:
            raise HTTPException(status_code=500, detail="Dados essenciais (antena, bounds_principal) ausentes para exportar.")

        kml = simplekml.Kml(name="Estudo de Sinal Irricontrol")
        doc = kml.document
        
        arquivos_de_imagem_para_kmz = kmz_exporter.build_kml_document_and_get_image_list(
            doc=doc,
            antena_data=antena_data,
            pivos_data=pivos_data_list,
            ciclos_data=ciclos_data_list,
            bombas_data=bombas_data_list, # Passa a lista de bombas atualizada
            imagem_principal_nome_relativo=payload.imagem, 
            bounds_principal_data=bounds_principal_data,
            generated_images_dir=job_images_dir,
            selected_template=selected_template,
            study_date_str_for_subfolder=datetime.now().strftime('%Y-%m-%d'),
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
