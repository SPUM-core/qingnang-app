"""report_parser — 检查报告文件解析层

职责：探测文件格式 → 提取可被 LLM 处理的纯文本。

支持格式：
  - 图片（jpeg/png/webp） → OCR（pytesseract，没装则提示走手动）
  - TXT / Markdown        → 直接读文本
  - XLSX（Excel）          → openpyxl 遍历 sheet 转文本表格
  - DOCX（Word）           → python-docx 读段落正文
  - PDF                    → pdfplumber（可选）

依赖 gracefully fallback：缺少可选库时返回 {ok:False, reason:"..."}，
media.py 据此把 recognized=False 入库，前端提示用户手动补填。
"""
from __future__ import annotations
import io
import os
import re
import tempfile
from typing import Optional


# ── MIME → 格式标签映射 ──
_EXT_MAP: dict[str, str] = {
    ".jpg":   "image",
    ".jpeg":  "image",
    ".png":   "image",
    ".webp":  "image",
    ".bmp":   "image",
    ".txt":   "text",
    ".md":    "markdown",
    ".markdown": "markdown",
    ".xlsx":  "xlsx",
    ".xls":   "xlsx",
    ".docx":  "docx",
    ".doc":   "doc",   # 老格式不支持，会返回 fallback
    ".pdf":   "pdf",
}


def detect_format(filename: str | None, mime: str | None = None) -> str:
    """返回格式标签：image / text / markdown / xlsx / docx / doc / pdf / unknown"""
    if filename:
        ext = os.path.splitext(filename)[1].lower()
        if ext in _EXT_MAP:
            return _EXT_MAP[ext]
    if mime:
        if mime.startswith("image/"): return "image"
        if mime == "text/plain":      return "text"
        if mime in ("text/markdown", "text/x-markdown"): return "markdown"
        if "spreadsheetml" in mime or "excel" in mime: return "xlsx"
        if "wordprocessingml" in mime: return "docx"
        if mime == "application/pdf": return "pdf"
    return "unknown"


def parse(raw_bytes: bytes, filename: str | None = None) -> dict:
    """统一入口：返回 {ok, format, text_content?, reason?}"""
    fmt = detect_format(filename)
    if fmt == "image":     return _parse_image(raw_bytes)
    if fmt == "text":      return {"ok": True, "format": "text",
                                    "text_content": raw_bytes.decode("utf-8", errors="replace")}
    if fmt == "markdown":  return {"ok": True, "format": "markdown",
                                    "text_content": raw_bytes.decode("utf-8", errors="replace")}
    if fmt == "xlsx":      return _parse_xlsx(raw_bytes)
    if fmt == "docx":      return _parse_docx(raw_bytes)
    if fmt == "doc":       return {"ok": False, "format": "doc",
                                    "reason": "老版 .doc 格式不支持，请另存为 .docx 或 PDF"}
    if fmt == "pdf":       return _parse_pdf(raw_bytes)
    return {"ok": False, "format": fmt, "reason": f"不支持的格式：{filename or fmt}"}


# ═══════════════════════════════════════════════════════════
# 各格式解析实现 — 每个都带缺少依赖时的 gracefully fallback
# ═══════════════════════════════════════════════════════════

def _parse_image(raw: bytes) -> dict:
    """图片 → 走 pytesseract OCR。没装 tesseract 就返回 ok=False，前端手动补填。"""
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return {"ok": False, "format": "image",
                "reason": "未安装 OCR 库（pytesseract + tesseract），请手动输入报告文字"}

    # PIL 从 bytes 打开
    try:
        img = Image.open(io.BytesIO(raw))
        text = pytesseract.image_to_string(img, lang="chi_sim+eng")
    except Exception as e:
        return {"ok": False, "format": "image",
                "reason": f"OCR 解析失败：{e}"}

    text = text.strip()
    if not text:
        return {"ok": False, "format": "image", "reason": "OCR 未能识别出文字，请手动输入"}

    return {"ok": True, "format": "image", "text_content": text,
            "note": "OCR 识别可能有误，请核对关键数值"}


def _parse_xlsx(raw: bytes) -> dict:
    try:
        from openpyxl import load_workbook
    except ImportError:
        return {"ok": False, "format": "xlsx",
                "reason": "未安装 openpyxl，请 pip install openpyxl"}

    try:
        wb = load_workbook(io.BytesIO(raw), data_only=True)
    except Exception as e:
        return {"ok": False, "format": "xlsx", "reason": f"Excel 打开失败：{e}"}

    parts = []
    for ws in wb.worksheets:
        parts.append(f"=== Sheet: {ws.title} ===")
        rows_text = []
        for row in ws.iter_rows(values_only=True):
            cells = [str(c).strip() if c is not None else "" for c in row]
            if any(cells):
                rows_text.append("\t".join(cells))
        parts.extend(rows_text)

    text = "\n".join(parts).strip()
    if not text:
        return {"ok": False, "format": "xlsx", "reason": "Excel 文件为空"}
    return {"ok": True, "format": "xlsx", "text_content": text}


def _parse_docx(raw: bytes) -> dict:
    try:
        from docx import Document
    except ImportError:
        return {"ok": False, "format": "docx",
                "reason": "未安装 python-docx，请 pip install python-docx"}

    try:
        doc = Document(io.BytesIO(raw))
    except Exception as e:
        return {"ok": False, "format": "docx", "reason": f"Word 打开失败：{e}"}

    parts = []
    for para in doc.paragraphs:
        t = para.text.strip()
        if t: parts.append(t)
    # 表格也读
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            if any(cells): parts.append("\t".join(cells))

    text = "\n".join(parts).strip()
    if not text:
        return {"ok": False, "format": "docx", "reason": "Word 文件为空"}
    return {"ok": True, "format": "docx", "text_content": text}


def _parse_pdf(raw: bytes) -> dict:
    try:
        import pdfplumber
    except ImportError:
        return {"ok": False, "format": "pdf",
                "reason": "未安装 pdfplumber，请 pip install pdfplumber；或把 PDF 另存为图片/Word"}

    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.write(raw); tmp.close()
    try:
        parts = []
        with pdfplumber.open(tmp.name) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t: parts.append(t)
    finally:
        try: os.remove(tmp.name)
        except Exception: pass

    text = "\n".join(parts).strip()
    if not text:
        return {"ok": False, "format": "pdf", "reason": "PDF 未能提取文字（可能是扫描版，需要 OCR）"}
    return {"ok": True, "format": "pdf", "text_content": text}
