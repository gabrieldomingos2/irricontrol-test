import httpx
import json
import os
from . import config  # Importa as configurações (API_KEY, URL, etc.)

# --- Funções Auxiliares ---

def format_coord(coord: float) -> str:
    """Formata coordenada para nomes de arquivos (igual ao JS)."""
    return f"{coord:.6f}".replace(".", "_").replace("-", "m")

async def get_http_client() -> httpx.AsyncClient:
    """Retorna um cliente HTTP assíncrono com timeout global."""
    return httpx.AsyncClient(timeout=httpx.Timeout(config.HTTP_TIMEOUT))

async def download_image(url: str, local_path: str):
    """Baixa uma imagem de uma URL e salva localmente."""
    print(f"   -> Baixando imagem de: {url}")
    try:
        async with await get_http_client() as client:
            r = await client.get(url)
            r.raise_for_status()  # Lança exceção para erros HTTP (4xx ou 5xx)
        
        with open(local_path, "wb") as f:
            f.write(r.content)
        print(f"   -> Imagem salva em: {local_path}")
        return True
    except httpx.HTTPStatusError as e:
        print(f"   -> ❌ Erro HTTP ao baixar imagem: {e.response.status_code} - {e.response.text}")
        raise ValueError(f"Falha ao baixar imagem de sinal. Status {e.response.status_code}")
    except Exception as e:
        print(f"   -> ❌ Erro crítico no download: {e}")
        raise ValueError(f"Falha crítica ao baixar imagem: {e}")

def save_bounds(bounds: list, local_path: str):
    """Salva os dados de bounds em um arquivo JSON."""
    json_path = local_path.replace(".png", ".json")
    try:
        with open(json_path, "w") as f:
            json.dump({"bounds": bounds}, f)
        print(f"   -> Bounds salvos em: {json_path}")
    except Exception as e:
        print(f"   -> ❌ Erro ao salvar bounds: {e}")

# --- Função Principal de Simulação ---

async def run_cloudrf_simulation(
    lat: float,
    lon: float,
    altura: int,
    template_id: str,
    is_repeater: bool = False
) -> dict:
    """
    Executa uma simulação na CloudRF, baixa a imagem e retorna os dados.

    Args:
        lat: Latitude do transmissor.
        lon: Longitude do transmissor.
        altura: Altura do transmissor em metros.
        template_id: ID do template a ser usado (ex: "Brazil_V6").
        is_repeater: Define se é uma repetidora (afeta nome do arquivo).

    Returns:
        Um dicionário com "imagem_url" e "bounds".
    """
    print(f"📡 Iniciando simulação CloudRF para ({lat:.6f}, {lon:.6f}) - Template: {template_id}")
    
    tpl = config.obter_template(template_id)
    
    payload = {
        "version": "CloudRF-API-v3.24",
        "site": tpl["site"],
        "network": f"Irricontrol Sim - {'Rep' if is_repeater else 'Main'}",
        "engine": 2,
        "coordinates": 1,
        "transmitter": {
            "lat": lat,
            "lon": lon,
            "alt": altura,
            "frq": tpl["frq"],
            "txw": tpl["transmitter"]["txw"],
            "bwi": tpl["transmitter"]["bwi"],
            "powerUnit": "W"
        },
        "receiver": {
            "lat": tpl["receiver"]["lat"],
            "lon": tpl["receiver"]["lon"],
            "alt": tpl["receiver"]["alt"],
            "rxg": tpl["receiver"]["rxg"],
            "rxs": tpl["receiver"]["rxs"]
        },
        "feeder": {"flt": 1, "fll": 0, "fcc": 0},
        "antenna": {
            "mode": "template",
            "txg": tpl["antenna"]["txg"],
            "txl": 0,
            "ant": 1,
            "azi": 0,
            "tlt": 0,
            "hbw": 360,
            "vbw": 90,
            "fbr": tpl["antenna"]["fbr"],
            "pol": "v"
        },
        "model": {"pm": 1, "pe": 2, "ked": 4, "rel": 95, "rcs": 1},
        "environment": {"elevation": 1, "landcover": 1, "buildings": 0, "clt": "Minimal.clt"},
        "output": {
            "units": "m",
            "col": tpl["col"],
            "out": 2, # PNG WGS84
            "ber": 1, "mod": 7, "nf": -120,
            "res": 30, # Resolução (metros)
            "rad": 10  # Raio (km) - Ajuste se necessário
        }
    }

    headers = {"key": config.API_KEY, "Content-Type": "application/json"}

    print("   -> Enviando payload para CloudRF...")
    async with await get_http_client() as client:
        try:
            resposta = await client.post(config.API_URL, headers=headers, json=payload)
            resposta.raise_for_status() # Lança exceção para erros HTTP
            data = resposta.json()
            print("   -> Resposta recebida da CloudRF.")
        except httpx.HTTPStatusError as e:
            print(f"   -> ❌ Erro HTTP na API CloudRF: {e.response.status_code} - {e.response.text}")
            raise ValueError(f"Erro na API CloudRF: {e.response.text}")
        except Exception as e:
            print(f"   -> ❌ Erro ao chamar CloudRF: {e}")
            raise ValueError(f"Erro de comunicação com a API: {e}")

    imagem_url_api = data.get("PNG_WGS84")
    bounds = data.get("bounds")

    if not imagem_url_api or not bounds:
        print("   -> ❌ Resposta inválida da CloudRF:", data)
        raise ValueError("Resposta inválida da API CloudRF (sem URL ou bounds).")

    # Gera nome do arquivo local
    lat_str = format_coord(lat)
    lon_str = format_coord(lon)
    prefix = "repetidora" if is_repeater else "sinal"
    nome_arquivo = f"{prefix}_{tpl['id'].lower()}_{lat_str}_{lon_str}.png"
    caminho_local = os.path.join(config.IMAGENS_DIR, nome_arquivo)

    # Baixa a imagem e salva os bounds
    await download_image(imagem_url_api, caminho_local)
    save_bounds(bounds, caminho_local)

    # Monta a URL para o frontend acessar a imagem (assumindo que o backend serve /static)
    # IMPORTANTE: A URL base deve ser a URL pública do seu backend no Render.
    # Se rodar localmente, seria algo como "http://127.0.0.1:8000"
    # Você pode colocar isso no config.py também.
    backend_public_url = os.getenv("BACKEND_URL", "https://irricontrol-test.onrender.com") # Exemplo
    
    imagem_servida_url = f"{backend_public_url}/{config.STATIC_DIR}/imagens/{nome_arquivo}"

    return {"imagem_url": imagem_servida_url, "bounds": bounds}