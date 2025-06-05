# backend/main.py

from pathlib import Path # Ainda útil para tipagem e se StaticFiles espera Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Importa a instância 'settings' do seu módulo de configuração Pydantic
import logging
from backend.config import settings
from backend.routers import kmz, simulation

# --- Instância da Aplicação FastAPI ---
# Configurações da aplicação agora vêm do objeto 'settings'
app = FastAPI(
    title=settings.APP_NAME,
    description="API para processar KMZ e simular cobertura de sinal.", # Pode vir de settings também se desejar
    version=settings.APP_VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json", # Usa o prefixo da API das configurações
    docs_url="/docs",  # Pode ser configurável via settings se necessário
    redoc_url="/redoc" # Pode ser configurável via settings se necessário
)

# --- Eventos de Ciclo de Vida da Aplicação ---
@app.on_event("startup")
async def startup_event():
    """
    Tarefas a serem executadas na inicialização da aplicação.
    """
    settings.initialize_directories() # Chama a função para criar os diretórios
    # Log para depuração de CORS - Verifique este log no Render
    print(f"INFO: Startup - ALLOWED_ORIGINS_CSV: {settings.ALLOWED_ORIGINS_CSV}")
    print(f"INFO: Startup - NETLIFY_APP_URL: {settings.NETLIFY_APP_URL}")
    print(f"INFO: Startup - Effective ALLOWED_ORIGINS for CORS: {settings.ALLOWED_ORIGINS}")

    # Você pode adicionar um check aqui para o API_KEY, se não feito em initialize_directories
    # if not settings.CLOUDRF_API_KEY:
    #     # Em produção, é melhor logar e talvez levantar um erro ou sair
    #     print("ALERTA CRÍTICO: CLOUDRF_API_KEY não está configurada!")
    #     # raise RuntimeError("Configuração crítica faltando: CLOUDRF_API_KEY não definida.")
    print("INFO: Aplicação iniciada, configurações carregadas e diretórios verificados/criados.")

# --- Configuração do CORS ---
# A lista de origens permitidas agora vem do objeto 'settings'
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS, # Esta é a lista crucial
    allow_credentials=True,
    allow_methods=["*"],    # Permite todos os métodos (GET, POST, etc.)
    allow_headers=["*"],    # Permite todos os cabeçalhos
)

# --- Montagem de Arquivos Estáticos ---
# O caminho para os arquivos estáticos agora vem do objeto 'settings'
# settings.STATIC_DIR_PATH já é um objeto Path configurado
app.mount(
    "/static", # O prefixo da URL para os arquivos estáticos
    StaticFiles(directory=settings.STATIC_DIR_PATH), # Diretório dos arquivos estáticos
    name="static"
)

# --- Inclusão dos Routers ---
# O prefixo da API agora vem do objeto 'settings'
app.include_router(kmz.router, prefix=settings.API_V1_STR, tags=["KMZ Operations"])
app.include_router(simulation.router, prefix=settings.API_V1_STR, tags=["Simulation"])

# --- Endpoint Raiz ---
@app.get("/", tags=["Root"])
def read_root() -> dict[str, str]: # Mantido type hint para o retorno
    """
    Endpoint raiz da API. Retorna uma mensagem de boas-vindas.
    """
    return {"message": f"Bem-vindo à {settings.APP_NAME}!"}

# --- Ponto de entrada para execução (opcional, para debug local com Uvicorn) ---
# if __name__ == "__main__":
#     import uvicorn
#     # Idealmente, host e porta também viriam de 'settings'
#     # Ex: uvicorn.run(app, host=settings.SERVER_HOST, port=settings.SERVER_PORT)
#     uvicorn.run(app, host="0.0.0.0", port=8000)

# Configuração global do logging
# Adicione LOG_LEVEL a AppSettings em config.py, ex: LOG_LEVEL: str = "INFO"
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__) # Para uso em main.py