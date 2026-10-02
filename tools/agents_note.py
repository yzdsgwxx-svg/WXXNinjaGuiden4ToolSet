from pathlib import Path
p = Path('AGENTS.md'); s = p.read_text(encoding='utf-8')
anchor = "- 发布（v1.0 流程，本机没有 gh CLI）："
note = ("- **远端报 `remote: Your account is suspended` 或 API 403 时**，是 GitHub 账号级封禁（`yzdsgwxx` 在 2026-02 遇到过一次，"
        "封禁前 push / Release / 155 MB 附件都成功）。这跟本地无关：提交、打包、zip 全都在本地完好；不要反复重试，"
        "去 <https://support.github.com> 申诉，解封后 `git push origin master` 一次性补齐即可。\n")
assert anchor in s
s = s.replace(anchor, note + anchor, 1)
p.write_text(s, encoding='utf-8')
print('AGENTS.md: account suspension note added')
