# backend/config.py

# Importa 'os' e 'pathlib' para manipulação de caminhos
import os
from pathlib import Path

# 👇 PASSO 1: Importar a biblioteca de logging
import logging

# Importações de tipos e Pydantic
from typing import List, Optional, Dict, Any
from pydantic import Field, HttpUrl, BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

# 👇 PASSO 2: Obter a instância do logger configurado na sua aplicação
logger = logging.getLogger("irricontrol")


# --- Modelos Pydantic para estruturas aninhadas nos templates ---
class TransmitterSettings(BaseModel):
    txw: float
    bwi: float

class ReceiverSettings(BaseModel):
    lat: float = 0.0
    lon: float = 0.0
    alt: int = 3
    rxg: float
    rxs: int

class AntennaSettings(BaseModel):
    txg: float
    fbr: float

class TemplateSettings(BaseModel):
    id: str
    nome: str
    frq: int
    col: str
    site: str
    rxs: int
    transmitter: TransmitterSettings
    receiver: ReceiverSettings
    antenna: AntennaSettings

# --- Dicionário de Internacionalização (i18n) ---
I18N_KEYWORDS: Dict[str, Dict[str, List[str]]] = {
    "ANTENA": {
        "pt": ["antena", "torre", "central", "base", "repetidora", "barracão", "galpão", "silo", "caixa"],
        "en": ["antenna", "tower", "base", "station", "repeater", "radio", "site"],
        "es": ["antena", "torre", "base", "estación", "repetidora", "radio"],
        "de": ["antenne", "turm", "basisstation", "repeater", "funkmast"],
        "ru": ["антенна", "башня", "станция", "репитер", "радиостанция"]
    },
    "PIVO": {
        "pt": ["pivô", "pivo"],
        "en": ["pivot", "sprinkler"],
        "es": ["pivote", "aspersor"],
        "de": ["pivot", "drehpunkt", "beregnung"],
        "ru": ["пивот", "ороситель", "спринклер"]
    },
    "BOMBA": {
        "pt": ["bomba", "irripump", "pump"],
        "en": ["pump", "pumping station", "irripump"],
        "es": ["bomba", "estación de bombeo", "irripump"],
        "de": ["pumpe", "pumpstation", "irripump"],
        "ru": ["насос", "насосная станция", "irripump"]
    }
}


# --- Classe Principal de Configurações ---
class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # --- Configurações Gerais da Aplicação ---
    APP_NAME: str = "Irricontrol Signal Simulator API"
    APP_VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # --- Configurações de CORS (Cross-Origin Resource Sharing) ---
    ALLOWED_ORIGINS_CSV: str = Field(default="http://localhost,http://localhost:8080,http://127.0.0.1,http://127.0.0.1:8080,null,http://localhost:5173", validation_alias="ALLOWED_ORIGINS_CSV")
    NETLIFY_APP_URL: Optional[str] = Field(None, validation_alias="NETLIFY_APP_URL")
    BACKEND_PUBLIC_URL: Optional[HttpUrl] = Field(None, validation_alias="BACKEND_PUBLIC_URL")

    @property
    def ALLOWED_ORIGINS(self) -> List[str]:
        origins_from_csv = [origin.strip() for origin in self.ALLOWED_ORIGINS_CSV.split(',')]
        if self.NETLIFY_APP_URL:
            normalized_netlify_url = self.NETLIFY_APP_URL.strip().rstrip('/')
            if normalized_netlify_url not in origins_from_csv:
                origins_from_csv.append(normalized_netlify_url)
        return [origin for origin in origins_from_csv if origin]

    # --- Configurações de Diretórios ---
    BACKEND_DIR: Path = Path(__file__).resolve().parent
    PROJECT_ROOT_DIR: Path = BACKEND_DIR.parent

    STATIC_DIR_NAME: str = "static"
    IMAGENS_DIR_NAME: str = "imagens"
    ARQUIVOS_DIR_NAME: str = "arquivos"
    
    CACHE_DIR_NAME: str = "cache"
    SIMULATIONS_CACHE_DIR_NAME: str = "simulations"
    ELEVATION_CACHE_DIR_NAME: str = "elevation"

    @property
    def STATIC_DIR_PATH(self) -> Path:
        return self.BACKEND_DIR / self.STATIC_DIR_NAME

    @property
    def IMAGENS_DIR_PATH(self) -> Path:
        return self.STATIC_DIR_PATH / self.IMAGENS_DIR_NAME

    @property
    def ARQUIVOS_DIR_PATH(self) -> Path:
        return self.BACKEND_DIR / self.ARQUIVOS_DIR_NAME

    @property
    def SIMULATIONS_CACHE_PATH(self) -> Path:
        """Caminho para o cache de resultados de simulação da CloudRF."""
        return self.ARQUIVOS_DIR_PATH / self.CACHE_DIR_NAME / self.SIMULATIONS_CACHE_DIR_NAME

    @property
    def ELEVATION_CACHE_PATH(self) -> Path:
        """Caminho para o cache de resultados de perfis de elevação."""
        return self.ARQUIVOS_DIR_PATH / self.CACHE_DIR_NAME / self.ELEVATION_CACHE_DIR_NAME
        
    @property
    def ENTITY_KEYWORDS(self) -> Dict[str, List[str]]:
        """
        Consolida as keywords de todos os idiomas em listas únicas para cada tipo de entidade.
        O parser usará esta propriedade para simplificar a verificação.
        """
        consolidated = {}
        for entity, lang_map in I18N_KEYWORDS.items():
            all_keywords = []
            for lang, words in lang_map.items():
                all_keywords.extend(words)
            consolidated[entity] = list(set(all_keywords))
        return consolidated

    # --- Configurações de API Externa (CloudRF) ---
    CLOUDRF_API_KEY: Optional[str] = Field(None, validation_alias="CLOUDRF_API_KEY")
    CLOUDRF_API_URL: HttpUrl = Field(default="https://api.cloudrf.com/area", validation_alias="CLOUDRF_API_URL")
    HTTP_TIMEOUT: float = Field(default=60.0, validation_alias="HTTP_TIMEOUT")
    LOG_LEVEL: str = "INFO"

    # --- Templates de Simulação Pré-definidos ---
    TEMPLATES_DISPONIVEIS: List[TemplateSettings] = [
        # ... (sem alteração aqui)
        {
            "id": "Brazil_V6", "nome": "🇧🇷 Brazil V6", "frq": 915,
            "col": "IRRICONTRO.dBm", "site": "Brazil_V6", "rxs": -90,
            "transmitter": {"txw": 0.3, "bwi": 0.1},
            "receiver": {"lat": 0, "lon": 0, "alt": 3, "rxg": 3, "rxs": -90},
            "antenna": {"txg": 3, "fbr": 3}
        },
        {
            "id": "Europe_V6_XR", "nome": "🇪🇺 Europe V6 XR", "frq": 868,
            "col": "IRRIEUROPE.dBm", "site": "Europe_V6_XR", "rxs": -105,
            "transmitter": {"txw": 0.02, "bwi": 0.05},
            "receiver": {"lat": 0, "lon": 0, "alt": 3, "rxg": 2.1, "rxs": -105},
            "antenna": {"txg": 2.1, "fbr": 2.1}
        }
    ]

    # --- Métodos de Inicialização e Utilitários ---
    def initialize_directories(self) -> None:
        """
        Garante que os diretórios necessários para a aplicação existam.
        Esta função é chamada no evento de startup do FastAPI.
        """
        # 👇 PASSO 3: Substituir todos os prints por chamadas ao logger
        logger.info(f"Verificando/Criando diretório de imagens em: {self.IMAGENS_DIR_PATH}")
        self.IMAGENS_DIR_PATH.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Verificando/Criando diretório de arquivos em: {self.ARQUIVOS_DIR_PATH}")
        self.ARQUIVOS_DIR_PATH.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Verificando/Criando diretório de cache de simulações em: {self.SIMULATIONS_CACHE_PATH}")
        self.SIMULATIONS_CACHE_PATH.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Verificando/Criando diretório de cache de elevação em: {self.ELEVATION_CACHE_PATH}")
        self.ELEVATION_CACHE_PATH.mkdir(parents=True, exist_ok=True)

        # Verificações de sanidade
        if not self.CLOUDRF_API_KEY:
            logger.warning("ALERTA DE SEGURANÇA: CLOUDRF_API_KEY não está definida!")
        if not self.BACKEND_PUBLIC_URL:
            logger.warning("ALERTA DE CONFIGURAÇÃO: BACKEND_PUBLIC_URL não está definida! As URLs de imagem podem estar incorretas.")

    def obter_template(self, template_id: str) -> TemplateSettings:
        template_obj = next(
            (t_obj for t_obj in self.TEMPLATES_DISPONIVEIS if t_obj.id == template_id),
            None
        )
        if not template_obj:
            # 👇 PASSO 3: Substituir print por logger.warning
            logger.warning(f"Template '{template_id}' não encontrado. Usando padrão '{self.TEMPLATES_DISPONIVEIS[0].id}'.")
            return self.TEMPLATES_DISPONIVEIS[0]
        return template_obj

    def listar_templates_ids(self) -> List[str]:
        return [t_obj.id for t_obj in self.TEMPLATES_DISPONIVEIS]

# --- Instanciação Global ---
settings = AppSettings()