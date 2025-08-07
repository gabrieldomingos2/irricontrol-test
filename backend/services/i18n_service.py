import json
import logging
from pathlib import Path
from typing import Dict, Callable, Any

from backend.config import settings

logger = logging.getLogger("irricontrol")

class TranslationService:
    def __init__(self, locales_dir: Path, default_lang: str = 'pt-br'):
        self.locales_dir = locales_dir
        self.default_lang = default_lang
        self.translations: Dict[str, Dict] = {}
        self._load_translations()

    def _load_translations(self):
        """Carrega todos os arquivos .json do diretório de locales."""
        if not self.locales_dir.is_dir():
            logger.error(f"Diretório de locales não encontrado em: {self.locales_dir}")
            return
            
        for file_path in self.locales_dir.glob("*.json"):
            lang_code = file_path.stem
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    self.translations[lang_code] = json.load(f)
                logger.info(f"Tradução para '{lang_code}' carregada com sucesso.")
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Falha ao carregar ou parsear o arquivo de tradução {file_path}: {e}")

    def _get_text(self, lang: str, key: str) -> str:
        """Busca um texto, com fallback para o idioma padrão."""
        keys = key.split('.')
        
        # Tenta no idioma solicitado
        lang_data = self.translations.get(lang, {})
        text = lang_data
        for k in keys:
            text = text.get(k) if isinstance(text, dict) else None
            if text is None: break
        
        if text is not None:
            return text

        # Fallback para o idioma padrão
        default_data = self.translations.get(self.default_lang, {})
        text = default_data
        for k in keys:
            text = text.get(k) if isinstance(text, dict) else None
            if text is None: break
        
        if text is not None:
            logger.warning(f"Chave de tradução '{key}' não encontrada para o idioma '{lang}'. Usando fallback '{self.default_lang}'.")
            return text
            
        logger.error(f"Chave de tradução '{key}' não encontrada para '{lang}' ou no fallback '{self.default_lang}'.")
        return key

    def get_translator(self, lang_code: str) -> Callable[..., str]:
        """Retorna uma função 't' que traduz para o idioma especificado."""
        def translator(key: str, **kwargs: Any) -> str:
            text = self._get_text(lang_code, key)
            if kwargs:
                try:
                    return text.format(**kwargs)
                except KeyError as e:
                    logger.error(f"Placeholder ausente na tradução para a chave '{key}' no idioma '{lang_code}': {e}")
                    return text
            return text
        return translator


locales_path = Path(__file__).resolve().parent.parent / "locales"
i18n_service = TranslationService(locales_dir=locales_path)