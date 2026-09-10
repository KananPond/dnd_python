# 开源合规与协议建议

> 本文档回答两个问题：**（一）这个仓库现在能不能公开？** **（二）按什么协议公开？**
> 结论与逐项证据都在下面。文中不构成法律意见；涉及商标、署名争议等实体判断时，请咨询律师。

---

## 一、结论速览

| 项 | 状态 | 说明 |
|---|---|---|
| 代码著作权 | ✅ 干净 | 全部自研，无第三方源码/片段、无 vendored 代码、无生成器产出的许可负担 |
| 运行期依赖 | ✅ 零 | 游戏本体只用 Python 标准库（`curses` 属标准库但不是所有平台都有）；`Pillow` 仅 `tools/preview.py` 需要，已标为可选依赖 |
| 内容素材 | ✅ 干净 | 无图片/音频/字体/地图资源；怪物/物品/法术均为公有领域通用词或自创名 |
| 与 PLATO《dnd》的关系 | ✅ 无代码派生 | 无原版 TUTOR 源码、无原版数据、无原版素材；只有玩法骨架与史实复述（见第三节） |
| 商标风险 | 🟡 低但存在 | 项目名 `dnd` 与 WotC 商标同形；可接受但需按第四节做三点防护 |
| 协议 | ⚠️ **缺失（发布前必须补）** | 本次补齐：`LICENSE`(MIT) + `dnd/data/LICENSE-CC0.txt`(CC0-1.0) 双协议 |
| 隐私/凭据 | ✅ 干净 | 无密钥、无 token、无个人数据；存档文件不入库且只含游戏状态 |
| 仓库卫生 | 🟡 待清 | 文档里有本机绝对路径、git 提交作者是 `eudora@localhost`、分支未保护、无 CI —— 见第六节清单 |

**一句话**：代码与素材本身可以放心开源；真正需要动手的是**补协议**和**发布前清理**这两件事。

---

## 二、协议方案（本次已落地）

采用**双协议**，与本项目的实际形态匹配（代码 + 数据是两类可独立复用的东西）：

| 范围 | 协议 | 文件 | 为什么 |
|---|---|---|---|
| 代码（`dnd/**.py`、`tests/`、`tools/`、`play.sh`、`pyproject.toml`） | **MIT** | `LICENSE` | 最宽松、最短、最被广泛理解；任何人可以 fork、改名、商用、闭源再发行，只需保留版权声明。对一个"供人玩、也供人改"的小型游戏最省事 |
| 内容数据（`dnd/data/*.json`） | **CC0-1.0**（公共领域奉献） | `dnd/data/LICENSE-CC0.txt` | 数据表是本项目最希望被替换/再创作的部分。CC0 取消一切署名与传染义务，别人可以直接把自己的怪物表贴进任何项目，不必声明来源。这与代码里 `_meta.confidence: invented`（"可整体替换"）的设计意图一致 |
| 文档（`README.md`、`docs/**`、检索报告） | 随代码走 MIT | 同 `LICENSE` | 文档含史实考据与出处链接，用最宽松的协议便于被引用 |

被否掉的备选，以及否掉的理由：

- **Apache-2.0**：同样宽松，多了显式专利授权与商标条款，适合企业/专利敏感场景。本项目无专利诉求、无企业参与，收益接近零而带来一份 200 行的 `NOTICE` 负担。
- **GPL-3.0**：只有当你希望"任何修改都必须回馈社区"时才值得用。游戏复刻的常见命运是被 fork 成各种私人口味版本，copyleft 会挡住一部分善意复用，与"内容表可自由替换"的设计目标冲突。
- **CC0 全仓**：放弃一切权利最彻底，但它**不含专利授权**，且不适合作为 Python 包的 SPDX 元数据（`pyproject.toml` 里 `license` 字段写 CC0 会让下游打包器困惑）。所以只用于数据目录。
- **WTFPL / Unlicense**：法律文本质量与司法承认度不如 CC0/MIT，没必要为省几行字牺牲确定性。

**发布时必须一起做的事**（否则双协议等于没写）：

1. `pyproject.toml` 里 `license = "MIT"` + `license-files = ["LICENSE"]`（已配）。
2. `README.md` 的「许可」一节写清双协议与文件分布（已写）。
3. 每个 `dnd/data/*.json` 的 `_meta` 里补一行 `"license": "CC0-1.0"`（**待办**，见第七节）。

---

## 三、与 PLATO《dnd》(1975) 的法律关系

这是本项目最需要说清楚、也最容易被人误判的一点。

| 问题 | 判断 |
|---|---|
| 用了原版的代码吗？ | **没有**。原版是 PLATO TUTOR 语言写的 lesson 文件，本仓库无一行来自它，也从未获取过其源码（`docs/research-dossier.md` 第六节记录了检索局限）。因此**不存在代码层面的演绎作品**。 |
| 用了原版的数值/怪物/法术表吗？ | **没有**。五张数据表全部标记 `confidence: invented`，`docs/research-dossier.md` 第四节把"原版数值"明确列为 C 类未确证项。 |
| 复刻玩法本身侵权吗？ | **不**。著作权保护表达，不保护玩法、规则、机制。俯视地牢、逐层下潜、掷骰战斗、永久死亡属于不受保护的思想/规则层。 |
| 用了原版的名称吗？ | 标题用了 `dnd`（作品名，见第四节）；正文与游戏内不出现原作者姓名以外的品牌标识，也没有把原作者的名义安到本项目上。**未声称是官方版本或原作者授权版本** —— 这一点已在 README 首屏写明"现代复刻、不做 1:1 还原"。 |
| 原作者有权主张吗？ | 1975 年的作品若仍在版权期内，其权利人可主张的是**原版代码与素材**本身，而不是玩法。本项目未复制前者。为稳妥，README 与本文档都明确标注来源与年代，不做"官方续作"暗示。 |

> 结论：**无需向原版权利人取得许可**即可开源本项目；但应保持"致敬 + 明确非官方"的表述，不要使用原作素材。

---

## 四、商标风险与三点防护

`dnd` 与 *Dungeons & Dragons* 的通用缩写 D&D / "DnD" 在游戏软件类别上高度关联，WotC 在多个司法辖区持有该商标。本项目的使用方式属于**描述性/致敬性使用**（用它指代"1975 年那款同名 PLATO 游戏"），风险低，但要做三点防护：

1. **不出现完整商标**：仓库内不得出现 `Dungeons & Dragons`、`D&D`、`TSR`、`WotC`、`Wizards of the Coast` 作为产品标识或卖点。目前正文只在**必要的出处说明**里以注释/文档形式提到"避免 TSR/WotC 专有名词"这类叙述性语句（`dnd/data/monsters.json` 的 `_meta`、`README.md` 与 `docs/reimplementation-plan.md` 的合规段）。这属于叙述性使用，保留；但**不要**把 `D&D` 放进项目简介、包名、PyPI 描述或 GitHub topics。
2. **不用专有名词做内容**：已核对全部 43 个内容条目（4 职业 / 4 种族 / 12 怪物 / 18 物品 / 5 法术），未出现任何 WotC 专有怪物、法术或设定名。复核命令见第五节。后续新增内容时请沿用同一标准（通用奇幻词或自创名）。
3. **非官方声明**：README 首屏已写明是"1975 年 PLATO 游戏的现代复刻"，建议再加一句显式声明（**待办**）：*"本项目与原作者、PLATO/cyber1 社区及 Wizards of the Coast 均无关联，未获其授权或背书。"*

补充：如果将来担心 PyPI/GitHub 上的名称冲突，最省事的做法是**保留仓库名 `dnd`，但把包名/发布名换成非冲突标识**（例如 `plato-dnd-remake`）。目前 `pyproject.toml` 的 `name = "dnd"` 与仓库名一致，便于本地 `pipx install .`；若日后要上 PyPI，再改这一行即可。

---

## 五、本次合规检查的做法与证据

**1) 商标/专有名词扫描**（全仓，排除 `.git` 与 `__pycache__`）：

```bash
grep -rniE "dungeons|dragons|d&d|tsr|wotc|wizards of the coast|beholder|mind flayer|illithid|tiamat|bahamut|vecna|greyhawk|faerun|forgotten realms|d20 system" \
  --include='*.py' --include='*.json' --include='*.md' .
```

命中仅 5 处，全部是"声明不使用"的叙述性语句或史实说明（`README.md`、`docs/reimplementation-plan.md`、`docs/research-dossier.md`、`dnd_PLATO_1975_检索报告.md`、`dnd/data/monsters.json` 的 `_meta`），无一处用作产品标识。

**2) 内容条目逐条目视核对**：43 条全部为公有领域通用奇幻词汇（`哥布林`/`骷髅`/`巨魔`/`吸血鬼`…）或自创名（`深渊守卫`/`深渊遗物`）。法术名（`魔法飞弹`/`护盾`/`闪电束`/`治疗轻伤`/`祝福`）为通用描述性名称。

**3) 依赖审计**：`grep` 全部 import 语句 → 仅标准库（`argparse`/`json`/`os`/`sys`/`pathlib`/`time`/`random` 被刻意回避、`curses`/`unicodedata`/`shutil`/`locale` 等）＋ `tools/preview.py` 的 `PIL`（可选）。

**4) 凭据与隐私扫描**：

```bash
grep -rniE "api[_-]?key|secret|token|password|BEGIN .*PRIVATE KEY|ghp_|sk-[A-Za-z0-9]" --include='*.py' --include='*.md' --include='*.json' .
```

命中仅出现在 `.mimosa/`（本机审查工具的会话记录目录，已在 `.gitignore` 中，不入库）中的字段名 `tokens`。`saves/*.json` 已 ignore，且内容只有游戏状态（角色名/职业/深度/种子），无个人信息。

**5) 资源文件**：仓库内无图片/音频/字体文件。`out/preview/*.png` 是本地渲染产物，已 ignore，且画面文字全部由代码生成。

---

## 六、发布前清单（按优先级）

**必须（否则等同于没开源）**

- [x] `LICENSE`（MIT）放仓库根 —— 没有协议的开源项目默认"保留一切权利"，别人**不能合法使用**
- [x] 数据目录的 CC0 声明（`dnd/data/LICENSE-CC0.txt` + 五张表的 `_meta.license`）
- [x] `pyproject.toml`（包元数据 + 协议 + 可选依赖 + 入口点 + Python 版本底线）
- [x] 跨平台启动脚本 `play.sh`（Linux / macOS / WSL2 统一入口）
- [x] `README.md` 许可、平台支持与启动章节
- [x] README 补"非官方、无关联"声明
- [x] 清掉文档里的本机绝对路径（`docs/how-to-play.md`、`README.md` 均已改为 `<仓库目录>`/相对路径）
- [ ] git 提交作者改成公开可用身份（当前是 `eudora@localhost`，会被写进提交历史且难以事后清除）

**建议（决定项目"看起来是否可协作"）**

- [ ] `CONTRIBUTING.md`：怎么跑测试、代码风格、提交信息语言、**贡献者许可**（MIT 入站=出站即可，无需 CLA；若坚持要 DCO，写明 `git commit -s`）
- [ ] GitHub Issues 模板（bug 报告请附 `./play.sh --check` 输出 —— 这是本次新增的自检命令，正好用于收集环境信息）
- [ ] CI（GitHub Actions 矩阵：ubuntu/macos × 3.10/3.14，跑 `python3 -m unittest discover -s tests` + `tools/pty_smoke.py`；Windows runner 只跑 `--headless-demo`，因为原生 Python 没有 curses）
- [ ] `SECURITY.md`（本游戏无网络、无凭据，安全面很小；一页写清"存档是本地 JSON 文件，读档会执行 JSON 解析但不会执行代码"即可）
- [ ] `CHANGELOG.md`（版本已在 `dnd/__init__.py` 定为 0.1.0，建议打 `v0.1.0` tag）
- [ ] README 加英文摘要段（面向国际读者降低门槛；游戏界面本身是中文）
- [ ] 仓库文件权限统一（`drvfs`/Windows 挂载盘下所有文件都显示 777，建议 `git update-index --chmod=+x play.sh` 固化可执行位，避免 clone 后 `./play.sh` 不可执行）

**可选（能力增强，不是合规要求）**

- [ ] 把存档目录从"仓库内 `saves/`"改为"用户数据目录"（`$XDG_DATA_HOME/dnd` 或 `~/.local/share/dnd`），或支持 `DND_SAVE_DIR` 环境变量覆盖 —— 这样 `pipx install dnd` 之后也能正常存档（当前存档写在仓库/安装目录旁）
- [ ] Windows 原生支持：需要额外依赖 `windows-curses`，与"零第三方依赖"目标冲突，本项目已明确**不支持**，Windows 用户走 WSL2（`play.sh` 会检测并给出安装指引）

---

## 七、逐项证据：为什么每条"干净"结论成立

| 结论 | 依据 |
|---|---|
| 无第三方源码 | 仓库 5 个提交全部由本项目一次性创建（`git log` 无 merge、无 vendor 目录）；46 个受版本控制的文件全部自研 |
| 无素材版权负担 | `git ls-files` 中无二进制资源（唯一 `*.png` 在 ignore 的 `out/`）；界面字符与配色由 `dnd/ui/theme.py` 代码生成 |
| 数据表可自由替换 | `dnd/content.py` 运行期读 `dnd/data/*.json`；`_meta.confidence` 全为 `invented`，无一处声称来自原版 |
| 存档不含隐私 | `dnd/save.py` 只序列化 `Game.to_json()`（种子/回合/角色属性/地图/RNG 状态）；`saves/*.json` 在 `.gitignore` |
| 无网络行为 | 全部 import 中无 `socket`/`urllib`/`http`/`requests`；游戏不联网、不检查更新、不回传统计 |

---

## 八、免责声明

本文档是**技术性合规检查记录与协议建议**，不是法律意见。若本项目要商业化、进入应用商店、或收到任何权利主张，请咨询执业律师。文档中的事实性判断（"未使用某商标""未复制源码"）基于 2026-09-10 这一版本仓库的实际内容，后续新增内容需重新核对。
