# dnd — PLATO(1975)《dnd》现代复刻（终端 TUI 版）

1975 年运行在 PLATO IV 系统上的地牢爬行游戏 **dnd**（Gary Whisenhunt & Ray Wood）的现代重制。
**不做 1:1 还原**：机制骨架忠实（L1）＋形式现代化（L2）＋内容再创作（L3），逐条可考据，见
`docs/research-dossier.md` 与 `docs/reimplementation-plan.md`。

- 前端：Python 标准库 **curses**（零第三方依赖，无 pip 也能跑）
- 后端：自研确定性内核（seeded PRNG、无 random/time 依赖），TUI / 机器人 / 回放测试共用同一份逻辑

> 📖 **第一次玩？看 [`docs/how-to-play.md`](docs/how-to-play.md)**（界面图解、键位总表、生存要点、常见问题）。

## 快速开始

```bash
cd /mnt/d/code_study/DND
python3 -m dnd                                   # 建角界面 → 开始游戏
python3 -m dnd --seed 42 --name Aria --class wizard --race elf   # 固定种子/职业/种族
# 建角界面：输入姓名 → ↑↓ 选职业 → Tab/←→ 切到种族栏 → ↑↓ 选种族 → 回车开始
python3 -m dnd --latest                          # 读最近存档
python3 -m dnd --list-saves                      # 列出存档
python3 -m dnd --roster                          # 打印名人堂
python3 -m dnd --headless-demo 300 --seed 5      # 无终端环境自检（跑 300 回合）
python3 -m dnd --modern --debug                  # 现代模式（免死一次）+ 调试键
```

环境：Python ≥ 3.10（开发用 3.14）、支持 curses 的终端（Linux / macOS / WSL，Windows 原生终端不支持）。
终端建议 ≥ 100×30（宽度 ≥ 100 时右侧显示角色卡与可见敌人）。

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
- 种族：人类（起始生命/法力 +1）、精灵（视野 +1、敏捷 +2）、矮人（起始生命 +2、体质 +2）、侏儒（起始法力 +2、视野 +1、智力/敏捷 +1）
- 视野：递归阴影投射（基础半径 9，种族可 +1）＋记忆雾；怪物有仇恨半径 7，不会全层同时扑来
- 恢复：每 12 回合 +1 HP；药水/卷轴/武器/护甲按深度掉落

## 目录结构

```
dnd/                 游戏包（python3 -m dnd）
  rng.py             确定性 PRNG（xoshiro256**，可序列化）
  dice.py            掷骰表达式
  content.py         JSON 数据表加载（带 _meta 出处与可信度）
  data/*.json        职业 / 种族 / 怪物 / 物品 / 法术
  level.py           地图生成（房间+走廊、门、楼梯、分层放置、连通性校验）
  fov.py             视野（递归阴影投射）
  entities.py        玩家 / 怪物 / 物品
  game.py            内核状态机（回合、战斗、法术、物品、升级、胜负）
  save.py            存档与名人堂
  replay.py          确定性回放（seed + 命令序列 → 状态哈希）
  ui/theme.py        配色与字形（PLATO 琥珀色观感）
  ui/widgets.py      绘制辅助
  ui/tui.py          curses 主界面与浮层
  __main__.py        命令行入口
tools/sim.py         无头机器人跑批（平衡性回归）
tools/pty_smoke.py   真实伪终端（tmux）里的 TUI 冒烟测试
tests/test_core.py   内核单元测试（unittest）
docs/                研究档案、复刻计划
saves/               存档与 roster.json
```

## 验证

```bash
python3 -m unittest discover -s tests -v   # 内核单元测试：RNG/骰子/生成/视野/战斗/种族/存档/回放
python3 tools/pty_smoke.py                 # TUI 冒烟：启动、渲染、按键、浮层、建角、存档、退出
python3 -m dnd --headless-demo 300 --seed 5
python3 tools/sim.py --runs 60 --class warrior    # 机器人跑批统计
```

内置的确定性保证：同一 `--seed` ＋ 同一操作序列，跨进程得到完全一致的状态哈希（`Game.state_hash()`）。

## 数据与考据（重要）

原版 dnd 的职业、法术、怪物、数值**均已不可考**（见研究档案第四节"未确证清单"）。因此：

| 层 | 内容 | 说明 |
|---|---|---|
| L1 忠实 | 单屏字符地牢、俯视探索、逐层下潜、掷骰战斗、角色持久化、永久死亡、宝物驱动成长 | 有公开史料支撑的骨架 |
| L2 现代化 | 键位、帮助、视野与记忆雾、仇恨半径、生命自然恢复、存档/名册、上升式 AC | 现代可玩性所需 |
| L3 再创作 | 4 职业、4 种族、5 法术、12 种怪物、物品与数值、10 层难度曲线、遗物结局 | 数据文件里全部标了 `confidence` 与 `_meta`，可整体替换 |

游戏内按 `?` 可看到同样的分级说明；`P` 在侧栏显示出处标记。

## 已知问题 / 路线图

- **平衡**：贪心机器人（不撤退、不主动休息）各职业平均下潜深度 warrior 4.45 / cleric 3.12 / rogue 3.02 / wizard 2.12（各 40 局）；
  法师偏弱是已知项，属于 M5 调参工作（也可通过增强机器人策略验证）。
- 金币目前只作计分，尚无商店/祭坛等消耗途径。
- 尚未实现：多角色槽位与存档导入导出 UI、通关回程（带遗物返回地面）、洞穴型/主题化层、音效、i18n、分享串。
- 尚未核实：原版的职业/法术/层数/胜利条件（拿到资料后只需替换 `dnd/data/*.json`，无需改代码）。

## 合规

不使用 TSR/WotC 的商标与专有名词；怪物与物品采用公有领域通用奇幻词汇或自创名。
