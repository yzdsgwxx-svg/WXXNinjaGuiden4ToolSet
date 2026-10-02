from pathlib import Path
p = Path('AGENTS.md'); s = p.read_text(encoding='utf-8')

header = "# NinjaGuiden6Slot 工程速查\n"
new_header = ("# WXXNinjaGuiden4ToolSet 工程速查\n"
              "> 工程根目录 `D:\\APP\\WXXNinjaGuiden4ToolSet`（2026 年从 `NinjaGuiden6Slot` 改名而来）；"
              "远端 `https://github.com/yzdsgwxx/WXXNinjaGuiden4ToolSet.git`，分支 `master`。已发布 v1.0。\n")
assert header in s
s = s.replace(header, new_header, 1)

old_lock = "- 打包产物锁：`overlay\\pack\\...\\app.asar` 在测试运行后可能被 Defender/索引器短暂持有而删不掉，等一会儿再 `rd /s /q`，不影响交付。"
new_lock = ("- **打包输出必须放 `%TEMP%`**：`overlay\\pack`、`overlay\\dist`、`overlay\\build-pack` 里的 `app.asar` 会被常驻的 "
            "**ChatGPT(Codex) 应用**（`C:\\Program Files\\WindowsApps\\OpenAI.Codex_*\\app\\ChatGPT.exe`）持久持有——删不掉、搬不动，"
            "还会连带锁住 `overlay` 乃至整个工程目录，**导致工程无法改名**（实测 Rename-Item 一直报“另一个进程正在使用此文件”）。"
            "持有者是用 Restart Manager（`rstrmgr.dll` 的 `RmStartSession`/`RmRegisterResources`/`RmGetList`）查出来的，"
            "任务管理器和 `Get-Process | Modules` 都看不到。改名只能在关掉该应用后做，或逐层 `Move-Item` 跳过被锁目录。")
assert old_lock in s
s = s.replace(old_lock, new_lock, 1)

anchor = "- 面板截图："
release = ("- 发布（v1.0 流程，本机没有 gh CLI）：`git push origin master` → 用 `git credential fill`（凭据管理器里存着 yzdsgwxx 的 token）"
           "→ `POST /repos/yzdsgwxx/WXXNinjaGuiden4ToolSet/releases`（`tag_name` 用 `v1.0`）→ 白名单压缩 `dist` 的 9 项"
           "（`WXXNinjaGuiden4ToolSet.exe` / `SixSlotConfig.exe` / `SixSlot.dll` / `SixSlot.ini` / `Start.cmd` / `Stop.cmd` / "
           "`README.zh-CN.md` / `MinHook-LICENSE.txt` / `ControllerOverlay/`，**不含 `saves`、日志、打包目录**），"
           "压缩包顶层套一层 `WXXNinjaGuiden4ToolSet/` → `POST uploads.github.com/repos/.../releases/{id}/assets?name=...`（155 MB 上传约 3 分钟）。"
           "发布包内不得出现任何存档：`ZipFile` 的条目列表用正则查 `save|SlotData|GameData|原始|全成就` 确认过。\n")
assert anchor in s
s = s.replace(anchor, release + anchor, 1)

habit = "- 顺手发现的问题先问后改；不擅自 git 提交推送。"
new_habit = ("- 顺手发现的问题先问后改；\n"
             "- **GitHub 推送已获授权**：用户在本轮明确要求提交并发布到 `yzdsgwxx/WXXNinjaGuiden4ToolSet`，"
             "凭据存在 Windows 凭据管理器（`git credential fill` 可取 token）。除这个仓库外仍不要擅自推送。")
assert habit in s
s = s.replace(habit, new_habit, 1)
p.write_text(s, encoding='utf-8')
print('AGENTS.md updated for rename + release workflow')
