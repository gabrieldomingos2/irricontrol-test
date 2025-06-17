import logging.config
from backend.config import settings

# Este dicionário é o padrão do Python para configurar logging de forma avançada.
# Ele nos dá controle total sobre formatadores, handlers e os próprios loggers.
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False, # Mantém os loggers de bibliotecas de terceiros funcionando.
    
    # Define como as mensagens de log serão formatadas.
    "formatters": {
        "default": {
            "()": "uvicorn.logging.DefaultFormatter",
            "fmt": "%(levelprefix)s %(asctime)s [%(name)s] :: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },

    # Define para onde as mensagens de log são enviadas (handlers).
    "handlers": {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler", # Envia para o console (saída padrão).
            "stream": "ext://sys.stderr",
        },
    },

    # Define o comportamento dos loggers.
    "loggers": {
        # Nosso logger principal da aplicação.
        "irricontrol": {
            "handlers": ["default"],
            "level": settings.LOG_LEVEL.upper(), # Pega o nível do arquivo .env
            "propagate": False
        },
        # Logger de erros do Uvicorn.
        "uvicorn.error": {
            "handlers": ["default"],
            "level": "INFO",
            "propagate": False
        },
        # Logger de acesso do Uvicorn (requisições).
        "uvicorn.access": {
            "handlers": ["default"],
            "level": "INFO",
            "propagate": False
        },
    },
}

def setup_logging():
    """Aplica a configuração de logging definida acima."""
    logging.config.dictConfig(LOGGING_CONFIG)
    logger = logging.getLogger("irricontrol")
    logger.info("Sistema de logging centralizado configurado com sucesso.")