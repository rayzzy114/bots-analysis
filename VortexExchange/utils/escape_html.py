from html import escape

def escape_html(text: str) -> str:
    if text is None:
        return ""
    return escape(str(text))