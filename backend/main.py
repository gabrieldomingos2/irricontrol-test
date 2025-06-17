# backend/main.py

# --- Importações de Módulos ---
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import logging

# Importa as configurações e os routers
from backend.config import settings
from backend.routers import kmz, simulation

# Importa a nova função de setup do logging que criamos
from backend.logging_config import setup_logging

logger = logging.getLogger("irricontrol")

# --- Instância da Aplicação FastAPI ---
app = FastAPI(
    title=settings.APP_NAME,
    description="API para processar KMZ e simular cobertura de sinal.",
    version=settings.APP_VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc"
)

# --- Eventos de Ciclo de Vida da Aplicação ---
@app.on_event("startup")
async def startup_event():
    """
    Executa tarefas essenciais na inicialização da aplicação.
    """
    # 1. Chama a nova função de configuração do logging PRIMEIRO.
    setup_logging()

    # 2. As outras tarefas de inicialização continuam como antes.
    settings.initialize_directories()

    # Logs de depuração para verificar a configuração do CORS.
    # Estes logs agora usarão o novo formato centralizado.
    logger.info(f"Startup - ALLOWED_ORIGINS_CSV: {settings.ALLOWED_ORIGINS_CSV}")
    logger.info(f"Startup - NETLIFY_APP_URL: {settings.NETLIFY_APP_URL}")
    logger.info(f"Startup - Effective ALLOWED_ORIGINS for CORS: {settings.ALLOWED_ORIGINS}")
    
    logger.info("Aplicação iniciada, configurações carregadas e diretórios verificados/criados.")


# --- Configuração do CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Montagem de Arquivos Estáticos ---
app.mount(
    "/static",
    StaticFiles(directory=settings.STATIC_DIR_PATH),
    name="static"
)

# --- Inclusão dos Routers ---
app.include_router(kmz.router, prefix=settings.API_V1_STR, tags=["KMZ Operations"])
app.include_router(simulation.router, prefix=settings.API_V1_STR, tags=["Simulation"])


# --- Endpoint Raiz ---
@app.get("/", tags=["Root"])
def read_root() -> dict[str, str]:
    """
    Endpoint raiz da API. Retorna uma mensagem de boas-vindas.
    """
    return {"message": f"Bem-vindo à {settings.APP_NAME}!"}
