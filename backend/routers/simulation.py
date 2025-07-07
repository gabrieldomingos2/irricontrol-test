# backend/routers/simulation.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Tuple, Literal
from pathlib import Path
import logging
import json
import shutil

from backend.config import settings
from backend.services import cloudrf_service, analysis_service

logger = logging.getLogger("irricontrol")
router = APIRouter(prefix="/simulation", tags=["Simulation & Analysis"])

# --- Modelos Pydantic ---
class PivoData(BaseModel):
    nome: str
    lat: float
    lon: float
    # Permite que 'tipo' seja qualquer string, mas o padrão é 'pivo'
    tipo: Optional[str] = 'pivo'
    fora: Optional[bool] = None
    # Adiciona os outros campos como opcionais para não quebrar em outras partes
    raio: Optional[float] = None
    angulo_central: Optional[float] = None
    abertura_arco: Optional[float] = None
    angulo_inicio: Optional[float] = None
    angulo_fim: Optional[float] = None

class BombaData(BaseModel):
    # (este modelo não precisa de alteração)
    nome: str; lat: float; lon: float
    type: Literal['bomba'] = 'bomba'; fora: Optional[bool] = None

class AntenaSimPayload(BaseModel):
    job_id: str
    lat: float; lon: float; altura: int
    altura_receiver: Optional[int] = 3
    nome: Optional[str] = "Antena Principal"
    template: str
    pivos_atuais: List[PivoData]
    bombas_atuais: List[BombaData] 

class ManualSimPayload(BaseModel):
    job_id: str; lat: float; lon: float; altura: float; altura_receiver: float
    template: str; pivos_atuais: List[PivoData]

class OverlayData(BaseModel):
    id: Optional[str] = None; imagem: str; bounds: Tuple[float, float, float, float]

class ReavaliarPayload(BaseModel):
    job_id: str; pivos: List[PivoData]; bombas: List[BombaData]; overlays: List[OverlayData]

class PerfilPayload(BaseModel):
    pontos: List[Tuple[float, float]]; altura_antena: float; altura_receiver: float

class FindRepeaterSitesPayload(BaseModel):
    job_id: str; target_pivot_lat: float; target_pivot_lon: float; target_pivot_nome: str
    altura_antena_repetidora_proposta: Optional[float] = 5.0; altura_receiver_pivo: Optional[float] = 3.0
    active_overlays: List[OverlayData]
    pivot_polygons_coords: Optional[List[List[Tuple[float, float]]]] = None

class GeneratePivotPayload(BaseModel):
    job_id: str
    center: Tuple[float, float]
    pivos_atuais: List[PivoData]
    language: str = 'pt-br'

def _get_image_filepath_for_analysis(image_filename: str, job_id: str) -> Path:
    filename_only = Path(image_filename.split('?')[0]).name
    return settings.IMAGENS_DIR_PATH / job_id / filename_only

# --- Endpoints ---
@router.get("/templates")
async def get_templates_endpoint():
    return settings.listar_templates_ids()

@router.post("/generate_pivot_in_circle")
async def generate_pivot_in_circle_endpoint(payload: GeneratePivotPayload):
    try:
        novo_pivo = analysis_service.generate_pivot_at_center(
            center_lat=payload.center[0], 
            center_lon=payload.center[1],
            existing_pivos=[p.model_dump() for p in payload.pivos_atuais],
            lang=payload.language
        )
        return {"novo_pivo": novo_pivo}
    except Exception as e:
        logger.error(f"❌ Erro em /generate_pivot_in_circle: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro ao gerar novo pivô: {str(e)}")

@router.post("/run_main")
async def run_main_simulation_endpoint(payload: AntenaSimPayload):
    try:
        logger.info(f"🛰️  Iniciando simulação principal para job: {payload.job_id}")
        sim_result = await cloudrf_service.run_cloudrf_simulation(
            lat=payload.lat, lon=payload.lon, altura=payload.altura,
            altura_receiver=payload.altura_receiver, template_id=payload.template,
        )
        
        job_image_dir = settings.IMAGENS_DIR_PATH / payload.job_id
        job_image_dir.mkdir(parents=True, exist_ok=True)
        cached_image_path = Path(sim_result["imagem_local_path"])
        imagem_filename = sim_result["imagem_filename"]
        imagem_path_servidor = job_image_dir / imagem_filename
        
        shutil.copy2(cached_image_path, imagem_path_servidor)
        shutil.copy2(cached_image_path.with_suffix(".json"), imagem_path_servidor.with_suffix(".json"))

        backend_url = str(settings.BACKEND_PUBLIC_URL).rstrip('/') if settings.BACKEND_PUBLIC_URL else ""
        imagem_servida_url = f"{backend_url}/{settings.STATIC_DIR_NAME}/{settings.IMAGENS_DIR_NAME}/{payload.job_id}/{imagem_filename}"

        overlay_info = {"imagem_path": imagem_path_servidor, "bounds": sim_result["bounds"]}
        
        pivos_com_status = await analysis_service.verificar_cobertura_pivos(
            [p.model_dump() for p in payload.pivos_atuais], [overlay_info]
        )
        bombas_com_status = await analysis_service.verificar_cobertura_bombas(
            [b.model_dump() for b in payload.bombas_atuais], [overlay_info]
        )
        
        logger.info(f"✅ Simulação principal para job {payload.job_id} concluída e analisada.")
        return {
            "imagem_salva": imagem_servida_url, "imagem_filename": imagem_filename,
            "bounds": sim_result["bounds"], "pivos": pivos_com_status, "bombas": bombas_com_status
        }
    except Exception as e:
        logger.error(f"❌ Erro Interno em /run_main: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro na simulação principal: {str(e)}")

@router.post("/run_manual")
async def run_manual_simulation_endpoint(payload: ManualSimPayload):
    try:
        logger.info(f"📡 Iniciando simulação manual para job: {payload.job_id}")

        sim_result_from_service = await cloudrf_service.run_cloudrf_simulation(
            lat=payload.lat,
            lon=payload.lon,
            altura=int(payload.altura),
            altura_receiver=int(payload.altura_receiver),
            template_id=payload.template,
            is_repeater=True
        )

        job_image_dir = settings.IMAGENS_DIR_PATH / payload.job_id
        job_image_dir.mkdir(parents=True, exist_ok=True)

        cached_image_path = Path(sim_result_from_service["imagem_local_path"])
        imagem_filename = sim_result_from_service["imagem_filename"]
        imagem_path_servidor = job_image_dir / imagem_filename

        shutil.copy2(cached_image_path, imagem_path_servidor)
        shutil.copy2(cached_image_path.with_suffix(".json"), imagem_path_servidor.with_suffix(".json"))
        logger.info(f" -> Arquivos '{imagem_filename}' copiados do cache para o job '{payload.job_id}'.")

        backend_url_prefix = str(settings.BACKEND_PUBLIC_URL).rstrip('/') if settings.BACKEND_PUBLIC_URL else ""
        imagem_servida_url = f"{backend_url_prefix}/{settings.STATIC_DIR_NAME}/{settings.IMAGENS_DIR_NAME}/{payload.job_id}/{imagem_filename}"

        logger.info(f"✅ Simulação CloudRF (manual) para job {payload.job_id} concluída.")

        return {
            "imagem_salva": imagem_servida_url,
            "imagem_filename": imagem_filename,
            "bounds": sim_result_from_service["bounds"],
            "status": "Simulação manual concluída",
        }
    except ValueError as e:
        logger.warning(f"❌ Erro de Validação em /run_manual (job: {payload.job_id}): {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Erro Interno em /simulation/run_manual (job: {payload.job_id}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro interno na simulação manual: {str(e)}")


@router.post("/reevaluate")
async def reevaluate_pivots_endpoint(payload: ReavaliarPayload):
    try:
        logger.info(f"🔄 Reavaliando cobertura para job {payload.job_id} com {len(payload.overlays)} overlays.")

        overlays_para_analise = []
        if payload.overlays:
            for o_data in payload.overlays:
                imagem_path_servidor = _get_image_filepath_for_analysis(o_data.imagem, payload.job_id)
                if not imagem_path_servidor.is_file():
                    logger.warning(f"Arquivo de imagem '{o_data.imagem}' não encontrado para job '{payload.job_id}'. Pulando overlay.")
                    continue

                overlays_para_analise.append({
                    "id": o_data.id or f"overlay_{Path(o_data.imagem).stem}",
                    "imagem_path": imagem_path_servidor,
                    "bounds": o_data.bounds
                })

        pivos_atualizados = [{"nome": p.nome, "lat": p.lat, "lon": p.lon, "fora": True} for p in payload.pivos]
        bombas_atualizadas = [{"nome": b.nome, "lat": b.lat, "lon": b.lon, "fora": True} for b in payload.bombas]

        if overlays_para_analise:
            pivos_atualizados = await analysis_service.verificar_cobertura_pivos(
                [p.model_dump() for p in payload.pivos], overlays_para_analise
            )
            if payload.bombas:
                 bombas_atualizadas = await analysis_service.verificar_cobertura_bombas(
                    [b.model_dump() for b in payload.bombas], overlays_para_analise
                 )
            # 👆 FIM DA CORREÇÃO

        logger.info(f"✅ Pivôs e Bombas atualizados pela reavaliação para o job {payload.job_id}.")
        return {"pivos": pivos_atualizados, "bombas": bombas_atualizadas}

    except Exception as e:
        logger.error(f"❌ Erro em /simulation/reevaluate (job: {payload.job_id}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro ao reavaliar cobertura: {str(e)}")


@router.post("/elevation_profile")
async def get_elevation_profile_endpoint(payload: PerfilPayload):
    try:
        logger.info(f"⛰️  Calculando perfil de elevação para {len(payload.pontos)} pontos.")
        resultado = await analysis_service.obter_perfil_elevacao(
            pontos=payload.pontos, alt1=payload.altura_antena, alt2=payload.altura_receiver
        )
        logger.info("✅ Perfil de elevação calculado.")
        return resultado
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar perfil de elevação: {str(e)}")


@router.post("/find_repeater_sites")
async def find_repeater_sites_endpoint(payload: FindRepeaterSitesPayload):
    try:
        logger.info(f"📡 Buscando locais de repetidora para pivô '{payload.target_pivot_nome}' no job {payload.job_id}.")

        active_overlays_for_analysis = [
            {"id": ov.id, "imagem_path": _get_image_filepath_for_analysis(ov.imagem, payload.job_id), "bounds": ov.bounds}
            for ov in payload.active_overlays if _get_image_filepath_for_analysis(ov.imagem, payload.job_id).is_file()
        ]

        if not active_overlays_for_analysis:
            return {"candidate_sites": []}

        candidate_sites = await analysis_service.encontrar_locais_altos_para_repetidora(
            alvo_lat=payload.target_pivot_lat, alvo_lon=payload.target_pivot_lon,
            alvo_nome=payload.target_pivot_nome, altura_antena_repetidora_proposta=payload.altura_antena_repetidora_proposta,
            altura_receptor_pivo=payload.altura_receiver_pivo, active_overlays_data=active_overlays_for_analysis,
            pivot_polygons_coords_data=payload.pivot_polygons_coords
        )
        logger.info(f"✅ Busca por locais de repetidora concluída para o job {payload.job_id}. {len(candidate_sites)} candidatos.")
        return {"candidate_sites": candidate_sites}

    except Exception as e:
        logger.error(f"❌ Erro Interno em /find_repeater_sites (job: {payload.job_id}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro interno ao buscar locais para repetidora: {str(e)}")