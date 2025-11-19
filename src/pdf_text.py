import os
from typing import List


def read_pdf_text(path: str) -> List[str]:
    try:
        import pypdf
    except ImportError:
        raise RuntimeError(
            "Missing dependency pypdf. Please install with: pip install pypdf"
        )

    if not os.path.isfile(path):
        raise FileNotFoundError(path)

    reader = pypdf.PdfReader(path)
    pages = []
    for page in reader.pages:
        text = page.extract_text() or ""
        pages.append(text)
    return pages
