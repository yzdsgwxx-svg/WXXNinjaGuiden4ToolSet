# WXX 忍龙 4 工具集

忍龙 4（Steam 版）本地工具集，三件套：

| 部件 | 文件 | 作用 |
|---|---|---|
| 控制器覆层 | `ControllerOverlay\WXXControllerOverlay.exe` | 手柄输入可视化（刀形震动强度条）、震动捕获 |
| 键盘版六槽武器 | `SixSlot.dll` + `SixSlotConfig.exe` | 额外两把武器绑键切换，保留原生四槽 |
| 存档切换 | `WXXNinjaGuiden4ToolSet.exe` | 原始存档 / 全成就存档互切，切换前自动备份 |

## 使用

从 Release 下载 `WXXNinjaGuiden4ToolSet-v1.0.zip`，解压到任意目录（**不要放进游戏目录**），双击 `Start.cmd`。

- `Start.cmd` 打开工具集面板；`Stop.cmd` 停用六槽武器。
- 面板三张卡片各带一个独立开关：
  - **六槽武器**：先启动游戏，再打开开关即完成注入；关掉就恢复原生武器选择器。
  - **控制器覆层**：开关直接开关覆层窗口；「启动忍龙4」通过 Steam 拉起游戏。
  - **存档切换**：下拉框展开时才刷新档案列表；「存档目录」直接打开 `saves\`。
- 覆层打开时会自动认到正在运行的忍龙 4 并接上震动捕获；也可手动选目标程序，或点「清除」断开。上次选中的目标会被记住，下次打开优先恢复。
- 存档切换只在**切换那一刻**同步当前进度，没有定时保存；游戏运行中不允许切换。

面向使用者的详细说明见 `dist/README.zh-CN.md`。

## 环境

Windows 10 / 11 64 位。解压即用，不需要安装 Node、Python 或 VC++ 运行库。

## 构建

- 原生部分：`build.cmd`（MSVC 2022 x64）→ `dist/SixSlot.dll`、`dist/WXXNinjaGuiden4ToolSet.exe`、`dist/SixSlotConfig.exe`
- 覆层：用 `AGENTS.md` 里记录的 electron-packager 命令（输出到临时目录，再 `robocopy` 同步到 `dist/ControllerOverlay`）

开发不变量、调试手法、踩过的坑都写在 `AGENTS.md`。

## 说明

- 只支持开发时核实的那一份 Steam 版 `NINJAGAIDEN4-Steam.exe`（SHA-256 比对，DLL 另外逐处核对指令字节），版本不匹配会明确拒绝加载。
- 不修改游戏磁盘资源、不联网；只切「游戏自己认为已解锁」的武器。
- 仓库不含游戏存档、运行日志与打包产物，见 `.gitignore`。

## 许可

MinHook v1.3.4（TsudaKageyu）：<https://github.com/TsudaKageyu/minhook> ，许可见 `dist/MinHook-LICENSE.txt`。
Electron / Chromium 许可见 `dist/ControllerOverlay/`。
