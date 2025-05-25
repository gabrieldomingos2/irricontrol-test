from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from backend.routers import kmz, simulation # Correto
from backend import config # Correto

app = FastAPI(
    title="Irricontrol Signal Simulator API",
    description="API para processar KMZ e simular cobertura de sinal.",
    version="1.0.0"
)

origins = [
    "http://localhost",
    "http://localhost:8080",
    "http://127.0.0.1",
    "http://127.0.0.1:8080",
    "https://irricontrol-test.netlify.app/", # MUITO IMPORTANTE: Adicione a URL do seu site Netlify aqui
    "null"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define o caminho para a pasta static DENTRO da pasta backend
# __file__ é o caminho para o main.py atual
# os.path.dirname(__file__) é a pasta 'backend'
# os.path.join junta com 'static' para formar 'backend/static'
static_files_path = os.path.join(os.path.dirname(__file__), "static")

# Monta a pasta 'static' para ser servida em '/static'
# Ex: BACKEND_URL/static/imagens/arquivo.png
app.mount("/static", StaticFiles(directory=static_files_path), name="static")


# Inclui os routers. Eles já têm seus próprios prefixos.
app.include_router(kmz.router) # kmz.router tem prefix="/kmz"
app.include_router(simulation.router) # simulation.router tem prefix="/simulation"


@app.get("/")
def read_root():
    return {"message": "Bem-vindo à API do Simulador de Sinal Irricontrol!"}