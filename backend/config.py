# Em backend/config.py

import os

# --- Caminhos (Usando __file__ para referência absoluta DENTRO do pacote backend) ---

# Diretório raiz DO PACOTE 'backend' (onde este config.py está)
# Ex: /opt/render/project/src/backend
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))

# Diretório base DO PROJETO (um nível acima de BACKEND_DIR, ou seja, /opt/render/project/src)
# É importante ter clareza se 'static' e 'arquivos' estão DENTRO de 'backend' ou na raiz do projeto.
# Pelo seu log de erro "/opt/render/project/src/backend/static/imagens/",
# parece que 'static' está DENTRO de 'backend'. Vamos manter essa estrutura.
PROJECT_ROOT_DIR = os.path.dirname(BACKEND_DIR) # Se config.py está em backend/

STATIC_DIR_NAME = "static"      # Apenas o nome da pasta
IMAGENS_DIR_NAME = "imagens"    # Apenas o nome da subpasta
ARQUIVOS_DIR_NAME = "arquivos"  # Apenas o nome da pasta

# Caminhos absolutos construídos a partir de BACKEND_DIR
# Ex: /opt/render/project/src/backend/static
STATIC_DIR_PATH = os.path.join(BACKEND_DIR, STATIC_DIR_NAME)
# Ex: /opt/render/project/src/backend/static/imagens
IMAGENS_DIR_PATH = os.path.join(STATIC_DIR_PATH, IMAGENS_DIR_NAME)
# Ex: /opt/render/project/src/backend/arquivos
ARQUIVOS_DIR_PATH = os.path.join(BACKEND_DIR, ARQUIVOS_DIR_NAME)

# VARIÁVEL QUE ESTAVA FALTANDO OU COM NOME DIFERENTE NO CONTEXTO DE USO:
# Se em routers/simulation.py você precisa do NOME da pasta static (ex: "static")
STATIC_DIR = STATIC_DIR_NAME
# Se em routers/simulation.py você precisa do CAMINHO ABSOLUTO para a pasta static
# STATIC_DIR_ABSOLUTE = STATIC_DIR_PATH # Você pode definir isso se precisar do caminho completo

# Garante que os diretórios existam no servidor DENTRO da pasta backend
print(f"INFO: Verificando/Criando diretório de imagens em: {IMAGENS_DIR_PATH}")
os.makedirs(IMAGENS_DIR_PATH, exist_ok=True)
print(f"INFO: Verificando/Criando diretório de arquivos em: {ARQUIVOS_DIR_PATH}")
os.makedirs(ARQUIVOS_DIR_PATH, exist_ok=True)


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
    # Corrigido para usar TEMPLATES_DISPONIVEIS em vez de retornar uma lista fixa
    return [t["id"] for t in TEMPLATES_DISPONIVEIS]