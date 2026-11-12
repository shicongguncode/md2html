# md2html

把 Markdown 转成**单文件 HTML** 的小工具。生成的 HTML 自带样式和 Mermaid 脚本，双击就能在浏览器里打开，不依赖网络。

## 功能

- 常用 Markdown 语法：标题、表格、列表、引用、任务列表
- 代码块语法高亮（Pygments）
- Mermaid 图表：流程图、时序图等
- 自动生成侧边目录，窄屏下变成可滑出的抽屉
- 支持一次转换多个文件，支持拖拽

## 安装

需要 Python 3.10+。

```bash
pip install -r requirements.txt
```

## 用法

```bash
python -m md2html 你的文件.md
```

常用参数：`--open` 转完自动打开浏览器，`--no-toc` 不要目录，`--no-mermaid` 把图表降级成代码块。

Windows 上也可以把 `.md` 文件直接拖到 `md2html.bat` 上。

## 开发

```bash
# 跑测试 + 编译检查
scripts\check.bat

# 启用仓库自带的 pre-commit 钩子（可选）
git config core.hooksPath .githooks
```

## 示例

`samples/全部元素测试.md` 覆盖了全部支持的语法，`samples/全部元素测试.html` 是转换效果。

## 许可证

MIT
