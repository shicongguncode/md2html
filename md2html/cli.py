import argparse
import sys
from pathlib import Path

from .core import convert


class ConversionError(RuntimeError):
    pass


def _fail(message: str) -> int:
    print(f"错误：{message}", file=sys.stderr)
    return 1


def _read_markdown(source: Path) -> str:
    data = source.read_bytes()
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ConversionError(f"无法识别 {source} 的编码（既不是 UTF-8 也不是 GB18030）")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="md2html", description="把 Markdown 文件转换成单文件 HTML"
    )
    parser.add_argument("source", help="要转换的 Markdown 文件")
    args = parser.parse_args(argv)

    source = Path(args.source)
    if not source.exists():
        return _fail(f"找不到文件：{source}")
    if not source.is_file():
        return _fail(f"不是文件：{source}")

    output = source.with_suffix(".html")
    try:
        page = convert(_read_markdown(source), source_name=source.name)
        output.write_text(page, encoding="utf-8")
    except (ConversionError, OSError) as exc:
        return _fail(str(exc))

    print(output)
    return 0
