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
_VENDOR_DIR = Path(__file__).with_name("vendor")
_MERMAID_JS_PATH = _VENDOR_DIR / "mermaid.min.js"
_MERMAID_VERSION_PATH = _VENDOR_DIR / "mermaid.VERSION"

_MERMAID_STYLE = """\
<style>
.mermaid {
  margin: 24px 0;
  padding: 20px;
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 12px;
  overflow-x: auto;
  text-align: center;
}
.mermaid svg { max-width: 100%; height: auto; }
.mermaid:not([data-processed]) {
  color: var(--muted);
  font-family: "JetBrains Mono", "Cascadia Code", "SFMono-Regular", Consolas, monospace;
  font-size: 13px;
  line-height: 1.6;
  text-align: left;
  white-space: pre-wrap;
}
@media print {
  .mermaid { break-inside: avoid; }
}
</style>
"""

_MERMAID_INIT = """\
<script>
(function () {
  if (typeof mermaid === 'undefined') return;
  mermaid.initialize({
    startOnLoad: false,
    theme: 'neutral',
    securityLevel: 'strict',
    fontFamily: '"Noto Sans SC", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", system-ui, sans-serif',
    themeVariables: {
      background: '#fffdf9',
      primaryColor: '#f7f1e7',
      primaryTextColor: '#24211d',
      primaryBorderColor: '#cdbfa9',
      lineColor: '#8a8175',
      secondaryColor: '#fbf0e2',
      tertiaryColor: '#f4efe6',
      noteBkgColor: '#fbf0e2',
      noteBorderColor: '#e2d5c1'
    }
  });
  mermaid.run({ querySelector: '.mermaid', suppressErrors: true });
})();
</script>
"""


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
def _mermaid_version() -> str:
    for line in _MERMAID_VERSION_PATH.read_text(encoding="utf-8").splitlines():
        key, _, value = line.partition(":")
        if key.strip() == "version":
            return value.strip()
    return "unknown"


@lru_cache(maxsize=1)
def _mermaid_library() -> str:
    return _MERMAID_JS_PATH.read_text(encoding="utf-8")


def _is_mermaid(token) -> bool:
    info = (token.info or "").strip()
    return bool(info) and info.split(None, 1)[0].lower() == "mermaid"


def _has_mermaid(tokens) -> bool:
    return any(token.type == "fence" and _is_mermaid(token) for token in tokens)


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

    def fence(tokens, idx, options, env):
        if env.get("mermaid") and _is_mermaid(tokens[idx]):
            return (
                '<div class="mermaid">\n'
                + html.escape(tokens[idx].content)
                + "</div>\n"
            )
        return _render_fence(tokens, idx, options, env)

    md.renderer.rules["table_open"] = table_open
    md.renderer.rules["table_close"] = table_close
    md.renderer.rules["fence"] = fence
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


_TOC_LEVELS = {"h2": (2, "sec"), "h3": (3, "item")}


def _assign_anchors(tokens) -> list[tuple[int, str, str]]:
    entries = []
    counters = {2: 0, 3: 0}
    for index, token in enumerate(tokens):
        if token.type != "heading_open":
            continue
        spec = _TOC_LEVELS.get(token.tag)
        if spec is None:
            continue
        level, prefix = spec
        counters[level] += 1
        anchor = f"{prefix}-{counters[level]}"
        token.attrSet("id", anchor)
        entries.append((level, anchor, _plain_text(tokens[index + 1])))
    return entries


def _render_toc(entries) -> str:
    if not entries:
        return ""
    nodes = []
    for level, anchor, title in entries:
        if level == 3 and nodes and nodes[-1]["level"] == 2:
            nodes[-1]["children"].append((anchor, title))
        else:
            nodes.append(
                {"level": level, "anchor": anchor, "title": title, "children": []}
            )
    lines = [
        '<nav class="toc" aria-label="目录">',
        '<div class="toc-title">目录</div>',
        "<ul>",
    ]
    for node in nodes:
        link = f'<a href="#{node["anchor"]}">{html.escape(node["title"])}</a>'
        if not node["children"]:
            lines.append(f"<li>{link}</li>")
            continue
        lines.append(f"<li>{link}")
        lines.append("<ul>")
        lines.extend(
            f'<li><a href="#{child_anchor}">{html.escape(child_title)}</a></li>'
            for child_anchor, child_title in node["children"]
        )
        lines.extend(["</ul>", "</li>"])
    lines.extend(["</ul>", "</nav>"])
    return "\n".join(lines)


def convert(
    text: str,
    *,
    source_name: str,
    today: date | None = None,
    toc: bool = True,
    mermaid: bool = True,
) -> str:
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

    entries = _assign_anchors(tokens)
    toc_html = _render_toc(entries) if toc else ""
    content = parser.renderer.render(tokens, parser.options, {"mermaid": mermaid})

    head_extra = ""
    body_extra = ""
    if mermaid and _has_mermaid(tokens):
        version = _mermaid_version()
        head_extra = _MERMAID_STYLE
        body_extra = (
            f"<!-- mermaid {version}（内联，MIT，本地固定版本） -->\n"
            "<script>\n"
            + _mermaid_library()
            + "\n</script>\n"
            + _MERMAID_INIT
        )

    generated_on = (today or date.today()).isoformat()
    return _template().substitute(
        title=html.escape(title),
        heading=heading,
        kicker=html.escape(stem),
        toc=toc_html,
        body_attr=' class="has-toc"' if toc_html else "",
        shell_class="" if toc_html else " no-toc",
        content=content,
        footer=html.escape(f"由 {source_name} 生成 · 生成日期 {generated_on}"),
        head_extra=head_extra,
        body_extra=body_extra,
    )
