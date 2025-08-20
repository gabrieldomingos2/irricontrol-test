# backend/services/pdf_service.py

from __future__ import annotations

import base64
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from fpdf import FPDF

from backend.config import settings
from backend.services.i18n_service import i18n_service
from backend.services.kmz_exporter import _get_formatted_entity_name_for_backend

logger = logging.getLogger("irricontrol")

# Paleta
COR_PRIMARIA = (34, 197, 94)   # Tailwind green-500
COR_SECUNDARIA = (10, 15, 20)  # Fundo topo
COR_TEXTO_ESCURO = (50, 50, 50)
COR_TEXTO_CLARO = (255, 255, 255)


def _fmt_coord(val: Optional[float], ndigits: int = 5) -> str:
    try:
        return f"{float(val):.{ndigits}f}"
    except Exception:
        return "N/A"


class PDFReportGenerator:
    """
    Gera relatório PDF com:
        - cabeçalho/rodapé estilizados,
        - tabelas para Centrais, Repetidoras, Bombas e Pivôs,
        - suporte a imagem de mapa base64 (opcional),
        - fallback de fonte robusto (FreeSans -> Helvetica).
    """

    def __init__(self, lang: str = "pt-br") -> None:
        self.t = i18n_service.get_translator(lang)
        self.pdf = FPDF(orientation="P", unit="mm", format="A4")
        self.font_family: str = "Helvetica"  # definido em setup_pdf
        self.has_unicode: bool = False
        self.setup_pdf()

    # ---------------------- infra de PDF ----------------------

    def setup_pdf(self) -> None:
        self.pdf.set_auto_page_break(auto=True, margin=15)
        self.pdf.alias_nb_pages()
        self.pdf.add_page()

        # Pasta de fontes: aceita settings.FONTS_DIR ou fallback para /services/fonts
        fonts_dir = getattr(settings, "FONTS_DIR", None)
        fonts_path = Path(str(fonts_dir)) if fonts_dir else Path(__file__).resolve().parent / "fonts"
        fonts_path.mkdir(parents=True, exist_ok=True)

        try:
            # Tenta FreeSans com Unicode
            self.pdf.add_font("FreeSans", "", str(fonts_path / "FreeSans.ttf"), uni=True)
            self.pdf.add_font("FreeSans", "B", str(fonts_path / "FreeSansBold.ttf"), uni=True)
            self.pdf.add_font("FreeSans", "I", str(fonts_path / "FreeSansOblique.ttf"), uni=True)
            self.pdf.add_font("FreeSans", "BI", str(fonts_path / "FreeSansBoldOblique.ttf"), uni=True)
            self.font_family = "FreeSans"
            self.has_unicode = True
            self._font(size=10)
        except Exception as e:
            # Fallback: Helvetica (sem Unicode pleno, mas estável)
            logger.warning("FreeSans indisponível (%s). Caindo para Helvetica.", e)
            self.font_family = "Helvetica"
            self.has_unicode = False
            self._font(size=10)

    def _font(self, size: int = 10, style: str = "") -> None:
        """Centraliza a seleção de fonte para evitar 'Undefined font' quando FreeSans não existir."""
        try:
            self.pdf.set_font(self.font_family, style=style, size=size)
        except Exception as e:
            # Último fallback: Helvetica
            logger.error("Erro ao setar fonte '%s'. Forçando Helvetica. (%s)", self.font_family, e)
            self.font_family = "Helvetica"
            self.pdf.set_font(self.font_family, style=style, size=size)

    # ---------------------- componentes ----------------------

    def add_header(self) -> None:
        # Logo: tenta logo-irricontrol.png, senão IRRICONTROL.png
        logo_paths = [
            settings.IMAGENS_DIR_PATH / "logo-irricontrol.png",
            settings.IMAGENS_DIR_PATH / "IRRICONTROL.png",
        ]
        logo_path = next((p for p in logo_paths if p.is_file()), None)

        # Barra superior
        self.pdf.set_fill_color(*COR_SECUNDARIA)
        self.pdf.rect(0, 0, self.pdf.w, 30, "F")

        if logo_path:
            try:
                self.pdf.image(str(logo_path), x=10, y=6, w=30)
            except Exception as e:
                logger.warning("Falha ao inserir logo '%s': %s", logo_path, e)

        # Título
        self._font(style="B", size=16)
        self.pdf.set_text_color(*COR_TEXTO_CLARO)
        self.pdf.set_xy(45, 8)
        self.pdf.cell(0, 8, self.t("ui.titles.main"), align="L")

        # App name
        self._font(size=8)
        self.pdf.set_text_color(200, 200, 200)
        self.pdf.set_xy(45, 16)
        self.pdf.cell(0, 6, settings.APP_NAME, align="L")

        # Data
        report_date = datetime.now().strftime("%d/%m/%Y %H:%M")
        self._font(size=8)
        self.pdf.set_text_color(200, 200, 200)
        self.pdf.set_xy(self.pdf.w - 60, 8)
        self.pdf.cell(50, 8, f"{self.t('ui.labels.report_date')} {report_date}", align="R")

        self.pdf.ln(25)
        self.pdf.set_text_color(*COR_TEXTO_ESCURO)

    def add_footer(self) -> None:
        self.pdf.set_y(-15)
        self._font(style="I", size=8)
        self.pdf.set_text_color(150, 150, 150)
        self.pdf.cell(
            0,
            10,
            f"{self.t('ui.labels.powered_by')} Irricontrol | {self.pdf.page_no()}/{{nb}}",
            align="C",
        )

    def add_section_title(self, title: str) -> None:
        self._font(style="B", size=12)
        self.pdf.set_text_color(*COR_PRIMARIA)
        self.pdf.ln(4)
        self.pdf.cell(0, 8, title, ln=1)
        self.pdf.set_text_color(*COR_TEXTO_ESCURO)
        self.pdf.ln(1)

    def add_text_line(self, label: str, value: Any) -> None:
        self._font(style="B", size=10)
        self.pdf.cell(40, 6, str(label), 0, 0, "L")
        self._font(size=10)
        self.pdf.cell(0, 6, str(value), 0, 1, "L")

    def _table_header(self, col_widths: List[float]) -> None:
        self._font(style="B", size=9)
        self.pdf.set_fill_color(230, 230, 230)
        self.pdf.set_text_color(*COR_TEXTO_ESCURO)
        headers = [
            self.t("ui.labels.name"),
            self.t("ui.labels.coordinates"),
            self.t("ui.labels.status"),
            self.t("ui.labels.height_short"),
        ]
        aligns = ["C", "C", "C", "C"]
        for width, text, align in zip(col_widths, headers, aligns):
            self.pdf.cell(width, 7, text, 1, 0, align, 1)
        self.pdf.ln(7)

    def _format_row(
        self,
        item: Dict[str, Any],
        *,
        is_main_antenna_table: bool = False,
        is_central_table: bool = False,
        title_label: str = "",
    ) -> Tuple[str, str, Tuple[int, int, int], str, str]:
        """Retorna (name, coords, status_color, status_text, altura_str_final)."""
        # Nome
        name = str(item.get("nome", "N/A"))

        if item.get("type") == "pivo":
            match = re.search(r"(\d+)$", str(item.get("nome", "")))
            pivo_num = match.group(1) if match else ""
            name = f"{self.t('entity_names.pivot')} {pivo_num}".strip()
        elif item.get("type") == "bomba":
            name = self.t("entity_names.irripump")
        elif is_main_antenna_table:
            name = _get_formatted_entity_name_for_backend(item, True, self.t, for_pdf=True)
        elif is_central_table:
            name = _get_formatted_entity_name_for_backend(item, False, self.t, for_pdf=True)
        elif title_label == self.t("ui.labels.repeaters"):
            name = _get_formatted_entity_name_for_backend(item, False, self.t, for_pdf=True)

        # Coords
        coords = f"Lat: {_fmt_coord(item.get('lat'))}, Lon: {_fmt_coord(item.get('lon'))}"

        # Status
        if is_central_table or title_label == self.t("ui.labels.repeaters"):
            status_text = "*"
            status_color = (0, 0, 0)
        else:
            fora = bool(item.get("fora", True))
            status_text = self.t("tooltips.out_of_signal") if fora else self.t("tooltips.in_signal")
            status_color = (255, 0, 0) if fora else (0, 128, 0)

        # Altura a exibir
        altura_para_exibir = item.get("altura")
        if altura_para_exibir is None:
            altura_para_exibir = item.get("altura_receiver", "N/A")
        altura_str_final = (
            f"{altura_para_exibir}m" if isinstance(altura_para_exibir, (int, float)) else str(altura_para_exibir)
        )

        return name, coords, status_color, status_text, altura_str_final

    def add_equipment_table(
        self,
        title: str,
        data: List[Dict[str, Any]],
        *,
        is_main_antenna_table: bool = False,
        is_central_table: bool = False,
    ) -> None:
        if not data:
            return

        self.add_section_title(title)

        # Larguras responsivas (margens padrão)
        total_w = self.pdf.w - self.pdf.l_margin - self.pdf.r_margin
        col_widths = [total_w * 0.25, total_w * 0.40, total_w * 0.20, total_w * 0.15]

        self._table_header(col_widths)

        self._font(size=8)
        self.pdf.set_fill_color(245, 245, 245)
        fill = False

        for item in data:
            name, coords, status_color, status_text, altura_str_final = self._format_row(
                item,
                is_main_antenna_table=is_main_antenna_table,
                is_central_table=is_central_table,
                title_label=title,
            )

            # Nome
            self.pdf.set_text_color(*COR_TEXTO_ESCURO)
            self.pdf.cell(col_widths[0], 7, name, 1, 0, "L", fill)

            # Coords
            self.pdf.cell(col_widths[1], 7, coords, 1, 0, "L", fill)

            # Status
            self.pdf.set_text_color(*status_color)
            self.pdf.cell(
                col_widths[2],
                7,
                status_text,
                1,
                0,
                "C",
                fill,
            )

            # Altura
            self.pdf.set_text_color(*COR_TEXTO_ESCURO)
            self.pdf.cell(col_widths[3], 7, altura_str_final, 1, 1, "C", fill)

            fill = not fill

        self.pdf.ln(3)

    # ---------------------- geração principal ----------------------

    def _embed_map_from_base64(self, map_image_base64: str) -> None:
        """
        Aceita 'data:image/png;base64,...' ou base64 puro. Salva temp e insere.
        Tenta calcular altura proporcional com PIL se disponível; senão, faz um avanço razoável.
        """
        try:
            header, b64 = (
                (map_image_base64.split(",", 1) + [""])[:2]
                if "base64," in map_image_base64
                else ("", map_image_base64)
            )
            b64 = b64.strip()
            ext = "png"
            if header.startswith("data:image/"):
                ext = header.split("/")[1].split(";")[0] or "png"

            tmp_dir = settings.ARQUIVOS_DIR_PATH / "reports" / "_tmp"
            tmp_dir.mkdir(parents=True, exist_ok=True)
            tmp_img = tmp_dir / f"map_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"

            with open(tmp_img, "wb") as f:
                f.write(base64.b64decode(b64, validate=False))

            # Insere a imagem ocupando largura útil
            usable_w = self.pdf.w - self.pdf.l_margin - self.pdf.r_margin

            # Tenta estimar altura com PIL (opcional)
            img_h_px = None
            try:
                from PIL import Image  # type: ignore

                with Image.open(tmp_img) as im:
                    w_px, h_px = im.size
                    if w_px > 0:
                        img_h_px = int(h_px * (usable_w / w_px))
            except Exception:
                pass

            if img_h_px and img_h_px > 0:
                self.pdf.image(str(tmp_img), x=self.pdf.l_margin, y=self.pdf.get_y(), w=usable_w, h=img_h_px)
                self.pdf.ln(max(10, img_h_px / 5))
            else:
                self.pdf.image(str(tmp_img), x=self.pdf.l_margin, y=self.pdf.get_y(), w=usable_w)
                # Avanço conservador
                self.pdf.ln(usable_w * 0.3)

            # Limpa o arquivo temp
            try:
                os.remove(tmp_img)
            except Exception:
                pass

        except Exception as e:
            logger.warning("Falha ao embutir map_image_base64: %s", e)
            # Fallback visual
            self.pdf.set_draw_color(200, 200, 200)
            self.pdf.cell(0, 30, self.t("ui.labels.map_view"), border=1, ln=1, align="C")

    def generate_report(
        self,
        antena_principal_data: Optional[Dict[str, Any]],
        pivos_data: List[Dict[str, Any]],
        bombas_data: List[Dict[str, Any]],
        repetidoras_data: List[Dict[str, Any]],
        template_id: str,
        map_image_base64: Optional[str] = None,
    ) -> Path:
        """Gera o PDF e retorna o caminho completo do arquivo."""
        # Header
        self.add_header()

        # Info geral
        self.add_section_title(self.t("ui.labels.general_info"))

        template_obj = settings.obter_template(template_id)
        nome_template_limpo = getattr(template_obj, "nome", getattr(template_obj, "id", str(template_obj)))
        self.add_text_line(f"{self.t('ui.labels.template')}:", nome_template_limpo)
        self.pdf.ln(3)

        # Resumo cobertura
        total_pivos = len(pivos_data)
        fora_cobertura = sum(1 for p in pivos_data if p.get("fora", True))

        total_repetidoras_resumo = 0
        total_centrais_resumo = 0

        def _contabiliza(ent: Dict[str, Any]) -> Tuple[int, int]:
            typ = ent.get("type")
            if typ == "central":
                return (0, 1)
            if typ == "central_repeater_combined":
                return (1, 1)
            return (1, 0)

        if antena_principal_data:
            r, c = _contabiliza(antena_principal_data)
            total_repetidoras_resumo += r
            total_centrais_resumo += c

        for rep in repetidoras_data:
            r, c = _contabiliza(rep)
            total_repetidoras_resumo += r
            total_centrais_resumo += c

        self.add_text_line(self.t("ui.labels.total_pivots"), total_pivos)
        self.add_text_line(self.t("ui.labels.out_of_coverage"), fora_cobertura)
        self.add_text_line(self.t("ui.labels.total_repeaters"), total_repetidoras_resumo)
        self.add_text_line(self.t("ui.labels.central_count"), total_centrais_resumo)
        self.add_text_line(self.t("ui.labels.pump_houses"), len(bombas_data))
        self.pdf.ln(3)

        # Mapa (opcional)
        if map_image_base64:
            self.add_section_title(self.t("ui.labels.map_view"))
            self._embed_map_from_base64(map_image_base64)
            self.pdf.ln(3)

        # --- Tabelas ---

        # 1) Centrais (combinado entra aqui com altura 5m)
        all_centrals_for_table: List[Dict[str, Any]] = []
        if antena_principal_data and antena_principal_data.get("type") in ["central", "central_repeater_combined"]:
            central_copy = dict(antena_principal_data)
            central_copy["is_main_antenna"] = True
            if central_copy.get("type") == "central_repeater_combined":
                central_copy["altura"] = 5
            all_centrals_for_table.append(central_copy)

        for rep in repetidoras_data:
            if rep.get("type") in ["central", "central_repeater_combined"]:
                c = dict(rep)
                if c.get("type") == "central_repeater_combined":
                    c["altura"] = 5
                all_centrals_for_table.append(c)

        all_centrals_for_table.sort(
            key=lambda x: (not x.get("is_main_antenna", False), str(x.get("nome", "")))
        )
        if all_centrals_for_table:
            self.add_equipment_table(
                self.t("ui.labels.central_count"),
                all_centrals_for_table,
                is_central_table=True,
                is_main_antenna_table=True,
            )

        # 2) Repetidoras (inclui “parte repetidora” de combinados com altura REAL)
        all_repeaters_for_table: List[Dict[str, Any]] = [
            rep for rep in repetidoras_data if rep.get("type") not in ["central", "central_repeater_combined"]
        ]

        if antena_principal_data and antena_principal_data.get("type") == "central_repeater_combined":
            rc = dict(antena_principal_data)
            rc["type"] = "default"  # força tratativa de nome de repetidora
            all_repeaters_for_table.append(rc)

        for rep in repetidoras_data:
            if rep.get("type") == "central_repeater_combined":
                rc = dict(rep)
                rc["type"] = "default"
                all_repeaters_for_table.append(rc)

        all_repeaters_for_table.sort(key=lambda x: str(x.get("nome", "")))
        if all_repeaters_for_table:
            self.add_equipment_table(self.t("ui.labels.repeaters"), all_repeaters_for_table)

        # 3) Bombas
        self.add_equipment_table(self.t("ui.labels.pump_houses"), bombas_data)

        # 4) Pivôs
        self.add_equipment_table(self.t("ui.labels.pivots"), pivos_data)

        # Rodapé
        self.add_footer()

        # Saída
        output_dir = settings.ARQUIVOS_DIR_PATH / "reports"
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename_prefix_clean = self.t("kml.filename_prefix")
        report_filename = f"{filename_prefix_clean}_report_{timestamp}.pdf"
        output_path = output_dir / report_filename

        try:
            self.pdf.output(str(output_path))
            logger.info("Relatório PDF gerado em: %s", output_path)
        except Exception as e:
            logger.error("Falha ao escrever PDF (%s). Caminho: %s", e, output_path)
            raise

        return output_path