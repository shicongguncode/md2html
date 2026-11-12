import argparse
import os
import sys
import webbrowser
from pathlib import Path

from .core import convert


class ConversionError(RuntimeError):
    pass


def _error(message: str) -> None:
    print(f"错误：{message}", file=sys.stderr)


def _read_markdown(source: Path) -> str:
    data = source.read_bytes()
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ConversionError(f"无法识别 {source} 的编码（既不是 UTF-8 也不是 GB18030）")


def _convert_file(source: Path, *, toc: bool, mermaid: bool) -> Path:
    if not source.exists():
        raise ConversionError(f"找不到文件：{source}")
    if not source.is_file():
        raise ConversionError(f"不是文件：{source}")

    output = source.with_suffix(".html")
    page = convert(
        _read_markdown(source), source_name=source.name, toc=toc, mermaid=mermaid
    )
    output.write_text(page, encoding="utf-8")
    return output


def _open_in_browser(path: Path) -> None:
    startfile = getattr(os, "startfile", None)
    if startfile is not None:
        startfile(str(path))
    else:
        webbrowser.open(path.resolve().as_uri())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="md2html", description="把 Markdown 文件转换成单文件 HTML"
    )
    parser.add_argument(
        "sources", nargs="+", metavar="source", help="要转换的 Markdown 文件，可传多个"
    )
    parser.add_argument(
        "--open",
        action="store_true",
        dest="open_browser",
        help="转换后用系统默认浏览器打开结果（仅在只传一个文件时生效）",
    )
    parser.add_argument(
        "--no-toc", action="store_true", help="不生成左侧目录，正文改为居中单栏"
    )
    parser.add_argument(
        "--no-mermaid",
        action="store_true",
        help="把 Mermaid 代码块按普通代码块显示，不内联图库",
    )
    args = parser.parse_args(argv)

    sources = [Path(item) for item in args.sources]
    failures = 0
    for source in sources:
        try:
            output = _convert_file(
                source, toc=not args.no_toc, mermaid=not args.no_mermaid
            )
        except (ConversionError, OSError) as exc:
            _error(str(exc))
            failures += 1
            continue
        print(output)

    if failures:
        if len(sources) > 1:
            _error(f"{failures} 个文件转换失败")
        return 1

    if args.open_browser and len(sources) == 1:
        try:
            _open_in_browser(sources[0].with_suffix(".html"))
        except OSError as exc:
            _error(f"无法打开浏览器：{exc}")
            return 1

    return 0
