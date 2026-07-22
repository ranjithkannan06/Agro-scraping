"""Minimal XLSX export writer for normalized commodity records."""

from pathlib import Path
from typing import Iterable, List
from xml.sax.saxutils import escape
import zipfile

from exporters.csv_exporter import CsvExporter
from models.commodity import CommodityRecord


class ExcelExporter:
    """Writes a simple workbook without adding another dependency."""

    def export(self, records: Iterable[CommodityRecord], path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        rows: List[List[str]] = [CsvExporter.fields]
        for record in records:
            data = record.to_dict()
            rows.append([str(data.get(field, "")) for field in CsvExporter.fields])

        sheet_xml = self._sheet_xml(rows)
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("[Content_Types].xml", self._content_types())
            archive.writestr("_rels/.rels", self._rels())
            archive.writestr("xl/workbook.xml", self._workbook())
            archive.writestr("xl/_rels/workbook.xml.rels", self._workbook_rels())
            archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)

    @staticmethod
    def _sheet_xml(rows: List[List[str]]) -> str:
        row_xml = []
        for r_index, row in enumerate(rows, start=1):
            cells = []
            for c_index, value in enumerate(row, start=1):
                col = chr(64 + c_index)
                cells.append(f'<c r="{col}{r_index}" t="inlineStr"><is><t>{escape(value)}</t></is></c>')
            row_xml.append(f'<row r="{r_index}">{"".join(cells)}</row>')
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f'<sheetData>{"".join(row_xml)}</sheetData></worksheet>'
        )

    @staticmethod
    def _content_types() -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            "</Types>"
        )

    @staticmethod
    def _rels() -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>"
        )

    @staticmethod
    def _workbook() -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="scraped_data" sheetId="1" r:id="rId1"/></sheets></workbook>'
        )

    @staticmethod
    def _workbook_rels() -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            "</Relationships>"
        )
