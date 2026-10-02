# 忍龙 4 六武器槽 Mod：初步可行性分析

检查日期：2026-10-01。目标：装备界面配置六把武器、战斗 HUD 显示六槽、额外两个可绑定的直接切换按键。

## 结论与证据边界

值得进行功能原型验证，但目前没有验证六槽可运行。六把武器的快捷选择、自定义六槽显示、原生装备菜单扩容是不同难度的工作，不能用单一还原百分比概括。最关键的未知是能否在战斗中安全切换到当前四槽之外、角色已经解锁的武器。

本次只读取文件与查询公开资料，没有写入游戏目录、修改存档或注入正在运行的游戏。工作目录在检查时为空。

## 本地确认

- 游戏目录：D:\APP\steam.exe\steamapps\common\NINJAGAIDEN4。
- 存在正在运行的 NINJAGAIDEN4-Steam 进程。
- Assets 使用 @image*.csv / @image*.dat 和 @patch_image*.csv / .dat；CSV 中含资源 GUID 路径、数值字段、内部文件名，尚未完整解析其格式。
- AssetDatabase.dat 内可读取资源路径。发现以下名称，不等于已经解析了表结构或找到了函数地址：
  - Assets/AssetTables/PlayerConfig/Player_Pl0000_Wep
  - Assets/AssetTables/PlayerConfig/Player_Pl0500_Wep
  - Assets/AssetTables/PlayerConfig/KeyBindDataTable
  - Assets/AssetTables/PlayerConfig/KeyBindAssetTable
  - Assets/UI/data/menu/menu_*
  - Assets/UI/data/hud/hud_*
  - Assets/UI/texture/wpn/wpn_menu
- 对磁盘 EXE 的 ASCII 字符串搜索未得到有用的 weapon/equip/keyconfig 线索。这不代表运行时没有对应逻辑。
- version.txt：Perforce changelist 762500；PlasticSCM changeset 143644。不是经过核实的公开版本号。
- NINJAGAIDEN4-Steam.exe SHA-256：3e3ecfe254c33aac2d906126f3b7a0ee9ac92e01ec414f6b7f77ec2f79e8c83a。

## 分项判断（工程评估，非实测结果）

| 需求 | 判断 | 关键工作 |
| --- | --- | --- |
| 两个新增可绑定按键 | 相对容易，可先用 Mod 配置界面/文件 | 输入焦点、按下沿、冲突处理、菜单屏蔽；还需有效的换武器入口 |
| 六把武器直接切换 | 核心可行性待验证 | 装备 ID、角色许可、资源加载、原生切换状态机 |
| HUD 六槽与当前武器高亮 | 自绘实现较有把握，原生扩容未知 | 真实状态同步、图标、分辨率、菜单/过场隐藏、选中动画 |
| 在装备界面配置六槽 | 原生版本难度高 | UI 节点、焦点导航、装备操作、数量限制及数据写回 |
| 原生设置菜单新增两个绑定项 | 难度高于独立 Mod 设置 | 绑定表格式、动作枚举、设置保存及提示图标 |
| 重启/死亡/换章后保留 | 必须专门验证 | Mod 配置与当前存档/角色隔离、重新加载、同步 |

## 实现顺序

1. 解析武器和按键表，跟踪一次原生装备变更与战斗切换，确定装备栏、当前武器和换武器请求的关系。
2. 最小原型：以一个测试按键请求切换到四槽外的合法已解锁武器。验证模型、招式、特效和切回原武器，覆盖落地、空中与攻击状态。
3. 验证通过后，建立六槽映射和额外绑定；优先复用原生状态检查，避免仅写当前武器 ID 导致半切换。
4. 添加六槽 HUD 和配置页。若原生菜单暂时不能扩容，可在装备菜单打开期间呈现 Mod 配置面板；这属于部分还原，必须明确标识。
5. 研究原生菜单/HUD 扩容，逐步替换自绘界面。不要直接对未知四元素数组写入第五、第六项。

备选方案是 Mod 保存六把武器，在原有四槽中动态换入额外武器，再请求原生切换；只有确认战斗中换入不会触发菜单限制、资源缺失、存档污染或状态不同步时才能采用。这个方案提供六个逻辑快捷槽，并不证明引擎原生拥有六槽。

本分析默认使用当前角色原本支持且已解锁的武器。跨角色使用另一角色武器、增加新武器招式属于额外范围。

## 公开资料

- 官方更新公告确认 Weapon Sets 已支持在装备菜单自定义武器/忍术轮盘，值得优先追踪现有逻辑：https://steamcommunity.com/app/2627260/allnews/
- Ryu 工具作者说明支持忍龙 4 资源提取，包括原始文件；不能据此推断支持 UI 编辑、重打包或运行时扩槽：https://dtzxporter.com/tools/ryu
- NG4 Blue 作者发布页提供游戏行为修改的先例，但不是六槽功能证据：https://www.nexusmods.com/ninjagaidenfour/mods/20
- Bao Shuang 作者页面描述战斗逻辑修改与 DLL 安装方式，也不能证明武器槽扩展可用：https://www.nexusmods.com/ninjagaidenfour/mods/50

下一项决定性成果应是“四槽之外的武器能通过额外按键稳定切换”的实机验证，而非先绘制六个装饰槽。
