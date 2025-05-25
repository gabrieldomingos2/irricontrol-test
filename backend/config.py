import os

# --- Configurações da API CloudRF ---
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
    template = next((t for t in TEMPLATES_DISPONIVEIS if t["id"] == template_id), None)
    if not template:
        print(f"⚠️ Template '{template_id}' não encontrado. Usando padrão '{TEMPLATES_DISPONIVEIS[0]['id']}'.")
        return TEMPLATES_DISPONIVEIS[0]
    return template

def listar_templates_ids():
    return [t["id"] for t in TEMPLATES_DISPONIVEIS]

# --- Caminhos (Usando __file__ para referência absoluta DENTRO do pacote backend) ---

# Diretório raiz do pacote 'backend' (onde este config.py está)
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))

STATIC_DIR_NAME = "static"          # Apenas o nome da pasta
IMAGENS_DIR_NAME = "imagens"        # Apenas o nome da subpasta
ARQUIVOS_DIR_NAME = "arquivos"      # Apenas o nome da pasta

# Caminhos absolutos construídos a partir de BACKEND_DIR
# Ex: /opt/render/project/src/backend/static
STATIC_DIR_PATH = os.path.join(BACKEND_DIR, STATIC_DIR_NAME)
# Ex: /opt/render/project/src/backend/static/imagens
IMAGENS_DIR_PATH = os.path.join(STATIC_DIR_PATH, IMAGENS_DIR_NAME)
# Ex: /opt/render/project/src/backend/arquivos
ARQUIVOS_DIR_PATH = os.path.join(BACKEND_DIR, ARQUIVOS_DIR_NAME)

# Garante que os diretórios existam no servidor DENTRO da pasta backend
print(f"INFO: Criando diretório de imagens em: {IMAGENS_DIR_PATH}")
os.makedirs(IMAGENS_DIR_PATH, exist_ok=True)
print(f"INFO: Criando diretório de arquivos em: {ARQUIVOS_DIR_PATH}")
os.makedirs(ARQUIVOS_DIR_PATH, exist_ok=True)