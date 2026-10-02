# WXXNinjaGuiden4ToolSet 工程速查
> 工程根目录 `D:\APP\WXXNinjaGuiden4ToolSet`（2026 年从 `NinjaGuiden6Slot` 改名而来）；远端 `https://github.com/yzdsgwxx/WXXNinjaGuiden4ToolSet.git`，分支 `master`。已发布 v1.0。

忍龙 4（Steam）工具集三件套：`WXXNinjaGuiden4ToolSet.exe`（Win32 面板）+ `ControllerOverlay\WXXControllerOverlay.exe`（Electron 手柄覆层）+ `SixSlot.dll`（注入 Mod）。定位：解压即用，用户不用装 Node / Python / VC++ 运行库。

## 文件职责
- `src/mod.cpp`：注入 DLL（v0.2）。MinHook hook 三处 RVA：`0x608730` 更新、`0xcbf680` 槽位选择、`0xcbfa80` 槽→武器解析；Worker 线程 `GetAsyncKeyState` 轮询配置键（仅游戏前台、无 Ctrl/Alt/Shift）→ `request=(tick<<8)|槽号(5/6)` → `UpdateHook` 临时置一帧"方向键上"输入位让原生逻辑自己走切换，随后还原。对外只暴露两个命名事件：`Local\NG4SixSlot_Stop_<pid>`（停用）、`Local\NG4SixSlot_Enabled_<pid>`（手动重置事件，置位=已启用，面板据此显示真实开关状态）。
- `src/config.cpp`：`SixSlotConfig.exe`「6槽武器设置」。每槽一组"按键下拉框 + 武器下拉框"，写 `SixSlot.ini` 的 `[Keys]`/`[Weapons]`。
- `src/launcher.cpp`：`WXXNinjaGuiden4ToolSet.exe`。`WS_POPUP` 全自绘面板（GDI + GDI+）：四张卡片（六槽武器 / 控制器覆层 / 存档切换 / F10 存档），卡片标题用 WM_PAINT 画，按钮统一 `BS_OWNERDRAW` 在 WM_DRAWITEM 里画。开关只有两个（六槽武器、F10 存档），状态写 `SixSlot.ini` 并在启动时恢复；六槽武器开关开着时游戏一运行就自动注入（`DoInject(silent)`，失败只记日志、每个游戏进程只试一次）。覆层卡片是「打开」按钮（不表示状态，已在跑就不重复启动）。命令行：`--stop`、`--overlay-open`、`--overlay-close`。
- `overlay/`：覆层源码（`main.js` 主进程、`renderer.js`+`index.html`+`style.css` 界面、`rumble-source.js` 震动采集、`native-input.js` + `native/rumble-hook` 原生注入）。标题栏只有「最小化 / 关闭」，底部设置区常显三项：震动捕获目标程序下拉框、`清除`、`复制 URL`。打包产物 `dist/ControllerOverlay/`，主程序 `WXXControllerOverlay.exe`，命令行 `--close`（第二实例收到即退出）、`--smoke-test`（自检后把结果写到 `%TEMP%\NinjaOverlaySmoke\smoke.json`，errors 非空则退出码 1）、`--probe`（写 `probe.json` 供命中测试）、`--soak=<ms>`。**覆层日志在 `%APPDATA%\wxx-ng4-controller-overlay\logs\main.log`**（不是 dist 目录），排查覆层第一步看它。
- **覆层保持沙箱开启、普通权限运行**：若启动即退出，先检查 EXE 的文件完整性标签。工程 Low 标签会使 EXE 普通启动也降为 Low；运行 `dist\Repair-Permissions.cmd` 后重启。不要用 `--no-sandbox` 掩盖文件权限问题。详见末尾的根因纠正。
- `assets/`：`toolset.svg/.ico/.png`（工具集图标 = 手柄 + 忍龙 logo + 震动进度条）、`overlay.svg/.png`（覆层图标，控制器 + 震动条效果图）。
- `dist/saves/`：**只允许 `原始存档`、`全成就存档` 两个目录**（`RefreshProfiles` 硬过滤）；`current.txt` 记录当前档案；`backups\<时间>_<来源>\` 是切换前完整备份，只增不删。
- `dist/SixSlot.ini`：`[Keys]` 触发键虚拟键码（十进制，Q=81 E=69 R=82 5=53 6=54；两槽不能相同，缺段回退 Q/E），`[Weapons]` 槽→武器 ID（0 双刀 1 棍 2 长枪 3 暗器 4 黑龙丸 6 DLC 镰刀；5/7 保留给龙隼），`[Toolset]WeaponSwitch` 六槽武器开关（面板写、重启面板后按它自动注入），`[Save]TestKey` 主动存档键（121=F10 开、0=关，面板写）。Worker 每秒比对文件时间戳热重载。
- 日志：`dist/SixSlot.log`（mod，配置与每次切换）、`dist/WXXToolset.log`（面板，注入/存档），排查第一步看它们。

## 命令
- 编译：`build.cmd`（MSVC 2022 x64，`vcvars64.bat` 路径写死）→ `dist/SixSlot.dll` + `WXXNinjaGuiden4ToolSet.exe` + `SixSlotConfig.exe`。编译前关掉占用者：游戏（锁 `SixSlot.dll`）、已打开的面板与 config（锁 exe，报 `LNK1104`）。
- 覆层打包（离线，本机 `%LOCALAPPDATA%\electron\Cache\<hash>\electron-v44.5.1-win32-x64.zip` 已有）：`cd overlay` → `node node_modules\@electron\packager\bin\electron-packager.mjs . WXXControllerOverlay --platform=win32 --arch=x64 --out="$env:TEMP\WXXOverlayPack" --overwrite --electron-zip-dir="<Cache 里那个 hash 目录>" --ignore="^/tests" --ignore="^/artifacts" --ignore="^/native/rumble-hook" --extra-resource=native/bin/RumbleHook.dll` → `robocopy "$env:TEMP\WXXOverlayPack\WXXControllerOverlay-win32-x64" dist\ControllerOverlay /MIR`。不加 `--electron-zip-dir` 会去联网下载，本机直接 `fetch failed`。
- **打包输出别放在 overlay 目录里**：`overlay\pack`、`overlay\dist`、`overlay\build-pack` 里的 `app.asar` 会被系统句柄长时间锁住，`rd /s /q` 删不掉、只会留下几百 MB 垃圾（工程里已有这三个残留目录）。输出到 `%TEMP%` 就没这个问题。
- **ignore 正则的坑**：`--ignore="^/native"` 会连 `native-input.js` 一起排除，运行时报 `Cannot find module './native-input'`；要写 `^/native/rumble-hook`。
- 覆层自测：`overlay\node_modules\electron\dist\electron.exe . --smoke-test`。**不要用 `npx electron` 或 `electron.cmd`**——在本机沙箱下它们会退化成 node 直接跑 main.js，报 `TypeError: Cannot read properties of undefined (reading 'isPackaged')`。单元测试 `cd overlay; npm test`。
- **`overlay\node_modules` 丢失时的恢复**（实测被清空过一次）：`npm ci` 能装齐 53 个包（走 npm 缓存，2 秒），但 npm 11 会拦 install script，所以 **electron 的 `dist\` 不会生成**——手动把 `%LOCALAPPDATA%\electron\Cache\<hash>\electron-v44.5.1-win32-x64.zip` 解压到 `node_modules\electron\dist`，再写 `node_modules\electron\path.txt`（内容只有 `electron.exe`、无换行）。`koffi` 不用编译：`@koromix/koffi-win32-x64` 自带 `win32_x64\koffi.node`，`node -e "require('koffi').load('user32')"` 能过就不用管它的 install 脚本。
- 原生振动 hook：`overlay/native/rumble-hook/build.bat` → `overlay/native/bin/RumbleHook.dll`；打包靠 `--extra-resource` 落到 `resources\RumbleHook.dll`（asar 里的 DLL 无法被目标进程 LoadLibrary，冒烟测试会检查这个路径）。
- **打包输出必须放 `%TEMP%`**：`overlay\pack`、`overlay\dist`、`overlay\build-pack` 里的 `app.asar` 会被常驻的 **ChatGPT(Codex) 应用**（`C:\Program Files\WindowsApps\OpenAI.Codex_*\app\ChatGPT.exe`）持久持有——删不掉、搬不动，还会连带锁住 `overlay` 乃至整个工程目录，**导致工程无法改名**（实测 Rename-Item 一直报“另一个进程正在使用此文件”）。持有者是用 Restart Manager（`rstrmgr.dll` 的 `RmStartSession`/`RmRegisterResources`/`RmGetList`）查出来的，任务管理器和 `Get-Process | Modules` 都看不到。改名只能在关掉该应用后做，或逐层 `Move-Item` 跳过被锁目录。
- **远端报 `remote: Your account is suspended` 或 API 403 时**，是 GitHub 账号级封禁（`yzdsgwxx` 在 2026-02 遇到过一次，封禁前 push / Release / 155 MB 附件都成功）。这跟本地无关：提交、打包、zip 全都在本地完好；不要反复重试，去 <https://support.github.com> 申诉，解封后 `git push origin master` 一次性补齐即可。
- 发布（v1.0 流程，本机没有 gh CLI）：`git push origin master` → 用 `git credential fill`（凭据管理器里存着 yzdsgwxx 的 token）→ `POST /repos/yzdsgwxx/WXXNinjaGuiden4ToolSet/releases`（`tag_name` 用 `v1.0`）→ 白名单压缩 `dist` 的发布项（`WXXNinjaGuiden4ToolSet.exe` / `SixSlotConfig.exe` / `SixSlot.dll` / `SixSlot.ini` / `Start.cmd` / `Stop.cmd` / `Repair-Permissions.cmd` / `README.zh-CN.md` / `MinHook-LICENSE.txt` / `ControllerOverlay/`，**不含 `saves`、日志、打包目录**），压缩包顶层套一层 `WXXNinjaGuiden4ToolSet/` → `POST uploads.github.com/repos/.../releases/{id}/assets?name=...`（155 MB 上传约 3 分钟）。发布包内不得出现任何存档：`ZipFile` 的条目列表用正则查 `save|SlotData|GameData|原始|全成就` 确认过。
- 面板截图：`powershell -ExecutionPolicy Bypass -File tools/shot.ps1` → `artifacts/toolset.png`（`PrintWindow`，被遮挡也能抓；句柄要轮询 `MainWindowHandle`）。
- 存档自测：`cmd /c tests\run.cmd`（`tests/save_sync_test.cpp`，用临时目录，要求游戏没运行）。

## 不变量
- 只支持开发时核实的那一份 `NINJAGAIDEN4-Steam.exe`（SHA-256 `3e3ecfe254c33aac…79e8c83a`）；DLL 另外逐处比对指令字节，不匹配拒绝加载。
- 请求超过 200 ms 丢弃（不排队）；按键只在游戏前台生效；两槽绑同一键时第 6 槽停用并写日志。
- 只切"游戏自己认为已解锁"的武器：解析钩子内调 `0xcc04a0` 判定，未解锁就原样返回旧武器。不改游戏内存数据、不联网。
- 武器选择器状态：`manager+0x218` = 页(byte)、`manager+0x21c` = 槽(dword，方向码 13上/15右/14下/16左)。`select(0xcbf680)` 先 `resolve(当前页, action)`，只有 `slot==action` 或结果=8 时才翻页，否则同页换槽；`update(0x608730)` 四个分支分别用 action 13/15/14/16 调 `select`+`resolve`，结果写 `player+0x8054`。实测原生布局：武器0(双刀)=页0槽13、武器4(黑龙丸)=页1槽13、武器2(夜刀穿)=页1槽15。
- 额外键切换跳过原生 `select`，必须自己把页/槽同步到该武器真实位置；原生槽位键 1..4 恒等于第一页四槽（原生翻页已按用户要求移除，页1 只能靠额外键 Q/E 到达）。**这套干预只在 `enabled` 为真时生效：停用后原生选择器完全恢复。**
- 存档同步只在切换存档时进行：`SwitchToProfile` 先 `SyncCurrentProfile()` 把游戏当前存档写回当前档案，再写目标档案。**没有定时保存、没有自动快照、没有"退出同步"开关**（用户明确要求删掉：不要每 5 分钟保存，也不要一堆副本）。
- 存档切换顺序不可改：全量备份当前存档目录并逐文件 SHA-256 → `SyncCurrentProfile` → 删旧存档文件 → 复制档案 → 逐文件校验。只删 `GameData.dat` / `SlotData_*.dat` / `SystemData.vdf`，保留 `steam_autocloud.vdf`；游戏运行中直接拒绝切换；任何一步失败立即中止并保留现场。
- 游戏内存档（**旧结论已推翻，别再照旧的做**）：闪退真因不是"野指针/外部线程"，而是**入口签名的坑**——`0x102e3d0`（code 7 → GameData.dat）和 `0x102e510`（code 6 → SystemData.vdf）的真实签名是 `(this, const Descriptor*)`：进门第一步 `add rcx,0x580; call 0x102cba0` 其实是**结构体拷贝**（memcpy 0x7f + 0x7f + 0x3ff 字节 + 一个 dword），只传 `this` 时 rdx 是调用者残留的垃圾指针，于是从垃圾地址读 0x4fd 字节 → 立刻崩。`0x102c220` 也不是"实例捕获点"，它是 `WaitForSingleObject(handle,INFINITE)` 的通用包装，hook 它再减 0xad0 对别的调用者会算出垃圾指针。管理器由 `0x1026790` new 出 0xae8 字节，**首 qword = vtable base+0x2262d10**，可直接做实例校验。已核实：游戏自己的完整存档 = code7(GameData) → code6(SystemData) → code8(SlotData_{n}.dat) → code7，`saveSlotData(slot, meta)` 的 meta 是 128 字节 snprintf `"Game Slot%d Data"`（槽号取 `manager+0x568`）。
- **主动存档（F10）的正确做法**：不要去拼 descriptor 调底层入口。会话对象（`0xc44980` 每帧被调用、入口 `rcx` 就是它）有一个**外层阶段机**，阶段在 `[session+0xf0]`、当前子状态在 `[session+0x100]`、阶段参数（槽位）在 `[session+0xf4]`；分发器按 `[0xf0]+1` 查表（表在 `0xc44f84`）挑处理函数。**1 = 空闲**（处理请求队列后返回），**3 = 存档阶段**（`0xc464d0`：GameData.dat+SystemData.vdf），**5 = 存档阶段**（`0xc468d0`：SlotData_{n}.dat+GameData.dat），各自走完自己把 `[0xf0]` 设回 1。游戏内部的"进入某阶段"API 是 `0xc44790(session, stage, ?, slot)`，它做的就是 `[0xf4]=slot; [0xf0]=stage; [0x100]=0`（并先问管理器 `0x10267e0` 能不能走）。
  踢一次完整存档 = **两段**（游戏自己也是两段，中间会回空闲）：先把 `[0xf0]` 设 **3**、`[0x100]` 清 0、`[0xf4]` 设当前槽（`manager+0x568`）→ 等 `[0xf0]` 回到 **1** → 再把 `[0xf0]` 设 **5**、`[0x100]` 清 0 → 再等回 1。**阶段 5 不会自动跟在阶段 3 后面**（它由请求队列驱动），只踢阶段 3 时实测只写了 GameData.dat + SystemData.vdf、SlotData 没写。第二段由 Worker 的 `NoteSaveProgress()` 接（那一刻玩家 update 可能已停），150 ms 没被分发器接手就重写阶段，最多 5 次。
  实测阶段序列（游戏自己读档+存档）：`1→8→2→1`（读档）然后 `1→3→1`（GameData+SystemData）再 `1→5→1`（SlotData+GameData）。
  `[Save] KickMode` 可切换：1=直接调状态机 0xc460b0（**会卡住**：只推进子状态、外层还是 1）、2/3=子状态、4=阶段 7、5=阶段 3（**默认**）、6=直接调 `0xc44790`。
  只在会话处于**空闲阶段 1** 时才踢（避免打断读档/存档中）；`KickGameSave` 自带 2 秒去重。
- **F10 的触发路径**：`[Save] TestKey`（默认 121=F10，0=关）是**唯一**写盘入口，且**与六槽武器的 `enabled` 无关**——武器开关关掉也能按 F10 存档。Worker 轮询到按键边沿（仅游戏前台、无 Ctrl/Alt/Shift）置 `kickRequest` → 游戏线程 `UpdateHook` 消费它（正常游玩这条路最先到）→ 没被消费（人在菜单里，玩家 update 停了）就由 Worker 在 400 ms 后补踢一次（只有这条才跨线程写阶段字段）。会话析构 `0xc420e0`、管理器析构只做**一次** 2.5 秒有界等待（`saveWaitDone` 防连环等），保证按完 F10 立刻退出游戏时存档不被截断。存档备份在 `dist\saves\backups\`。
- **用户点名删掉的自动存档（别加回来）**：`[Save] ExitSave` 总开关、`[Save] SaveOnPause`（菜单打开就存）、`[Save] MenuIntervalMs`（菜单补存）、LB/RB 页签触发（曾用 XInput 只读轮询）、`SE_Sys_BackToTitle`（`0xc42350`）hook 里的踢存档。历史结论留作参考：两个"离开"动作（返回标题 / 退出游戏）都**先拆会话**，等 `0xc420e0` 通知到手时游戏已不再跑阶段分发器，那一刻踢的 `[0xf0]=3` 没人执行（日志实测白等 8 秒）。
  **待验证**：训练模式里按 F10 会不会把战役进度写成训练状态（要验证得进训练菜单手动按一次，看 `SixSlot.log` 与存档时间）。
- 用户明确点名删掉的入口不要加回来：导入全成就、游戏内存档、刷新档案、新建档案、退出同步、**存档卡片里的两个开关（「存档切换」「退出时存档」，2026-10 删）**、覆层里的 demo/主题/LT-RT 说明文字、覆层的「复位 / 设置 / 鼠标穿透」（连带 `setLocked`、`resetPosition`、`onLock`/`onSettings`、托盘里那两项菜单、`body.locked` 样式一并删除；设置面板改为常显）。
- 覆层震动捕获：**目标记忆优先**。每次成功连上（手动选 / 自动认 / 恢复）都把 `{pid, name}` 写进 `localStorage['rumble-target']`；打开覆层的顺序是 ① 有记忆且该 pid **仍在进程列表里、名字也对得上** → 恢复它并注入；② 否则 `forgetTarget()` 后走 `autoSelectGame()`（找 `/NINJAGAIDEN4/i` 直接选中 + 注入）；③ 展开下拉框（`openProcesses`）时同样先刷新、仍未选中就再跑一次 ① ②。「清除」会 `forgetTarget()`，否则下次打开又自动连回来。pid 会被系统复用，所以校验必须带进程名。
- 覆层「清除」按钮（在 `复制 URL` 左边）：IPC `rumble-clear` → 对当前注入 pid 发 `setEnabled(pid,false)`（通知 DLL 停 hook）+ `selectTarget(0)`（断开共享内存、清空 targetPid），renderer 再把下拉框 `value` 置空、状态文字写成「已清除 · 展开下拉框可重新选择」。清除后下拉框是空的，所以下次展开又会自动认忍龙 4（这是有意为之）。
- 震动强度抖动：`Input.wobble(value, timeMs, amplitude=.025, hz=16, threshold=.02)`（`overlay/input.js`，纯函数、有单测）。强度 ≥ 2% 时显示值在 **±2.5%**（进度条的 5%）之间以 **16 次/秒**摆动（用户先定 8，后来要求翻倍），**用 `Math.sin` 插值**——值是连续变化的，不要在上下限之间硬切。低于阈值或静止时如实显示；刀身高度和 `#rumble-value` 百分比都用抖动后的值。单测里有一条"逐帧最大跳变 < 幅度"守插值，改回方波（跳变 0.05）会失败。

## 界面约定（用户已验收的形态）
- 深色卡片 + 红金配色：背景 `#111217`，卡片 `#1a1a21`，描边 `#4d2e37`，主色 `#ec4454`，金色 `#b39b73`，正文 `#e8dccf`。
- 开关统一"胶囊轨道 + 圆形滑块"（GDI+ 画，宽 62 高 26，左 48px 是"开启/关闭"文字），**只有两个**：六槽武器、F10 存档。控制器覆层是普通按钮（文本「打开」，永远这个文本，不表示状态）。
- 标题栏 76px 高，最小化/关闭是细线图标（`—` / `×` 用 GDI+ DrawLine 画，不用字符），窗口圆角 `DwmSetWindowAttribute(33)`。
- 全部用微软雅黑 UI，正文 16px、卡片标题 24px semibold。
- 不弹成功提示框：开关自身状态就是反馈，只有失败才 MessageBox。
- 状态文本和开关文字一律走 `SetText()`（先比较内容，相同就 return）；**一秒轮询里禁止直接 `SetWindowTextW` / `InvalidateRect`**。`SetWindowTextW` 内容不变也会重绘控件，4 个控件每秒重绘一次就是肉眼可见的闪烁（实测 8 秒：修复前 35 次文本重设 / 40 次 owner-draw，修复后 2 次 / 10 次）。
- 文案尽量少，用户反感无意义的说明文字。
- 覆层是**普通窗口，不置顶**：`alwaysOnTop: false`，不要 `setAlwaysOnTop(...)`。原来写的 `setAlwaysOnTop(true, 'screen-saver')` 是最高层级，会永远压在别的程序上面（用户明确要求"点别的软件它就该失焦被盖住"）。`window-action` 的 `'top'` 分支和 preload 白名单里的 `'top'` 已删除，别再加回来。自检用 `result.topmost.alwaysOnTop` 守着这条。
- 覆层窗口拖动**不用 CSS**，用 JS：renderer 在非控件区域 `pointerdown` → IPC `drag-start`，主进程每 8 ms 跟随光标，`pointerup` / `blur` / `minimize` / `hookWindowMessage(0x0202)`(WM_LBUTTONUP) 结束。控件判断是 `target.closest('button,select,input,textarea,option,label,a')`，直播源页面（`source`）不拖。
- **跨不同缩放率的显示器必须用 Win32 物理像素移动窗口**：`koffi` 加载 user32，`GetCursorPos` / `GetWindowRect` 取物理值，`SetWindowPos(hwnd, 0, x, y, 0, 0, SWP_NOSIZE|SWP_NOZORDER|SWP_NOACTIVATE)` 只挪位置。用 Electron 的 DIP 坐标 + `setBounds(...width,height)` 会漂移——实测 880x740 → 副屏 1100x925 → 回主屏 704x592（视口跟着变，界面越拖越大、标题栏按钮跑到左边）。`--probe` 会把窗口在三块屏之间搬一遍，写 `probe.json` / `probe-other-screen.json` / `probe-back.json`，用 `tools\show_probe.ps1` 对比 `inner`/`navLeft` 是否稳定。
- **别再用 `-webkit-app-region` 做这块窗口的拖动**（style.css 里已全部删除）。实测矩阵（`WM_NCHITTEST` 逐点探测，标题栏按钮那一列）：无 drag 时全部 CLICK；只给 `aside` 加 drag 时按钮仍 CLICK；**只给 `main` 加 drag 时按钮立刻变 HTCAPTION 点不动**；`footer` 的 drag 则完全不生效；`body` 加 drag 同样毁掉标题栏按钮。所以 CSS 方案在无边框透明窗口上不可靠。
- 自检里的拖动必须干跑：`startDrag` 的轮询里有 `if (testing) return;`，否则冒烟测试会跟着测试机的真实鼠标搬动用户窗口（踩过一次，窗口被搬走后用户直接关掉了它）。
- 十字键是**「+」形**（用户已验收）：`controller.svg` 里 = 描边底板十字（比按键外扩 2px，`fill#111418 stroke#63615e`）+ 中心方块 + 四个方向键（`data-button` 12上 / 13下 / 14左 / 15右），每臂 44×44、末端圆角 9。`.dpad .surface{stroke:none}` 让四臂与中心静止时拼成一个完整十字（描边只由底板出）；按下变红靠 `.dpad .pressed .surface`。**别把这条写成 `.dpad .surface`：特异性 0,2,0 与 `.pressed .surface` 相同、位置又靠后，会把高亮整个盖掉——这就是原来十字键按住不变红的原因。** 方向箭头是 `#b3a791` 折线（`stroke-width=2`），按下转 `#fff3d4`。
- 面板内容区是**滚动容器**（用户要求"现有功能放进一个滚动框"）：子窗口类 `WXXToolsetScroll`（`WS_CHILD|WS_VSCROLL|WS_CLIPCHILDREN`，占 `(0,80,774,490)`）由 `ScrollProc` 管；四张卡片在容器里画（坐标 = 原绝对 y **减 `kScrollTop`(80)** 再减滚动量，**漏减这 80 会整体下移、卡片和控件错位**），控件全部挂在容器上（坐标同样减 80），滚动用 `ScrollWindowEx(...SW_SCROLLCHILDREN)`。控件查找一律走 `Ctl(id)`（容器优先），不要再写 `GetDlgItem(gMain/w,…)`。内容高度按最下面那个控件算（**下拉框 150 的窗口高度含弹出列表，要跳过**），超过 `nPage` 才出现滚动条——当前内容刚好放得下，所以平时看不到滚动条，加功能后自动出现。
- 四张卡片的绝对 y（画卡片和建控件都用这一套）：六槽武器 `88..216`、控制器覆层 `226..310`、存档切换 `320..440`、F10 存档 `450..534`；卡片标题 y 分别是 96 / 234 / 328 / 458。存档卡片**没有任何开关**（只有状态行 + 档案下拉框 + 「切换存档」+「存档目录」），F10 卡片右上是开关（`(600,458,126,36)`）+ 左边「查看日志」`(462,458,126,36)`，状态行在 `(48,500)`。

## 测试与诊断
- 面板控件 ID：101 六槽武器开关、103 6槽武器设置、104 档案下拉框、105 切换存档、109 查看日志、120 覆层「打开」按钮、123 最小化、124 关闭、125 启动忍龙4、127 F10 存档开关、209 存档目录；静态文本 110/111/130/128。下拉框只在 `CBN_DROPDOWN` 时刷新档案列表。点击开关验 ini：`127` → `[Save]TestKey` 121↔0，`101` → `[Toolset]WeaponSwitch` 1↔0（游戏没运行时点六槽武器开关只写 ini + 写日志，不弹框）。
- 跨进程操作控件：`CB_GETCURSEL=0x0147`、`CB_SETCURSEL=0x014E`、`BM_CLICK=0x00F5`；点击必须 `PostMessage`（`SendMessage` 会被模态 MessageBox 阻塞）。**控件现在挂在滚动容器里，必须先 `FindWindowEx(主窗口, 0, "WXXToolsetScroll", 0)` 拿到容器再 `GetDlgItem(容器, id)`**——直接 `GetDlgItem(主窗口, id)` 会拿到 NULL，点了没反应（踩过：以为注入失败）。声明 `SendMessageW` 字符串重载必须写 `EntryPoint="SendMessageW"`。配置窗口控件：101 武器5、102 武器6、103 保存、104 按键5、105 按键6。
- ini 读写用 `GetPrivateProfileIntW` 直接验；脚本改 ini 必须按段解析（`^Key5=` 在 `[Keys]` 和 `[Weapons]` 里都有，全局正则替换会把武器 ID 改坏）。
- 面板改到的 `dist/SixSlot.ini` 属于用户运行时状态：测试时改过（例如 `WeaponSwitch`、`TestKey`）记得还原成可用值（默认 `WeaponSwitch=0`、`TestKey=121`、`KickMode=5`、`Probe=0`）。
- **本机 pwsh 读写含中文的文本文件必须用 .NET 显式 UTF-8**：`[System.IO.File]::ReadAllText/WriteAllText($p, $s, (New-Object System.Text.UTF8Encoding($false)))`。`Get-Content`/`Set-Content` 按 GBK 解码 UTF-8，会把中文注释写成乱码、**还会吃掉换行**，实测把 `SixSlot.ini` 的 `[Save]` 段头和注释挤成一行 → `GetPrivateProfileIntW` 读回默认值（面板开关显示和 ini 相反）。写完用 `[System.IO.File]::ReadAllText(...,UTF8)` 复核一遍。
- **低完整性（Low IL）上下文会让面板既看不到、也注入不了游戏**（2026-10 实测根因）：从 DSH 的文件卡片 / agent 会话 / `cmd start` 打开 `WXXNinjaGuiden4ToolSet.exe`，进程是 **Low IL (0x1000)**（父进程被伪造成 explorer，令牌来自 DSH，所以别用"父进程是谁"判断来源）；此时 `CreateToolhelp32Snapshot` 和 `K32EnumProcesses` 只剩 ~29 个进程（`NINJAGAIDEN4-Steam.exe`、explorer、steam 全不可见，但窗口枚举照常），`OpenProcess(VM_WRITE/CREATE_THREAD)` 报 err=5 → 面板显示「等待游戏启动」、不注入、F10 自然没反应。判定 IL：`OpenProcess(QUERY_LIMITED)` + `OpenProcessToken` + `GetTokenInformation(TokenIntegrityLevel)`，中=0x2000、低=0x1000；`schtasks` 默认 `/rl LIMITED` 也是 Low，别用它验证注入。定位游戏还有一个 Low IL 下也可用的通道：`FindWindowW(L"MainWindowClass",L"NINJAGAIDEN4")` + `GetWindowThreadProcessId` → PID（实测拿到 22628）。
  **2026-10-02 纠正**：上述低权限现象的根因是工程目录可继承的 Low 完整性标签，不是 SmartScreen 或父进程名字。
  先运行 `dist\Repair-Permissions.cmd` 恢复文件 Medium 标签，之后正常双击即可。面板自检遇到 Low 时提示修复脚本，不能直接建议管理员运行。
  未签名信誉警告需单独处理；不要声称改文件权限等于有可信发布签名。

- **在这个环境里启动 GUI 子进程要用 `cmd /c start "" <exe>`**：`Start-Process -PassThru` 会让 pwsh 工具一直挂到子进程退出（截图脚本也因此卡住）。
- **运行中的 exe 会被锁成"能改名、不能写、不能删"**：`LNK1104` 或 `Open ReadWrite` 失败但 `Rename-Item` 成功 = 进程还在跑（沙箱里 `Get-Process` 可能看不见它）。做法：改名旧文件 → 拷入新构建 → 进程退出后再删 `.old`。
- 只改面板源码时用 `tools\build_panel.cmd`（单独编 launcher）；游戏运行时锁着 `SixSlot.dll`，`build.cmd` 会在 DLL 那步失败。**只编 DLL 用 `tools\build_dll.cmd`**（游戏占用时改 DLL 的常态做法，输出可直接落到 `dist`）。
- **python `subprocess` 抓管道在本沙箱会被拦**：命令静默不执行、旧 exe 原样留着，于是"一直在测旧构建"（踩过一次，查了半天消息路由）。编译/运行一律走 pwsh，python 只用来生成源码或解析文件。判据：产物时间戳没变就是没真编译。
- 重绘回归：`python tools\make_diag.py` + `tools\build_diag.cmd` 生成离屏插桩版（类名 `WXXToolsetDiag`，跑 8 秒自动退出），把 `timer_ticks/settext_actual/drawitem/paint` 写到 `%TEMP%\WXXToolset_diag.txt`。界面静止时 `settext_actual` 必须是个位数，否则面板在闪。插桩版窗口创建在屏幕外，不干扰用户。
- 覆层命中测试：`WXXControllerOverlay.exe --probe`（开发时 `electron.exe . --probe`）把关键控件的屏幕坐标写到 `probe.json`（打包版在 `%TEMP%\NinjaOverlaySmoke\`，dev 在 `overlay\artifacts\`），随后 `powershell -ExecutionPolicy Bypass -File tools\hittest3.ps1 [-Dev]` 对窗口逐点发 `WM_NCHITTEST`，输出 `CLICK` / `DRAG`。**`sendInputEvent` 的合成点击会绕过系统命中测试，抓不到“按钮点不动”这类 bug——必须用这个探针。** JS 拖动方案下所有点都应 `CLICK`。
- 十字键回归（smoke 里三条，改 `controller.svg` / `style.css` 后必看）：`dpadHighlight`（上键按下色必须 `===` ABXY 的 `rgb(223, 52, 75)`，静止 `rgb(37, 39, 43)`）、`dpadVisual`（五个键都要被真实输入点亮）、截图 `artifacts/dpad.png` / `%TEMP%\NinjaOverlaySmoke\dpad.png`（只按「上」+A，未按的三向正好是静止态，用来核对「+」拼得完整）。
- **截图必须替换 `readPads` 造输入，不能 `classList.add('pressed')`**：手工加的类只能骗过同帧的 `getComputedStyle`，`capturePage` 期间渲染循环会把类改回去，截出来还是静止态。历史教训：照着 `.dpad .surface` 的写法做样式，按下永远不变红，只有截图能看出来。
- 已知抖动（未修，待确认）：smoke 里 `preview.png` 的 `capturePage()` 偶发 `Error: UnknownVizError` 让整轮退出码 1，重跑即过，与功能无关。

## 用户协作习惯
- 中文、描述短、常打错字；意图不清先问。常在玩游戏时提需求，动手前先确认能否打断（注入/替换 DLL 依赖游戏状态）。
- **默认自动打包部署**：改完源码 → 开发模式自检（`electron.exe . --smoke-test`）→ `electron-packager` 打包 + `robocopy` 到 `dist\ControllerOverlay` → 重启覆层（先 `Stop-Process WXXControllerOverlay`）→ 再用打包版跑一次 `--smoke-test` 确认。用户要的是"能直接打开的最新版"，只改源码不打包他用不到（他明确说过：既然要打包才能用到最新版，那就自动打包）。只有他主动说「先别打包」时才停在源码 + 自检。
- 交付要落到能直接用的形态：编译好的 `dist`、截图或下拉框配置项，不要只说"代码改好了"；改完界面必须自己截图核对再回报。
- 顺手发现的问题先问后改；
- **GitHub 推送已获授权**：用户在本轮明确要求提交并发布到 `yzdsgwxx/WXXNinjaGuiden4ToolSet`，凭据存在 Windows 凭据管理器（`git credential fill` 可取 token）。除这个仓库外仍不要擅自推送。


## 2026-10-02 权限根因纠正（优先于上面的旧推断）

- 本次实查：工程根目录有 `(OI)(CI)Low` 标签，dist 两个 EXE 和开发 electron.exe 都继承了 Low。
  Windows 新进程完整性取用户令牌和 EXE 文件的较低者；不是 SmartScreen 把进程降权。
  所以从 explorer/cmd 启动也不能修复 EXE 标签。之前“管理员 Electron 必須 no-sandbox”的归因未被证实。
- 修复：`icacls dist /setintegritylevel "(OI)(CI)M"`，开发 electron.exe 单独设置 M。
  只改工具的完整性标签，保留 DACL，不修改系统安全设置。dist 带显式可继承 Medium 防止工程根 Low 继续污染。
- `dist/Repair-Permissions.cmd` 是可分发的修复入口，build.cmd 和 tools/build_panel.cmd 自动调用。
  发布白名单要包含这个脚本。覆盖输出后仍需检查 EXE 标签；不要复制旧 Low SACL 到 dist。
- 已删除面板给覆层附带的 `--no-sandbox`。恢复 Medium 后，原打包覆层普通权限完整 smoke 成功，
  还成功注入运行中的 PID 22628。未签名的信誉提示与 MIC 权限分开处理，不声称修复 MIC 就获得可信发布者。
