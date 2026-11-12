import html
from datetime import date
from functools import lru_cache
from pathlib import Path
from string import Template

from markdown_it import MarkdownIt
from mdit_py_plugins.tasklists import tasklists_plugin

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

    default_fence = md.renderer.rules["fence"]

    def fence(tokens, idx, options, env):
        if env.get("mermaid") and _is_mermaid(tokens[idx]):
            return '<div class="mermaid">\n' + html.escape(tokens[idx].content) + "</div>\n"
        return default_fence(tokens, idx, options, env)

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


def _has_mermaid(tokens) -> bool:
    return any(token.type == "fence" and _is_mermaid(token) for token in tokens)


def convert(
    text: str,
    *,
    source_name: str,
    today: date | None = None,
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
        toc="",
        shell_class="no-toc",
        content=content,
        footer=html.escape(f"由 {source_name} 生成 · 生成日期 {generated_on}"),
        head_extra=head_extra,
        body_extra=body_extra,
    )
