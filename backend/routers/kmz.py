from fastapi import APIRouter, UploadFile, File, Query, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import zipfile
import json 
import simplekml 
from datetime import datetime 
from pathlib import Path
import logging

# Assume que os imports de backend estão corretos
from backend.services import kmz_parser
from backend.services import kmz_exporter 
from backend.config import settings

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO) 

router = APIRouter(
    prefix="/kmz",
    tags=["KMZ Operations"],
)

_INPUT_KMZ_DIR: Path = settings.ARQUIVOS_DIR_PATH
_GENERATED_IMAGES_DIR: Path = settings.IMAGENS_DIR_PATH 
_INPUT_KMZ_FILENAME = "entrada.kmz"
INPUT_KMZ_PATH: Path = _INPUT_KMZ_DIR / _INPUT_KMZ_FILENAME

TORRE_ICON_NAME = "cloudrf.png"
DEFAULT_ICON_URL = "http://maps.google.com/mapfiles/kml/pushpin/ylw-pushpin.png"

@router.post("/processar")
async def processar_kmz_endpoint(file: UploadFile = File(...)):
    try:
        logger.info("📥 Recebendo arquivo KMZ...")
        conteudo = await file.read()
        _INPUT_KMZ_DIR.mkdir(parents=True, exist_ok=True)
        with open(INPUT_KMZ_PATH, "wb") as f:
            f.write(conteudo)
        logger.info(f"  -> KMZ salvo em: {INPUT_KMZ_PATH}")
        
        antena, pivos, ciclos, bombas = kmz_parser.parse_kmz(str(INPUT_KMZ_PATH), str(_INPUT_KMZ_DIR))
        
        if not antena:
            raise HTTPException(status_code=404, detail="Antena principal (torre, barracão, etc.) não encontrada no KMZ.")
        return {"antena": antena, "pivos": pivos, "ciclos": ciclos, "bombas": bombas}
    except ValueError as ve:
        logger.error(f"❌ Erro de Validação KMZ: {ve}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"❌ Erro Interno em /kmz/processar: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro interno ao processar KMZ: {type(e).__name__} - {str(e)}")

@router.get("/exportar")
async def exportar_kmz_endpoint(
    background_tasks: BackgroundTasks,
    imagem: str = Query(..., description="Nome da imagem PNG principal (ex: 'cobertura_principal.png')."),
    bounds_file: str = Query(..., description="Nome do JSON de bounds principal (ex: 'cobertura_principal.json').")
):
    logger.info("📦 Iniciando exportação KMZ via endpoint /exportar...")
    if not INPUT_KMZ_PATH.exists():
        raise HTTPException(status_code=400, detail=f"Nenhum KMZ foi processado ainda ({_INPUT_KMZ_FILENAME}). Faça o upload primeiro.")
    
    # ... (toda a lógica de encontrar o template permanece a mesma)
    caminho_imagem_principal_servidor = _GENERATED_IMAGES_DIR / imagem
    caminho_bounds_principal_servidor = _GENERATED_IMAGES_DIR / bounds_file

    if not caminho_imagem_principal_servidor.exists():
        raise HTTPException(status_code=404, detail=f"Imagem principal '{imagem}' não encontrada em {_GENERATED_IMAGES_DIR}.")
    if not caminho_bounds_principal_servidor.exists():
        raise HTTPException(status_code=404, detail=f"Bounds '{bounds_file}' não encontrados em {_GENERATED_IMAGES_DIR}.")

    try:
        image_name_base = imagem.lower()
        if image_name_base.startswith("principal_"):
            image_name_suffix = image_name_base[len("principal_"):]
        else:
            logger.error(f"Nome da imagem '{imagem}' não começa com 'principal_'.")
            raise HTTPException(status_code=400, detail=f"Formato de nome de imagem inválido: {imagem}")

        selected_template = None
        attempted_extracted_id_for_error = image_name_suffix
        sorted_templates = sorted(settings.TEMPLATES_DISPONIVEIS, key=lambda t: len(t.id), reverse=True)

        for t_config in sorted_templates:
            template_id_config_lower = t_config.id.lower()
            if image_name_suffix.startswith(template_id_config_lower):
                if (len(image_name_suffix) == len(template_id_config_lower) or 
                   (len(image_name_suffix) > len(template_id_config_lower) and image_name_suffix[len(template_id_config_lower)] == '_')):
                    selected_template = t_config
                    attempted_extracted_id_for_error = t_config.id
                    logger.info(f"Template correspondente encontrado: ID '{t_config.id}' para imagem '{imagem}'")
                    break
        
        if not selected_template:
            logger.error(f"Nenhum template correspondente encontrado para o nome base da imagem: '{image_name_suffix}'")
            raise HTTPException(status_code=404, detail=f"Template com ID derivado '{attempted_extracted_id_for_error}' não encontrado nas configurações.")

        template_id_for_name = selected_template.id 
        template_frq = selected_template.frq        
        template_txw = selected_template.transmitter.txw
        study_date_str = datetime.now().strftime('%Y-%m-%d')

        if hasattr(selected_template, 'col') and selected_template.col:
            dynamic_colour_key_filename = f"{selected_template.col}.key.png"
            logger.info(f"Usando legenda específica do template: {dynamic_colour_key_filename}")
        else:
            logger.error(f"Atributo 'col' da legenda não encontrado no template '{selected_template.id}'.")
            raise HTTPException(status_code=500, detail=f"Configuração da legenda (col) ausente para o template {selected_template.id}")

        antena_data, pivos_data, ciclos_data, bombas_data = kmz_parser.parse_kmz(str(INPUT_KMZ_PATH), str(_INPUT_KMZ_DIR))

        with open(caminho_bounds_principal_servidor, "r") as f:
            bounds_principal_data = json.load(f).get("bounds")

        if not antena_data or not bounds_principal_data:
            raise HTTPException(status_code=500, detail="Dados essenciais (antena, bounds_principal) ausentes para exportar.")

        kml = simplekml.Kml(name="Estudo de Sinal Irricontrol") 
        doc = kml.document 

        # --- MODIFICAÇÃO PRINCIPAL AQUI ---
        # A função agora retorna uma lista de caminhos para os sub-KMZs gerados.
        sub_kmz_files_to_add = kmz_exporter.build_main_kml_and_sub_kmzs(
            doc=doc,
            antena_data=antena_data,
            pivos_data=pivos_data,
            ciclos_data=ciclos_data,
            bombas_data=bombas_data,
            imagem_principal_nome_relativo=imagem, 
            bounds_principal_data=bounds_principal_data,
            generated_images_dir=_GENERATED_IMAGES_DIR,
            torre_icon_name=TORRE_ICON_NAME,
            default_icon_url=DEFAULT_ICON_URL,
            colour_key_filename=dynamic_colour_key_filename, 
            template_id_for_subfolder=template_id_for_name,
            study_date_str_for_subfolder=study_date_str,
            template_frq_for_main_coverage=template_frq,
            template_txw_for_main_coverage=template_txw
        )

        caminho_kml_temp = _INPUT_KMZ_DIR / "estudo_temp.kml"
        kml.save(str(caminho_kml_temp))
        logger.info(f"  -> KML principal temporário salvo em: {caminho_kml_temp}")

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        nome_kmz_final = f"estudo-irricontrol-{timestamp}.kmz"
        caminho_kmz_final_servidor = _INPUT_KMZ_DIR / nome_kmz_final

        logger.info(f"  -> Criando KMZ final: {caminho_kmz_final_servidor}")
        with zipfile.ZipFile(str(caminho_kmz_final_servidor), "w", zipfile.ZIP_DEFLATED) as kmz_zip:
            # 1. Adiciona o KML principal (o contêiner com os NetworkLinks)
            kmz_zip.write(str(caminho_kml_temp), "doc.kml") 
            
            # 2. Adiciona cada um dos sub-KMZs gerados
            for path_sub_kmz in sub_kmz_files_to_add:
                if path_sub_kmz.exists():
                    kmz_zip.write(str(path_sub_kmz), path_sub_kmz.name)
                    logger.info(f"      -> Sub-KMZ '{path_sub_kmz.name}' adicionado ao KMZ principal.")
                else:
                    logger.warning(f"      -> ⚠️ Sub-KMZ '{path_sub_kmz}' não encontrado, não foi adicionado.")
        
        # --- TAREFAS DE LIMPEZA ATUALIZADAS ---
        # Limpa o KML principal temporário
        background_tasks.add_task(Path.unlink, caminho_kml_temp, missing_ok=True)
        # Limpa cada um dos sub-KMZs temporários que foram criados
        for path_sub_kmz in sub_kmz_files_to_add:
            background_tasks.add_task(Path.unlink, path_sub_kmz, missing_ok=True)

        logger.info("  -> Exportação KMZ concluída.")
        return FileResponse(
            str(caminho_kmz_final_servidor),
            media_type="application/vnd.google-earth.kmz",
            filename=nome_kmz_final
            # Removido 'background=background_tasks' daqui, pois já foi adicionado
        )
    except FileNotFoundError as fnfe:
        logger.error(f"❌ Arquivo não encontrado durante a exportação: {fnfe}", exc_info=True)
        raise HTTPException(status_code=404, detail=f"Arquivo necessário não encontrado: {fnfe.filename}")
    except Exception as e:
        logger.error(f"❌ Erro Interno em /kmz/exportar: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro ao exportar KMZ: {type(e).__name__} - {str(e)}")

@router.get("/icone-torre")
async def get_icone_torre():
    caminho_icone = _GENERATED_IMAGES_DIR / TORRE_ICON_NAME
    if caminho_icone.is_file():
        return FileResponse(str(caminho_icone), media_type="image/png")
    logger.warning(f"Ícone da torre não encontrado em: {caminho_icone}")
    raise HTTPException(status_code=404, detail=f"Ícone '{TORRE_ICON_NAME}' não encontrado.")