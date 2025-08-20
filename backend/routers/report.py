# backend/routers/report.py

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.config import settings
from backend.services import pdf_service
from backend.services.i18n_service import i18n_service

logger = logging.getLogger("irricontrol")

router = APIRouter(
    prefix="/report",
    tags=["Report Operations"],
)


# ---------------------------------------------------------------------------
# Payload para exportação de relatórios em PDF
# ---------------------------------------------------------------------------
class PdfExportPayload(BaseModel):
    job_id: str
    language: str = "pt-br"
    antena_principal_data: Optional[Dict[str, Any]] = None
    pivos_data: List[Dict[str, Any]]
    bombas_data: List[Dict[str, Any]]
    repetidoras_data: List[Dict[str, Any]]
    template_id: str
    map_image_base64: Optional[str] = None


# ---------------------------------------------------------------------------
# Endpoint principal
# ---------------------------------------------------------------------------
@router.post("/pdf_export")
async def export_pdf_report_endpoint(
    payload: PdfExportPayload, background_tasks: BackgroundTasks
):
    """
    Gera relatório PDF de um job existente.
    - Usa `pdf_service.PDFReportGenerator` para compor o relatório.
    - Arquivo é nomeado com prefixo traduzido + timestamp.
    - PDF temporário é agendado para remoção após envio.
    """
    DEBUG = bool(getattr(settings, "DEBUG", False))

    try:
        logger.info(
            "📄 Iniciando exportação de relatório PDF para a sessão: %s no idioma: '%s'",
            payload.job_id,
            payload.language,
        )

        pdf_generator = pdf_service.PDFReportGenerator(lang=payload.language)

        pdf_path = pdf_generator.generate_report(
            antena_principal_data=payload.antena_principal_data,
            pivos_data=payload.pivos_data,
            bombas_data=payload.bombas_data,
            repetidoras_data=payload.repetidoras_data,
            template_id=payload.template_id,
            map_image_base64=payload.map_image_base64,
        )

        pdf_path = Path(pdf_path)

        # Nome amigável com timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        t = i18n_service.get_translator(payload.language)
        filename_prefix = t("kml.filename_prefix") or "estudo"
        nome_pdf_final = f"{filename_prefix}_report_{timestamp}.pdf"

        # Agenda remoção do PDF temporário após envio
        background_tasks.add_task(pdf_path.unlink, missing_ok=True)

        logger.info("✅ Relatório PDF para a sessão %s pronto para download.", payload.job_id)
        return FileResponse(
            str(pdf_path),
            media_type="application/pdf",
            filename=nome_pdf_final,
            background=background_tasks,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "❌ Erro Interno em /report/pdf_export para a sessão %s: %s",
            payload.job_id,
            e,
            exc_info=True,
        )
        if DEBUG:
            raise HTTPException(
                status_code=500,
                detail=f"Erro ao gerar relatório PDF: {type(e).__name__} - {str(e)}",
            )
        raise HTTPException(
            status_code=500,
            detail="Erro interno ao gerar relatório PDF.",
        )