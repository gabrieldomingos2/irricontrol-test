from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field # Adicionei Field se for usar
from typing import List, Dict, Optional, Tuple

# Usa imports absolutos
from backend.services import cloudrf_service, analysis_service
from backend import config
import os

# ESTA É A LINHA CRUCIAL QUE DEVE ESTAR CORRETA:
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
    imagem: str # Caminho relativo como 'static/imagens/nome_do_arquivo.png'
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

        imagem_nome_com_query = os.path.basename(sim_result["imagem_url"])
        imagem_nome = imagem_nome_com_query.split('?')[0]
        caminho_relativo_para_analise = os.path.join("static", "imagens", imagem_nome)

        pivos_com_status = analysis_service.verificar_cobertura_pivos(
            pivos=[p.dict() for p in payload.pivos_atuais],
            overlays_info=[{
                "imagem": caminho_relativo_para_analise,
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
        print(f"❌ Erro em /simulation/run_main: {e}")
        raise HTTPException(status_code=500, detail=f"Erro interno na simulação principal: {str(e)}")

@router.post("/run_manual")
async def run_manual_simulation_endpoint(payload: ManualSimPayload):
    """Executa uma simulação para uma repetidora manual."""
    try:
        sim_result = await cloudrf_service.run_cloudrf_simulation(
            lat=payload.lat,
            lon=payload.lon,
            altura=int(payload.altura),
            template_id=payload.template,
            is_repeater=True
        )

        imagem_nome_com_query = os.path.basename(sim_result["imagem_url"])
        imagem_nome = imagem_nome_com_query.split('?')[0]
        caminho_relativo_para_analise = os.path.join("static", "imagens", imagem_nome)

        pivos_com_status = analysis_service.verificar_cobertura_pivos(
            pivos=[p.dict() for p in payload.pivos_atuais],
            overlays_info=[{
                "imagem": caminho_relativo_para_analise,
                "bounds": sim_result["bounds"]
            }]
        )

        return {
            "imagem_salva": sim_result["imagem_url"],
            "bounds": sim_result["bounds"],
            "status": "Simulação manual concluída",
            "pivos": pivos_com_status
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"❌ Erro em /simulation/run_manual: {e}")
        raise HTTPException(status_code=500, detail=f"Erro interno na simulação manual: {str(e)}")


@router.post("/reevaluate")
async def reevaluate_pivots_endpoint(payload: ReavaliarPayload):
    """Reavalia a cobertura dos pivôs com base nos overlays fornecidos."""
    try:
        overlays_para_analise = []
        for o in payload.overlays:
            img_path = o.imagem
            # Garante que o caminho da imagem para analysis_service seja relativo à pasta 'backend'
            # Ex: 'static/imagens/nome.png'
            if o.imagem.startswith("http"): # Se for uma URL completa vinda do frontend
                # Tenta extrair 'static/imagens/...' da URL
                # Assume que config.STATIC_DIR é 'static'
                path_part = o.imagem.split(f"/{config.STATIC_DIR}/imagens/", 1)
                if len(path_part) > 1:
                    img_path = os.path.join(config.STATIC_DIR, "imagens", path_part[1].split('?')[0])
                else: # Fallback se não conseguir extrair
                    img_path = os.path.join(config.STATIC_DIR, "imagens", os.path.basename(o.imagem.split('?')[0]))
            elif not o.imagem.startswith(config.STATIC_DIR): # Se for um nome de arquivo e não um path relativo
                 img_path = os.path.join(config.STATIC_DIR, "imagens", o.imagem)


            overlays_para_analise.append({
                "imagem": img_path,
                "bounds": o.bounds
            })

        pivos_atualizados = analysis_service.verificar_cobertura_pivos(
            pivos=[p.dict() for p in payload.pivos],
            overlays_info=overlays_para_analise
        )
        return {"pivos": pivos_atualizados}
    except Exception as e:
        print(f"❌ Erro em /simulation/reevaluate: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao reavaliar pivôs: {str(e)}")


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
        print(f"❌ Erro em /simulation/elevation_profile: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao buscar perfil de elevação: {str(e)}")