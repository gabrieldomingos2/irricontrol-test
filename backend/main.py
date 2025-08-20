# backend/main.py

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
import logging
from typing import Dict, List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.routers import kmz, simulation, report
from backend.logging_config import setup_logging
from backend.middlewares import RequestContextMiddleware  # correlaciona request (job_id)


# ---------------------------------------------------------------------------
# Lifespan: inicializa logging e diretórios ANTES do app subir
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1) Logging primeiro (assim Uvicorn/Docs também herdam a config)
    setup_logging()
    logger = logging.getLogger("irricontrol")

    # 2) Diretórios essenciais
    try:
        settings.initialize_directories()
        # Garante estáticos também (evita erro ao montar)
        Path(settings.STATIC_DIR_PATH).mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.exception("Falha ao inicializar diretórios: %s", e)
        # Em produção você pode optar por abortar o boot:
        # raise

    # 3) Loga config efetiva (sem vazar segredos)
    logger.info("Startup - ALLOWED_ORIGINS: %s", settings.ALLOWED_ORIGINS)
    logger.info("Startup - LOG_LEVEL: %s", getattr(settings, "LOG_LEVEL", "INFO"))
    logger.info(
        "Aplicação iniciando... name=%s version=%s api_base=%s",
        settings.APP_NAME,
        settings.APP_VERSION,
        settings.API_V1_STR,
    )

    yield

    logger.info("Aplicação finalizando (lifespan shutdown).")


# ---------------------------------------------------------------------------
# Instância FastAPI com lifespan robusto
# ---------------------------------------------------------------------------
app = FastAPI(
    title=settings.APP_NAME,
    description="API para processar KMZ e simular cobertura de sinal.",
    version=settings.APP_VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Middleware de correlação por request (X-Request-ID)
# ---------------------------------------------------------------------------
app.add_middleware(RequestContextMiddleware)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Arquivos estáticos
# ---------------------------------------------------------------------------
app.mount(
    "/static",
    StaticFiles(directory=settings.STATIC_DIR_PATH),
    name="static",
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(kmz.router,        prefix=settings.API_V1_STR, tags=["KMZ Operations"])
app.include_router(simulation.router, prefix=settings.API_V1_STR, tags=["Simulation"])
app.include_router(report.router,     prefix=settings.API_V1_STR, tags=["Report Operations"])

# ---------------------------------------------------------------------------
# Logger da app (depois do setup no lifespan ele já sai formatado com job_id)
# ---------------------------------------------------------------------------
logger = logging.getLogger("irricontrol")

# ---------------------------------------------------------------------------
# Endpoints básicos e utilitários
# ---------------------------------------------------------------------------
@app.get("/", tags=["Root"])
async def read_root() -> Dict[str, str]:
    logger.info("Root hit.")
    return {"message": f"Bem-vindo à {settings.APP_NAME}!"}


@app.get(f"{settings.API_V1_STR}/health", tags=["Health"])
async def health() -> Dict[str, str]:
    logger.info("Health check ok.")
    return {"status": "ok"}


@app.get(f"{settings.API_V1_STR}/version", tags=["Health"])
async def version_info() -> Dict[str, str]:
    """Informação simples de versão/nome — útil para automations e monitoramento."""
    return {"name": settings.APP_NAME, "version": settings.APP_VERSION}


@app.get(f"{settings.API_V1_STR}/templates", tags=["Simulation"])
async def list_templates() -> Dict[str, List[str]]:
    """Lista os IDs de templates disponíveis (sem expor segredos)."""
    ids = settings.listar_templates_ids()
    logger.info("Listando templates: %s", ids)
    return {"templates": ids}