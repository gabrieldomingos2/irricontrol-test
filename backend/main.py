# backend/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from backend.routers import kmz, simulation
from backend import config

app = FastAPI(
    title="Irricontrol Signal Simulator API",
    description="API para processar KMZ e simular cobertura de sinal.",
    version="1.0.0"
)

# --- Configuração do CORS ---
origins = [
    "http://localhost",         # Para desenvolvimento local
    "http://localhost:8080",    # Outra porta local comum
    "http://127.0.0.1",
    "http://127.0.0.1:8080",
    "https://irricontrol-test.netlify.app",  # <-- SUA URL DO NETLIFY DEVE ESTAR AQUI!
    "null" # Para permitir testes locais abrindo o HTML direto do arquivo (opcional)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, # Garanta que esta variável 'origins' está sendo usada
    allow_credentials=True,
    allow_methods=["*"],    # Permite todos os métodos (GET, POST, etc.)
    allow_headers=["*"],    # Permite todos os cabeçalhos
)

# --- Montagem de Arquivos Estáticos ---
static_files_path = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_files_path), name="static")

# --- Inclusão dos Routers ---
app.include_router(kmz.router)
app.include_router(simulation.router)

# --- Endpoint Raiz (Opcional) ---
@app.get("/")
def read_root():
    return {"message": "Bem-vindo à API do Simulador de Sinal Irricontrol!"}