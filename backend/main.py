from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

# Importa os routers que criamos
from .routers import kmz, simulation
# Importa config para garantir que os diretórios sejam criados
from . import config

# Cria a instância principal da aplicação FastAPI
app = FastAPI(
    title="Irricontrol Signal Simulator API",
    description="API para processar KMZ e simular cobertura de sinal.",
    version="1.0.0"
)

# --- Configuração do CORS ---
# Permite que seu frontend acesse esta API.
# ATENÇÃO: Em produção, é mais seguro restringir a origem
# para a URL exata do seu frontend (ex: "https://seu-frontend.netlify.app").
origins = [
    "http://localhost",         # Para desenvolvimento local
    "http://localhost:8080",    # Outra porta local comum
    "http://127.0.0.1",
    "http://127.0.0.1:8080",
    "https://irricontrol-test.netlify.app", # Seu frontend atual (exemplo)
    "null" # Para permitir testes locais abrindo o HTML direto do arquivo
    # Adicione a URL do seu frontend Netlify/Vercel/etc. aqui!
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, # Lista de origens permitidas (ou ["*"] para qualquer uma)
    allow_credentials=True,
    allow_methods=["*"],    # Permite todos os métodos (GET, POST, etc.)
    allow_headers=["*"],    # Permite todos os cabeçalhos
)

# --- Montagem de Arquivos Estáticos ---
# Faz com que a pasta 'backend/static' seja acessível via URL '/static'
# Ex: http://endereco/static/imagens/cloudrf.png
# Usa os.path.join para funcionar em diferentes sistemas operacionais
static_path = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_path), name="static")


# --- Inclusão dos Routers ---
# Adiciona os endpoints definidos em kmz.py e simulation.py à aplicação principal
app.include_router(kmz.router)
app.include_router(simulation.router)


# --- Endpoint Raiz (Opcional) ---
@app.get("/")
def read_root():
    """Endpoint raiz para verificar se a API está funcionando."""
    return {"message": "Bem-vindo à API do Simulador de Sinal Irricontrol!"}

# --- Como Rodar (Instruções) ---
# 1. Navegue até a pasta 'irricontrol-test/backend' no seu terminal.
# 2. (Opcional, mas recomendado) Crie e ative um ambiente virtual:
#    python -m venv venv
#    source venv/bin/activate  (Linux/Mac) ou venv\Scripts\activate (Windows)
# 3. Instale as dependências: pip install -r requirements.txt
# 4. Rode o servidor: uvicorn main:app --reload
#    O '--reload' faz o servidor reiniciar automaticamente quando você salva um arquivo.