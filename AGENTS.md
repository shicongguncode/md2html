## 项目速览

单文件 Markdown→HTML 转换器：`python -m md2html <file.md>`。依赖用 `pip install -r requirements.txt` 安装，提交前运行 `scripts/check.bat`（测试 + 编译检查）。视觉基准在 `docs/reference/agent-skills-sample.html`。

## Agent skills

### Issue tracker

Issues live as markdown files under `.scratch/<feature>/`. See `docs/agents/issue-tracker.md`.

### Triage labels

Default five-role vocabulary (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` at the root plus `docs/adr/`. See `docs/agents/domain.md`.
