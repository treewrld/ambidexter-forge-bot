# utils/sanitize.py
import html


def sanitize_text(text: str, max_len: int = 2000) -> str:
    if not text:
        return ""
    text = text.strip()
    text = html.escape(text)
    if len(text) > max_len:
        text = text[:max_len] + "..."
    return text
