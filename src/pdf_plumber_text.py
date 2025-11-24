import os
from typing import List, Dict


def read_pdf_plumber_text(path: str, table_cell_sep: str = "\t") -> List[Dict]:
    try:
        import pdfplumber
    except ImportError:
        raise RuntimeError(
            "Missing dependency pdfplumber. Please install with: pip install pdfplumber"
        )
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    out: List[Dict] = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            txt = page.extract_text() or ""
            if txt.strip():
                # 按段落拆分，保持简单
                for seg in [s.strip() for s in txt.split("\n") if s.strip()]:
                    out.append({"page": i, "text": seg})
            # 提取表格
            try:
                tables = page.extract_tables()
            except Exception:
                tables = []
            for tbl in tables or []:
                for row in tbl or []:
                    cells = [((c or "").strip()) for c in row]
                    if any(cells):
                        out.append({"page": i, "text": table_cell_sep.join(cells)})
    if not out:
        out.append({"page": 1, "text": ""})
    return out

