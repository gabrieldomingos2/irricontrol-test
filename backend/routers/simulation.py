from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Tuple
from pathlib import Path # Adicionado para manipulação moderna de caminhos
import logging # Adicionado para logging

# Importa o objeto settings e os serviços
from backend.config import settings # Usando o objeto settings centralizado
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
    lat: float
    lon: float
    altura: int
    altura_receiver: Optional[int] = 3
    nome: Optional[str] = "Antena Principal"
    template: str
    pivos_atuais: List[PivoData]

class ManualSimPayload(BaseModel):
    lat: float
    lon: float
    altura: float
    altura_receiver: float
    template: str
    pivos_atuais: List[PivoData]

class OverlayData(BaseModel):
    id: Optional[str] = None
    imagem: str # Esperado ser uma URL relativa como 'static/imagens/nome.png?timestamp=...'
    bounds: Tuple[float, float, float, float] # S, W, N, E

class ReavaliarPayload(BaseModel):
    pivos: List[PivoData]
    overlays: List[OverlayData]

class PerfilPayload(BaseModel):
    pontos: List[Tuple[float, float]]
    altura_antena: float
    altura_receiver: float

class FindRepeaterSitesPayload(BaseModel):
    target_pivot_lat: float
    target_pivot_lon: float
    target_pivot_nome: str
    altura_antena_repetidora_proposta: Optional[float] = 5.0
    altura_receiver_pivo: Optional[float] = 3.0
    active_overlays: List[OverlayData] # Frontend envia lista de OverlayData
    pivot_polygons_coords: Optional[List[List[Tuple[float, float]]]] = None


# --- Funções Auxiliares ---

def _get_image_filepath_for_analysis(image_url_or_relative_path: str) -> Path:
    """
    Converte uma URL de imagem ou caminho relativo para um Path absoluto no servidor.
    """
    path_sem_query = image_url_or_relative_path.split('?')[0]
    # O frontend envia 'imagem' como 'static/imagens/nome_arquivo.png'
    # Precisamos remover o 'static/' se IMAGENS_DIR_PATH já inclui 'static'
    # settings.IMAGENS_DIR_PATH é backend/static/imagens
    # image_url_or_relative_path pode ser 'static/imagens/arquivo.png'
    
    # Se o caminho já começa com o nome da pasta estática, removemos esse prefixo
    # para evitar duplicação ao juntar com settings.IMAGENS_DIR_PATH.
    # No entanto, a lógica atual de apenas pegar Path(path_sem_query).name
    # e juntar com settings.IMAGENS_DIR_PATH é mais robusta se o frontend
    # sempre enviar um caminho que leve ao nome do arquivo.
    
    filename = Path(path_sem_query).name # Extrai 'nome.png'
    filepath = settings.IMAGENS_DIR_PATH / filename
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
        logger.info(f"🛰️ Iniciando simulação principal para: {payload.nome} ({payload.lat}, {payload.lon}), Altura Rec: {payload.altura_receiver}")
        sim_result = await cloudrf_service.run_cloudrf_simulation(
            lat=payload.lat,
            lon=payload.lon,
            altura=payload.altura,
            altura_receiver=payload.altura_receiver,
            template_id=payload.template,
            is_repeater=False
        )
        
        # Usa o imagem_local_path diretamente retornado pelo cloudrf_service
        imagem_path_servidor = Path(sim_result["imagem_local_path"])
        if not imagem_path_servidor.is_file(): # Verificação adicional
            logger.error(f"Arquivo de imagem principal não encontrado em: {imagem_path_servidor} após simulação.")
            raise HTTPException(status_code=500, detail="Erro interno: Imagem da simulação principal não encontrada no servidor.")

        logger.info(f"✅ Simulação CloudRF (principal) URL: {sim_result.get('imagem_url')}, Path Local: {imagem_path_servidor}")

        logger.info(f"ℹ️ Pivôs para análise (principal): {[p.nome for p in payload.pivos_atuais]}")
        pivos_com_status = analysis_service.verificar_cobertura_pivos(
            pivos=[p.model_dump() for p in payload.pivos_atuais],
            overlays_info=[{
                "id": f"antena_principal_{payload.nome or 'sim'}",
                "imagem_path": imagem_path_servidor, # Passando o Path absoluto
                "bounds": sim_result["bounds"]
            }]
        )
        logger.info(f"ℹ️ Status dos pivôs (principal): {pivos_com_status}")

        return {
            "imagem_salva": sim_result["imagem_url"],
            "imagem_filename": sim_result["imagem_filename"],
            "bounds": sim_result["bounds"],
            "status": "Simulação principal concluída",
            "pivos": pivos_com_status
        }
    except ValueError as e:
        logger.warning(f"❌ Erro de Validação em /run_main: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Erro Interno em /simulation/run_main: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro interno na simulação principal: {str(e)}")

@router.post("/run_manual")
async def run_manual_simulation_endpoint(payload: ManualSimPayload):
    """Executa uma simulação para uma repetidora manual."""
    try:
        logger.info(f"📡 Iniciando simulação manual para repetidora em: ({payload.lat}, {payload.lon}), Altura Rec: {payload.altura_receiver}")
        sim_result = await cloudrf_service.run_cloudrf_simulation(
            lat=payload.lat,
            lon=payload.lon,
            altura=int(payload.altura),
            altura_receiver=int(payload.altura_receiver),
            template_id=payload.template,
            is_repeater=True
        )
        # imagem_path_servidor = _get_image_filepath_for_analysis(sim_result["imagem_url"]) # Não é necessário se não for usar para análise aqui
        logger.info(f"✅ Simulação CloudRF (manual) URL: {sim_result.get('imagem_url')}, Path Local: {sim_result.get('imagem_local_path')}")

        return {
            "imagem_salva": sim_result["imagem_url"],
            "imagem_filename": sim_result["imagem_filename"],
            "bounds": sim_result["bounds"],
            "status": "Simulação manual concluída",
        }
    except ValueError as e:
        logger.warning(f"❌ Erro de Validação em /run_manual: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Erro Interno em /simulation/run_manual: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro interno na simulação manual: {str(e)}")

@router.post("/reevaluate")
async def reevaluate_pivots_endpoint(payload: ReavaliarPayload):
    """Reavalia a cobertura dos pivôs com base nos overlays fornecidos."""
    try:
        logger.info(f"🔄 Reavaliando cobertura para {len(payload.pivos)} pivôs com {len(payload.overlays)} overlays.")
        
        overlays_para_analise = []
        if payload.overlays:
            for o_data in payload.overlays:
                imagem_path_servidor = _get_image_filepath_for_analysis(o_data.imagem)
                if not imagem_path_servidor.is_file():
                    logger.warning(f"Arquivo de imagem não encontrado para overlay ID '{o_data.id}': {imagem_path_servidor}. Pulando este overlay.")
                    continue

                overlays_para_analise.append({
                    "id": o_data.id or f"overlay_{Path(o_data.imagem).stem}",
                    "imagem_path": imagem_path_servidor,
                    "bounds": o_data.bounds
                })
        
        if not overlays_para_analise and payload.overlays:
             logger.warning("⚠️ Nenhum arquivo de overlay válido encontrado. Pivôs serão marcados como 'fora'.")
             pivos_atualizados = [{"nome": p.nome, "lat": p.lat, "lon": p.lon, "fora": True} for p in payload.pivos]
        elif not overlays_para_analise and not payload.overlays:
            logger.info("ℹ️ Nenhum overlay ativo fornecido. Todos os pivôs serão marcados como 'fora'.")
            pivos_atualizados = [{"nome": p.nome, "lat": p.lat, "lon": p.lon, "fora": True} for p in payload.pivos]
        else:
            logger.info(f"📞 Chamando analysis_service.verificar_cobertura_pivos com {len(overlays_para_analise)} overlays válidos.")
            pivos_atualizados = analysis_service.verificar_cobertura_pivos(
                pivos=[p.model_dump() for p in payload.pivos],
                overlays_info=overlays_para_analise
            )
        
        logger.info(f"✅ Pivôs atualizados pela reavaliação.")
        return {"pivos": pivos_atualizados}

    except Exception as e:
        logger.error(f"❌ Erro em /simulation/reevaluate: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro ao reavaliar pivôs: {str(e)}")

@router.post("/elevation_profile")
async def get_elevation_profile_endpoint(payload: PerfilPayload):
    """Calcula e retorna o perfil de elevação e o ponto de bloqueio."""
    try:
        logger.info(f"⛰️ Calculando perfil de elevação para {len(payload.pontos)} pontos.")
        resultado = await analysis_service.obter_perfil_elevacao(
            pontos=payload.pontos,
            alt1=payload.altura_antena,
            alt2=payload.altura_receiver
        )
        logger.info(f"✅ Perfil de elevação calculado.")
        return resultado
    except ValueError as e:
        logger.warning(f"❌ Erro de Validação em /elevation_profile: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Erro Interno em /simulation/elevation_profile: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro ao buscar perfil de elevação: {str(e)}")

@router.post("/find_repeater_sites")
async def find_repeater_sites_endpoint(payload: FindRepeaterSitesPayload):
    """Encontra locais candidatos para repetidoras."""
    try:
        logger.info(f"📡 Buscando locais de repetidora para pivô: {payload.target_pivot_nome} ({len(payload.active_overlays)} overlays ativos).")
        
        active_overlays_for_analysis = []
        for ov_data in payload.active_overlays: 
            imagem_path_servidor = _get_image_filepath_for_analysis(ov_data.imagem)
            if not imagem_path_servidor.is_file():
                logger.warning(f"Arquivo de imagem não encontrado para overlay ID '{ov_data.id}' em find_repeater_sites: {imagem_path_servidor}. Pulando.")
                continue
            active_overlays_for_analysis.append({
                "id": ov_data.id or f"overlay_{Path(ov_data.imagem).stem}",
                "imagem_path": imagem_path_servidor, 
                "bounds": ov_data.bounds
            })

        if not active_overlays_for_analysis and payload.active_overlays:
             logger.warning("⚠️ Nenhum arquivo de overlay válido encontrado para busca de repetidoras.")
             return {"candidate_sites": []}
        if not active_overlays_for_analysis and not payload.active_overlays:
            logger.info("ℹ️ Nenhum overlay ativo fornecido para busca de repetidoras.")
            return {"candidate_sites": []}

        candidate_sites = await analysis_service.encontrar_locais_altos_para_repetidora(
            alvo_lat=payload.target_pivot_lat,
            alvo_lon=payload.target_pivot_lon,
            alvo_nome=payload.target_pivot_nome,
            altura_antena_repetidora_proposta=payload.altura_antena_repetidora_proposta,
            altura_receptor_pivo=payload.altura_receiver_pivo,
            # A linha que passava [ov.model_dump() for ov in payload.active_overlays] foi removida.
            # Agora passamos a lista processada que contém os paths de imagem corretos.
            active_overlays_data=active_overlays_for_analysis, # << CORREÇÃO APLICADA
            pivot_polygons_coords_data=payload.pivot_polygons_coords
        )
        
        logger.info(f"✅ Busca por locais de repetidora concluída. {len(candidate_sites)} candidatos.")
        return {"candidate_sites": candidate_sites}

    except ValueError as ve:
        logger.warning(f"❌ Erro de Validação em /find_repeater_sites: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    except FileNotFoundError as fnfe:
        logger.error(f"❌ Arquivo DEM não encontrado: {fnfe}", exc_info=True)
        raise HTTPException(status_code=404, detail=f"Dados de elevação não encontrados: {str(fnfe)}")
    except NotImplementedError as nie:
        logger.error(f"❌ Funcionalidade não implementada: {nie}", exc_info=True)
        raise HTTPException(status_code=501, detail=str(nie))
    except Exception as e:
        logger.error(f"❌ Erro Interno em /find_repeater_sites: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro interno ao buscar locais para repetidora: {str(e)}")
