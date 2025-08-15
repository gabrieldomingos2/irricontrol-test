from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Form
from fastapi.responses import FileResponse
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
from backend.services.i18n_service import i18n_service

logger = logging.getLogger("irricontrol")

router = APIRouter(
    prefix="/kmz",
    tags=["KMZ Operations"],
)

# ---- Configs de segurança/robustez ----
MAX_UPLOAD_MB = 50
CHUNK_SIZE = 1024 * 1024  # 1MB por chunk
ALLOWED_EXTS = {".kmz", ".kml"}
ALLOWED_CTYPES = {
    "application/vnd.google-earth.kmz",
    "application/octet-stream",  # navegadores costumam mandar isso
    "application/xml",
    "text/xml",
}
DEBUG = getattr(settings, "DEBUG", False)


# --- util: garantir diretórios ---
def _ensure_dir(p: Path) -> None:
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.error("❌ Falha ao criar diretório '%s': %s", p, e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Falha ao criar diretório '{p}': {type(e).__name__} - {str(e)}")


# --- util: salvar UploadFile em streaming com limite de tamanho ---
async def _save_upload_stream(upload: UploadFile, dst: Path, max_mb: int) -> int:
    total = 0
    _ensure_dir(dst.parent)
    # Garante início do arquivo
    try:
        upload.file.seek(0)
    except Exception:
        pass
    try:
        with open(dst, "wb") as f:
            while True:
                chunk = await upload.read(CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_mb * 1024 * 1024:
                    try:
                        f.close()
                    finally:
                        try:
                            dst.unlink(missing_ok=True)
                        except Exception:
                            pass
                    raise HTTPException(status_code=413, detail=f"Arquivo excede {max_mb}MB")
                f.write(chunk)
    finally:
        try:
            await upload.close()
        except Exception:
            pass
    return total


@router.post("/iniciar_job_vazio")
async def iniciar_job_vazio_endpoint():
    job_id = str(uuid.uuid4())
    logger.info("🆕 Novo job VAZIO iniciado com ID: %s", job_id)

    job_input_dir = settings.ARQUIVOS_DIR_PATH / job_id
    job_images_dir = settings.IMAGENS_DIR_PATH / job_id

    _ensure_dir(job_input_dir)
    _ensure_dir(job_images_dir)

    parsed_data_path = job_input_dir / "parsed_data.json"
    parsed_content_vazio = {"antenas": [], "pivos": [], "ciclos": [], "bombas": []}
    with open(parsed_data_path, "w", encoding="utf-8") as f:
        json.dump(parsed_content_vazio, f, ensure_ascii=False, indent=4)

    logger.info("  -> Estrutura de diretórios para job vazio '%s' criada.", job_id)
    return {"job_id": job_id}


class ExportPayload(BaseModel):
    job_id: str
    template_id: str
    language: str = 'pt-br'
    antena_principal_data: Optional[Dict[str, Any]] = None
    imagem: Optional[str] = None
    bounds_file: Optional[str] = None
    pivos_data: List[Dict[str, Any]]
    ciclos_data: List[Dict[str, Any]]
    bombas_data: List[Dict[str, Any]]
    repetidoras_data: List[Dict[str, Any]]


@router.post("/processar")
async def processar_kmz_endpoint(file: UploadFile = File(...), language: str = Form('pt-br')):
    job_id = str(uuid.uuid4())
    logger.info("🆕 Novo job de processamento de arquivo GIS (%s) iniciado com ID: %s para o idioma: '%s'", file.filename, job_id, language)

    job_input_dir = settings.ARQUIVOS_DIR_PATH / job_id
    job_images_dir = settings.IMAGENS_DIR_PATH / job_id

    _ensure_dir(job_input_dir)
    _ensure_dir(job_images_dir)

    # Nome do arquivo sanitizado (evita path traversal)
    nome_seguro = Path(file.filename).name
    input_file_path = job_input_dir / nome_seguro

    # Validação básica de extensão/MIME
    ext = Path(nome_seguro).suffix.lower()
    if ext not in ALLOWED_EXTS:
        raise HTTPException(status_code=400, detail="Arquivo deve ser .kmz ou .kml")

    ctype = (file.content_type or "").lower()
    if ctype and ctype not in ALLOWED_CTYPES:
        logger.warning("Content-Type inesperado para %s: %s", nome_seguro, ctype)

    try:
        # Salva em streaming com limite de tamanho
        total_bytes = await _save_upload_stream(file, input_file_path, MAX_UPLOAD_MB)
        logger.info("  -> Arquivo de entrada salvo em: %s (%0.2f MB)", input_file_path, total_bytes / (1024 * 1024))

        antenas, pivos, ciclos, bombas = kmz_parser.parse_gis_file(str(input_file_path), str(job_input_dir), lang=language)

        parsed_data_path = job_input_dir / "parsed_data.json"
        parsed_content = {"antenas": antenas, "pivos": pivos, "ciclos": ciclos, "bombas": bombas}
        with open(parsed_data_path, "w", encoding="utf-8") as f:
            json.dump(parsed_content, f, ensure_ascii=False, indent=4)

        logger.info("  -> Dados parseados salvos para o job em: %s", parsed_data_path)
        return {"job_id": job_id, "antenas": antenas, "pivos": pivos, "ciclos": ciclos, "bombas": bombas}

    except ValueError as ve:
        logger.error("❌ Erro de Validação de Arquivo (job: %s): %s", job_id, ve, exc_info=True)
        raise HTTPException(status_code=400, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("❌ Erro Interno em /kmz/processar (job: %s): %s", job_id, e, exc_info=True)
        if DEBUG:
            raise HTTPException(status_code=500, detail=f"Erro interno ao processar o arquivo: {type(e).__name__} - {str(e)}")
        else:
            raise HTTPException(status_code=500, detail=f"Erro interno ao processar o arquivo: {type(e).__name__}")


@router.post("/exportar")
async def exportar_kmz_endpoint(payload: ExportPayload, background_tasks: BackgroundTasks):
    logger.info("📦 Iniciando exportação KMZ para o job: %s no idioma: '%s'", payload.job_id, payload.language)

    job_input_dir = settings.ARQUIVOS_DIR_PATH / payload.job_id
    job_images_dir = settings.IMAGENS_DIR_PATH / payload.job_id

    _ensure_dir(job_input_dir)
    _ensure_dir(job_images_dir)

    bounds_principal_data = None

    if payload.antena_principal_data and payload.imagem and payload.bounds_file:
        logger.info(" -> Antena principal detectada no payload. Verificando arquivos...")
        caminho_imagem_principal_servidor = job_images_dir / payload.imagem
        caminho_bounds_principal_servidor = job_images_dir / payload.bounds_file
        if not caminho_imagem_principal_servidor.exists():
            raise HTTPException(status_code=404, detail=f"Imagem principal '{payload.imagem}' não encontrada no job '{payload.job_id}'.")
        if not caminho_bounds_principal_servidor.exists():
            raise HTTPException(status_code=404, detail=f"Bounds '{payload.bounds_file}' não encontrados no job '{payload.job_id}'.")
        with open(caminho_bounds_principal_servidor, "r", encoding="utf-8") as f:
            bounds_principal_json = json.load(f)
            bounds_principal_data = bounds_principal_json.get("bounds")
    else:
        logger.info(" -> Nenhuma antena principal no payload. Exportando sem ela.")

    try:
        selected_template = settings.obter_template(payload.template_id)
        if not selected_template:
            raise HTTPException(status_code=404, detail=f"O template com ID '{payload.template_id}' não foi encontrado.")
        logger.info("  -> Usando template '%s' do payload.", selected_template.id)

        t = i18n_service.get_translator(payload.language)

        kml = simplekml.Kml(name=t("kml.main_name"))
        doc = kml.document

        arquivos_de_imagem_para_kmz = kmz_exporter.build_kml_document_and_get_image_list(
            doc=doc,
            lang=payload.language,
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
        _ensure_dir(caminho_kml_temp.parent)

        kml.save(str(caminho_kml_temp))
        logger.info("  -> KML temporário salvo em: %s", caminho_kml_temp)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename_prefix = t("kml.filename_prefix")
        nome_kmz_final = f"{filename_prefix}-{timestamp}.kmz"

        caminho_kmz_final_servidor = job_input_dir / nome_kmz_final

        logger.info("  -> Criando KMZ final: %s", caminho_kmz_final_servidor)
        with zipfile.ZipFile(str(caminho_kmz_final_servidor), "w", zipfile.ZIP_DEFLATED) as kmz_zip:
            kmz_zip.write(str(caminho_kml_temp), "doc.kml")

            added_to_zip = set()
            for path_origem_img_servidor, nome_destino_img_kmz in arquivos_de_imagem_para_kmz:
                src = Path(path_origem_img_servidor)
                if nome_destino_img_kmz not in added_to_zip:
                    if src.exists():
                        kmz_zip.write(str(src), nome_destino_img_kmz)
                        added_to_zip.add(nome_destino_img_kmz)
                        logger.info("      -> Arquivo '%s' adicionado ao KMZ.", nome_destino_img_kmz)
                    else:
                        logger.warning("      -> ⚠️ Imagem '%s' não encontrada, não adicionada ao KMZ.", src)

        background_tasks.add_task(Path.unlink, caminho_kml_temp, missing_ok=True)

        logger.info("  -> Exportação KMZ concluída.")
        return FileResponse(
            str(caminho_kmz_final_servidor),
            media_type="application/vnd.google-earth.kmz",
            filename=nome_kmz_final,
            background=background_tasks
        )

    except FileNotFoundError as fnfe:
        logger.error("❌ Arquivo não encontrado durante a exportação (job: %s): %s", payload.job_id, fnfe, exc_info=True)
        raise HTTPException(status_code=404, detail=f"Arquivo necessário não encontrado: {str(fnfe)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("❌ Erro Interno em /kmz/exportar (job: %s): %s", payload.job_id, e, exc_info=True)
        if DEBUG:
            raise HTTPException(status_code=500, detail=f"Erro ao exportar KMZ: {type(e).__name__} - {str(e)}")
        else:
            raise HTTPException(status_code=500, detail=f"Erro ao exportar KMZ: {type(e).__name__}")


@router.get("/icone-torre")
async def get_icone_torre():
    caminho_icone = settings.IMAGENS_DIR_PATH / "cloudrf.png"
    if caminho_icone.is_file():
        return FileResponse(str(caminho_icone), media_type="image/png")
    logger.warning("Ícone da torre não encontrado no caminho base: %s", caminho_icone)
    raise HTTPException(status_code=404, detail="Ícone 'cloudrf.png' não encontrado.")