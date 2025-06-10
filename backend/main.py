# backend/main.py

# --- Importações de Módulos ---
# A importação de 'Path' da biblioteca 'pathlib' é utilizada para manipulação de caminhos de
# arquivos e diretórios de forma orientada a objetos e independente do sistema operacional.
# Mesmo que não seja usada diretamente em uma variável, é uma boa prática para tipagem (type hinting)
# e é esperada por algumas funções do FastAPI, como StaticFiles, que pode receber um objeto Path.
from pathlib import Path

# Importações principais do framework FastAPI para a criação da API.
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware # Middleware para gerenciar o Cross-Origin Resource Sharing (CORS).
from fastapi.staticfiles import StaticFiles # Para servir arquivos estáticos como CSS, JS e imagens.

# Importação de logging para registrar eventos e erros da aplicação.
import logging
# Importa a instância 'settings' do módulo de configuração. Este objeto, baseado no Pydantic,
# carrega e valida as variáveis de ambiente (como chaves de API, URLs, etc.),
# centralizando toda a configuração da aplicação em um único local.
from backend.config import settings
# Importa os módulos de rotas (routers). Cada router agrupa os endpoints relacionados a uma
# funcionalidade específica (neste caso, 'kmz' e 'simulation'), ajudando a organizar o projeto.
from backend.routers import kmz, simulation

# --- Instância da Aplicação FastAPI ---
# Aqui criamos a instância principal da aplicação FastAPI.
# Os metadados da API (título, descrição, versão) são carregados a partir do objeto 'settings',
# o que permite que sejam facilmente alterados via variáveis de ambiente sem tocar no código.
app = FastAPI(
    # Nome da aplicação, lido das configurações.
    title=settings.APP_NAME,
    # Descrição que aparecerá na documentação da API (Swagger/ReDoc).
    description="API para processar KMZ e simular cobertura de sinal.",
    # Versão da aplicação, também lida das configurações.
    version=settings.APP_VERSION,
    # URL para o arquivo de especificação OpenAPI (JSON). O uso de f-string com 'settings.API_V1_STR'
    # garante que a URL da documentação acompanhe o versionamento da API (ex: /api/v1/openapi.json).
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    # URL para a interface de documentação interativa Swagger UI.
    docs_url="/docs",
    # URL para a interface de documentação alternativa ReDoc.
    redoc_url="/redoc"
)

# --- Eventos de Ciclo de Vida da Aplicação ---
# O decorador '@app.on_event("startup")' registra uma função para ser executada
# uma única vez, quando o servidor FastAPI é iniciado. É o local ideal para tarefas
# de inicialização, como criar diretórios, estabelecer conexões com bancos de dados, etc.
@app.on_event("startup")
async def startup_event():
    """
    Executa tarefas essenciais na inicialização da aplicação.
    """
    # Chama o método 'initialize_directories' do objeto de configurações.
    # Essa função, definida em 'config.py', é responsável por verificar se os diretórios
    # necessários para a aplicação (uploads, logs, etc.) existem e, se não, criá-los.
    # Isso evita erros de 'FileNotFoundError' durante a execução.
    settings.initialize_directories()

    # Logs de depuração para verificar a configuração do CORS.
    # Isso é extremamente útil ao fazer deploy em serviços como Render, Vercel ou Netlify,
    # pois permite confirmar no console do servidor se as variáveis de ambiente
    # foram carregadas corretamente e se a lista de origens permitidas está como esperado.
    # <-- ponto crítico: Erros de CORS são comuns em produção. Estes logs são a primeira linha de defesa para diagnóstico.
    print(f"INFO: Startup - ALLOWED_ORIGINS_CSV: {settings.ALLOWED_ORIGINS_CSV}")
    print(f"INFO: Startup - NETLIFY_APP_URL: {settings.NETLIFY_APP_URL}")
    print(f"INFO: Startup - Effective ALLOWED_ORIGINS for CORS: {settings.ALLOWED_ORIGINS}")

    # Bloco comentado para uma verificação de segurança adicional.
    # Em um ambiente de produção, seria crucial garantir que a chave da API CloudRF está
    # configurada. Se não estiver, a aplicação não funcionaria. Descomentar este bloco
    # faria a aplicação falhar na inicialização (fail-fast), o que é uma boa prática
    # para evitar que um serviço "zumbi" (rodando mas não funcional) fique no ar.
    # if not settings.CLOUDRF_API_KEY:
    #     print("ALERTA CRÍTICO: CLOUDRF_API_KEY não está configurada!")
    #     raise RuntimeError("Configuração crítica faltando: CLOUDRF_API_KEY não definida.")
    
    print("INFO: Aplicação iniciada, configurações carregadas e diretórios verificados/criados.")

# --- Configuração do CORS ---
# O middleware 'CORSMiddleware' é adicionado à aplicação para lidar com as políticas de CORS.
# CORS é um mecanismo de segurança do navegador que impede que um frontend (ex: em netlify.app)
# faça requisições para uma API em um domínio diferente (ex: em onrender.com), a menos que
# a API autorize explicitamente.
app.add_middleware(
    CORSMiddleware,
    # 'allow_origins' é a lista de domínios (frontends) que têm permissão para acessar esta API.
    # Carregar esta lista de 'settings.ALLOWED_ORIGINS' é fundamental para a segurança e flexibilidade,
    # permitindo adicionar novos ambientes (desenvolvimento, staging) sem alterar o código.
    allow_origins=settings.ALLOWED_ORIGINS, # <-- ponto crítico: A configuração mais importante do CORS.
    # 'allow_credentials=True' permite que cookies e headers de autenticação sejam enviados pelo navegador.
    allow_credentials=True,
    # 'allow_methods=["*"]' permite todos os métodos HTTP padrão (GET, POST, PUT, DELETE, etc.).
    allow_methods=["*"],
    # 'allow_headers=["*"]' permite que o frontend envie quaisquer cabeçalhos na requisição.
    allow_headers=["*"],
)

# --- Montagem de Arquivos Estáticos ---
# A função 'app.mount' cria um "sub-aplicativo" que serve arquivos diretamente do sistema de arquivos.
# Isso é usado para disponibilizar arquivos que não são parte da API, como o próprio arquivo KMZ gerado.
app.mount(
    # '/static' é o prefixo da URL. Qualquer requisição para `http://seu-domínio/static/...`
    # será tratada por este montador.
    "/static",
    # 'StaticFiles' é a classe do FastAPI que lida com o serviço de arquivos.
    # O argumento 'directory' aponta para o caminho no servidor onde os arquivos estão localizados.
    # Usar 'settings.STATIC_DIR_PATH' garante que o caminho está correto e centralizado nas configurações.
    StaticFiles(directory=settings.STATIC_DIR_PATH),
    # 'name="static"' dá um nome interno para esta montagem, que pode ser usado para gerar URLs.
    name="static"
)

# --- Inclusão dos Routers ---
# 'app.include_router' é a forma de organizar e escalar a aplicação. Em vez de definir todos
# os endpoints neste arquivo, eles são agrupados em arquivos separados ('kmz.py', 'simulation.py')
# e depois incluídos na aplicação principal.
# O 'prefix=settings.API_V1_STR' adiciona um prefixo de caminho a todas as rotas definidas no router.
# Por exemplo, uma rota '/calculate' em 'simulation.router' se tornará '/api/v1/calculate'.
# Isso é essencial para o versionamento da API.
app.include_router(kmz.router, prefix=settings.API_V1_STR, tags=["KMZ Operations"])
app.include_router(simulation.router, prefix=settings.API_V1_STR, tags=["Simulation"])

# --- Endpoint Raiz ---
# Este é o endpoint principal da API (o caminho "/").
# É útil para verificações de saúde ("health checks") ou simplesmente para fornecer uma
# mensagem de boas-vindas.
@app.get("/", tags=["Root"])
def read_root() -> dict[str, str]: # A anotação de tipo '-> dict[str, str]' indica que a função retorna um dicionário com chaves e valores string.
    """
    Endpoint raiz da API. Retorna uma mensagem de boas-vindas.
    """
    # Retorna uma resposta JSON simples. Usar 'settings.APP_NAME' mantém a consistência.
    return {"message": f"Bem-vindo à {settings.APP_NAME}!"}

# --- Ponto de entrada para execução (opcional, para debug local com Uvicorn) ---
# Este bloco 'if __name__ == "__main__":' permite que o arquivo seja executado diretamente
# com 'python -m backend.main'. Isso inicia um servidor de desenvolvimento Uvicorn, o que é
# muito útil para testes locais rápidos sem precisar usar o comando 'uvicorn backend.main:app --reload'.
# Em produção, um servidor WSGI/ASGI como Gunicorn ou o próprio Uvicorn (sem modo de desenvolvimento)
# será usado para executar a aplicação, então este bloco não será chamado.
# if __name__ == "__main__":
#     import uvicorn
#     # O ideal é que o host e a porta também venham das configurações para consistência.
#     # Por exemplo: uvicorn.run(app, host=settings.SERVER_HOST, port=settings.SERVER_PORT)
#     uvicorn.run(app, host="0.0.0.0", port=8000)

# --- Configuração global do logging ---
# 'logging.basicConfig' configura o sistema de logging padrão do Python.
# É chamado aqui no final do arquivo para garantir que todas as configurações
# (incluindo as dos routers importados) sejam aplicadas.
logging.basicConfig(
    # O nível de log (DEBUG, INFO, WARNING, ERROR) é pego das configurações.
    # 'getattr' é usado de forma segura para obter o atributo do módulo 'logging'
    # (ex: logging.INFO) a partir da string "INFO". Se o nível for inválido,
    # ele assume 'logging.INFO' como padrão.
    # <-- ponto crítico: Controlar o nível de log via variável de ambiente é vital para depuração em produção
    # sem precisar fazer um novo deploy.
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    # Define o formato de cada mensagem de log, incluindo data, nome do logger, nível e a mensagem.
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    # Define o formato da data e hora no log.
    datefmt='%Y-%m-%d %H:%M:%S'
)
# Cria uma instância de logger específica para este arquivo (main.py).
# Usar 'logging.getLogger(__name__)' é a convenção padrão e permite um controle
# mais granular sobre os logs de diferentes partes da aplicação.
logger = logging.getLogger(__name__)
