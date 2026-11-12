import html
from datetime import date
from functools import lru_cache
from pathlib import Path
from string import Template

from markdown_it import MarkdownIt
from mdit_py_plugins.tasklists import tasklists_plugin

_TEMPLATE_PATH = Path(__file__).with_name("template.html")


@lru_cache(maxsize=1)
def _template() -> Template:
    return Template(_TEMPLATE_PATH.read_text(encoding="utf-8"))


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
    text: str, *, source_name: str, today: date | None = None, toc: bool = True
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
    content = parser.renderer.render(tokens, parser.options, {})
    generated_on = (today or date.today()).isoformat()
    return _template().substitute(
        title=html.escape(title),
        heading=heading,
        kicker=html.escape(stem),
        toc=toc_html,
        shell_class="" if toc_html else " no-toc",
        content=content,
        footer=html.escape(f"由 {source_name} 生成 · 生成日期 {generated_on}"),
        head_extra="",
        body_extra="",
    )
