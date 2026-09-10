# dnd — PLATO(1975)《dnd》现代复刻（终端 TUI 版）

1975 年运行在 PLATO IV 系统上的地牢爬行游戏 **dnd**（Gary Whisenhunt & Ray Wood）的现代重制。
**不做 1:1 还原**：机制骨架忠实（L1）＋形式现代化（L2）＋内容再创作（L3），逐条可考据，见
`docs/research-dossier.md` 与 `docs/reimplementation-plan.md`。

- 前端：Python 标准库 **curses**（零第三方依赖，无 pip 也能跑）
- 后端：自研确定性内核（seeded PRNG、无 random/time 依赖），TUI / 机器人 / 回放测试共用同一份逻辑
- 规模：游戏本体约 2900 行 Python，含测试与工具共约 4600 行；53 项单元测试 + 19 项伪终端冒烟全绿

> 📖 **第一次玩？看 [`docs/how-to-play.md`](docs/how-to-play.md)**（界面图解、键位总表、生存要点、常见问题）。
> 📐 **想改代码/看设计？** [`docs/reimplementation-plan.md`](docs/reimplementation-plan.md)（技术选型、目录、保真度矩阵、里程碑进度、决策留痕）；
> 🔍 **想核对出处？** [`docs/research-dossier.md`](docs/research-dossier.md)（PLATO《dnd》史料与 A/B/C 可信度分级）。

## 快速开始

```bash
./play.sh                                         # 唯一入口：Linux / macOS / WSL2 通用（自动查 Python、终端、编码）
./play.sh --check                                 # 只做环境自检并打印报告，不启动游戏（报 bug 时请附上它）
./play.sh --seed 42 --name Aria --class wizard --race elf   # 固定种子/职业/种族；参数原样转发给游戏
# 建角界面：输入姓名 → ↑↓ 选职业 → Tab/←→ 切到种族栏 → ↑↓ 选种族 → 回车开始
./play.sh --latest                                # 读最近存档
./play.sh --list-saves                            # 列出存档
./play.sh --roster                                # 打印名人堂
./play.sh --headless-demo 300 --seed 5            # 无终端环境自检（跑 300 回合）
./play.sh --modern --debug                        # 现代模式（免死一次）+ 调试键
./play.sh --ascii                                 # 框线/进度条退回纯 ASCII（中文终端把 ─│ 当两格宽时用）
```

不想用脚本也可以直接调包（效果完全一样，脚本只是帮你把环境问题提前拦住）：

```bash
python3 -m dnd --seed 42
```

### 平台支持

| 系统 | 怎么跑 | 说明 |
|---|---|---|
| **Linux** | `./play.sh` | 需要 `python3`（≥ 3.10）。发行版若未自带：`sudo apt install -y python3` |
| **macOS** | `./play.sh` | 系统自带 `python3` 可能只有 3.9；用 `brew install python` 装新的，或 `DND_PYTHON=/opt/homebrew/bin/python3 ./play.sh` |
| **Windows** | **必须用 WSL2** | WSL 终端里 `cd` 到仓库后 `./play.sh`。Windows 原生 cmd/PowerShell/Git Bash **不支持**（原生 Python 没有标准库 `curses`）。安装：管理员 PowerShell 执行 `wsl --install -d Ubuntu`，重启后进入 `wsl` |

`play.sh` 会依次检查：平台（原生 Windows 直接给出 WSL2 安装指引）→ Python 版本与 `curses` → 是否为真实终端 →
终端编码（不是 UTF-8 且系统有可用 UTF-8 locale 时自动补上，避免中文乱码）→ 窗口尺寸（< 62×18 提示调大、
< 100×30 提示不显示侧栏）→ 然后才 `exec python3 -m dnd`。任何一步不过都给出可操作的中英文提示，
**不会留下一个意义不明的 traceback**。自检失败时脚本以退出码 2 结束。

环境：Python ≥ 3.10（开发用 3.14）、支持 curses 的终端（Linux / macOS / WSL2，Windows 原生终端不支持）。
终端建议 ≥ 100×30（宽度 ≥ 100 时右侧显示**冒险者档案**：生命/法力/经验条、视野内敌人、装备、属性、背包）。

界面：反白标题栏（深度进度条 + 回合）、体征栏（生命/法力/经验条）、带边框的地图视口（火把式远近明暗 + 记忆雾）、
侧栏角色卡、越旧越暗的消息日志、按键高亮的提示栏。框线默认用 Unicode（`─│┌┐`），
终端编码不是 UTF-8 时自动退回 ASCII；东亚洲终端把框线当两格宽时用 `--ascii`（或 `DND_ASCII=1`）手动指定。

## 操作

| 键 | 作用 | 键 | 作用 |
|---|---|---|---|
| **W A S D** / 方向键 / hjkl / yubn | 移动（含斜向） | `.` 或 `5` | 原地等待一回合 |
| `>` / `<` | 下楼梯 / 上楼梯 | `g` 或 `,` | 拾取脚下物品 |
| `i` | 背包（按字母使用/装备/喝/读） | `c` | 施法（按字母选择） |
| `F5` 或 `Shift+S` | 存档 | `R` | 名人堂名册 |
| `?` | 帮助（含考据说明） | `P` | 切换侧栏出处标记 |
| `Q` | 退出（需确认） | `x` / `t` | 调试：全图 / 传送（仅 `--debug`） |

## 玩法

建角（**4 职业 × 4 种族**，↑↓ 选择）→ 潜入 10 层地牢 → 探索、战斗、拾宝、升级 → 第 10 层夺取「深渊遗物」即胜利。
死亡即永久消失（角色进名人堂，存档被删除）；`--modern` 模式可免死一次。

- 战斗：d20 + 命中加值 vs 上升式 AC，20 暴击（双倍伤害），1 必失手
- 法术：法师 魔法飞弹/护盾/闪电束；牧师 治疗轻伤/祝福（消耗 MP）
- 种族：人类（起始生命/法力各 +1）、精灵（视野 +1、法力 +1，敏捷 +2、体质 -1）、矮人（起始生命 +2，体质 +2、敏捷 -1）、侏儒（起始法力 +2、视野 +1，智力/敏捷 +1、力量 -1）
- 视野：递归阴影投射（基础半径 9，种族可 +1）＋记忆雾；怪物有仇恨半径 7，不会全层同时扑来
- 恢复：每 12 回合 +1 HP；药水/卷轴/武器/护甲按深度掉落

## 目录结构

```
play.sh              跨平台启动脚本（Linux / macOS / WSL2 通用；环境自检 + 启动，含 --check）
dnd/                 游戏包（python3 -m dnd）
  rng.py             确定性 PRNG（xoshiro256**，可序列化）
  dice.py            掷骰表达式
  content.py         JSON 数据表加载（带 _meta 出处与可信度）
  data/*.json        职业 / 种族 / 怪物 / 物品 / 法术（CC0-1.0，见 dnd/data/LICENSE-CC0.txt）
  level.py           地图生成（房间+走廊、门、楼梯、分层放置、连通性校验）
  fov.py             视野（递归阴影投射）
  entities.py        玩家 / 怪物 / 物品
  game.py            内核状态机（回合、战斗、法术、物品、升级、胜负）
  save.py            存档与名人堂
  replay.py          确定性回放（seed + 命令序列 → 状态哈希）
  ui/theme.py        配色与字形（PLATO 琥珀色观感；真彩/256/8 色三级降级 + Unicode/ASCII 字形集 + 光照层次）
  ui/widgets.py      绘制辅助（框线/分隔线/进度条/按键提示，按显示宽度裁剪中文）
  ui/describe.py     物品/法术说明（内部 effect id -> 玩家看得懂的一句话）
  ui/tui.py          curses 主界面与浮层
  __main__.py        命令行入口
tools/sim.py         无头机器人跑批（平衡性回归）
tools/pty_smoke.py   真实伪终端（tmux）里的 TUI 冒烟测试
tools/preview.py     把界面渲染成 PNG 供人工审阅（需要 Pillow，仅开发用）
tests/test_core.py   内核单元测试（27 项，unittest）
tests/test_tui.py    TUI 布局测试（22 项，假 curses 屏幕；含框线/裁剪/说明文案回归）
tests/test_cli.py    CLI/读档路径测试（4 项，伪终端启动 TUI）
docs/                研究档案（史料）、复刻计划（设计与进度）、上手指南
saves/               存档与 roster.json（存档不入库）
out/                 机器人跑批与界面预览输出（gitignore）
```

## 文档索引

| 文档 | 面向 | 内容 |
|---|---|---|
| [`README.md`](README.md) | 所有人 | 快速开始、操作、玩法、目录、验证命令 |
| [`docs/how-to-play.md`](docs/how-to-play.md) | 玩家 | 界面图解、键位总表、建角流程、生存要点、FAQ |
| [`docs/reimplementation-plan.md`](docs/reimplementation-plan.md) | 开发者 | 技术选型与理由、目录与模块依赖、保真度策略与矩阵、M0–M7 进度、测试与质量、决策留痕（含废弃的 Web 方案对照） |
| [`docs/research-dossier.md`](docs/research-dossier.md) | 考据 | PLATO《dnd》史料底稿、A/B/C 可信度分级、C 类未确证清单、核实路线与链接 |
| [`docs/open-source-compliance.md`](docs/open-source-compliance.md) | 开源/法务 | 开源合规检查（商标、素材、依赖、隐私逐项证据）、双协议建议与否决理由、与 PLATO 原版的法律关系、发布前清单 |
| [`dnd_PLATO_1975_检索报告.md`](dnd_PLATO_1975_检索报告.md) | 考据 | 首轮联网检索报告（结论速览、基本档案、PLATO 地牢游戏谱系、检索局限） |

## 验证

```bash
./play.sh --check                          # 最快的一道体检：平台/Python/curses/终端编码/尺寸，一次全打印
python3 -m unittest discover -s tests -v   # 53 项：内核 27 / TUI 布局 22 / CLI 读档 4（含伪终端启动真实 TUI）
python3 tools/pty_smoke.py                 # 19 项 TUI 冒烟：启动、渲染、按键、浮层、建角、F5 存档、读档续玩、退出
python3 -m dnd --headless-demo 300 --seed 5
python3 tools/sim.py --runs 60 --class warrior    # 机器人跑批统计（--json out/sim.json 可落盘）
python3 tools/preview.py                   # 把界面渲染成 PNG（改界面时用来"看一眼"，需要 Pillow）
```

`tests/` 分工：`test_core.py`（内核：RNG/骰子/生成/视野/战斗/种族/存档/回放/回归）、
`test_tui.py`（假 curses 屏幕渲染：日志区/侧栏/浮层是否越界、中文按显示宽度裁剪、Unicode/ASCII 字形切换、说明文案）、
`test_cli.py`（命令行参数与 `--load` 启动路径）。

改界面的工作流：`test_tui.py` 断言**布局关系**（谁压谁、有没有越界），`tools/preview.py` 给出**观感**
（渲染成 PNG，12 个场景：主界面/背包/法术/帮助/名人堂/结算/建角/最小尺寸/窄窗口/过小窗口/ASCII 兜底/放大）。

内置的确定性保证：同一 `--seed` ＋ 同一操作序列，跨进程得到完全一致的状态哈希（`Game.state_hash()`）；
本局执行过的命令（含 `--debug` 的 `x`/`t`）都会完整记进 `Game.commands`，因此 `replay.run(seed, game.commands)` 能原样复现。

## 数据与考据（重要）

原版 dnd 的职业、法术、怪物、数值**均已不可考**（见研究档案第四节"未确证清单"）。因此：

| 层 | 内容 | 说明 |
|---|---|---|
| L1 忠实 | 单屏字符地牢、俯视探索、逐层下潜、掷骰战斗、角色持久化、永久死亡、宝物驱动成长 | 有公开史料支撑的骨架 |
| L2 现代化 | 键位、帮助、视野与记忆雾、仇恨半径、生命自然恢复、存档/名册、上升式 AC | 现代可玩性所需 |
| L3 再创作 | 4 职业、4 种族、5 法术、12 种怪物、18 种物品与数值、10 层难度曲线、遗物结局 | 数据文件里全部标了 `confidence` 与 `_meta`，可整体替换 |

游戏内按 `?` 可看到同样的分级说明；`P` 在侧栏显示出处标记。

## 已知问题 / 路线图

- **平衡**：贪心机器人（不撤退、不主动休息）平均下潜深度 warrior 4.50 / cleric 3.12 / rogue 3.02 / wizard 2.12（各 40 局；
  战士 40 局里 39 局阵亡、最高到第 6 层，主要死因是狗头人与骷髅）。法师偏弱是已知项，属于 M5 调参工作（也可通过增强机器人策略验证）。
- **终局**：深渊守卫（AC 19 / 10d8+20 / +11 3d8+3）正面硬拼胜率 <8%（顶装 10 级角色也不行），
  设计意图是"引开它、再冲刺抢遗物"——隔离模拟里冲刺抢宝成功率约 18%~50%（随等级/药水/装备提升）。
  守卫必定生成，且遗物就放在它身边（不会压在它脚下，否则必须杀掉打不过的 boss 才能通关）。
- 金币目前只作计分，尚无商店/祭坛等消耗途径。
- 尚未实现：多角色槽位与存档导入导出 UI、通关回程（带遗物返回地面）、洞穴型/主题化层、音效、i18n、分享串。
- 尚未核实：原版的职业/法术/层数/胜利条件（拿到资料后只需替换 `dnd/data/*.json`，无需改代码）。
- 开发注意：`ui/theme.py` 在模块级 import curses，新增 UI 引用请照 `__main__.py` 的写法**延迟导入**，
  否则 `--headless-demo` / `--list-saves` 在无 curses 的环境（Windows 原生 Python）会直接崩。

## 许可与合规

**双协议**（代码与数据分开，各自用最合适的协议）：

| 范围 | 协议 | 文件 |
|---|---|---|
| 代码：`dnd/**/*.py`、`tests/`、`tools/`、`play.sh`、`pyproject.toml` | **MIT** | [`LICENSE`](LICENSE) |
| 内容数据：`dnd/data/*.json`（职业/种族/怪物/物品/法术表） | **CC0-1.0**（公共领域） | [`dnd/data/LICENSE-CC0.txt`](dnd/data/LICENSE-CC0.txt) |
| 文档：`README.md`、`docs/**`、检索报告 | MIT | 同 `LICENSE` |

数据表单独用 CC0 是**故意**的：它们是本项目最希望被别人替换、再创作、贴到自己项目里的部分，
CC0 取消了署名与传染义务，你可以直接改数值、加怪物、做成自己的版本，无需声明来源（当然欢迎注明）。
代码用 MIT 则是最省事的宽松协议：可 fork、可商用、可闭源再发行，只需保留版权声明。

**与原版的关系**：本项目是 1975 年 PLATO 系统上《dnd》(Gary Whisenhunt & Ray Wood) 的**非官方**现代复刻。
未使用原版 TUTOR 源码、原版数值或任何原版素材——只复刻了不受著作权保护的玩法骨架，内容表全部为本项目再创作
（每张表的 `_meta` 都标了 `confidence: invented`）。本项目与原作者、PLATO/cyber1 社区及
Wizards of the Coast **均无关联，未获其授权或背书**。

**商标**：仓库内不使用 TSR/WotC 的商标与专有名词（不出现 D&D 品牌标识）；怪物与物品采用公有领域通用奇幻词汇或自创名
（4 职业 / 4 种族 / 12 怪物 / 18 物品 / 5 法术共 43 条内容已逐条核对）。
标题 `dnd` 属于对原作的指称性使用，不声称任何商标权。

**依赖**：游戏本体零第三方依赖（仅 Python 标准库）；`Pillow` 只被开发工具 `tools/preview.py` 使用，已标为可选依赖
（`pip install ".[preview]"`）。无网络行为、不回传统计、存档仅本地 JSON。

完整的逐项检查证据（商标扫描命令、依赖审计、凭据与隐私扫描、与 PLATO 原版的法律关系分析、
协议选型与否决理由、发布前清单）见 **[`docs/open-source-compliance.md`](docs/open-source-compliance.md)**。
