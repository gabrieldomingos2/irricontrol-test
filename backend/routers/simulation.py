# backend/routers/simulation.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field # Field pode não ser usado aqui, mas é bom manter
from typing import List, Dict, Optional, Tuple

# Usa imports absolutos
from backend.services import cloudrf_service, analysis_service
from backend import config # Assume que config.py tem BASE_DIR e STATIC_DIR definidos
import os
import traceback # Para logging de erro detalhado

router = APIRouter(
    prefix="/simulation",
    tags=["Simulation & Analysis"],
)

# 👇 FUNÇÃO AUXILIAR ADICIONADA 👇
def _separar_resultados_por_tipo(
    resultados_combinados: List[Dict],
    nomes_pivos_originais: List[str],
    nomes_bombas_originais: List[str]
) -> Tuple[List[Dict], List[Dict]]:
    """
    Separa uma lista combinada de resultados em listas distintas para pivôs e bombas.
    """
    pivos_finais = []
    bombas_finais = []
    set_nomes_pivos = set(nomes_pivos_originais)
    set_nomes_bombas = set(nomes_bombas_originais)

    for item in resultados_combinados:
        nome_item = item.get("nome")
        if nome_item in set_nomes_pivos:
            pivos_finais.append(item)
        elif nome_item in set_nomes_bombas:
            bombas_finais.append(item)
        else:
            # Este caso não deve acontecer se os nomes forem únicos e as listas originais corretas
            print(f"⚠️ Alerta: Item '{nome_item}' não foi classificado como pivô ou bomba durante a separação.")
            # Você pode decidir adicionar a uma lista 'outros' ou apenas logar.
    return pivos_finais, bombas_finais

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
    bombas_atuais: Optional[List[PivoData]] = []

class ManualSimPayload(BaseModel):
    lat: float
    lon: float
    altura: float
    altura_receiver: float
    template: str
    pivos_atuais: List[PivoData]
    bombas_atuais: Optional[List[PivoData]] = []

class OverlayData(BaseModel):
    id: Optional[str] = None # Adicionado para facilitar a depuração, o frontend envia isso
    imagem: str
    bounds: Tuple[float, float, float, float] # S, W, N, E

class ReavaliarPayload(BaseModel): # ATUALIZADO
    pivos: List[PivoData]
    bombas: Optional[List[PivoData]] = [] # <--- CAMPO ADICIONADO
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
    active_overlays: List[OverlayData]
    pivot_polygons_coords: Optional[List[List[Tuple[float, float]]]] = None

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
        caminho_relativo_servidor = os.path.join(config.STATIC_DIR, "imagens", imagem_nome)
        
        print(f"ℹ️  Imagem principal para análise: {caminho_relativo_servidor}")
        print(f"ℹ️  Bounds da imagem principal: {sim_result['bounds']}")
        
        # Prepara a lista combinada para análise e coleta nomes para separação posterior
        elementos_para_analise = []
        nomes_pivos = [p.nome for p in payload.pivos_atuais]
        nomes_bombas = [] 

        for pivo_data in payload.pivos_atuais:
            elementos_para_analise.append(pivo_data.dict())
        
        if payload.bombas_atuais:
            nomes_bombas = [b.nome for b in payload.bombas_atuais]
            for bomba_data in payload.bombas_atuais:
                elementos_para_analise.append(bomba_data.dict())
        
        print(f"ℹ️  Total de elementos (pivôs+bombas) para análise (principal): {len(elementos_para_analise)}")

        elementos_com_status_combinado = analysis_service.verificar_cobertura_pivos(
            pivos=elementos_para_analise, 
            overlays_info=[{
                "id": "antena_principal_sim_run_main",
                "imagem": caminho_relativo_servidor,
                "bounds": sim_result["bounds"]
            }]
        )
        
        pivos_resultado, bombas_resultado = _separar_resultados_por_tipo(
            elementos_com_status_combinado, nomes_pivos, nomes_bombas
        )
        
        print(f"ℹ️  Status dos pivôs ({len(pivos_resultado)}) e bombas ({len(bombas_resultado)}) após análise (principal).")

        return {
            "imagem_salva": sim_result["imagem_url"], 
            "bounds": sim_result["bounds"],
            "status": "Simulação principal concluída",
            "pivos": pivos_resultado, 
            "bombas_status": bombas_resultado 
        }
    except ValueError as e:
        print(f"❌ Erro de Valor em /simulation/run_main: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"❌ Erro em /simulation/run_main: {str(e)}")
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
            is_repeater=True
        )
        print(f"✅ Resultado da simulação CloudRF (manual): {sim_result.get('imagem_url')}")

        imagem_nome_com_query = os.path.basename(sim_result["imagem_url"])
        imagem_nome = imagem_nome_com_query.split('?')[0]
        caminho_relativo_servidor = os.path.join(config.STATIC_DIR, "imagens", imagem_nome)

        print(f"ℹ️  Imagem manual para análise: {caminho_relativo_servidor}")
        print(f"ℹ️  Bounds da imagem manual: {sim_result['bounds']}")

        # Opcional: Análise parcial apenas para este overlay
        elementos_para_analise_manual = []
        nomes_pivos_manual = [p.nome for p in payload.pivos_atuais]
        nomes_bombas_manual = []

        for pivo_data in payload.pivos_atuais:
            elementos_para_analise_manual.append(pivo_data.dict())
        
        if payload.bombas_atuais:
            nomes_bombas_manual = [b.nome for b in payload.bombas_atuais]
            for bomba_data in payload.bombas_atuais:
                elementos_para_analise_manual.append(bomba_data.dict())
        
        print(f"ℹ️  Total de elementos (pivôs+bombas) para análise parcial (manual): {len(elementos_para_analise_manual)}")

        elementos_com_status_parcial = []
        if elementos_para_analise_manual: # Só analisa se houver elementos
            elementos_com_status_parcial = analysis_service.verificar_cobertura_pivos(
                 pivos=elementos_para_analise_manual,
                 overlays_info=[{
                     "id": "repetidora_sim_run_manual",
                     "imagem": caminho_relativo_servidor,
                     "bounds": sim_result["bounds"]
                 }]
            )
        
        pivos_resultado_manual, bombas_resultado_manual = _separar_resultados_por_tipo(
            elementos_com_status_parcial, nomes_pivos_manual, nomes_bombas_manual
        )
        print(f"ℹ️  Status parcial dos pivôs ({len(pivos_resultado_manual)}) e bombas ({len(bombas_resultado_manual)}) para este overlay manual.")

        return {
            "imagem_salva": sim_result["imagem_url"], 
            "bounds": sim_result["bounds"],
            "status": "Simulação manual concluída",
            "pivos": pivos_resultado_manual, # Descomente ou mantenha conforme a necessidade do frontend
            "bombas_status": bombas_resultado_manual # Descomente ou mantenha
        }
    except ValueError as e:
        print(f"❌ Erro de Valor em /simulation/run_manual: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"❌ Erro em /simulation/run_manual: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro interno na simulação manual: {str(e)}")


@router.post("/reevaluate")
async def reevaluate_pivots_endpoint(payload: ReavaliarPayload):
    """Reavalia a cobertura dos pivôs e bombas com base nos overlays fornecidos."""
    try:
        print(f"🔄 Recebida requisição para /reevaluate")
        
        elementos_para_reavaliacao = []
        nomes_pivos_reav = [p.nome for p in payload.pivos]
        nomes_bombas_reav = [] 

        for pivo_data in payload.pivos:
            elementos_para_reavaliacao.append(pivo_data.dict())
        
        if payload.bombas: 
            nomes_bombas_reav = [b.nome for b in payload.bombas]
            for bomba_data in payload.bombas:
                elementos_para_reavaliacao.append(bomba_data.dict())
        
        print(f"ℹ️  Elementos (pivôs+bombas) para reavaliação: {len(elementos_para_reavaliacao)}")
        print(f"ℹ️  Overlays recebidos para reavaliação: {[(o.id, o.imagem) for o in payload.overlays]}")

        overlays_para_analise = []
        for o in payload.overlays:
            img_path_original_frontend = o.imagem
            img_path_sem_query = img_path_original_frontend.split('?')[0]
            caminho_para_servico = img_path_sem_query
            print(f"  ➡️ Overlay ID: {o.id}, Imagem Original: {o.imagem}, Caminho Processado para Análise: {caminho_para_servico}")
            overlays_para_analise.append({
                "id": o.id, "imagem": caminho_para_servico, "bounds": o.bounds
            })

        elementos_atualizados_combinado = []
        if not overlays_para_analise:
            print("⚠️ Nenhum overlay ativo para análise. Todos os elementos serão marcados como 'fora'.")
            for elem in elementos_para_reavaliacao:
                elem["fora"] = True
            elementos_atualizados_combinado = elementos_para_reavaliacao
        elif not elementos_para_reavaliacao: # Se não há pivôs nem bombas
             print("⚠️ Nenhum pivô ou bomba para reavaliar.")
             # elementos_atualizados_combinado permanecerá uma lista vazia
        else:
            print(f"📞 Chamando analysis_service.verificar_cobertura_pivos com {len(overlays_para_analise)} overlays.")
            elementos_atualizados_combinado = analysis_service.verificar_cobertura_pivos(
                pivos=elementos_para_reavaliacao, 
                overlays_info=overlays_para_analise
            )
        
        pivos_reav_resultado, bombas_reav_resultado = _separar_resultados_por_tipo(
            elementos_atualizados_combinado, nomes_pivos_reav, nomes_bombas_reav
        )
        
        print(f"✅ Pivôs ({len(pivos_reav_resultado)}) e Bombas ({len(bombas_reav_resultado)}) atualizados pela reavaliação.")
        return {
            "pivos": pivos_reav_resultado,
            "bombas_status": bombas_reav_resultado 
        }

    except Exception as e:
        print(f"❌ Erro em /simulation/reevaluate: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao reavaliar elementos: {str(e)}")


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
        print(f"❌ Erro de Valor em /simulation/elevation_profile: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"❌ Erro em /simulation/elevation_profile: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao buscar perfil de elevação: {str(e)}")

@router.post("/find_repeater_sites")
async def find_repeater_sites_endpoint(payload: FindRepeaterSitesPayload):
    """
    Encontra locais altos candidatos DENTRO DAS ÁREAS DE COBERTURA EXISTENTES,
    FORA DOS POLÍGONOS DE PIVÔS, e a uma distância máxima do pivô alvo.
    """
    try:
        print(f"📡 Iniciando busca por locais de repetidora para o pivô: {payload.target_pivot_nome}")
        print(f"ℹ️  Utilizando {len(payload.active_overlays)} áreas de cobertura existentes.")
        if payload.pivot_polygons_coords:
            print(f"ℹ️  Excluindo áreas de {len(payload.pivot_polygons_coords)} polígonos de pivôs.")

        candidate_sites = await analysis_service.encontrar_locais_altos_para_repetidora(
            alvo_lat=payload.target_pivot_lat,
            alvo_lon=payload.target_pivot_lon,
            alvo_nome=payload.target_pivot_nome,
            altura_antena_repetidora_proposta=payload.altura_antena_repetidora_proposta,
            altura_receptor_pivo=payload.altura_receiver_pivo,
            active_overlays_data=[ov.dict() for ov in payload.active_overlays],
            pivot_polygons_coords_data=payload.pivot_polygons_coords
        )
        
        print(f"✅ Busca por locais de repetidora concluída. Encontrados {len(candidate_sites)} candidatos.")
        return {"candidate_sites": candidate_sites}

    except ValueError as ve: 
        print(f"❌ Erro de Validação em /find_repeater_sites: {str(ve)}")
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(ve))
    except FileNotFoundError as fnfe: 
        print(f"❌ Arquivo DEM não encontrado durante a busca: {str(fnfe)}")
        traceback.print_exc()
        raise HTTPException(status_code=404, detail=f"Dados de elevação não encontrados para a área: {str(fnfe)}")
    except NotImplementedError as nie: 
        print(f"❌ Funcionalidade não implementada em /find_repeater_sites: {str(nie)}")
        traceback.print_exc()
        raise HTTPException(status_code=501, detail=str(nie))
    except Exception as e: 
        print(f"❌ Erro Interno em /find_repeater_sites: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro interno ao buscar locais para repetidora: {str(e)}")