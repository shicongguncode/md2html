import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args):
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
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


if __name__ == "__main__":
    unittest.main()
