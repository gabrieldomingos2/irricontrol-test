from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Tuple

from ..services import cloudrf_service, analysis_service
from .. import config
import os # Precisamos para construir o caminho da imagem no reavaliar

router = APIRouter(
    prefix="/simulation", # Adiciona /simulation antes de cada endpoint aqui
    tags=["Simulation & Analysis"], # Agrupa na documentação /docs
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
    imagem: str # Caminho relativo: 'static/imagens/...'
    bounds: Tuple[float, float, float, float] # S, W, N, E

class ReavaliarPayload(BaseModel):
    pivos: List[PivoData]
    overlays: List[OverlayData]

class PerfilPayload(BaseModel):
    pontos: List[Tuple[float, float]]
    altura_antena: float
    altura_receiver: float

# --- Endpoints ---

@router.get("/templates")
def get_templates_endpoint():
    """Retorna a lista de IDs dos templates disponíveis."""
    return config.listar_templates_ids()

@router.post("/run_main")
async def run_main_simulation_endpoint(payload: AntenaSimPayload):
    """Executa a simulação principal a partir da antena."""
    try:
        sim_result = await cloudrf_service.run_cloudrf_simulation(
            lat=payload.lat,
            lon=payload.lon,
            altura=payload.altura,
            template_id=payload.template,
            is_repeater=False
        )
        
        # Pega o caminho local da imagem gerada para análise
        imagem_nome = os.path.basename(sim_result["imagem_url"].split('?')[0]) # Remove query params se houver
        caminho_imagem_local = os.path.join(config.IMAGENS_DIR, imagem_nome)
        
        # Verifica a cobertura usando a imagem recém-gerada
        pivos_com_status = analysis_service.verificar_cobertura_pivos(
            pivos=[p.dict() for p in payload.pivos_atuais],
            overlays_info=[{
                "imagem": os.path.join(config.STATIC_DIR, "imagens", imagem_nome),
                "bounds": sim_result["bounds"]
            }]
        )

        return {
            "imagem_salva": sim_result["imagem_url"],
            "bounds": sim_result["bounds"],
            "status": "Simulação principal concluída",
            "pivos": pivos_com_status
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"❌ Erro em /run_main: {e}")
        raise HTTPException(status_code=500, detail=f"Erro interno na simulação principal: {e}")

@router.post("/run_manual")
async def run_manual_simulation_endpoint(payload: ManualSimPayload):
    """Executa uma simulação para uma repetidora manual."""
    try:
        sim_result = await cloudrf_service.run_cloudrf_simulation(
            lat=payload.lat,
            lon=payload.lon,
            altura=int(payload.altura), # CloudRF espera int? Se não, use float.
            template_id=payload.template,
            is_repeater=True
        )

        # Pega o caminho local da imagem gerada para análise
        imagem_nome = os.path.basename(sim_result["imagem_url"].split('?')[0])
        caminho_imagem_local = os.path.join(config.IMAGENS_DIR, imagem_nome)

        # Verifica a cobertura (poderia ser feito no frontend ou aqui)
        # Por enquanto, retornamos a imagem e o frontend pode chamar /reavaliar
        # Ou, podemos reavaliar aqui mesmo, mas precisaríamos dos overlays existentes.
        # Vamos retornar como no original e deixar /reavaliar fazer o trabalho cumulativo.
        
        # No entanto, o original *fazia* uma detecção inicial. Vamos replicar isso.
        pivos_com_status = analysis_service.verificar_cobertura_pivos(
            pivos=[p.dict() for p in payload.pivos_atuais],
            overlays_info=[{
                "imagem": os.path.join(config.STATIC_DIR, "imagens", imagem_nome),
                "bounds": sim_result["bounds"]
            }]
        )
        
        return {
            "imagem_salva": sim_result["imagem_url"],
            "bounds": sim_result["bounds"],
            "status": "Simulação manual concluída",
            "pivos": pivos_com_status # Retorna pivôs com status *apenas* desta repetidora
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"❌ Erro em /run_manual: {e}")
        raise HTTPException(status_code=500, detail=f"Erro interno na simulação manual: {e}")


@router.post("/reevaluate")
async def reevaluate_pivots_endpoint(payload: ReavaliarPayload):
    """Reavalia a cobertura dos pivôs com base nos overlays fornecidos."""
    try:
        pivos_atualizados = analysis_service.verificar_cobertura_pivos(
            pivos=[p.dict() for p in payload.pivos],
            overlays_info=[o.dict() for o in payload.overlays]
        )
        return {"pivos": pivos_atualizados}
    except Exception as e:
        print(f"❌ Erro em /reevaluate: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao reavaliar pivôs: {e}")


@router.post("/elevation_profile")
async def get_elevation_profile_endpoint(payload: PerfilPayload):
    """Calcula e retorna o perfil de elevação e o ponto de bloqueio."""
    try:
        resultado = await analysis_service.obter_perfil_elevacao(
            pontos=payload.pontos,
            alt1=payload.altura_antena,
            alt2=payload.altura_receiver
        )
        return resultado
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"❌ Erro em /elevation_profile: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao buscar perfil de elevação: {e}")