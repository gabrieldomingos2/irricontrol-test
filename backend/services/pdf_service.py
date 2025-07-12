# backend/services/pdf_service.py

from fpdf import FPDF
from datetime import datetime
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

from backend.config import settings
from backend.services.i18n_service import i18n_service

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
        # Usando 'Helvetica' ou 'Arial' para fontes padrão do FPDF.
        # Estas fontes não suportam emojis ou caracteres Unicode complexos.
        # Para isso, uma fonte Unicode (como DejaVuSans.ttf) precisaria ser adicionada
        # e registrada (self.pdf.add_font) e então usada (self.pdf.set_font).
        # Por enquanto, vamos limpar os textos que contêm emojis.
        self.pdf.set_font("Helvetica", size=10) # Fonte padrão

    def add_header(self):
        # Logo
        logo_path = settings.IMAGENS_DIR_PATH / "logo-irricontrol.png"
        if logo_path.exists():
            self.pdf.image(str(logo_path), x=10, y=8, w=30)
        
        self.pdf.set_fill_color(*COR_SECUNDARIA) # Cor de fundo do cabeçalho
        self.pdf.rect(0, 0, self.pdf.w, 30, 'F') # Retângulo para o cabeçalho

        self.pdf.set_font("Helvetica", "B", 16)
        self.pdf.set_text_color(255, 255, 255) # Branco
        self.pdf.set_xy(45, 10)
        self.pdf.cell(0, 10, self.t("ui.titles.main"), align="L")

        self.pdf.set_font("Helvetica", size=8)
        self.pdf.set_text_color(200, 200, 200) # Cinza claro
        self.pdf.set_xy(45, 18)
        self.pdf.cell(0, 10, settings.APP_NAME, align="L")
        
        # Data do relatório
        report_date = datetime.now().strftime("%d/%m/%Y %H:%M")
        self.pdf.set_font("Helvetica", size=8)
        self.pdf.set_text_color(200, 200, 200)
        self.pdf.set_xy(self.pdf.w - 50, 10)
        self.pdf.cell(0, 10, f"{self.t('ui.labels.report_date')} {report_date}", align="R")

        self.pdf.ln(25) # Pula espaço após o cabeçalho

    def add_footer(self):
        self.pdf.set_y(-15)
        self.pdf.set_font("Helvetica", "I", 8)
        self.pdf.set_text_color(150, 150, 150) # Cinza
        self.pdf.cell(0, 10, f"{self.t('ui.labels.powered_by')} Irricontrol | {self.pdf.page_no()}/{{nb}}", align="C")

    def add_section_title(self, title: str):
        self.pdf.set_font("Helvetica", "B", 12)
        self.pdf.set_text_color(*COR_PRIMARIA) # Verde
        self.pdf.ln(5)
        self.pdf.cell(0, 10, title, border=0, ln=1, align="L")
        self.pdf.set_text_color(*COR_TEXTO_ESCURO) # Volta para cor padrão
        self.pdf.ln(2)

    def add_text_line(self, label: str, value: Any):
        self.pdf.set_font("Helvetica", "B", 10)
        # Limpa emojis/caracteres não ASCII do label
        cleaned_label = str(label).encode('ascii', 'ignore').decode('ascii')
        self.pdf.cell(40, 7, cleaned_label, 0, 0, 'L')
        self.pdf.set_font("Helvetica", size=10)
        # Limpa emojis/caracteres não ASCII do value
        cleaned_value = str(value).encode('ascii', 'ignore').decode('ascii')
        self.pdf.cell(0, 7, cleaned_value, 0, 1, 'L')

    def add_equipment_table(self, title: str, data: List[Dict[str, Any]]):
        if not data:
            return
        
        self.add_section_title(title)
        
        # Ajuste de largura das colunas
        # Colunas: Nome (25%), Coordenadas (35%), Status (20%), Altura (10%)
        col_widths = [self.pdf.w * 0.25, self.pdf.w * 0.35, self.pdf.w * 0.2, self.pdf.w * 0.1]
        
        # Cabeçalho da tabela
        self.pdf.set_font("Helvetica", "B", 9)
        self.pdf.set_fill_color(230, 230, 230) # Cinza claro
        self.pdf.set_text_color(*COR_TEXTO_ESCURO)
        self.pdf.cell(col_widths[0], 8, self.t("ui.labels.name"), 1, 0, 'C', 1)
        self.pdf.cell(col_widths[1], 8, self.t("ui.labels.coordinates"), 1, 0, 'C', 1)
        self.pdf.cell(col_widths[2], 8, self.t("ui.labels.status"), 1, 0, 'C', 1)
        self.pdf.cell(col_widths[3], 8, self.t("ui.labels.height_short"), 1, 1, 'C', 1) 
        
        # Dados da tabela
        self.pdf.set_font("Helvetica", size=8)
        self.pdf.set_fill_color(245, 245, 245) # Cinza mais claro
        fill = False

        for item in data:
            # Limpa emojis/caracteres não ASCII dos valores antes de passá-los para a célula
            name = str(item.get('nome', 'N/A')).encode('ascii', 'ignore').decode('ascii')
            coords = f"Lat: {item.get('lat'):.5f}, Lon: {item.get('lon'):.5f}".encode('ascii', 'ignore').decode('ascii')
            status = self.t("tooltips.out_of_signal") if item.get('fora', True) else self.t("tooltips.in_signal")
            status = status.encode('ascii', 'ignore').decode('ascii') # Limpa o status também
            altura = f"{item.get('altura', item.get('altura_receiver', 'N/A'))}m".encode('ascii', 'ignore').decode('ascii')
            
            self.pdf.set_text_color(*COR_TEXTO_ESCURO)
            self.pdf.cell(col_widths[0], 7, name, 1, 0, 'L', fill)
            self.pdf.cell(col_widths[1], 7, coords, 1, 0, 'L', fill)
            
            # Cor do status
            if item.get('fora', True): # Fora de sinal
                self.pdf.set_text_color(255, 0, 0) # Vermelho
            else: # Com sinal
                self.pdf.set_text_color(0, 128, 0) # Verde
            self.pdf.cell(col_widths[2], 7, status, 1, 0, 'C', fill)
            
            self.pdf.set_text_color(*COR_TEXTO_ESCURO) # Volta cor do texto
            self.pdf.cell(col_widths[3], 7, altura, 1, 1, 'C', fill)
            fill = not fill
        self.pdf.ln(5)


    def generate_report(
        self,
        antena_principal_data: Optional[Dict[str, Any]],
        pivos_data: List[Dict[str, Any]],
        bombas_data: List[Dict[str, Any]],
        repetidoras_data: List[Dict[str, Any]],
        template_id: str,
        map_image_base64: Optional[str] = None # Se você for passar uma imagem do mapa
    ) -> Path:
        
        self.add_header()
        
        self.add_section_title(self.t("ui.labels.general_info"))
        
        # Obter o nome do template e remover emojis ou caracteres não suportados pela fonte
        template_obj = settings.obter_template(template_id)
        nome_template_limpo = template_obj.nome.encode('ascii', 'ignore').decode('ascii')

        self.add_text_line(f"{self.t('ui.labels.template')}:", nome_template_limpo)
        self.pdf.ln(5)

        # Resumo da cobertura
        total_pivos = len(pivos_data)
        fora_cobertura = sum(1 for p in pivos_data if p.get('fora', True))
        self.add_text_line(f"{self.t('ui.labels.total_pivots')}:", total_pivos)
        self.add_text_line(f"{self.t('ui.labels.out_of_coverage')}:", fora_cobertura)
        self.add_text_line(f"{self.t('ui.labels.total_repeaters')}:", len(repetidoras_data))
        self.add_text_line(f"{self.t('ui.labels.pump_houses')}:", len(bombas_data))
        self.pdf.ln(5)

        # Informações da Antena Principal
        if antena_principal_data:
            self.add_section_title(self.t("kml.folders.main_antenna"))
            # Limpa o nome da antena principal, se houver
            antena_nome_limpo = str(antena_principal_data.get('nome', self.t("ui.labels.main_antenna_default"))).encode('ascii', 'ignore').decode('ascii')
            self.add_text_line(self.t("ui.labels.name"), antena_nome_limpo)
            self.add_text_line(self.t("ui.labels.coordinates"), f"Lat: {antena_principal_data.get('lat'):.5f}, Lon: {antena_principal_data.get('lon'):.5f}")
            self.add_text_line(self.t("ui.labels.antenna_height"), f"{antena_principal_data.get('altura')}m")
            self.add_text_line(self.t("ui.labels.receiver_height"), f"{antena_principal_data.get('altura_receiver')}m")
            self.pdf.ln(5)
        
        # Adicionar imagem do mapa (se fornecida)
        if map_image_base64:
            self.add_section_title(self.t("ui.labels.map_view"))
            # FPDF não suporta imagem base64 diretamente. Precisaria salvar para um arquivo temporário.
            self.pdf.multi_cell(0, 10, "Mapa (requer captura de tela do frontend e decodificação)", border=1, align='C')
            self.pdf.ln(5)


        # Tabelas de equipamentos
        self.add_equipment_table(self.t("ui.labels.pivots"), pivos_data)
        self.add_equipment_table(self.t("ui.labels.repeaters"), repetidoras_data)
        self.add_equipment_table(self.t("ui.labels.pump_houses"), bombas_data)


        # Concluir e salvar
        output_dir = settings.ARQUIVOS_DIR_PATH / "reports"
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        # Limpa o nome do arquivo prefixo também, para evitar problemas em sistemas de arquivos
        filename_prefix_clean = self.t('kml.filename_prefix').encode('ascii', 'ignore').decode('ascii')
        report_filename = f"{filename_prefix_clean}_report_{timestamp}.pdf"
        output_path = output_dir / report_filename
        
        self.pdf.output(str(output_path))
        logger.info(f"Relatório PDF gerado em: {output_path}")
        return output_path