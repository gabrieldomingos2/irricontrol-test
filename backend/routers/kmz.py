from fastapi import APIRouter, UploadFile, File, Query, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import zipfile
import json 
import simplekml 
from datetime import datetime 
from pathlib import Path
import logging

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
# A constante COLOUR_KEY_FILENAME foi removida daqui, pois será determinada dinamicamente

@router.post("/processar")
async def processar_kmz_endpoint(file: UploadFile = File(...)):
    try:
        logger.info("📥 Recebendo arquivo KMZ...")
        conteudo = await file.read()
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
    imagem: str = Query(..., description="Nome da imagem PNG principal (ex: 'cobertura_principal.png'). Formato esperado: 'principal_[template_id]_...'.png"),
    bounds_file: str = Query(..., description="Nome do JSON de bounds principal (ex: 'cobertura_principal.json').")
):
    logger.info("📦 Iniciando exportação KMZ via endpoint /exportar...")
    if not INPUT_KMZ_PATH.exists():
        raise HTTPException(status_code=400, detail=f"Nenhum KMZ foi processado ainda ({_INPUT_KMZ_FILENAME}). Faça o upload primeiro.")
    
    caminho_imagem_principal_servidor = _GENERATED_IMAGES_DIR / imagem
    caminho_bounds_principal_servidor = _GENERATED_IMAGES_DIR / bounds_file

    if not caminho_imagem_principal_servidor.exists():
        raise HTTPException(status_code=404, detail=f"Imagem principal '{imagem}' não encontrada em {_GENERATED_IMAGES_DIR}.")
    if not caminho_bounds_principal_servidor.exists():
        raise HTTPException(status_code=404, detail=f"Bounds '{bounds_file}' não encontrados em {_GENERATED_IMAGES_DIR}.")

    try:
        # --- Obter dados do template ---
        image_name_base = imagem.lower()
        if image_name_base.startswith("principal_"):
            # Remove o prefixo "principal_" para obter o restante do nome do arquivo
            image_name_suffix = image_name_base[len("principal_"):] # Ex: "brazil_v6_tx35m_..."
        else:
            logger.error(f"Nome da imagem '{imagem}' não começa com 'principal_'.")
            raise HTTPException(status_code=400, detail=f"Formato de nome de imagem inválido: {imagem}")

        selected_template = None
        # Guarda o ID que foi tentado para uma mensagem de erro mais clara
        attempted_extracted_id_for_error = image_name_suffix 

        # Ordena os templates configurados pelo comprimento do ID (do maior para o menor).
        # Isso é crucial se um ID de template for um prefixo de outro 
        # (ex: "Europe_V6" e "Europe_V6_XR", para que "Europe_V6_XR" seja verificado primeiro).
        sorted_templates = sorted(settings.TEMPLATES_DISPONIVEIS, key=lambda t: len(t.id), reverse=True)

        for t_config in sorted_templates:
            template_id_config_lower = t_config.id.lower() # ID do template da configuração, em minúsculas
            
            # Verifica se o sufixo do nome da imagem começa com o ID do template da configuração
            if image_name_suffix.startswith(template_id_config_lower):
                # Confirma se a correspondência é exata ou se o ID no nome da imagem 
                # é seguido por um underscore '_'. Isso evita correspondências parciais erradas
                # (ex: se existisse um ID "brazil", não deveria corresponder a "brazil_v6...").
                if (len(image_name_suffix) == len(template_id_config_lower) or \
                   (len(image_name_suffix) > len(template_id_config_lower) and \
                    image_name_suffix[len(template_id_config_lower)] == '_')):
                    selected_template = t_config
                    attempted_extracted_id_for_error = t_config.id # Usa o ID real do template para logs/erros
                    logger.info(f"Template correspondente encontrado: ID '{t_config.id}' para imagem '{imagem}'")
                    break # Para o loop assim que a melhor correspondência (mais longa) for encontrada
        
        if not selected_template:
            # Se nenhum template foi encontrado, tenta uma "melhor suposição" para o ID na mensagem de erro
            parts = image_name_suffix.split('_')
            guessed_id_parts = []
            # Tenta reconstruir o ID até encontrar algo que não pareça parte dele (ex: 'tx', 'lat', 'lon')
            # Esta é uma heurística e pode precisar de ajuste dependendo dos seus padrões de nome de arquivo.
            for part in parts:
                # Adiciona mais padrões de terminação do ID se necessário
                if not (part.startswith("tx") or part.startswith("lat") or part.startswith("lon") or part.startswith("bwi") or part.isdigit() or "mhz" in part):
                    guessed_id_parts.append(part)
                else:
                    break # Para quando encontrar um parâmetro técnico
            
            if guessed_id_parts:
                attempted_extracted_id_for_error = "_".join(guessed_id_parts)
            else: # Se não conseguir adivinhar, usa a primeira parte do sufixo ou o sufixo inteiro
                 attempted_extracted_id_for_error = image_name_suffix.split('_')[0] if '_' in image_name_suffix else image_name_suffix

            logger.error(f"Nenhum template correspondente encontrado para o nome base da imagem: '{image_name_suffix}' (derivado de '{imagem}')")
            raise HTTPException(status_code=404, detail=f"Template com ID derivado '{attempted_extracted_id_for_error}' não encontrado nas configurações.")

        # A partir daqui, selected_template é o objeto TemplateSettings correto
        template_id_for_name = selected_template.id 
        template_frq = selected_template.frq        
        template_txw = selected_template.transmitter.txw # Acesso correto ao atributo do sub-objeto
        
        study_date_str = datetime.now().strftime('%Y-%m-%d')

        # --- Determinar o nome do arquivo da legenda dinamicamente ---
        if hasattr(selected_template, 'col') and selected_template.col:
            dynamic_colour_key_filename = f"{selected_template.col}.key.png"
            logger.info(f"Usando legenda específica do template: {dynamic_colour_key_filename}")
        else:
            # Se o template não tiver o atributo 'col' ou ele estiver vazio, lança um erro.
            logger.error(f"Atributo 'col' da legenda não encontrado ou vazio no template '{selected_template.id}'. Verifique as configurações do template.")
            raise HTTPException(status_code=500, detail=f"Configuração da legenda (col) ausente para o template {selected_template.id}")
        # --- Fim da determinação da legenda ---

        antena_data, pivos_data, ciclos_data, bombas_data = kmz_parser.parse_kmz(str(INPUT_KMZ_PATH), str(_INPUT_KMZ_DIR))

        with open(caminho_bounds_principal_servidor, "r") as f:
            bounds_principal_data = json.load(f).get("bounds")

        if not antena_data or not bounds_principal_data:
            logger.warning("⚠️ Dados incompletos para exportar. Antena ou bounds_principal ausentes.")
            raise HTTPException(status_code=500, detail="Dados essenciais (antena, bounds_principal) ausentes para exportar.")

        kml = simplekml.Kml(name="Estudo de Sinal Irricontrol") 
        doc = kml.document 

        arquivos_de_imagem_para_kmz = kmz_exporter.build_kml_document_and_get_image_list(
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
        logger.info(f"  -> KML temporário salvo em: {caminho_kml_temp}")

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        nome_kmz_final = f"estudo-irricontrol-{timestamp}.kmz"
        caminho_kmz_final_servidor = _INPUT_KMZ_DIR / nome_kmz_final

        logger.info(f"  -> Criando KMZ final: {caminho_kmz_final_servidor}")
        with zipfile.ZipFile(str(caminho_kmz_final_servidor), "w", zipfile.ZIP_DEFLATED) as kmz_zip:
            kmz_zip.write(str(caminho_kml_temp), "doc.kml") 
            
            added_to_zip = set()
            for path_origem_img_servidor, nome_destino_img_kmz in arquivos_de_imagem_para_kmz:
                if nome_destino_img_kmz not in added_to_zip:
                    if path_origem_img_servidor.exists():
                        kmz_zip.write(str(path_origem_img_servidor), nome_destino_img_kmz)
                        added_to_zip.add(nome_destino_img_kmz)
                        logger.info(f"      -> Arquivo '{nome_destino_img_kmz}' adicionado ao KMZ.")
                    else:
                        logger.warning(f"      -> ⚠️ Imagem '{path_origem_img_servidor}' não encontrada, não adicionada ao KMZ.")
        
        background_tasks.add_task(Path.unlink, caminho_kml_temp, missing_ok=True)
        logger.info("  -> Exportação KMZ concluída.")
        return FileResponse(
            str(caminho_kmz_final_servidor),
            media_type="application/vnd.google-earth.kmz",
            filename=nome_kmz_final,
            background=background_tasks
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