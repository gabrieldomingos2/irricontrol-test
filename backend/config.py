# config.py (deprecado)

import warnings
from backend.config.settings import settings  # importa a instância global

# Aviso de depreciação
warnings.warn(
    "backend/config.py está deprecado. "
    "Use 'from backend.config import settings'.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["settings"]