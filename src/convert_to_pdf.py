import os


def convert_docx_to_pdf(path: str, out_dir: str) -> str:
    try:
        import docx2pdf  # type: ignore
    except Exception:
        docx2pdf = None
    os.makedirs(out_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(path))[0]
    out_pdf = os.path.join(out_dir, base_name + ".converted.pdf")
    if docx2pdf:
        docx2pdf.convert(path, out_pdf)
        return out_pdf
    try:
        import win32com.client  # type: ignore
    except Exception:
        raise RuntimeError("Missing docx2pdf/pywin32 for DOCX->PDF conversion on this platform")
    word = None
    try:
        word = win32com.client.Dispatch("Word.Application")
        doc = word.Documents.Open(path)
        doc.SaveAs(out_pdf, FileFormat=17)
        doc.Close()
        word.Quit()
        return out_pdf
    finally:
        try:
            if word:
                word.Quit()
        except Exception:
            pass


def convert_doc_to_pdf(path: str, out_dir: str) -> str:
    try:
        import win32com.client  # type: ignore
    except Exception:
        raise RuntimeError("Missing pywin32 for DOC->PDF conversion on this platform")
    os.makedirs(out_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(path))[0]
    out_pdf = os.path.join(out_dir, base_name + ".converted.pdf")
    word = None
    try:
        word = win32com.client.Dispatch("Word.Application")
        doc = word.Documents.Open(path)
        doc.SaveAs(out_pdf, FileFormat=17)
        doc.Close()
        word.Quit()
        return out_pdf
    finally:
        try:
            if word:
                word.Quit()
        except Exception:
            pass
