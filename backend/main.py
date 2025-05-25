from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

# Importa os routers usando o caminho absoluto a partir de 'backend'
from backend.routers import kmz, simulation
# Importa config usando o caminho absoluto
from backend import config

# Cria a instância principal da aplicação FastAPI
app = FastAPI(
    title="Irricontrol Signal Simulator API",
    description="API para processar KMZ e simular cobertura de sinal.",
    version="1.0.0"
)

# --- Configuração do CORS ---
origins = [
    "http://localhost",
    "http://localhost:8080",
    "http://127.0.0.1",
    "http://127.0.0.1:8080",
    "https://irricontrol-test.netlify.app", # Adicione a URL do seu Netlify aqui
    "null"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Montagem de Arquivos Estáticos ---
# O 'backend' não está mais no caminho porque o Render roda a partir da raiz
static_path = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_path), name="static")


# --- Inclusão dos Routers ---
app.include_router(kmz.router)
app.include_router(simulation.router)


# --- Endpoint Raiz (Opcional) ---
@app.get("/")
def read_root():
    """Endpoint raiz para verificar se a API está funcionando."""
    return {"message": "Bem-vindo à API do Simulador de Sinal Irricontrol!"}