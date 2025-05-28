from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Tuple

# Usa imports absolutos
from backend.services import cloudrf_service, analysis_service
from backend import config # Assume que config.py tem BASE_DIR e STATIC_DIR definidos
import os

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
    # Se você quiser enviar o status atual do frontend para o backend para depuração:
    # statusAtualCor: Optional[str] = None 

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
    id: Optional[str] = None # Adicionado para facilitar a depuração, o frontend envia isso
    imagem: str 
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
        print(f"🛰️  Iniciando simulação principal para: {payload.nome} ({payload.lat}, {payload.lon})")
        sim_result = await cloudrf_service.run_cloudrf_simulation(
            lat=payload.lat,
            lon=payload.lon,
            altura=payload.altura,
            template_id=payload.template,
            is_repeater=False
        )
        print(f"✅ Resultado da simulação CloudRF (principal): {sim_result.get('imagem_url')}")

        imagem_nome_com_query = os.path.basename(sim_result["imagem_url"])
        imagem_nome = imagem_nome_com_query.split('?')[0]
        # Caminho relativo como o frontend espera e como o analysis_service pode precisar
        caminho_relativo_servidor = os.path.join(config.STATIC_DIR, "imagens", imagem_nome)
        
        print(f"ℹ️  Imagem principal para análise: {caminho_relativo_servidor}")
        print(f"ℹ️  Bounds da imagem principal: {sim_result['bounds']}")
        print(f"ℹ️  Pivôs recebidos para análise (principal): {[p.nome for p in payload.pivos_atuais]}")


        pivos_com_status = analysis_service.verificar_cobertura_pivos(
            pivos=[p.dict() for p in payload.pivos_atuais],
            overlays_info=[{
                "id": "antena_principal_sim_run_main", # ID para depuração
                "imagem": caminho_relativo_servidor, # Deve ser o caminho que o analysis_service espera
                "bounds": sim_result["bounds"]
            }]
        )
        print(f"ℹ️  Status dos pivôs após análise (principal): {pivos_com_status}")

        return {
            "imagem_salva": sim_result["imagem_url"], # URL completa para o frontend
            "bounds": sim_result["bounds"],
            "status": "Simulação principal concluída",
            "pivos": pivos_com_status
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"❌ Erro em /simulation/run_main: {e}")
        # Adicionar mais detalhes do erro no log do servidor
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro interno na simulação principal: {str(e)}")

@router.post("/run_manual")
async def run_manual_simulation_endpoint(payload: ManualSimPayload):
    """Executa uma simulação para uma repetidora manual."""
    try:
        print(f"📡 Iniciando simulação manual para repetidora em: ({payload.lat}, {payload.lon})")
        sim_result = await cloudrf_service.run_cloudrf_simulation(
            lat=payload.lat,
            lon=payload.lon,
            altura=int(payload.altura),
            template_id=payload.template,
            is_repeater=True # ou um nome específico se precisar
        )
        print(f"✅ Resultado da simulação CloudRF (manual): {sim_result.get('imagem_url')}")

        imagem_nome_com_query = os.path.basename(sim_result["imagem_url"])
        imagem_nome = imagem_nome_com_query.split('?')[0]
        caminho_relativo_servidor = os.path.join(config.STATIC_DIR, "imagens", imagem_nome)

        print(f"ℹ️  Imagem manual para análise: {caminho_relativo_servidor}")
        print(f"ℹ️  Bounds da imagem manual: {sim_result['bounds']}")
        print(f"ℹ️  Pivôs recebidos para análise (manual): {[p.nome for p in payload.pivos_atuais]}")

        # Nota: /run_manual geralmente só retorna o overlay da repetidora.
        # A reavaliação de TODOS os pivôs com TODOS os overlays ativos
        # é feita pelo endpoint /reevaluate.
        # Se você quiser que /run_manual também retorne os pivôs atualizados APENAS por esta repetidora:
        pivos_com_status_para_este_overlay = analysis_service.verificar_cobertura_pivos(
             pivos=[p.dict() for p in payload.pivos_atuais],
             overlays_info=[{
                 "id": "repetidora_sim_run_manual", # ID para depuração
                 "imagem": caminho_relativo_servidor,
                 "bounds": sim_result["bounds"]
             }]
        )
        print(f"ℹ️  Status dos pivôs (considerando apenas este overlay manual): {pivos_com_status_para_este_overlay}")


        return {
            "imagem_salva": sim_result["imagem_url"], # URL completa para o frontend
            "bounds": sim_result["bounds"],
            "status": "Simulação manual concluída",
            # "pivos": pivos_com_status_para_este_overlay # Descomente se quiser este comportamento
            # Normalmente, o frontend chama /reevaluate após isso para obter o status combinado.
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"❌ Erro em /simulation/run_manual: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro interno na simulação manual: {str(e)}")


@router.post("/reevaluate")
async def reevaluate_pivots_endpoint(payload: ReavaliarPayload):
    """Reavalia a cobertura dos pivôs com base nos overlays fornecidos."""
    try:
        print(f"🔄 Recebida requisição para /reevaluate")
        print(f"ℹ️  Pivôs recebidos para reavaliação: {[p.nome for p in payload.pivos]}")
        print(f"ℹ️  Overlays recebidos para reavaliação: {[(o.id, o.imagem) for o in payload.overlays]}")

        overlays_para_analise = []
        for o in payload.overlays:
            img_path_original_frontend = o.imagem # Ex: 'static/imagens/nome.png?timestamp=...'
            
            # Remove query string se houver
            img_path_sem_query = img_path_original_frontend.split('?')[0]

            # O frontend já deve estar enviando o caminho relativo correto (ex: "static/imagens/nome.png")
            # após o `BACKEND_URL + '/'` ser removido.
            # Se `img_path_sem_query` já é "static/imagens/nome.png", não precisa de mais manipulação.
            # Se for apenas "nome.png", precisa do `os.path.join`.
            
            # Vamos assumir que o frontend envia o caminho como "static/imagens/arquivo.png"
            # Esta é a forma como o frontend main.js foi instruído a enviar:
            # imagem: antenaGlobal.overlay._url.replace(BACKEND_URL + '/', '')
            # ou imagem: rep.overlay._url.replace(BACKEND_URL + '/', '')
            # que resultaria em algo como 'static/imagens/generated_image.png?timestamp=123'
            # e após split('?')[0] seria 'static/imagens/generated_image.png'

            # Se o `analysis_service` espera caminhos relativos a partir da raiz do projeto
            # e `config.STATIC_DIR` é 'static', então o `img_path_sem_query` já deve ser o caminho relativo correto.
            
            # Verifique se `config.STATIC_DIR` está definido e é 'static'
            # E se `config.IMAGENS_DIR_SUBPATH` (ou similar) é 'imagens'
            # O caminho final para `analysis_service` deve ser algo como 'static/imagens/nome.png'
            # se o `analysis_service` constrói o caminho absoluto a partir da raiz do projeto.

            # A lógica de normalização que você tinha:
            caminho_para_servico = img_path_sem_query # Começa com o caminho limpo
            
            # Se o caminho já começa com o diretório estático (ex: "static/imagens/..."), está ok.
            # Se não, e for apenas um nome de arquivo, prefixamos.
            # (Esta parte da sua lógica original parecia tentar cobrir vários casos)
            # if not caminho_para_servico.startswith(config.STATIC_DIR):
            #    caminho_para_servico = os.path.join(config.STATIC_DIR, "imagens", os.path.basename(caminho_para_servico))
            # A linha acima pode ser perigosa se `caminho_para_servico` já for "static/imagens/..."
            # pois resultaria em "static/imagens/static/imagens/..."

            # Simplificação: Assume que o frontend envia 'static/imagens/nome.png'
            # Se o seu `analysis_service` precisar de um caminho absoluto:
            # caminho_abs_para_servico = os.path.join(config.BASE_DIR, caminho_para_servico)
            # Se precisar apenas do relativo à raiz do projeto, `caminho_para_servico` já é isso.

            print(f"  ➡️ Overlay ID: {o.id}, Imagem Original: {o.imagem}, Caminho Processado para Análise: {caminho_para_servico}")

            overlays_para_analise.append({
                "id": o.id, # Passa o ID para o serviço, pode ser útil para logs no serviço
                "imagem": caminho_para_servico, # O caminho que analysis_service.verificar_cobertura_pivos espera
                "bounds": o.bounds
            })

        if not overlays_para_analise:
            print("⚠️ Nenhum overlay ativo para análise. Todos os pivôs serão marcados como 'fora'.")
            # Se não há overlays, todos os pivôs estão "fora"
            pivos_atualizados = [{"nome": p.nome, "lat": p.lat, "lon": p.lon, "fora": True} for p in payload.pivos]
        else:
            print(f"📞 Chamando analysis_service.verificar_cobertura_pivos com {len(overlays_para_analise)} overlays.")
            pivos_atualizados = analysis_service.verificar_cobertura_pivos(
                pivos=[p.dict() for p in payload.pivos],
                overlays_info=overlays_para_analise # Esta lista contém todos os overlays ativos
            )
        
        print(f"✅ Pivôs atualizados pela reavaliação: {pivos_atualizados}")
        return {"pivos": pivos_atualizados}

    except Exception as e:
        print(f"❌ Erro em /simulation/reevaluate: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao reavaliar pivôs: {str(e)}")


@router.post("/elevation_profile")
async def get_elevation_profile_endpoint(payload: PerfilPayload):
    """Calcula e retorna o perfil de elevação e o ponto de bloqueio."""
    try:
        print(f"⛰️  Calculando perfil de elevação para pontos: {payload.pontos}")
        resultado = await analysis_service.obter_perfil_elevacao(
            pontos=payload.pontos,
            alt1=payload.altura_antena,
            alt2=payload.altura_receiver
        )
        print(f"✅ Perfil de elevação calculado.")
        return resultado
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"❌ Erro em /simulation/elevation_profile: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao buscar perfil de elevação: {str(e)}")