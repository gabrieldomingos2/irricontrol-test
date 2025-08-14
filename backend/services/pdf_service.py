# backend/services/pdf_service.py

from fpdf import FPDF
from datetime import datetime
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
import re

from backend.config import settings
from backend.services.i18n_service import i18n_service
from backend.services.kmz_exporter import _get_formatted_entity_name_for_backend


logger = logging.getLogger("irricontrol")

# Definição de cores em RGB
COR_PRIMARIA = (34, 197, 94)  # Tailwind green-500
COR_SECUNDARIA = (10, 15, 20) # Cor de fundo escura
COR_TEXTO_ESCURO = (50, 50, 50)
COR_TEXTO_CLARO = (255, 255, 255)

class PDFReportGenerator:
    def __init__(self, lang: str = 'pt-br'):
        self.t = i18n_service.get_translator(lang) # Tradutor para o idioma selecionado
        self.pdf = FPDF()
        self.setup_pdf()

    def setup_pdf(self):
        self.pdf.set_auto_page_break(auto=True, margin=15)
        self.pdf.add_page()
        
        fonts_dir = Path(__file__).parent / "fonts"
        fonts_dir.mkdir(parents=True, exist_ok=True) 

        try:
            # Adiciona as fontes. FPDF fará o registro globalmente na primeira vez.
            self.pdf.add_font("FreeSans", "", str(fonts_dir / "FreeSans.ttf"), uni=True)
            self.pdf.add_font("FreeSans", "B", str(fonts_dir / "FreeSansBold.ttf"), uni=True)
            self.pdf.add_font("FreeSans", "I", str(fonts_dir / "FreeSansOblique.ttf"), uni=True)
            self.pdf.add_font("FreeSans", "BI", str(fonts_dir / "FreeSansBoldOblique.ttf"), uni=True)
            
            self.pdf.set_font("FreeSans", size=10) # Define FreeSans como fonte padrão
        except Exception as e:
            logger.error(f"Erro ao carregar fontes FreeSans, usando Helvetica como fallback: {e}")
            self.pdf.set_font("Helvetica", size=10) # Fallback para Helvetica se der erro


    def add_header(self):
        logo_path = settings.IMAGENS_DIR_PATH / "logo-irricontrol.png"
        if logo_path.exists():
            self.pdf.image(str(logo_path), x=10, y=8, w=30)
        
        self.pdf.set_fill_color(*COR_SECUNDARIA)
        self.pdf.rect(0, 0, self.pdf.w, 30, 'F')

        self.pdf.set_font("FreeSans", "B", 16)
        self.pdf.set_text_color(255, 255, 255)
        self.pdf.set_xy(45, 10)
        self.pdf.cell(0, 10, self.t("ui.titles.main"), align="L")

        self.pdf.set_font("FreeSans", size=8) # Normal, para o APP_NAME
        self.pdf.set_text_color(200, 200, 200)
        self.pdf.set_xy(45, 18)
        self.pdf.cell(0, 10, settings.APP_NAME, align="L")
        
        report_date = datetime.now().strftime("%d/%m/%Y %H:%M")
        self.pdf.set_font("FreeSans", size=8) # Normal, para a data
        self.pdf.set_text_color(200, 200, 200)
        self.pdf.set_xy(self.pdf.w - 50, 10)
        self.pdf.cell(0, 10, f"{self.t('ui.labels.report_date')} {report_date}", align="R")

        self.pdf.ln(25)

    def add_footer(self):
        self.pdf.set_y(-15)
        self.pdf.set_font("FreeSans", "I", 8)
        self.pdf.set_text_color(150, 150, 150)
        self.pdf.cell(0, 10, f"{self.t('ui.labels.powered_by')} Irricontrol | {self.pdf.page_no()}/{{nb}}", align="C")

    def add_section_title(self, title: str):
        self.pdf.set_font("FreeSans", "B", 12)
        self.pdf.set_text_color(*COR_PRIMARIA)
        self.pdf.ln(5)
        self.pdf.cell(0, 10, title, border=0, ln=1, align="L")
        self.pdf.set_text_color(*COR_TEXTO_ESCURO)
        self.pdf.ln(2)

    def add_text_line(self, label: str, value: Any):
        self.pdf.set_font("FreeSans", "B", 10)
        self.pdf.cell(40, 7, str(label), 0, 0, 'L')
        self.pdf.set_font("FreeSans", size=10)
        self.pdf.cell(0, 7, str(value), 0, 1, 'L')

    def add_equipment_table(self, title: str, data: List[Dict[str, Any]], is_main_antenna_table: bool = False, is_central_table: bool = False):
        if not data:
            return
        
        self.add_section_title(title)
        
        col_widths = [self.pdf.w * 0.25, self.pdf.w * 0.35, self.pdf.w * 0.2, self.pdf.w * 0.1]
        
        self.pdf.set_font("FreeSans", "B", 9)
        self.pdf.set_fill_color(230, 230, 230)
        self.pdf.set_text_color(*COR_TEXTO_ESCURO)
        self.pdf.cell(col_widths[0], 8, self.t("ui.labels.name"), 1, 0, 'C', 1)
        self.pdf.cell(col_widths[1], 8, self.t("ui.labels.coordinates"), 1, 0, 'C', 1)
        self.pdf.cell(col_widths[2], 8, self.t("ui.labels.status"), 1, 0, 'C', 1)
        self.pdf.cell(col_widths[3], 8, self.t("ui.labels.height_short"), 1, 1, 'C', 1) 
        
        self.pdf.set_font("FreeSans", size=8)
        self.pdf.set_fill_color(245, 245, 245)
        fill = False

        for item in data:
            name = str(item.get('nome', 'N/A'))

            if item.get('type') == 'pivo':
                match = re.search(r'(\d+)$', str(item.get('nome', '')))
                pivo_num = match.group(1) if match else ''
                name = f"{self.t('entity_names.pivot')} {pivo_num}".strip()
            elif item.get('type') == 'bomba':
                name = self.t("entity_names.irripump")
            
            elif is_main_antenna_table:
                name = _get_formatted_entity_name_for_backend(entity_data=item, is_main_antenna=True, t=self.t, for_pdf=True)
            elif is_central_table:
                name = _get_formatted_entity_name_for_backend(entity_data=item, is_main_antenna=False, t=self.t, for_pdf=True)
            elif title == self.t("ui.labels.repeaters"):
                name = _get_formatted_entity_name_for_backend(entity_data=item, is_main_antenna=False, t=self.t, for_pdf=True)
            
            coords = f"Lat: {item.get('lat'):.5f}, Lon: {item.get('lon'):.5f}"

            if is_central_table or title == self.t("ui.labels.repeaters"):
                status_text = "*"
                status_color = (0, 0, 0)
            else:
                status_text = self.t("tooltips.out_of_signal") if item.get('fora', True) else self.t("tooltips.in_signal")
                status_color = (255, 0, 0) if item.get('fora', True) else (0, 128, 0)

            altura_para_exibir = item.get('altura')
            if altura_para_exibir is None:
                altura_para_exibir = item.get('altura_receiver', 'N/A') 

            altura_str_final = f"{altura_para_exibir}m" 
            
            self.pdf.set_text_color(*COR_TEXTO_ESCURO)
            self.pdf.cell(col_widths[0], 7, name, 1, 0, 'L', fill)
            self.pdf.cell(col_widths[1], 7, coords, 1, 0, 'L', fill)
            
            self.pdf.set_text_color(*status_color)
            self.pdf.cell(col_widths[2], 7, status_text, 1, 0, 'C', fill)
            
            self.pdf.set_text_color(*COR_TEXTO_ESCURO)
            self.pdf.cell(col_widths[3], 7, altura_str_final, 1, 1, 'C', fill)
            fill = not fill
        self.pdf.ln(5)


    def generate_report(
        self,
        antena_principal_data: Optional[Dict[str, Any]],
        pivos_data: List[Dict[str, Any]],
        bombas_data: List[Dict[str, Any]],
        repetidoras_data: List[Dict[str, Any]],
        template_id: str,
        map_image_base64: Optional[str] = None
    ) -> Path:
        
        self.add_header()
        
        self.add_section_title(self.t("ui.labels.general_info"))
        
        template_obj = settings.obter_template(template_id)
        nome_template_limpo = template_obj.nome

        self.add_text_line(f"{self.t('ui.labels.template')}:", nome_template_limpo)
        self.pdf.ln(5)

        # --- RESUMO DE COBERTURA ---
        total_pivos = len(pivos_data)
        fora_cobertura = sum(1 for p in pivos_data if p.get('fora', True))
        
        total_repetidoras_resumo = 0
        total_centrais_resumo = 0

        if antena_principal_data:
            main_antenna_type = antena_principal_data.get('type')
            if main_antenna_type == 'central':
                total_centrais_resumo += 1
            elif main_antenna_type == 'central_repeater_combined':
                total_centrais_resumo += 1
                total_repetidoras_resumo += 1
            else: 
                total_repetidoras_resumo += 1
        
        for rep_data in repetidoras_data:
            rep_type = rep_data.get('type')
            if rep_type == 'central':
                total_centrais_resumo += 1
            elif rep_type == 'central_repeater_combined':
                total_centrais_resumo += 1
                total_repetidoras_resumo += 1
            else: 
                total_repetidoras_resumo += 1

        self.add_text_line(self.t('ui.labels.total_pivots'), total_pivos)
        self.add_text_line(self.t('ui.labels.out_of_coverage'), fora_cobertura)
        self.add_text_line(self.t('ui.labels.total_repeaters'), total_repetidoras_resumo)
        self.add_text_line(self.t('ui.labels.central_count'), total_centrais_resumo)
        self.add_text_line(self.t('ui.labels.pump_houses'), len(bombas_data))
        self.pdf.ln(5)

        if map_image_base64:
            self.add_section_title(self.t("ui.labels.map_view"))
            self.pdf.multi_cell(0, 10, "Mapa (requer captura de tela do frontend e decodificação)", border=1, align='C')
            self.pdf.ln(5)

        # --- INÍCIO DAS TABELAS DE EQUIPAMENTOS NA ORDEM DESEJADA ---

        # 1. Tabela de Centrais (Lógica de altura CORRIGIDA)
        all_centrals_for_table = []
        if antena_principal_data:
            # Se for 'central' ou 'central_repeater_combined', adicione à lista
            if antena_principal_data.get('type') in ['central', 'central_repeater_combined']:
                central_copy = antena_principal_data.copy()
                central_copy['is_main_antenna'] = True
                # Se for do tipo combinado, defina a altura como 5m para a tabela de centrais
                if central_copy.get('type') == 'central_repeater_combined':
                    central_copy['altura'] = 5
                all_centrals_for_table.append(central_copy)

        for rep_data in repetidoras_data:
            if rep_data.get('type') in ['central', 'central_repeater_combined']:
                central_copy = rep_data.copy()
                if central_copy.get('type') == 'central_repeater_combined':
                    central_copy['altura'] = 5
                all_centrals_for_table.append(central_copy)

        all_centrals_for_table.sort(key=lambda x: (not x.get('is_main_antenna', False), x.get('nome', '')))
        
        if all_centrals_for_table:
            self.add_equipment_table(self.t("ui.labels.central_count"), all_centrals_for_table, is_central_table=True, is_main_antenna_table=True)

        # 2. Tabela de Repetidoras (Lógica de altura CORRIGIDA)
        all_repeaters_for_table = []
        
        # Adiciona repetidoras "normais"
        normal_repeaters = [
            rep for rep in repetidoras_data 
            if rep.get('type') not in ['central', 'central_repeater_combined']
        ]
        all_repeaters_for_table.extend(normal_repeaters)

        # Adiciona a "parte repetidora" das entidades combinadas, com a altura REAL
        if antena_principal_data and antena_principal_data.get('type') == 'central_repeater_combined':
            repeater_copy = antena_principal_data.copy()
            # A altura REAL é mantida aqui
            repeater_copy['type'] = 'default'  # Força a formatação do nome como repetidora
            all_repeaters_for_table.append(repeater_copy)
            
        for rep_data in repetidoras_data:
            if rep_data.get('type') == 'central_repeater_combined':
                repeater_copy = rep_data.copy()
                # A altura REAL é mantida aqui
                repeater_copy['type'] = 'default'
                all_repeaters_for_table.append(repeater_copy)
        
        all_repeaters_for_table.sort(key=lambda x: x.get('nome', ''))
        
        self.add_equipment_table(self.t("ui.labels.repeaters"), all_repeaters_for_table)

        # 3. Tabela de Irripumps
        self.add_equipment_table(self.t("ui.labels.pump_houses"), bombas_data)

        # 4. Tabela de Pivôs
        self.add_equipment_table(self.t("ui.labels.pivots"), pivos_data)

        # --- FIM DAS TABELAS DE EQUIPAMENTOS ---

        output_dir = settings.ARQUIVOS_DIR_PATH / "reports"
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename_prefix_clean = self.t('kml.filename_prefix')
        report_filename = f"{filename_prefix_clean}_report_{timestamp}.pdf"
        output_path = output_dir / report_filename
        
        self.pdf.output(str(output_path))
        logger.info(f"Relatório PDF gerado em: {output_path}")
        return output_path