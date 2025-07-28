import logging.config
from backend.config import settings

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    
    "formatters": {
        # Formatter padrão para o console
        "default": {
            "()": "uvicorn.logging.DefaultFormatter",
            "fmt": "%(levelprefix)s %(asctime)s [%(name)s] :: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        # ✅ NOVO: Formatter para logs estruturados em JSON
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(name)s %(levelname)s %(message)s %(pathname)s %(lineno)d"
        }
    },

    "handlers": {
        # Handler padrão para o console
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
        },
        # Handler para salvar em arquivo com rotação
        "rotating_file": {
            "formatter": "json", # Usando o novo formatter JSON
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "irricontrol_app.log", # Nome do arquivo de log
            "maxBytes": 10485760,  # 10 MB
            "backupCount": 5,      # Mantém 5 arquivos de backup
            "encoding": "utf8"
        }
    },

    "loggers": {
        "irricontrol": {
            # Envia logs para o console E para o arquivo
            "handlers": ["default", "rotating_file"],
            "level": settings.LOG_LEVEL.upper(),
            "propagate": False
        },
        "uvicorn.error": {
            # Envia erros do Uvicorn para o arquivo também
            "handlers": ["default", "rotating_file"],
            "level": "INFO",
            "propagate": False
        },
        "uvicorn.access": {
            "handlers": ["default"], # Mantemos o acesso apenas no console
            "level": "WARNING",
            "propagate": False
        },
    },
}

def setup_logging():
    """Aplica a configuração de logging definida acima."""
    # Instala a dependência se não existir (opcional, mas útil)
    try:
        import pythonjsonlogger
    except ImportError:
        print("AVISO: 'python-json-logger' não está instalado. Logs JSON não funcionarão.")
        # Remove a configuração de JSON se a lib não estiver presente
        del LOGGING_CONFIG["formatters"]["json"]
        del LOGGING_CONFIG["handlers"]["rotating_file"]
        LOGGING_CONFIG["loggers"]["irricontrol"]["handlers"] = ["default"]
        LOGGING_CONFIG["loggers"]["uvicorn.error"]["handlers"] = ["default"]

    logging.config.dictConfig(LOGGING_CONFIG)
    logger = logging.getLogger("irricontrol")
    logger.info("Sistema de logging centralizado configurado com sucesso.")