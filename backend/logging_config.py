# logging_config.py
import logging
import logging.config
from logging import Filter
from contextvars import ContextVar
from typing import Optional
from uuid import uuid4
from pathlib import Path

# Se quiser pegar do seu settings:
try:
    from backend.config import settings
    LOG_LEVEL = settings.LOG_LEVEL.upper()
    LOG_FILE = getattr(settings, "LOG_FILE", "irricontrol_app.log")
    LOG_TO_FILE = getattr(settings, "LOG_TO_FILE", True)
except (ImportError, AttributeError):
    LOG_LEVEL = "INFO"
    LOG_FILE = "irricontrol_app.log"
    LOG_TO_FILE = True

# ---- Contexto por request/job ----
job_id_ctx: ContextVar[str] = ContextVar("job_id", default="global")
user_ctx: ContextVar[str] = ContextVar("user", default="-")

def set_job_id(job_id: Optional[str] = None) -> str:
    """Define o job_id no contexto atual e retorna o valor usado."""
    jid = job_id or str(uuid4())
    job_id_ctx.set(jid)
    return jid

def clear_job_id():
    """Reseta o job_id no contexto (boa prática ao encerrar tarefas)."""
    job_id_ctx.set("global")

def set_user(user: Optional[str] = None):
    user_ctx.set(user or "-")

def clear_user():
    user_ctx.set("-")

class ContextFilter(Filter):
    """Injeta job_id e user em TODOS os registros, sem quebrar terceiros."""
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "job_id"):
            record.job_id = job_id_ctx.get()
        if not hasattr(record, "user"):
            record.user = user_ctx.get()
        return True

def _ensure_parent_dir(path: str):
    try:
        Path(path).resolve().parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass  # sem drama se não conseguir criar — handler vai cair no console se falhar

def build_logging_config(json_available: bool) -> dict:
    # Formatter console legível + job_id
    default_fmt = {
        "()": "uvicorn.logging.DefaultFormatter",
        "fmt": "%(levelprefix)s %(asctime)s [%(name)s] [job_id=%(job_id)s] :: %(message)s",
        "datefmt": "%Y-%m-%d %H:%M:%S",
    }

    # Formatter JSON estável (nada de multiline esquisito)
    json_fmt = {
        "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
        "format": "%(asctime)s %(levelname)s %(name)s %(message)s %(pathname)s %(lineno)d %(module)s %(funcName)s %(job_id)s %(user)s",
    }

    handlers = {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "filters": ["ctx"],
            "stream": "ext://sys.stderr",
        }
    }

    if LOG_TO_FILE:
        _ensure_parent_dir(LOG_FILE)
        handlers["rotating_file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_FILE,
            "maxBytes": 10 * 1024 * 1024,  # 10MB
            "backupCount": 5,
            "encoding": "utf8",
            "formatter": "json" if json_available else "default",
            "filters": ["ctx"],
            "delay": True,
        }

    # Se quiser log assíncrono no futuro, é só trocar para QueueHandler/QueueListener.
    # Aqui mantemos simples e estável.

    logger_handlers = ["console"] + (["rotating_file"] if LOG_TO_FILE else [])

    return {
        "version": 1,
        "disable_existing_loggers": False,

        "filters": {
            "ctx": {"()": ContextFilter},
        },

        "formatters": {
            "default": default_fmt,
            "json": json_fmt,
        },

        "handlers": handlers,

        "loggers": {
            # Seu app
            "irricontrol": {
                "handlers": logger_handlers,
                "level": LOG_LEVEL,
                "propagate": False,
            },
            # Uvicorn (erros também vão pro arquivo)
            "uvicorn.error": {
                "handlers": logger_handlers,
                "level": "INFO",
                "propagate": False,
            },
            # Access: só console por padrão (arquivo enche fácil)
            "uvicorn.access": {
                "handlers": ["console"],
                "level": "WARNING",
                "propagate": False,
            },
        },
    }

def setup_logging():
    """Aplica configuração, com fallback automático se python-json-logger não existir."""
    try:
        import pythonjsonlogger  # noqa: F401
        json_available = True
    except ImportError:
        print("AVISO: 'python-json-logger' não instalado. Mantendo logs legíveis no console/arquivo.")
        json_available = False

    config = build_logging_config(json_available=json_available)
    logging.config.dictConfig(config)

    # Mensagem de prova de vida com job_id
    logger = logging.getLogger("irricontrol")
    set_job_id("setup")
    logger.info(
        "Sistema de logging configurado com sucesso%s.",
        "" if json_available else " (sem JSON)"
    )

    clear_job_id()
