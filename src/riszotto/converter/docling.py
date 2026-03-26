"""Docling-based PDF converter with rich extraction."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from riszotto.converter.base import ConversionResult, EquationMode, StyleOption
from riszotto.converter.cache import (
    cache_dir_for,
    compute_pdf_hash,
    read_cache,
    write_cache,
)

try:
    from docling.datamodel.accelerator_options import (
        AcceleratorDevice,
        AcceleratorOptions,
    )
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import (
        TableFormerMode,
        TableStructureOptions,
        ThreadedPdfPipelineOptions,
    )
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling_core.types.doc import FormulaItem, PictureItem, TableItem, TextItem

    DOCLING_AVAILABLE = True
except ImportError:
    DOCLING_AVAILABLE = False


def _save_element_image(element, doc, dest: Path) -> bool:
    """Save an element's image to dest. Returns False if no image available."""
    image = element.get_image(doc)
    if image is None:
        return False
    image.save(str(dest), "PNG")
    return True


class DoclingConverter:
    """Convert PDFs using docling with figure, table, and equation extraction.

    Requires ``riszotto[full]`` to be installed.
    """

    def __init__(self) -> None:
        if not DOCLING_AVAILABLE:
            raise ImportError(
                "docling is not installed. Install with: uv add riszotto[full]"
            )

    def convert(
        self,
        pdf_path: Path,
        *,
        table_style: StyleOption = "inline",
        equation_style: StyleOption = "inline",
        zotero_key: str,
        no_cache: bool = False,
        ocr: bool = False,
        table_mode: str = "fast",
        equation_mode: EquationMode = "image",
    ) -> ConversionResult:
        """Convert a PDF to markdown with rich extraction."""
        pdf_hash = compute_pdf_hash(pdf_path)

        if not no_cache:
            cached = read_cache(
                zotero_key=zotero_key,
                pdf_hash=pdf_hash,
                table_style=table_style,
                equation_style=equation_style,
            )
            if cached is not None:
                return cached

        needs_page_images = table_style == "image" or equation_mode == "image"

        print("Converting PDF with docling...", file=sys.stderr)

        pipeline_options = ThreadedPdfPipelineOptions()
        pipeline_options.do_ocr = ocr
        pipeline_options.generate_picture_images = True
        pipeline_options.generate_page_images = needs_page_images
        pipeline_options.images_scale = 2.0 if needs_page_images else 1.0
        pipeline_options.do_table_structure = True
        pipeline_options.table_structure_options = TableStructureOptions(
            do_cell_matching=True,
            mode=(
                TableFormerMode.ACCURATE
                if table_mode == "accurate"
                else TableFormerMode.FAST
            ),
        )
        pipeline_options.do_formula_enrichment = equation_mode == "latex"
        pipeline_options.accelerator_options = AcceleratorOptions(
            num_threads=os.cpu_count() or 4,
            device=AcceleratorDevice.AUTO,
        )

        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )
        doc_result = converter.convert(pdf_path)
        doc = doc_result.document

        cache_path = cache_dir_for(zotero_key, pdf_hash)
        cache_path.mkdir(parents=True, exist_ok=True)

        parts: list[str] = []
        figures: dict[str, Path] = {}
        figure_count = 0
        table_count = 0
        equation_count = 0

        for element, _level in doc.iterate_items():
            if isinstance(element, PictureItem):
                figure_count += 1
                filename = f"figure_{figure_count}.png"
                fig_path = cache_path / filename
                if _save_element_image(element, doc, fig_path):
                    figures[filename] = fig_path
                    parts.append(f"![Figure {figure_count}]({fig_path})")
                else:
                    parts.append(f"[Figure {figure_count}: image not available]")

            elif isinstance(element, TableItem):
                table_count += 1
                if table_style == "inline":
                    df = element.export_to_dataframe(doc=doc)
                    parts.append(df.to_markdown())
                else:
                    filename = f"table_{table_count}.png"
                    tbl_path = cache_path / filename
                    if _save_element_image(element, doc, tbl_path):
                        figures[filename] = tbl_path
                        parts.append(f"![Table {table_count}]({tbl_path})")
                    else:
                        df = element.export_to_dataframe(doc=doc)
                        parts.append(df.to_markdown())

            elif isinstance(element, FormulaItem):
                equation_count += 1
                if equation_mode == "latex" and element.text:
                    parts.append(f"$${element.text}$$")
                else:
                    filename = f"equation_{equation_count}.png"
                    eq_path = cache_path / filename
                    if _save_element_image(element, doc, eq_path):
                        figures[filename] = eq_path
                        parts.append(f"![Equation {equation_count}]({eq_path})")
                    elif element.text:
                        parts.append(f"$${element.text}$$")
                    else:
                        parts.append(f"[Equation {equation_count}: not available]")

            elif isinstance(element, TextItem):
                parts.append(element.text)

        markdown = "\n\n".join(parts)

        write_cache(
            zotero_key=zotero_key,
            pdf_hash=pdf_hash,
            markdown=markdown,
            figures=figures,
            backend="docling",
            table_style=table_style,
            equation_style=equation_style,
        )

        return ConversionResult(markdown=markdown, figures=figures)
