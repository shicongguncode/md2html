import os
import re
import subprocess
import sys
import tempfile
import unittest
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args, extra_env=None):
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, "-m", "md2html", *map(str, args)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )


class BasicConversionTest(unittest.TestCase):
    def test_converts_single_file_next_to_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "note.md"
            source.write_text("# 标题\n\n一个段落。\n", encoding="utf-8")

            result = run_cli(source)

            self.assertEqual(result.returncode, 0, result.stderr)
            output = Path(tmp) / "note.html"
            self.assertTrue(output.exists())
            self.assertIn(str(output), result.stdout)
            self.assertIn("一个段落。", output.read_text(encoding="utf-8"))


class PageTitleTest(unittest.TestCase):
    def test_first_h1_becomes_page_title(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "draft.md"
            source.write_text(
                "# 真正的标题\n\n正文。\n\n# 后面的一级标题\n", encoding="utf-8"
            )

            result = run_cli(source)

            self.assertEqual(result.returncode, 0, result.stderr)
            html = (Path(tmp) / "draft.html").read_text(encoding="utf-8")
            self.assertIn("<title>真正的标题</title>", html)
            self.assertIn("<h1>真正的标题</h1>", html)
            self.assertEqual(html.count("<h1>真正的标题</h1>"), 1)
            self.assertIn("后面的一级标题", html)

    def test_h1_after_preamble_keeps_document_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "preamble.md"
            source.write_text(
                "前言段落。\n\n# 文档标题\n\n正文段落。\n", encoding="utf-8"
            )

            result = run_cli(source)

            self.assertEqual(result.returncode, 0, result.stderr)
            html = (Path(tmp) / "preamble.html").read_text(encoding="utf-8")
            self.assertIn("<title>文档标题</title>", html)
            self.assertLess(html.index("前言段落。"), html.index("<h1>文档标题</h1>"))
            self.assertLess(html.index("<h1>文档标题</h1>"), html.index("正文段落。"))

    def test_page_title_falls_back_to_file_name_without_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "我的 笔记.md"
            source.write_text("没有一级标题的正文。\n", encoding="utf-8")

            result = run_cli(source)

            self.assertEqual(result.returncode, 0, result.stderr)
            html = (Path(tmp) / "我的 笔记.html").read_text(encoding="utf-8")
            self.assertIn("<title>我的 笔记</title>", html)


class MarkdownElementsTest(unittest.TestCase):
    def test_common_markdown_elements_render(self):
        markdown = """\
## 二级标题

段落里有 **粗体**、*斜体*、`行内代码`、[链接](https://example.com) 和 ~~删除线~~。

内联 <span class="raw">原样 HTML</span> 也应该保留。

- 项目一
- 项目二
  - 子项

1. 第一步
2. 第二步

> 引用文字

| 列一 | 列二 |
| --- | --- |
| 甲 | 乙 |

---

- [ ] 待办
- [x] 已办
"""
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "elements.md"
            source.write_text(markdown, encoding="utf-8")

            result = run_cli(source)

            self.assertEqual(result.returncode, 0, result.stderr)
            html = (Path(tmp) / "elements.html").read_text(encoding="utf-8")
            self.assertIn("<h2", html)
            self.assertIn("<ul>", html)
            self.assertIn("<ol>", html)
            self.assertIn("<blockquote>", html)
            self.assertIn('<div class="table-wrap"><table>', html)
            self.assertIn("<code>行内代码</code>", html)
            self.assertIn('<a href="https://example.com">链接</a>', html)
            self.assertIn("<hr", html)
            self.assertIn("<s>删除线</s>", html)
            self.assertIn('type="checkbox"', html)
            self.assertIn("<strong>粗体</strong>", html)
            self.assertIn("<em>斜体</em>", html)
            self.assertIn('<span class="raw">原样 HTML</span>', html)


class SingleFilePageTest(unittest.TestCase):
    def test_image_keeps_relative_path_and_does_not_exceed_content_width(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "photo.md"
            source.write_text(
                "# 图文\n\n![示意图](images/pic.png)\n\n![网图](https://example.com/a.png)\n",
                encoding="utf-8",
            )

            result = run_cli(source)

            self.assertEqual(result.returncode, 0, result.stderr)
            html = (Path(tmp) / "photo.html").read_text(encoding="utf-8")
            self.assertIn('<img src="images/pic.png"', html)
            self.assertIn('<img src="https://example.com/a.png"', html)
            self.assertNotIn("data:image", html)
            self.assertRegex(html, r"max-width:\s*100%")

    def test_page_is_self_contained_and_has_theme_toggle(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "standalone.md"
            source.write_text("# 独立页面\n\n正文。\n", encoding="utf-8")

            result = run_cli(source)

            self.assertEqual(result.returncode, 0, result.stderr)
            html = (Path(tmp) / "standalone.html").read_text(encoding="utf-8")
            self.assertNotIn("<script src=", html)
            self.assertNotIn("<link ", html)
            self.assertNotIn("@import", html)
            self.assertIn('id="themeBtn"', html)
            self.assertIn("doc-theme", html)
            self.assertIn("localStorage", html)
            self.assertIn("prefers-color-scheme: dark", html)
            self.assertIn("@media print", html)
            self.assertRegex(html, r"max-width:\s*640px")


class MermaidTest(unittest.TestCase):
    DIAGRAM = "```mermaid\nflowchart LR\n  A[开始] --> B{判断}\n  B -->|是| C[结束]\n```\n"

    def test_diagram_becomes_container_with_inlined_library(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "flow.md"
            source.write_text("# 流程\n\n" + self.DIAGRAM, encoding="utf-8")

            result = run_cli(source)

            self.assertEqual(result.returncode, 0, result.stderr)
            html = (Path(tmp) / "flow.html").read_text(encoding="utf-8")
            self.assertIn('<div class="mermaid">', html)
            self.assertIn("A[开始]", html)
            self.assertNotIn('class="language-mermaid"', html)
            self.assertIn("<!-- mermaid ", html)
            self.assertIn("mermaid.initialize", html)
            self.assertGreater(len(html), 1_000_000)
            self.assertNotIn("<script src=", html)
            self.assertNotIn("<link ", html)

    def test_document_without_diagram_has_no_container_or_library(self):
        with tempfile.TemporaryDirectory() as tmp:
            with_diagram = Path(tmp) / "with.md"
            with_diagram.write_text("# 有图\n\n" + self.DIAGRAM, encoding="utf-8")
            without_diagram = Path(tmp) / "without.md"
            without_diagram.write_text("# 无图\n\n普通段落。\n", encoding="utf-8")

            self.assertEqual(run_cli(with_diagram).returncode, 0)
            self.assertEqual(run_cli(without_diagram).returncode, 0)

            plain = (Path(tmp) / "without.html").read_text(encoding="utf-8")
            diagram = (Path(tmp) / "with.html").read_text(encoding="utf-8")
            self.assertNotIn("mermaid", plain)
            self.assertLess(len(plain), 100_000)
            self.assertGreater(len(diagram) - len(plain), 1_000_000)

    def test_no_mermaid_flag_shows_plain_code_block_without_library(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "flow.md"
            source.write_text("# 流程\n\n" + self.DIAGRAM, encoding="utf-8")

            result = run_cli(source, "--no-mermaid")

            self.assertEqual(result.returncode, 0, result.stderr)
            html = (Path(tmp) / "flow.html").read_text(encoding="utf-8")
            self.assertIn('<pre><code class="language-mermaid">', html)
            self.assertIn("A[开始]", html)
            self.assertNotIn('<div class="mermaid">', html)
            self.assertNotIn("<!-- mermaid ", html)
            self.assertNotIn("mermaid.initialize", html)
            self.assertLess(len(html), 100_000)


class FileHandlingTest(unittest.TestCase):
    def test_overwrites_existing_html_and_handles_spaces_and_chinese_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "我的 笔记.md"
            source.write_text("# 我的笔记\n\n新版内容\n", encoding="utf-8")
            existing = Path(tmp) / "我的 笔记.html"
            existing.write_text("OLD CONTENT", encoding="utf-8")

            result = run_cli(source)

            self.assertEqual(result.returncode, 0, result.stderr)
            html = existing.read_text(encoding="utf-8")
            self.assertNotIn("OLD CONTENT", html)
            self.assertIn("新版内容", html)
            self.assertIn("<title>我的笔记</title>", html)
            self.assertIn("我的 笔记.md", html)


class EncodingTest(unittest.TestCase):
    def test_reads_utf8_with_bom(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "bom.md"
            source.write_bytes(
                b"\xef\xbb\xbf" + "# 带 BOM 的标题\n\n中文内容\n".encode("utf-8")
            )

            result = run_cli(source)

            self.assertEqual(result.returncode, 0, result.stderr)
            html = (Path(tmp) / "bom.html").read_text(encoding="utf-8")
            self.assertIn("<title>带 BOM 的标题</title>", html)
            self.assertIn("中文内容", html)

    def test_reads_gb18030(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "legacy.md"
            source.write_bytes("# 旧文件\n\n中文内容\n".encode("gb18030"))

            result = run_cli(source)

            self.assertEqual(result.returncode, 0, result.stderr)
            html = (Path(tmp) / "legacy.html").read_text(encoding="utf-8")
            self.assertIn("<title>旧文件</title>", html)
            self.assertIn("中文内容", html)


class ErrorHandlingTest(unittest.TestCase):
    def test_missing_input_reports_readable_error_and_nonzero_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "不存在.md"

            result = run_cli(missing)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("不存在.md", result.stderr)
            self.assertIn("找不到", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertFalse((Path(tmp) / "不存在.html").exists())


class TocAndAnchorTest(unittest.TestCase):
    markdown = """\
# 总标题

## 第一节

### 子节一

### 子节二

## 第二节

### 子节三

#### 四级标题

二级段落。
"""

    def convert(self, tmp, *args):
        source = Path(tmp) / "guide.md"
        source.write_text(self.markdown, encoding="utf-8")
        result = run_cli(source, *args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return (Path(tmp) / "guide.html").read_text(encoding="utf-8")

    def test_headings_get_sequential_anchors_per_level(self):
        with tempfile.TemporaryDirectory() as tmp:
            html = self.convert(tmp)

            self.assertIn('<h2 id="sec-1">第一节</h2>', html)
            self.assertIn('<h2 id="sec-2">第二节</h2>', html)
            self.assertIn('<h3 id="item-1">子节一</h3>', html)
            self.assertIn('<h3 id="item-2">子节二</h3>', html)
            self.assertIn('<h3 id="item-3">子节三</h3>', html)
            self.assertIn("<h4>四级标题</h4>", html)

    def test_toc_lists_only_h2_and_h3_in_nested_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            html = self.convert(tmp)

            self.assertRegex(html, r'<nav class="toc"')
            match = re.search(r'<nav class="toc".*?</nav>', html, re.DOTALL)
            self.assertIsNotNone(match)
            nav = match.group(0)
            self.assertNotIn("总标题", nav)
            self.assertNotIn("四级标题", nav)
            for anchor, title in (
                ("sec-1", "第一节"),
                ("sec-2", "第二节"),
                ("item-1", "子节一"),
                ("item-2", "子节二"),
                ("item-3", "子节三"),
            ):
                self.assertIn(f'<a href="#{anchor}">{title}</a>', nav)
            positions = [
                nav.index(f'href="#{anchor}"')
                for anchor in ("sec-1", "item-1", "item-2", "sec-2", "item-3")
            ]
            self.assertEqual(positions, sorted(positions))
            self.assertIn('<li><a href="#sec-1">第一节</a>\n<ul>', nav)

    def test_document_without_h2_or_h3_has_no_toc(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "short.md"
            source.write_text("# 只有标题\n\n一段正文。\n", encoding="utf-8")

            result = run_cli(source)

            self.assertEqual(result.returncode, 0, result.stderr)
            html = (Path(tmp) / "short.html").read_text(encoding="utf-8")
            self.assertNotIn('<nav class="toc"', html)
            self.assertIn('class="shell no-toc"', html)
            self.assertIn("<body>", html)
            self.assertIn("一段正文。", html)


class TocToggleTest(unittest.TestCase):
    markdown = "# 标题\n\n## 章节\n\n### 小节\n\n正文。\n"

    def convert(self, tmp, *args):
        source = Path(tmp) / "toggle.md"
        source.write_text(self.markdown, encoding="utf-8")
        result = run_cli(source, *args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return (Path(tmp) / "toggle.html").read_text(encoding="utf-8")

    def test_default_layout_keeps_toc_column(self):
        with tempfile.TemporaryDirectory() as tmp:
            html = self.convert(tmp)

            self.assertIn('<nav class="toc"', html)
            self.assertIn('class="shell"', html)
            self.assertNotIn('class="shell no-toc"', html)
            self.assertIn('<h2 id="sec-1">章节</h2>', html)

    def test_no_toc_flag_removes_toc_and_centers_single_column(self):
        with tempfile.TemporaryDirectory() as tmp:
            html = self.convert(tmp, "--no-toc")

            self.assertNotIn('<nav class="toc"', html)
            self.assertIn('class="shell no-toc"', html)
            self.assertIn("正文。", html)
            self.assertIn('<h2 id="sec-1">章节</h2>', html)
            self.assertIn('<h3 id="item-1">小节</h3>', html)

    def test_narrow_screen_has_drawer_controls(self):
        with tempfile.TemporaryDirectory() as tmp:
            html = self.convert(tmp)

            self.assertIn('<body class="has-toc">', html)
            self.assertIn('id="tocHandle"', html)
            self.assertIn('id="tocBackdrop"', html)


class CodeHighlightTest(unittest.TestCase):
    def test_fenced_blocks_with_known_languages_are_highlighted(self):
        samples = [
            ("python", "def f(x):\n    return x + 1\n", '<span class="k">def</span>'),
            ("javascript", "const n = 1;\n", '<span class="kd">const</span>'),
            ("bash", 'echo "hi"\n', '<span class="s2">"hi"</span>'),
            ("html", '<p class="x">hi</p>\n', '<span class="nt">p</span>'),
            ("css", "a { color: red; }\n", '<span class="k">color</span>'),
            ("json", '{"a": 1}\n', '<span class="nt">"a"</span>'),
        ]
        markdown = "\n".join(
            f"```{language}\n{code}```" for language, code, _ in samples
        )
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "highlight.md"
            source.write_text(markdown, encoding="utf-8")

            result = run_cli(source)

            self.assertEqual(result.returncode, 0, result.stderr)
            html = (Path(tmp) / "highlight.html").read_text(encoding="utf-8")
            self.assertIn('<pre class="highlight">', html)
            text = unescape(re.sub(r"<[^>]+>", "", html))
            for language, code, marker in samples:
                self.assertIn(f'<code class="language-{language}">', html)
                self.assertIn(marker, html)
                self.assertIn(code.strip(), text)

    def test_highlight_styles_are_inlined_for_light_and_dark_without_external_resources(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "style.md"
            source.write_text("```python\nx = 1\n```\n", encoding="utf-8")

            result = run_cli(source)

            self.assertEqual(result.returncode, 0, result.stderr)
            html = (Path(tmp) / "style.html").read_text(encoding="utf-8")
            self.assertIn("pre.highlight .k", html)
            self.assertIn("var(--hl-key)", html)
            self.assertRegex(html, r":root\s*\{[^}]*--hl-key:")
            self.assertRegex(
                html, r"@media \(prefers-color-scheme: dark\)[\s\S]*?--hl-key:"
            )
            self.assertRegex(html, r':root\[data-theme="dark"\][\s\S]*?--hl-key:')
            self.assertNotIn("<link ", html)
            self.assertNotIn("@import", html)
            self.assertNotIn("<script src=", html)

    def test_unknown_language_fence_falls_back_to_plain_text(self):
        markdown = "```foobar\nx < 3 && y > 1\n```\n"
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "unknown.md"
            source.write_text(markdown, encoding="utf-8")

            result = run_cli(source)

            self.assertEqual(result.returncode, 0, result.stderr)
            html = (Path(tmp) / "unknown.html").read_text(encoding="utf-8")
            self.assertIn('<pre><code class="language-foobar">', html)
            self.assertIn("x &lt; 3 &amp;&amp; y &gt; 1", html)
            self.assertNotIn('<pre class="highlight">', html)
            self.assertNotIn('<span class="', html)

    def test_unlabeled_fence_falls_back_to_plain_text(self):
        markdown = "```\n没有语言标记\n```\n"
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "plain.md"
            source.write_text(markdown, encoding="utf-8")

            result = run_cli(source)

            self.assertEqual(result.returncode, 0, result.stderr)
            html = (Path(tmp) / "plain.html").read_text(encoding="utf-8")
            self.assertIn("<pre><code>没有语言标记\n</code></pre>", html)
            self.assertNotIn('<pre class="highlight">', html)

    def test_inline_code_is_not_highlighted(self):
        markdown = '行内 `def f(x)` 与 `{"a": 1}` 保持原样。\n'
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "inline.md"
            source.write_text(markdown, encoding="utf-8")

            result = run_cli(source)

            self.assertEqual(result.returncode, 0, result.stderr)
            html = (Path(tmp) / "inline.html").read_text(encoding="utf-8")
            self.assertIn("<code>def f(x)</code>", html)
            self.assertIn("<code>{&quot;a&quot;: 1}</code>", html)
            self.assertNotIn('<pre class="highlight">', html)
            self.assertNotIn('<span class="k">', html)


class BatchConversionTest(unittest.TestCase):
    def test_converts_every_path_and_prints_each_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "第一篇 笔记.md"
            second = Path(tmp) / "second note.md"
            first.write_text("# 第一篇\n\n批量内容一。\n", encoding="utf-8")
            second.write_text("# 第二篇\n\n批量内容二。\n", encoding="utf-8")

            result = run_cli(first, second)

            self.assertEqual(result.returncode, 0, result.stderr)
            first_html = Path(tmp) / "第一篇 笔记.html"
            second_html = Path(tmp) / "second note.html"
            self.assertIn("批量内容一。", first_html.read_text(encoding="utf-8"))
            self.assertIn("批量内容二。", second_html.read_text(encoding="utf-8"))
            self.assertIn(str(first_html), result.stdout)
            self.assertIn(str(second_html), result.stdout)
            self.assertLess(
                result.stdout.index(str(first_html)),
                result.stdout.index(str(second_html)),
            )

    def test_failure_keeps_converting_other_files_and_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            good = Path(tmp) / "good.md"
            missing = Path(tmp) / "missing.md"
            another = Path(tmp) / "another.md"
            good.write_text("# 好文件\n\n正常内容。\n", encoding="utf-8")
            another.write_text("# 另一个文件\n\n也要转换。\n", encoding="utf-8")

            result = run_cli(good, missing, another)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing.md", result.stderr)
            self.assertIn("找不到", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertTrue((Path(tmp) / "good.html").exists())
            self.assertTrue((Path(tmp) / "another.html").exists())
            self.assertFalse((Path(tmp) / "missing.html").exists())


BROWSER_PROBE = '''\
import os

_marker = os.environ.get("MD2HTML_TEST_OPEN_MARKER")


def _record(target):
    if _marker:
        with open(_marker, "a", encoding="utf-8") as handle:
            handle.write(str(target) + "\\n")


def _startfile(path, *args, **kwargs):
    _record(path)


os.startfile = _startfile

import webbrowser


def _webbrowser_open(url, *args, **kwargs):
    _record(url)
    return True


webbrowser.open = _webbrowser_open
'''


class OpenFlagTest(unittest.TestCase):
    def _browser_probe(self, tmp):
        hook = Path(tmp) / "probe"
        hook.mkdir()
        (hook / "sitecustomize.py").write_text(BROWSER_PROBE, encoding="utf-8")
        marker = Path(tmp) / "opened.txt"
        env = {
            "PYTHONPATH": str(hook),
            "MD2HTML_TEST_OPEN_MARKER": str(marker),
        }
        return marker, env

    def test_open_opens_single_file_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "single.md"
            source.write_text("# 单个文件\n\n正文。\n", encoding="utf-8")
            marker, env = self._browser_probe(tmp)

            result = run_cli(source, "--open", extra_env=env)

            self.assertEqual(result.returncode, 0, result.stderr)
            output = Path(tmp) / "single.html"
            self.assertTrue(output.exists())
            opened = marker.read_text(encoding="utf-8").splitlines()
            self.assertEqual(opened, [str(output)])

    def test_open_does_not_open_any_file_when_multiple_given(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "a.md"
            second = Path(tmp) / "b.md"
            first.write_text("# A\n\n甲。\n", encoding="utf-8")
            second.write_text("# B\n\n乙。\n", encoding="utf-8")
            marker, env = self._browser_probe(tmp)

            result = run_cli(first, second, "--open", extra_env=env)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((Path(tmp) / "a.html").exists())
            self.assertTrue((Path(tmp) / "b.html").exists())
            self.assertFalse(marker.exists())

    def test_open_is_skipped_when_single_file_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing.md"
            marker, env = self._browser_probe(tmp)

            result = run_cli(missing, "--open", extra_env=env)

            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
