# backend/routers/farm.py
import logging
from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Tuple
import json

from backend.config import settings
from backend.services import farm_service # Vamos criar este arquivo a seguir

logger = logging.getLogger("irricontrol")
router = APIRouter(prefix="/farm", tags=["Farm Analysis"])

class FarmAoiPayload(BaseModel):
    job_id: str
    aoi_coordinates: List[Tuple[float, float]]

@router.post("/detect-pivots")
async def detect_pivots_endpoint(payload: FarmAoiPayload, background_tasks: BackgroundTasks):
    logger.info(f"API: Requisição de detecção de pivôs para job {payload.job_id} recebida.")
    background_tasks.add_task(
        farm_service.detect_pivots_in_background,
        payload.job_id,
        payload.aoi_coordinates
    )
    return {"job_id": payload.job_id, "status": "detection_started"}

@router.get("/jobs/{job_id}/detection_result")
async def get_detection_result(job_id: str):
    result_file_path = settings.ARQUIVOS_DIR_PATH / job_id / "detection_result.json"
    if not result_file_path.exists():
        return JSONResponse(status_code=202, content={"status": "processing"})

    with open(result_file_path, "r", encoding="utf-8") as f:
        return json.load(f)