from PIL import Image
import httpx
import os
from math import sqrt
from . import config
from . import cloudrf_service # Para usar o get_http_client

# --- Análise de Cobertura ---

def verificar_cobertura_pivos(pivos: list, overlays_info: list) -> list:
    """
    Verifica quais pivôs estão cobertos por pelo menos um dos overlays fornecidos.

    Args:
        pivos: Lista de dicionários de pivôs ({'nome': str, 'lat': float, 'lon': float}).
        overlays_info: Lista de dicionários de overlays 
                       ({'imagem': str, 'bounds': [s, w, n, e]}).

    Returns:
        A lista de pivôs atualizada com a chave 'fora' (True ou False).
    """
    print(f"🔎 Verificando cobertura para {len(pivos)} pivôs com {len(overlays_info)} overlays.")
    
    # Cache para imagens abertas para evitar reabrir a mesma imagem várias vezes
    imagens_abertas = {}
    
    pivos_atualizados = []

    for pivo in pivos:
        lat, lon = pivo["lat"], pivo["lon"]
        coberto = False

        for overlay in overlays_info:
            bounds = overlay["bounds"]  # [sul, oeste, norte, leste]
            imagem_rel_path = overlay["imagem"] # Vem como 'static/imagens/...'
            
            # Constrói o caminho completo no servidor
            imagem_full_path = os.path.join(os.getcwd(), 'backend', imagem_rel_path)

            if not os.path.exists(imagem_full_path):
                print(f"   -> ⚠️ Imagem não encontrada: {imagem_full_path}")
                continue

            try:
                # Usa cache para abrir a imagem
                if imagem_full_path not in imagens_abertas:
                    imagens_abertas[imagem_full_path] = Image.open(imagem_full_path).convert("RGBA")
                
                img = imagens_abertas[imagem_full_path]
                largura, altura_img = img.size # Renomeado para não conflitar

                sul, oeste, norte, leste = bounds
                # Garante a ordem correta
                if sul > norte: sul, norte = norte, sul
                if oeste > leste: oeste, leste = leste, oeste

                # Evita divisão por zero se bounds forem iguais
                delta_lon = leste - oeste
                delta_lat = norte - sul
                if delta_lon == 0 or delta_lat == 0:
                    continue

                # Calcula posição do pivô na imagem
                x = int((lon - oeste) / delta_lon * largura)
                y = int((norte - lat) / delta_lat * altura_img)

                # Verifica se está dentro dos limites da imagem
                if 0 <= x < largura and 0 <= y < altura_img:
                    _, _, _, a = img.getpixel((x, y)) # Pega apenas o canal Alpha (transparência)
                    # Se o pixel não for transparente (a > 0), está coberto
                    if a > 50: # Usar um limiar > 0 para mais robustez
                        coberto = True
                        break  # Se já está coberto por um, não precisa checar os outros

            except FileNotFoundError:
                 print(f"   -> ⚠️ Imagem não encontrada (verificação dupla): {imagem_full_path}")
            except Exception as e:
                print(f"   -> ❌ Erro ao analisar overlay {imagem_rel_path} para {pivo['nome']}: {e}")

        pivo["fora"] = not coberto
        pivos_atualizados.append(pivo)
        # print(f"   -> Pivô {pivo['nome']}: {'Coberto' if coberto else 'Fora'}")

    # Fecha todas as imagens abertas
    for img in imagens_abertas.values():
        img.close()

    print("   -> Verificação de cobertura concluída.")
    return pivos_atualizados


# --- Análise de Elevação ---

async def obter_perfil_elevacao(pontos: list, alt1: float, alt2: float) -> dict:
    """
    Busca elevações e calcula se há bloqueio de visada.

    Args:
        pontos: Lista com 2 pontos [[lat1, lon1], [lat2, lon2]].
        alt1: Altura do ponto 1 (antena) em metros.
        alt2: Altura do ponto 2 (receiver) em metros.

    Returns:
        Um dicionário com "bloqueio" (dados do ponto de bloqueio) e "elevacao".
    """
    if len(pontos) != 2:
        raise ValueError("São necessários exatamente dois pontos.")

    steps = 50  # Número de pontos amostrados entre os dois extremos
    print(f"⛰️  Calculando perfil de elevação com {steps} passos...")

    # Gera os pontos intermediários para a API
    amostrados = [
        (
            pontos[0][0] + (pontos[1][0] - pontos[0][0]) * i / steps,
            pontos[0][1] + (pontos[1][1] - pontos[0][1]) * i / steps
        )
        for i in range(steps + 1)
    ]

    coords_param = "|".join([f"{lat:.6f},{lon:.6f}" for lat, lon in amostrados])
    url = f"https://api.opentopodata.org/v1/srtm90m?locations={coords_param}"

    print("   -> Buscando elevações na OpenTopoData...")
    async with await cloudrf_service.get_http_client() as client:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            dados = resp.json()
        except Exception as e:
            print(f"   -> ❌ Erro ao buscar elevações: {e}")
            raise ValueError(f"Falha ao buscar dados de elevação: {e}")

    if not dados or "results" not in dados or not dados["results"]:
        raise ValueError("Resposta inválida ou vazia da API de elevação.")

    elevs = [r["elevation"] for r in dados["results"]]
    print(f"   -> Elevações recebidas (Min: {min(elevs):.1f}m, Max: {max(elevs):.1f}m)")

    # Adiciona as alturas dos equipamentos às elevações dos extremos
    elev1_total = elevs[0] + alt1
    elev2_total = elevs[-1] + alt2

    # Calcula a linha de visada (Fresnel simplificada)
    linha_visada = [
        elev1_total + i * (elev2_total - elev1_total) / steps
        for i in range(steps + 1)
    ]

    # Detecta o ponto de maior bloqueio (se houver)
    bloqueio = None
    max_diferenca = 0

    # Ignora os dois primeiros e os dois últimos pontos para evitar ruídos perto das torres
    for i in range(2, steps - 1): 
        elev_terreno = elevs[i]
        elev_visada = linha_visada[i]
        
        # Considera bloqueio se o terreno estiver acima da linha de visada
        if elev_terreno > elev_visada:
            diferenca = elev_terreno - elev_visada
            if diferenca > max_diferenca:
                max_diferenca = diferenca
                bloqueio = {
                    "lat": amostrados[i][0],
                    "lon": amostrados[i][1],
                    "elev": elev_terreno,
                    "diff": diferenca
                }

    if bloqueio:
        print(f"   -> ⛔ Bloqueio detectado! Diferença máx: {max_diferenca:.1f}m")
    else:
        print("   -> ✅ Visada livre!")


    return {"bloqueio": bloqueio, "elevacao": elevs}