"""Shared email formatting utilities.

Consolidates _text_to_html() from all providers. Uses CRM's 5-tag detection
(more comprehensive) + provider_hint for Gmail vs Outlook styling.
"""

import html as html_module
import re


# Tags that indicate the input is already HTML
_HTML_TAGS = ['<div', '<img', '<br/', '<span', '<a ']


def text_to_html(text: str, provider_hint: str | None = None) -> str:
    """Convert plain text or raw HTML to an email-ready HTML document.

    Args:
        text: Plain text or HTML content.
        provider_hint: 'outlook' uses inline styles (Outlook strips <style> blocks).
                       None or 'gmail' uses <style> block with <p> paragraph wrapping.
    """
    if not text:
        return text

    use_inline = provider_hint == 'outlook'
    has_html = any(tag in text for tag in _HTML_TAGS)

    if has_html:
        formatted = text.replace('\n\n', '<br><br>').replace('\n', '<br>')
        return _wrap_document(formatted, use_inline, include_p_style=False)

    escaped = html_module.escape(text)

    if use_inline:
        # Outlook: <br> only, no <p> tags (Outlook strips margins)
        escaped = escaped.replace('\n\n', '<br><br>').replace('\n', '<br>')
        return _wrap_document(escaped, use_inline=True, include_p_style=False)
    else:
        # Gmail: wrap paragraphs in <p> tags for proper spacing
        escaped = escaped.replace('\n\n', '|||PARAGRAPH|||')
        escaped = escaped.replace('\n', '<br>')
        paragraphs = escaped.split('|||PARAGRAPH|||')
        body = '\n'.join(f'<p>{p}</p>' for p in paragraphs if p.strip())
        return _wrap_document(body, use_inline=False, include_p_style=True)


def html_to_plain(html: str) -> str:
    """Strip HTML tags to produce plain-text fallback for Gmail multipart MIME."""
    if not html:
        return html
    # Remove HTML tags
    text = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)
    text = re.sub(r'</p>\s*<p[^>]*>', '\n\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    # Decode HTML entities
    text = html_module.unescape(text)
    return text.strip()


def _wrap_document(body: str, use_inline: bool, include_p_style: bool) -> str:
    """Wrap content in a minimal HTML document."""
    if use_inline:
        return (
            '<!DOCTYPE html>\n<html>\n<head>\n<meta charset="UTF-8">\n</head>\n'
            '<body style="font-family: Arial, Helvetica, sans-serif; font-size: 14px; '
            f'line-height: 1.5; color: #222;">\n{body}\n</body>\n</html>'
        )

    p_rule = 'p { margin: 0 0 1em 0; }\n' if include_p_style else ''
    return (
        '<!DOCTYPE html>\n<html>\n<head>\n<meta charset="UTF-8">\n'
        '<style>\n'
        'body { font-family: Arial, Helvetica, sans-serif; font-size: 14px; '
        'line-height: 1.5; color: #222; }\n'
        f'{p_rule}'
        '</style>\n</head>\n<body>\n'
        f'{body}\n</body>\n</html>'
    )
