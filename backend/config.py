import os

# --- Configurações da API CloudRF ---
# !! ATENÇÃO: É mais seguro carregar a chave de variáveis de ambiente !!
# !! Ex: API_KEY = os.getenv("CLOUDRF_API_KEY", "SUA_CHAVE_PADRAO_SE_NAO_ENCONTRAR")
API_KEY = "35113-e181126d4af70994359d767890b3a4f2604eb0ef"
API_URL = "https://api.cloudrf.com/area"

# --- Configurações Gerais ---
HTTP_TIMEOUT = 60.0  # Timeout em segundos para chamadas HTTP

# --- Templates de Simulação ---
TEMPLATES_DISPONIVEIS = [
    {
        "id": "Brazil_V6",
        "nome": "🇧🇷 Brazil V6",
        "frq": 915,
        "col": "IRRICONTRO.dBm",
        "site": "Brazil_V6", # Nome do template na CloudRF
        "rxs": -90, # Sensibilidade do receptor
        "transmitter": {
            "txw": 0.3,  # Potência em watts
            "bwi": 0.1   # Largura de banda
        },
        "receiver": {
            "lat": 0,    # Latitude (padrão, não usado diretamente aqui)
            "lon": 0,    # Longitude (padrão, não usado diretamente aqui)
            "alt": 3,    # Altura do receiver (pivô) em metros
            "rxg": 3,    # Ganho da antena do receiver
            "rxs": -90   # Sensibilidade do receiver
        },
        "antenna": {
            "txg": 3,    # Ganho da antena transmissora
            "fbr": 3     # Relação frente/costas
        }
    },
    {
        "id": "Europe_V6_XR",
        "nome": "🇪🇺 Europe V6 XR",
        "frq": 868,
        "col": "IRRIEUROPE.dBm",
        "site": "V6_XR.dBm", # Nome do template na CloudRF
        "rxs": -105,
        "transmitter": {
            "txw": 0.02,
            "bwi": 0.05
        },
        "receiver": {
            "lat": 0,
            "lon": 0,
            "alt": 3,
            "rxg": 2.1,
            "rxs": -105
        },
        "antenna": {
            "txg": 2.1,
            "fbr": 2.1
        }
    }
    # Adicione mais templates aqui se necessário
]

# --- Funções Auxiliares de Configuração ---

def obter_template(template_id: str):
    """Retorna os dados de um template pelo seu ID."""
    template = next((t for t in TEMPLATES_DISPONIVEIS if t["id"] == template_id), None)
    if not template:
        # Retorna o primeiro template como padrão se o ID não for encontrado
        print(f"⚠️ Template '{template_id}' não encontrado. Usando padrão.")
        return TEMPLATES_DISPONIVEIS[0]
    return template

def listar_templates_ids():
    """Retorna uma lista com os IDs de todos os templates disponíveis."""
    return [t["id"] for t in TEMPLATES_DISPONIVEIS]

# --- Caminhos ---
STATIC_DIR = "static"
IMAGENS_DIR = os.path.join(STATIC_DIR, "imagens")
ARQUIVOS_DIR = "arquivos"

# Garante que os diretórios existam
os.makedirs(IMAGENS_DIR, exist_ok=True)
os.makedirs(ARQUIVOS_DIR, exist_ok=True)