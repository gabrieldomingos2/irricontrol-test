# backend/routers/simulation.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import logging

# Importa o objeto settings e os serviços
from backend.config import settings
from backend.services import cloudrf_service, analysis_service

# Configuração do Logger
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/simulation",
    tags=["Simulation & Analysis"],
)

# --- Modelos Pydantic para Validação ---

class PivoData(BaseModel):
    nome: str
    lat: float
    lon: float
    fora: Optional[bool] = None

class AntenaSimPayload(BaseModel):
    job_id: str  # 👈 NOVO: ID do Job é obrigatório
    lat: float
    lon: float
    altura: int
    altura_receiver: Optional[int] = 3
    nome: Optional[str] = "Antena Principal"
    template: str
    pivos_atuais: List[PivoData]

class ManualSimPayload(BaseModel):
    job_id: str  # 👈 NOVO: ID do Job é obrigatório
    lat: float
    lon: float
    altura: float
    altura_receiver: float
    template: str
    pivos_atuais: List[PivoData]

class OverlayData(BaseModel):
    id: Optional[str] = None
    # 👇 ALTERADO: Frontend deve enviar apenas o NOME do arquivo (ex: 'principal_...png')
    imagem: str 
    bounds: Tuple[float, float, float, float] # S, W, N, E

class ReavaliarPayload(BaseModel):
    job_id: str  # 👈 NOVO: ID do Job é obrigatório
    pivos: List[PivoData]
    overlays: List[OverlayData]

class PerfilPayload(BaseModel):
    pontos: List[Tuple[float, float]]
    altura_antena: float
    altura_receiver: float

class FindRepeaterSitesPayload(BaseModel):
    job_id: str # 👈 NOVO: ID do Job é obrigatório
    target_pivot_lat: float
    target_pivot_lon: float
    target_pivot_nome: str
    altura_antena_repetidora_proposta: Optional[float] = 5.0
    altura_receiver_pivo: Optional[float] = 3.0
    active_overlays: List[OverlayData]
    pivot_polygons_coords: Optional[List[List[Tuple[float, float]]]] = None


# --- Funções Auxiliares ---

def _get_image_filepath_for_analysis(image_filename: str, job_id: str) -> Path:
    """
    👇 ALTERADO: Converte um NOME de arquivo de imagem e um job_id para um Path absoluto no servidor.
    """
    # Remove qualquer parte do caminho que o frontend possa ter enviado, pegando só o nome do arquivo.
    filename_only = Path(image_filename.split('?')[0]).name
    filepath = settings.IMAGENS_DIR_PATH / job_id / filename_only
    return filepath


# --- Endpoints ---

@router.get("/templates")
async def get_templates_endpoint():
    """Retorna a lista de IDs dos templates disponíveis."""
    return settings.listar_templates_ids()

@router.post("/run_main")
async def run_main_simulation_endpoint(payload: AntenaSimPayload):
    """Executa a simulação principal a partir da antena."""
    try:
        logger.info(f"🛰️  Iniciando simulação principal para job: {payload.job_id}")
        # 👇 ALTERADO: Passa o job_id para o serviço da CloudRF
        sim_result = await cloudrf_service.run_cloudrf_simulation(
            job_id=payload.job_id,
            lat=payload.lat,
            lon=payload.lon,
            altura=payload.altura,
            altura_receiver=payload.altura_receiver,
            template_id=payload.template,
            is_repeater=False
        )
        
        imagem_path_servidor = Path(sim_result["imagem_local_path"])
        if not imagem_path_servidor.is_file():
            raise HTTPException(status_code=500, detail="Erro interno: Imagem da simulação principal não encontrada no servidor.")

        logger.info(f"✅ Simulação CloudRF (principal) para job {payload.job_id} concluída.")
        logger.info(f"ℹ️  Analisando cobertura de pivôs para o job {payload.job_id}")
        
        pivos_com_status = analysis_service.verificar_cobertura_pivos(
            pivos=[p.model_dump() for p in payload.pivos_atuais],
            overlays_info=[{
                "id": f"antena_principal_{payload.nome or 'sim'}",
                "imagem_path": imagem_path_servidor,
                "bounds": sim_result["bounds"]
            }]
        )
        logger.info(f"ℹ️  Status dos pivôs (principal) para job {payload.job_id}: {pivos_com_status}")

        return {
            "imagem_salva": sim_result["imagem_url"],
            "imagem_filename": sim_result["imagem_filename"],
            "bounds": sim_result["bounds"],
            "status": "Simulação principal concluída",
            "pivos": pivos_com_status
        }
    except ValueError as e:
        logger.warning(f"❌ Erro de Validação em /run_main (job: {payload.job_id}): {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Erro Interno em /simulation/run_main (job: {payload.job_id}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro interno na simulação principal: {str(e)}")

@router.post("/run_manual")
async def run_manual_simulation_endpoint(payload: ManualSimPayload):
    """Executa uma simulação para uma repetidora manual."""
    try:
        logger.info(f"📡 Iniciando simulação manual para job: {payload.job_id}")
        # 👇 ALTERADO: Passa o job_id para o serviço da CloudRF
        sim_result = await cloudrf_service.run_cloudrf_simulation(
            job_id=payload.job_id,
            lat=payload.lat,
            lon=payload.lon,
            altura=int(payload.altura),
            altura_receiver=int(payload.altura_receiver),
            template_id=payload.template,
            is_repeater=True
        )
        
        logger.info(f"✅ Simulação CloudRF (manual) para job {payload.job_id} concluída.")

        return {
            "imagem_salva": sim_result["imagem_url"],
            "imagem_filename": sim_result["imagem_filename"],
            "bounds": sim_result["bounds"],
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
    """Reavalia a cobertura dos pivôs com base nos overlays fornecidos."""
    try:
        logger.info(f"🔄 Reavaliando cobertura para job {payload.job_id} com {len(payload.overlays)} overlays.")
        
        overlays_para_analise = []
        if payload.overlays:
            for o_data in payload.overlays:
                # 👇 ALTERADO: Usa a função auxiliar para obter o caminho correto dentro do job
                imagem_path_servidor = _get_image_filepath_for_analysis(o_data.imagem, payload.job_id)
                if not imagem_path_servidor.is_file():
                    logger.warning(f"Arquivo de imagem '{o_data.imagem}' não encontrado para job '{payload.job_id}'. Pulando overlay.")
                    continue

                overlays_para_analise.append({
                    "id": o_data.id or f"overlay_{Path(o_data.imagem).stem}",
                    "imagem_path": imagem_path_servidor,
                    "bounds": o_data.bounds
                })
        
        if not overlays_para_analise and payload.overlays:
             logger.warning(f"⚠️ Nenhum arquivo de overlay válido encontrado para o job {payload.job_id}.")
             pivos_atualizados = [{"nome": p.nome, "lat": p.lat, "lon": p.lon, "fora": True} for p in payload.pivos]
        elif not overlays_para_analise and not payload.overlays:
            logger.info(f"ℹ️ Nenhum overlay ativo fornecido para o job {payload.job_id}. Pivôs marcados como 'fora'.")
            pivos_atualizados = [{"nome": p.nome, "lat": p.lat, "lon": p.lon, "fora": True} for p in payload.pivos]
        else:
            pivos_atualizados = analysis_service.verificar_cobertura_pivos(
                pivos=[p.model_dump() for p in payload.pivos],
                overlays_info=overlays_para_analise
            )
        
        logger.info(f"✅ Pivôs atualizados pela reavaliação para o job {payload.job_id}.")
        return {"pivos": pivos_atualizados}

    except Exception as e:
        logger.error(f"❌ Erro em /simulation/reevaluate (job: {payload.job_id}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro ao reavaliar pivôs: {str(e)}")

@router.post("/elevation_profile")
async def get_elevation_profile_endpoint(payload: PerfilPayload):
    """Calcula e retorna o perfil de elevação e o ponto de bloqueio."""
    try:
        logger.info(f"⛰️  Calculando perfil de elevação para {len(payload.pontos)} pontos.")
        resultado = await analysis_service.obter_perfil_elevacao(
            pontos=payload.pontos,
            alt1=payload.altura_antena,
            alt2=payload.altura_receiver
        )
        logger.info("✅ Perfil de elevação calculado.")
        return resultado
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar perfil de elevação: {str(e)}")

@router.post("/find_repeater_sites")
async def find_repeater_sites_endpoint(payload: FindRepeaterSitesPayload):
    """Encontra locais candidatos para repetidoras."""
    try:
        logger.info(f"📡 Buscando locais de repetidora para pivô '{payload.target_pivot_nome}' no job {payload.job_id}.")
        
        active_overlays_for_analysis = []
        for ov_data in payload.active_overlays: 
            # 👇 ALTERADO: Usa a função auxiliar para obter o caminho correto dentro do job
            imagem_path_servidor = _get_image_filepath_for_analysis(ov_data.imagem, payload.job_id)
            if not imagem_path_servidor.is_file():
                logger.warning(f"Arquivo de imagem '{ov_data.imagem}' não encontrado para job '{payload.job_id}'. Pulando.")
                continue
            active_overlays_for_analysis.append({
                "id": ov_data.id or f"overlay_{Path(ov_data.imagem).stem}",
                "imagem_path": imagem_path_servidor, 
                "bounds": ov_data.bounds
            })

        if not active_overlays_for_analysis and payload.active_overlays:
             return {"candidate_sites": []}
        if not active_overlays_for_analysis and not payload.active_overlays:
            return {"candidate_sites": []}

        candidate_sites = await analysis_service.encontrar_locais_altos_para_repetidora(
            alvo_lat=payload.target_pivot_lat,
            alvo_lon=payload.target_pivot_lon,
            alvo_nome=payload.target_pivot_nome,
            altura_antena_repetidora_proposta=payload.altura_antena_repetidora_proposta,
            altura_receptor_pivo=payload.altura_receiver_pivo,
            active_overlays_data=active_overlays_for_analysis,
            pivot_polygons_coords_data=payload.pivot_polygons_coords
        )
        
        logger.info(f"✅ Busca por locais de repetidora concluída para o job {payload.job_id}. {len(candidate_sites)} candidatos.")
        return {"candidate_sites": candidate_sites}

    except Exception as e:
        logger.error(f"❌ Erro Interno em /find_repeater_sites (job: {payload.job_id}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro interno ao buscar locais para repetidora: {str(e)}")