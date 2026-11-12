import html
from datetime import date
from functools import lru_cache
from pathlib import Path
from string import Template

from markdown_it import MarkdownIt
from mdit_py_plugins.tasklists import tasklists_plugin
from pygments import highlight as pygments_highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound

_TEMPLATE_PATH = Path(__file__).with_name("template.html")


@lru_cache(maxsize=1)
def _template() -> Template:
    return Template(_TEMPLATE_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _formatter() -> HtmlFormatter:
    return HtmlFormatter(nowrap=True)


@lru_cache(maxsize=None)
def _lexer(language: str):
    try:
        return get_lexer_by_name(
            language, stripnl=False, stripall=False, ensurenl=False
        )
    except ClassNotFound:
        return None


def _render_fence(tokens, idx, options, env):
    token = tokens[idx]
    info = (token.info or "").strip()
    language = info.split(maxsplit=1)[0] if info else ""
    lexer = _lexer(language) if language else None
    if lexer is None:
        attrs = ""
        if language:
            attrs = f' class="language-{html.escape(language, quote=True)}"'
        return f"<pre><code{attrs}>{html.escape(token.content)}</code></pre>\n"
    body = pygments_highlight(token.content, lexer, _formatter())
    return (
        f'<pre class="highlight"><code class="language-{html.escape(language, quote=True)}">'
        f"{body}</code></pre>\n"
    )


@lru_cache(maxsize=1)
def _parser() -> MarkdownIt:
    md = MarkdownIt("commonmark", {"html": True, "linkify": False})
    md.enable(["table", "strikethrough"])
    md.use(tasklists_plugin, label=False)

    def table_open(tokens, idx, options, env):
        return '<div class="table-wrap">' + md.renderer.renderToken(
            tokens, idx, options, env
        )

    def table_close(tokens, idx, options, env):
        return md.renderer.renderToken(tokens, idx, options, env) + "</div>"

    md.renderer.rules["table_open"] = table_open
    md.renderer.rules["table_close"] = table_close
    md.renderer.rules["fence"] = _render_fence
    return md


def _plain_text(token) -> str:
    parts = []
    for child in token.children or []:
        if child.type in ("text", "code_inline"):
            parts.append(child.content)
        elif child.type == "image":
            parts.append(child.content)
        elif child.type in ("softbreak", "hardbreak"):
            parts.append(" ")
    return "".join(parts).strip()


def _first_h1_index(tokens) -> int | None:
    for index, token in enumerate(tokens):
        if token.type == "heading_open" and token.tag == "h1":
            return index
    return None


def convert(text: str, *, source_name: str, today: date | None = None) -> str:
    stem = Path(source_name).stem
    parser = _parser()
    tokens = parser.parse(text)

    title = stem
    heading = ""
    index = _first_h1_index(tokens)
    if index is not None:
        title = _plain_text(tokens[index + 1]) or stem
        if index == 0:
            del tokens[0:3]
            heading = f"<h1>{html.escape(title)}</h1>"

    content = parser.renderer.render(tokens, parser.options, {})
    generated_on = (today or date.today()).isoformat()
    return _template().substitute(
        title=html.escape(title),
        heading=heading,
        kicker=html.escape(stem),
        toc="",
        shell_class="no-toc",
        content=content,
        footer=html.escape(f"由 {source_name} 生成 · 生成日期 {generated_on}"),
        head_extra="",
        body_extra="",
    )
