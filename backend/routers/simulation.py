# routers/simulation.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import logging
import json
import shutil # ✅ ADIÇÃO: Importamos shutil para copiar arquivos do cache para o job.

# Importa o objeto settings e os serviços
from backend.config import settings
from backend.services import cloudrf_service, analysis_service

# Configuração do Logger
logger = logging.getLogger("irricontrol")

router = APIRouter(
    prefix="/simulation",
    tags=["Simulation & Analysis"],
)

# --- Modelos Pydantic ---
class PivoData(BaseModel):
    nome: str
    lat: float
    lon: float
    type: Literal['pivo'] = 'pivo'
    fora: Optional[bool] = None

class BombaData(BaseModel):
    nome: str
    lat: float
    lon: float
    type: Literal['bomba'] = 'bomba'
    fora: Optional[bool] = None

class AntenaSimPayload(BaseModel):
    job_id: str
    lat: float
    lon: float
    altura: int
    altura_receiver: Optional[int] = 3
    nome: Optional[str] = "Antena Principal"
    template: str
    pivos_atuais: List[PivoData]

class ManualSimPayload(BaseModel):
    job_id: str
    lat: float
    lon: float
    altura: float
    altura_receiver: float
    template: str
    pivos_atuais: List[PivoData]

class OverlayData(BaseModel):
    id: Optional[str] = None
    imagem: str
    bounds: Tuple[float, float, float, float]

class ReavaliarPayload(BaseModel):
    job_id: str
    pivos: List[PivoData]
    # Adicionamos bombas aqui para o endpoint de reavaliação ser completo
    bombas: List[BombaData]
    overlays: List[OverlayData]

class PerfilPayload(BaseModel):
    pontos: List[Tuple[float, float]]
    altura_antena: float
    altura_receiver: float

class FindRepeaterSitesPayload(BaseModel):
    job_id: str
    target_pivot_lat: float
    target_pivot_lon: float
    target_pivot_nome: str
    altura_antena_repetidora_proposta: Optional[float] = 5.0
    altura_receiver_pivo: Optional[float] = 3.0
    active_overlays: List[OverlayData]
    pivot_polygons_coords: Optional[List[List[Tuple[float, float]]]] = None


# --- Funções Auxiliares ---
def _get_image_filepath_for_analysis(image_filename: str, job_id: str) -> Path:
    filename_only = Path(image_filename.split('?')[0]).name
    filepath = settings.IMAGENS_DIR_PATH / job_id / filename_only
    return filepath


# --- Endpoints ---

@router.get("/templates")
async def get_templates_endpoint():
    return settings.listar_templates_ids()

@router.post("/run_main")
async def run_main_simulation_endpoint(payload: AntenaSimPayload):
    try:
        logger.info(f"🛰️  Iniciando simulação principal para job: {payload.job_id}")

        sim_result_from_service = await cloudrf_service.run_cloudrf_simulation(
            lat=payload.lat,
            lon=payload.lon,
            altura=payload.altura,
            altura_receiver=payload.altura_receiver,
            template_id=payload.template,
            is_repeater=False
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

        if not imagem_path_servidor.is_file():
            raise HTTPException(status_code=500, detail="Erro interno: Imagem da simulação principal não encontrada no servidor após cópia.")

        job_input_dir = settings.ARQUIVOS_DIR_PATH / payload.job_id
        metadata_path = job_input_dir / "job_metadata.json"
        metadata_content = {"template_id": payload.template}
        with open(metadata_path, "w") as f:
            json.dump(metadata_content, f, indent=4)
        logger.info(f"💾 Metadados do job {payload.job_id} salvos com template_id: '{payload.template}'")

        logger.info(f"✅ Simulação CloudRF (principal) para job {payload.job_id} concluída.")
        logger.info(f"ℹ️  Analisando cobertura de pivôs para o job {payload.job_id}")

        # Define os dados do overlay da simulação principal para usar na análise
        overlay_principal_info = {
            "id": f"antena_principal_{payload.nome or 'sim'}",
            "imagem_path": imagem_path_servidor,
            "bounds": sim_result_from_service["bounds"]
        }

        # Verifica a cobertura dos pivôs
        pivos_com_status = analysis_service.verificar_cobertura_pivos(
            pivos=[p.model_dump() for p in payload.pivos_atuais],
            overlays_info=[overlay_principal_info]
        )
        logger.info(f"ℹ️  Status dos pivôs (principal) para job {payload.job_id} atualizado.")

        # =================================================================
        # ✅ INÍCIO DA NOVA LÓGICA: VERIFICAR COBERTURA DAS BOMBAS
        # =================================================================
        logger.info(f"ℹ️  Analisando cobertura de bombas para o job {payload.job_id}")
        
        # 1. Carregar dados das bombas do arquivo JSON parseado do KMZ inicial
        parsed_data_path = settings.ARQUIVOS_DIR_PATH / payload.job_id / "parsed_data.json"
        bombas_data = []
        if parsed_data_path.exists():
            with open(parsed_data_path, "r", encoding="utf-8") as f:
                parsed_data = json.load(f)
                bombas_data = parsed_data.get("bombas", [])
        else:
            logger.warning(f"Arquivo 'parsed_data.json' não encontrado para o job {payload.job_id}. Não foi possível verificar as bombas.")

        # 2. Chamar o serviço de análise para as bombas (se houver alguma)
        bombas_com_status = []
        if bombas_data:
            # Assumindo que a função `verificar_cobertura_bombas` existe em `analysis_service`
            bombas_com_status = analysis_service.verificar_cobertura_bombas(
                bombas=bombas_data,
                overlays_info=[overlay_principal_info]
            )
            logger.info(f"ℹ️  Status das bombas (principal) para job {payload.job_id} atualizado.")
        # =================================================================
        # ✅ FIM DA NOVA LÓGICA
        # =================================================================

        return {
            "imagem_salva": imagem_servida_url,
            "imagem_filename": imagem_filename,
            "bounds": sim_result_from_service["bounds"],
            "status": "Simulação principal concluída",
            "pivos": pivos_com_status,
            "bombas": bombas_com_status  # 3. Adiciona o resultado das bombas na resposta da API
        }
    except ValueError as e:
        logger.warning(f"❌ Erro de Validação em /run_main (job: {payload.job_id}): {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Erro Interno em /simulation/run_main (job: {payload.job_id}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro interno na simulação principal: {str(e)}")


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

        # Inicializa listas de resultados
        pivos_atualizados = []
        bombas_atualizadas = []

        if not overlays_para_analise:
            if payload.overlays:
                 logger.warning(f"⚠️ Nenhum arquivo de overlay válido encontrado para o job {payload.job_id}.")
            else:
                logger.info(f"ℹ️ Nenhum overlay ativo fornecido para o job {payload.job_id}. Itens marcados como 'fora'.")
            
            pivos_atualizados = [{"nome": p.nome, "lat": p.lat, "lon": p.lon, "fora": True} for p in payload.pivos]
            if payload.bombas:
                bombas_atualizadas = [{"nome": b.nome, "lat": b.lat, "lon": b.lon, "fora": True} for b in payload.bombas]
        else:
            pivos_atualizados = analysis_service.verificar_cobertura_pivos(
                pivos=[p.model_dump() for p in payload.pivos],
                overlays_info=overlays_para_analise
            )
            if payload.bombas:
                 bombas_atualizadas = analysis_service.verificar_cobertura_bombas(
                    bombas=[b.model_dump() for b in payload.bombas],
                    overlays_info=overlays_para_analise
                 )

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
    try:
        logger.info(f"📡 Buscando locais de repetidora para pivô '{payload.target_pivot_nome}' no job {payload.job_id}.")

        active_overlays_for_analysis = []
        for ov_data in payload.active_overlays:
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