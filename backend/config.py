# backend/config.py

# Importa 'os' para interações com o sistema operacional, embora não seja usado diretamente,
# é comum em arquivos de configuração.
import os
# A importação de 'Path' da biblioteca 'pathlib' é fundamental aqui para criar caminhos de
# arquivos e diretórios de forma robusta e independente de sistema operacional (Windows, Linux, etc.).
from pathlib import Path
# Importações de tipos do módulo 'typing' para anotações de tipo (type hinting),
# o que melhora a legibilidade e permite a verificação estática de tipos.
from typing import List, Optional, Dict, Any

# Importações do Pydantic, a biblioteca central para esta configuração.
# 'Field' permite adicionar metadados e validação a campos individuais.
# 'HttpUrl' é um tipo especial que valida se uma string é uma URL HTTP válida.
# 'BaseModel' é a classe base para criar modelos de dados estruturados.
from pydantic import Field, HttpUrl, BaseModel
# 'BaseSettings' é a classe chave para gerenciar configurações que podem vir de variáveis
# de ambiente ou de um arquivo .env. 'SettingsConfigDict' é usado para configurar seu comportamento.
from pydantic_settings import BaseSettings, SettingsConfigDict


# --- Modelos Pydantic para estruturas aninhadas nos templates ---
# O uso de 'BaseModel' aqui serve para definir um "esquema" ou "contrato" claro para
# os parâmetros de cada parte do template de simulação. Isso garante que todo template
# definido na aplicação terá exatamente essa estrutura, com os tipos de dados corretos.

class TransmitterSettings(BaseModel):
    # Potência do transmissor em Watts.
    txw: float
    # Largura de banda do sinal em MHz.
    bwi: float

class ReceiverSettings(BaseModel):
    # Coordenadas do receptor. São inicializadas com 0.0, mas serão sobreescritas
    # pelos dados do KMZ durante o processamento.
    lat: float = 0.0
    lon: float = 0.0
    # Altitude do receptor em metros.
    alt: int = 3
    # Ganho da antena do receptor em dBi.
    rxg: float
    # Sensibilidade do receptor em dBm (nível mínimo de sinal para operar).
    rxs: int

class AntennaSettings(BaseModel):
    # Ganho da antena do transmissor em dBi.
    txg: float
    # Relação frente-costas da antena (atenuação na direção oposta) em dB.
    fbr: float

# Este é o modelo principal que agrega todas as sub-estruturas.
class TemplateSettings(BaseModel):
    id: str         # Identificador único para o template (ex: "Brazil_V6").
    nome: str       # Nome amigável para exibição no frontend (ex: "🇧🇷 Brazil V6").
    frq: int        # Frequência de operação em MHz.
    col: str        # Nome da "escala de cores" (colour key) na API CloudRF.
    site: str       # Nome do "site" ou local de referência.
    rxs: int        # Sensibilidade do receptor (repetido aqui para acesso rápido, mas também presente em receiver).
    transmitter: TransmitterSettings # Objeto aninhado com as configurações do transmissor.
    receiver: ReceiverSettings     # Objeto aninhado com as configurações do receptor.
    antenna: AntennaSettings       # Objeto aninhado com as configurações da antena.

# --- Classe Principal de Configurações ---
# 'AppSettings' herda de 'BaseSettings', o que lhe dá o poder de ler configurações
# de variáveis de ambiente e arquivos .env automaticamente.
class AppSettings(BaseSettings):
    # 'model_config' é um dicionário especial para configurar o comportamento do Pydantic.
    model_config = SettingsConfigDict(
        # Especifica o nome do arquivo .env a ser procurado e carregado.
        env_file=".env",
        # Define a codificação do arquivo .env.
        env_file_encoding="utf-8",
        # 'extra="ignore"' instrui o Pydantic a ignorar quaisquer variáveis de ambiente
        # extras que não correspondam aos campos definidos nesta classe, evitando erros.
        extra="ignore"
    )

    # --- Configurações Gerais da Aplicação ---
    APP_NAME: str = "Irricontrol Signal Simulator API"
    APP_VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1" # Prefixo para o versionamento da API.

    # --- Configurações de CORS (Cross-Origin Resource Sharing) ---
    # Define uma string CSV com as origens permitidas por padrão. É um formato fácil de
    # definir em uma única variável de ambiente. Inclui 'null' para permitir requisições de arquivos locais (file://).
    ALLOWED_ORIGINS_CSV: str = Field(default="http://localhost,http://localhost:8080,http://127.0.0.1,http://127.0.0.1:8080,null,http://localhost:5173", validation_alias="ALLOWED_ORIGINS_CSV")
    # URL do frontend hospedado no Netlify. É opcional e será lido da variável de ambiente 'NETLIFY_APP_URL'.
    NETLIFY_APP_URL: Optional[str] = Field(None, validation_alias="NETLIFY_APP_URL")
    # URL pública do backend. Essencial para gerar URLs absolutas para arquivos estáticos.
    BACKEND_PUBLIC_URL: Optional[HttpUrl] = Field(None, validation_alias="BACKEND_PUBLIC_URL")

    # '@property' transforma um método em um atributo somente leitura que é calculado dinamicamente.
    # Esta é a forma elegante de processar as variáveis de ambiente de CORS.
    @property
    def ALLOWED_ORIGINS(self) -> List[str]:
        # Converte a string CSV em uma lista de strings, removendo espaços em branco.
        origins_from_csv = [origin.strip() for origin in self.ALLOWED_ORIGINS_CSV.split(',')]
        # Se a URL do Netlify foi definida no ambiente...
        if self.NETLIFY_APP_URL:
            # Limpa a URL (remove espaços e a barra final '/' para evitar inconsistências).
            normalized_netlify_url = self.NETLIFY_APP_URL.strip().rstrip('/')
            # Adiciona a URL do Netlify à lista, se ainda não estiver presente.
            # <-- ponto crítico: Lógica crucial para permitir que o frontend de produção/preview acesse a API dinamicamente.
            if normalized_netlify_url not in origins_from_csv:
                origins_from_csv.append(normalized_netlify_url)
        # Retorna a lista final, removendo quaisquer entradas vazias que possam ter resultado de vírgulas extras.
        return [origin for origin in origins_from_csv if origin]

    # --- Configurações de Diretórios ---
    # Define os caminhos base usando a mágica do 'pathlib' e da variável especial '__file__'.
    # '__file__' é o caminho para o arquivo atual ('config.py').
    # .resolve() obtém o caminho absoluto.
    # .parent aponta para o diretório que contém o arquivo (a pasta 'backend').
    BACKEND_DIR: Path = Path(__file__).resolve().parent
    PROJECT_ROOT_DIR: Path = BACKEND_DIR.parent # O diretório pai de 'backend' é a raiz do projeto.

    # Nomes dos diretórios para centralizar a nomenclatura.
    STATIC_DIR_NAME: str = "static"
    IMAGENS_DIR_NAME: str = "imagens"
    ARQUIVOS_DIR_NAME: str = "arquivos"

    # Propriedades computadas para os caminhos completos. Se 'BACKEND_DIR' mudar, estes
    # caminhos se ajustam automaticamente. O operador '/' é sobrecarregado por 'pathlib' para juntar caminhos.
    @property
    def STATIC_DIR_PATH(self) -> Path:
        return self.BACKEND_DIR / self.STATIC_DIR_NAME

    @property
    def IMAGENS_DIR_PATH(self) -> Path:
        return self.STATIC_DIR_PATH / self.IMAGENS_DIR_NAME

    @property
    def ARQUIVOS_DIR_PATH(self) -> Path:
        # Nota: este diretório está dentro de 'backend', não de 'static'.
        return self.BACKEND_DIR / self.ARQUIVOS_DIR_NAME

    # --- Configurações de API Externa (CloudRF) ---
    # Chave da API CloudRF. É opcional no código, mas obrigatória em tempo de execução.
    # 'Field(None, ...)' significa que, se a variável 'CLOUDRF_API_KEY' não for encontrada no ambiente, o valor será 'None'.
    # <-- ponto crítico: A aplicação não funcionará sem esta chave. A verificação é feita no método 'initialize_directories'.
    CLOUDRF_API_KEY: Optional[str] = Field(None, validation_alias="CLOUDRF_API_KEY")
    # URL da API CloudRF. O tipo 'HttpUrl' garante que é uma URL válida.
    CLOUDRF_API_URL: HttpUrl = Field(default="https://api.cloudrf.com/area", validation_alias="CLOUDRF_API_URL")
    # Timeout para requisições HTTP, em segundos. Um valor generoso para acomodar a latência da API CloudRF.
    HTTP_TIMEOUT: float = Field(default=60.0, validation_alias="HTTP_TIMEOUT")
    # Nível de log para a aplicação (ex: "INFO", "DEBUG").
    LOG_LEVEL: str = "INFO"

    # --- Templates de Simulação Pré-definidos ---
    # Uma lista de dicionários que define os templates disponíveis.
    # Ao ser atribuída ao campo 'TEMPLATES_DISPONIVEIS' que é tipado como 'List[TemplateSettings]',
    # o Pydantic automaticamente valida cada dicionário contra o modelo 'TemplateSettings',
    # convertendo-os em objetos 'TemplateSettings'. Isso captura erros de configuração na inicialização.
    # <-- ponto crítico: Esta é a fonte da verdade para os parâmetros de simulação.
    TEMPLATES_DISPONIVEIS: List[TemplateSettings] = [
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
        print(f"INFO: Verificando/Criando diretório de imagens em: {self.IMAGENS_DIR_PATH}")
        # 'mkdir' cria o diretório. 'parents=True' cria diretórios pais se necessário (ex: 'static/').
        # 'exist_ok=True' evita um erro se o diretório já existir.
        self.IMAGENS_DIR_PATH.mkdir(parents=True, exist_ok=True)
        print(f"INFO: Verificando/Criando diretório de arquivos em: {self.ARQUIVOS_DIR_PATH}")
        self.ARQUIVOS_DIR_PATH.mkdir(parents=True, exist_ok=True)
        # Verificações de sanidade que emitem alertas no log se configurações críticas estiverem ausentes.
        if not self.CLOUDRF_API_KEY:
            print("⚠️ ALERTA DE SEGURANÇA: CLOUDRF_API_KEY não está definida!")
        if not self.BACKEND_PUBLIC_URL:
            print("⚠️ ALERTA DE CONFIGURAÇÃO: BACKEND_PUBLIC_URL não está definida! As URLs de imagem podem estar incorretas.")

    def obter_template(self, template_id: str) -> TemplateSettings:
        """
        Busca um template pelo seu 'id' na lista de templates disponíveis.
        Retorna um template padrão se o id não for encontrado.
        """
        # Como 'TEMPLATES_DISPONIVEIS' já contém objetos 'TemplateSettings' (graças ao Pydantic),
        # podemos iterar e acessar os atributos diretamente (t_obj.id).
        # A expressão geradora `(t_obj for ...)` é mais eficiente em memória do que criar uma lista.
        # `next(..., None)` busca o primeiro item que satisfaz a condição ou retorna 'None' se não encontrar.
        template_obj = next(
            (t_obj for t_obj in self.TEMPLATES_DISPONIVEIS if t_obj.id == template_id),
            None
        )
        # Se nenhum template for encontrado, aplica uma lógica de fallback para evitar erros.
        if not template_obj:
            print(f"⚠️ Template '{template_id}' não encontrado. Usando padrão '{self.TEMPLATES_DISPONIVEIS[0].id}'.")
            # Retorna o primeiro template da lista como padrão.
            return self.TEMPLATES_DISPONIVEIS[0]
        return template_obj

    def listar_templates_ids(self) -> List[str]:
        """Retorna uma lista simples com os IDs de todos os templates disponíveis."""
        # Usa uma list comprehension para extrair de forma concisa o 'id' de cada objeto de template.
        # Útil para, por exemplo, popular um menu dropdown no frontend.
        return [t_obj.id for t_obj in self.TEMPLATES_DISPONIVEIS]

# --- Instanciação Global ---
# Esta é a linha que efetivamente cria o objeto de configuração.
# O Pydantic irá ler o .env, as variáveis de ambiente, validar tudo contra os modelos definidos
# e criar uma única instância 'settings'. Este objeto será importado em outras partes da aplicação.
settings = AppSettings()
