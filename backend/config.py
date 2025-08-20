# backend/config.py

# Importações de bibliotecas padrão
import os
import logging
from pathlib import Path
from enum import Enum  # 👈 ADICIONADO: Para criar Enums

# Importações de tipos e Pydantic
from typing import List, Optional, Dict, Any
from pydantic import Field, HttpUrl, BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

# Obter a instância do logger configurado
logger = logging.getLogger("irricontrol")


# --- Modelos Pydantic para estruturas aninhadas ---
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

# ✨ MELHORIA 1: Enum para os IDs dos templates para evitar erros de digitação
class TemplateID(str, Enum):
    """Define os identificadores únicos para cada template de simulação."""
    BRAZIL_V6_100DBM = "Brazil_V6_100dBm"
    EUROPE_V6_XR = "Europe_V6_XR"
    BRAZIL_V6_90DBM = "Brazil_V6_90dBm"


# --- Dicionário de Internacionalização (i18n) ---
I18N_KEYWORDS: Dict[str, Dict[str, List[str]]] = {
    "ANTENA": {
        "pt": ["antena", "torre", "central", "base", "repetidora", "barracão", "galpão", "silo", "caixa", "caixa d'água", "poste"],
        "en": ["antenna", "tower", "base", "station", "repeater", "radio", "site", "shed", "warehouse", "silo", "water tank", "pole", "post"],
        "es": ["antena", "torre", "base", "estación", "repetidora", "radio", "cobertizo", "galpón", "almacén", "silo", "tanque de agua", "depósito de agua", "poste"],
        "de": ["antenne", "turm", "basisstation", "repeater", "funkmast", "schuppen", "lagerhalle", "silo", "wassertank", "mast", "pfosten"],
        "ru": ["антенна", "башня", "станция", "репитер", "радиостанция", "сарай", "ангар", "склад", "силос", "водяной бак", "водонапорная башня", "столб", "мачта"]
    },
    "PIVO": {
        "pt": ["pivô", "pivo"],
        "en": ["pivot", "sprinkler"],
        "es": ["pivote", "aspersor"],
        "de": ["pivot", "drehpunkt", "beregnung"],
        "ru": ["пивот", "ороситель", "спринклер"]
    },
    "BOMBA": {
        "pt": ["bomba", "irripump", "pump", "captação", "poço"],
        "en": ["pump", "pumping station", "irripump", "water intake", "well"],
        "es": ["bomba", "estación de bombeo", "irripump", "captación", "toma de agua", "pozo"],
        "de": ["pumpe", "pumpstation", "irripump", "wasserentnahme", "brunnen"],
        "ru": ["насос", "насосная станция", "irripump", "водозабор", "колодец", "скважина"]
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

    # ✨ MELHORIA 2: Centraliza a definição do template padrão
    DEFAULT_TEMPLATE_ID: TemplateID = TemplateID.BRAZIL_V6_100DBM

    # --- Configurações de CORS ---
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
        return self.ARQUIVOS_DIR_PATH / self.CACHE_DIR_NAME / self.SIMULATIONS_CACHE_DIR_NAME

    @property
    def ELEVATION_CACHE_PATH(self) -> Path:
        return self.ARQUIVOS_DIR_PATH / self.CACHE_DIR_NAME / self.ELEVATION_CACHE_DIR_NAME
        
    @property
    def ENTITY_KEYWORDS(self) -> Dict[str, List[str]]:
        consolidated = {}
        for entity, lang_map in I18N_KEYWORDS.items():
            all_keywords = [word for words in lang_map.values() for word in words]
            consolidated[entity] = list(set(all_keywords))
        return consolidated

    # --- Configurações de API Externa (CloudRF) ---
    CLOUDRF_API_KEY: Optional[str] = Field(None, validation_alias="CLOUDRF_API_KEY")
    CLOUDRF_API_URL: HttpUrl = Field(default="https://api.cloudrf.com/area", validation_alias="CLOUDRF_API_URL")
    HTTP_TIMEOUT: float = Field(default=60.0, validation_alias="HTTP_TIMEOUT")
    LOG_LEVEL: str = "INFO"

    # --- Templates de Simulação Pré-definidos ---
    TEMPLATES_DISPONIVEIS: List[TemplateSettings] = [
        {
            "id": "Brazil_V6_100dBm", "nome": "🇧🇷 Brazil V6 100dBm", "frq": 915,
            "col": "IRRICONTRO.dBm", "site": "Brazil_V6_100dBm", "rxs": -100,
            "transmitter": {"txw": 0.3, "bwi": 0.1},
            "receiver": {"lat": 0, "lon": 0, "alt": 3, "rxg": 3, "rxs": -100},
            "antenna": {"txg": 3, "fbr": 3}
        },
        {
            "id": "Europe_V6_XR", "nome": "🇪🇺 Europe V6 XR", "frq": 868,
            "col": "IRRIEUROPE.dBm", "site": "Europe_V6_XR", "rxs": -105,
            "transmitter": {"txw": 0.02, "bwi": 0.05},
            "receiver": {"lat": 0, "lon": 0, "alt": 3, "rxg": 2.1, "rxs": -105},
            "antenna": {"txg": 2.1, "fbr": 2.1}
        },
        {
            "id": "Brazil_V6_90dBm", "nome": "Brazil V6 90dBm", "frq": 915,
            "col": "CONTROL90.dBm", "site": "Brazil_V6_90dBm", "rxs": -90,
            "transmitter": {"txw": 0.3, "bwi": 0.1},
            "receiver": {"lat": 0, "lon": 0, "alt": 3, "rxg": 3, "rxs": -90},
            "antenna": {"txg": 3, "fbr": 3}
        },
    ]

    # --- Métodos de Inicialização e Utilitários ---
    def initialize_directories(self) -> None:
        """Garante que os diretórios necessários para a aplicação existam."""
        logger.info(f"Verificando/Criando diretório de imagens em: {self.IMAGENS_DIR_PATH}")
        self.IMAGENS_DIR_PATH.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Verificando/Criando diretório de arquivos em: {self.ARQUIVOS_DIR_PATH}")
        self.ARQUIVOS_DIR_PATH.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Verificando/Criando diretório de cache de simulações em: {self.SIMULATIONS_CACHE_PATH}")
        self.SIMULATIONS_CACHE_PATH.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Verificando/Criando diretório de cache de elevação em: {self.ELEVATION_CACHE_PATH}")
        self.ELEVATION_CACHE_PATH.mkdir(parents=True, exist_ok=True)

        if not self.CLOUDRF_API_KEY:
            logger.warning("ALERTA DE SEGURANÇA: CLOUDRF_API_KEY não está definida!")
        if not self.BACKEND_PUBLIC_URL:
            logger.warning("ALERTA DE CONFIGURAÇÃO: BACKEND_PUBLIC_URL não está definida! As URLs de imagem podem estar incorretas.")

    # ✨ MELHORIA 3: Método atualizado para usar o Enum e o ID padrão centralizado
    def obter_template(self, template_id: str | TemplateID) -> TemplateSettings:
        """Busca um template por ID, retornando um padrão se não for encontrado."""
        # Garante que estamos comparando a string do ID
        id_value = template_id.value if isinstance(template_id, Enum) else template_id

        template_obj = next(
            (t for t in self.TEMPLATES_DISPONIVEIS if t.id == id_value),
            None
        )
        
        if not template_obj:
            logger.warning(f"Template '{id_value}' não encontrado. Usando padrão '{self.DEFAULT_TEMPLATE_ID.value}'.")
            # Busca o template padrão de forma segura, evitando recursão infinita
            return next(t for t in self.TEMPLATES_DISPONIVEIS if t.id == self.DEFAULT_TEMPLATE_ID.value)
            
        return template_obj

    def listar_templates_ids(self) -> List[str]:
        """Retorna uma lista com os IDs (strings) de todos os templates disponíveis."""
        return [t.id for t in self.TEMPLATES_DISPONIVEIS]

# --- Instanciação Global ---
settings = AppSettings()