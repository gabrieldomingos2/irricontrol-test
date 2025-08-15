from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import logging

from backend.services import pdf_service
from backend.config import settings
from backend.services.i18n_service import i18n_service

logger = logging.getLogger("irricontrol")

router = APIRouter(
    prefix="/report",  # Este roteador tem o prefixo /report
    tags=["Report Operations"],
)

# O Payload CORRETO que o frontend envia
class PdfExportPayload(BaseModel):
    job_id: str
    language: str = 'pt-br'
    antena_principal_data: Optional[Dict[str, Any]] = None
    pivos_data: List[Dict[str, Any]]
    bombas_data: List[Dict[str, Any]]
    repetidoras_data: List[Dict[str, Any]]  # As repetidoras também vão para o relatório
    template_id: str
    # map_image_base64: Optional[str] = None  # Se for usar a imagem do mapa (mais complexo)


@router.post("/pdf_export")  # O endpoint é apenas /pdf_export (com o prefixo do router, fica /report/pdf_export)
async def export_pdf_report_endpoint(payload: PdfExportPayload, background_tasks: BackgroundTasks):
    DEBUG = getattr(settings, "DEBUG", False)
    try:
        logger.info("📄 Iniciando exportação de relatório PDF para o job: %s no idioma: '%s'", payload.job_id, payload.language)

        # Instancia o gerador de PDF
        pdf_generator = pdf_service.PDFReportGenerator(lang=payload.language)

        # Gera o PDF usando a função generate_report do pdf_service
        pdf_path = pdf_generator.generate_report(
            antena_principal_data=payload.antena_principal_data,
            pivos_data=payload.pivos_data,
            bombas_data=payload.bombas_data,
            repetidoras_data=payload.repetidoras_data,  # Passa as repetidoras aqui
            template_id=payload.template_id,
            # map_image_base64=payload.map_image_base64  # Se for usar esta feature
        )

        # Garante que é Path (BackgroundTasks com Path.unlink precisa de método bound)
        pdf_path = Path(pdf_path)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        # Usa o tradutor para o filename_prefix do KML, que é adequado para o PDF também
        t = i18n_service.get_translator(payload.language)
        filename_prefix = t("kml.filename_prefix") or "estudo"
        nome_pdf_final = f"{filename_prefix}_report_{timestamp}.pdf"

        # Adiciona a tarefa para excluir o PDF após o envio
        background_tasks.add_task(pdf_path.unlink, missing_ok=True)

        logger.info("✅ Relatório PDF para o job %s gerado e pronto para download.", payload.job_id)
        return FileResponse(
            str(pdf_path),
            media_type="application/pdf",
            filename=nome_pdf_final,
            background=background_tasks
        )

    except HTTPException:
        # Se alguém levantou HTTPException específica, só repassa
        raise
    except Exception as e:
        logger.error("❌ Erro Interno em /report/pdf_export (job: %s): %s", payload.job_id, e, exc_info=True)
        if DEBUG:
            raise HTTPException(status_code=500, detail=f"Erro ao gerar relatório PDF: {type(e).__name__} - {str(e)}")
        else:
            raise HTTPException(status_code=500, detail=f"Erro ao gerar relatório PDF: {type(e).__name__}")