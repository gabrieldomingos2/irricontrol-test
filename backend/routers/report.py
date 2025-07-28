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
    prefix="/report",
    tags=["Report Operations"],
)

# O Payload CORRETO que o frontend envia
class PdfExportPayload(BaseModel):
    job_id: str
    language: str = 'pt-br'
    antena_principal_data: Optional[Dict[str, Any]] = None
    pivos_data: List[Dict[str, Any]]
    bombas_data: List[Dict[str, Any]]
    repetidoras_data: List[Dict[str, Any]]
    template_id: str
    # map_image_base64: Optional[str] = None # Se for usar a imagem do mapa (mais complexo)

@router.post("/pdf_export") # O endpoint é apenas /pdf_export (com o prefixo do router, fica /report/pdf_export)
async def export_pdf_report_endpoint(payload: PdfExportPayload, background_tasks: BackgroundTasks):
    try:
        logger.info(f"📄 Iniciando exportação de relatório PDF para o job: {payload.job_id} no idioma: '{payload.language}'")

        # Instancia o gerador de PDF
        pdf_generator = pdf_service.PDFReportGenerator(lang=payload.language)

        # Gera o PDF usando a função generate_report do pdf_service
        pdf_path = pdf_generator.generate_report(
            antena_principal_data=payload.antena_principal_data,
            pivos_data=payload.pivos_data,
            bombas_data=payload.bombas_data,
            repetidoras_data=payload.repetidoras_data,
            template_id=payload.template_id,
            # map_image_base64=payload.map_image_base64 # Se for usar esta feature
        )
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        # Usa o tradutor para o filename_prefix do KML, que é adequado para o PDF também
        filename_prefix = i18n_service.get_translator(payload.language)("kml.filename_prefix") 
        nome_pdf_final = f"{filename_prefix}_report_{timestamp}.pdf"

        # Adiciona a tarefa para excluir o PDF após o envio
        background_tasks.add_task(Path.unlink, pdf_path, missing_ok=True) 

        logger.info(f"✅ Relatório PDF para o job {payload.job_id} gerado e pronto para download.")
        return FileResponse(
            str(pdf_path),
            media_type="application/pdf",
            filename=nome_pdf_final,
            background=background_tasks
        )

    except Exception as e:
        logger.error(f"❌ Erro Interno em /report/pdf_export (job: {payload.job_id}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro ao gerar relatório PDF: {str(e)}")
