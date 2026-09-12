# 开源合规与协议说明

> 本文档回答两个问题：**（一）这个仓库现在能不能公开？** **（二）按什么协议公开？**
> 结论与逐项证据都在下面。文中不构成法律意见；涉及商标、署名争议等实体判断时，请咨询律师。
>
> 本轮为**全文重写**：上一版里的若干"待办"项已经完成（数据表补 CC0 声明、README 补非官方声明、
> 清掉本机绝对路径），另一些事实已经过时（提交数量、依赖审计的环境前提、网络可达性）。
> 本文按**当前仓库实测状态**重写，并在第六节保留仍未完成的事项。

---

## 一、结论速览

| 项 | 状态 | 说明 |
|---|---|---|
| 代码著作权 | ✅ 干净 | 全部自研，无第三方源码/片段、无 vendored 代码、无生成器产出的许可负担 |
| 运行期依赖 | ✅ 零 | 游戏本体只用 Python 标准库（`curses` 属标准库，但不是所有平台都有）；`Pillow` 仅 `tools/preview.py` 需要，已标为可选依赖 |
| 内容素材 | ✅ 干净 | 无图片/音频/字体/地图资源；怪物/物品/法术均为公有领域通用词或自创名。**背景故事同样是自创世界**：游戏内序章（`dnd/data/lore.json`）与完整设定（`docs/world-setting.md`）只借用"失落浮空帝国 / 维系魔法的源流 / 地下幽暗世界 / 疯法师地牢"这类公共母题，名词全部自造，并有自动扫描守住（第五节第 1 条与 `tests/test_core.py::TestLore`） |
| 与 PLATO《dnd》的关系 | ✅ 无代码派生 | 无原版 TUTOR 源码、无原版数据、无原版素材；只有玩法骨架与史实复述（见第三节） |
| 商标风险 | 🟡 低但存在 | 项目名 `dnd` 与 WotC 商标同形；可接受，但需保持第四节的防护做法 |
| 协议 | ✅ 已落地 | `LICENSE`（MIT）+ `dnd/data/LICENSE-CC0.txt`（CC0-1.0）双协议，六张数据表的 `_meta.license` 亦已标注（含背景故事表） |
| 作者身份/来源 | ✅ 已声明 | 本仓库由 AI 代理生成；模型、框架、插件与发布情况见 `README.md` 的「AI 参与声明」 |
| 人工审查 | ⚠️ **无** | 代码与文档是 AI（`deepseek-flash` in DSH，high 思考强度）自主"调研→计划→开发→审查"多轮的产出，**从未经过人类 code review**；采用方如需问责，请把本文与 README 的验证记录当作"AI 自查"，并自行安排人工审查 |
| 隐私/凭据 | ✅ 干净 | 无密钥、无 token、无个人数据；存档文件不入库且只含游戏状态 |
| 仓库卫生 | 🟡 部分待清 | 提交作者仍是本机身份 `eudora@localhost`；无分支保护、无 CI、无 CONTRIBUTING/SECURITY/CHANGELOG —— 见第六节清单 |

**一句话**：代码与素材本身可以放心开源；协议也已补齐，剩下的是"发布前清理"这一类工程卫生工作。

---

## 二、协议方案（已落地）

采用**双协议**，与本项目的实际形态匹配（代码 + 数据是两类可独立复用的东西）：

| 范围 | 协议 | 文件 | 为什么 |
|---|---|---|---|
| 代码（`dnd/**.py`、`tests/`、`tools/`、`play.sh`、`pyproject.toml`） | **MIT** | `LICENSE` | 最宽松、最短、最被广泛理解；任何人可以 fork、改名、商用、闭源再发行，只需保留版权声明。对一个"供人玩、也供人改"的小型游戏最省事 |
| 内容数据（`dnd/data/*.json`，含序章文本 `lore.json`） | **CC0-1.0**（公共领域奉献） | `dnd/data/LICENSE-CC0.txt` | 数据表是本项目最希望被替换/再创作的部分。CC0 取消一切署名与传染义务，别人可以直接把自己的怪物表、甚至整份世界观贴进任何项目。这与数据里 `_meta.confidence: invented`（"可整体替换"）的设计意图一致 |
| 文档（`README.md`、`docs/**`、根目录检索报告） | 随代码走 MIT | 同 `LICENSE` | 文档含史实考据与出处链接，用最宽松的协议便于被引用 |

被否掉的备选，以及否掉的理由：

- **Apache-2.0**：同样宽松，多了显式专利授权与商标条款，适合企业/专利敏感场景。本项目无专利诉求、无企业参与，
  收益接近零而带来一份 `NOTICE` 负担。
- **GPL-3.0**：只有当你希望"任何修改都必须回馈社区"时才值得用。游戏复刻的常见命运是被 fork 成各种私人口味版本，
  copyleft 会挡住一部分善意复用，与"内容表可自由替换"的设计目标冲突。
- **CC0 全仓**：放弃一切权利最彻底，但它**不含专利授权**，且不适合作为 Python 包的 SPDX 元数据
  （`pyproject.toml` 里 `license` 字段写 CC0 会让下游打包器困惑）。所以只用于数据目录。
- **WTFPL / Unlicense**：法律文本质量与司法承认度不如 CC0/MIT，没必要为省几行字牺牲确定性。

**"双协议不能等于没写"的配套动作（均已完成）**：

1. `pyproject.toml` 配了 `license = "MIT"` + `license-files = ["LICENSE"]`。
2. `README.md` 的「许可与合规」一节写清了双协议与文件分布。
3. 五个 `dnd/data/*.json` 的 `_meta` 都补了 `"license": "CC0-1.0"` 与 `license_note`；新增的
   序章文本 `dnd/data/lore.json` 同样带 `license` / `confidence: invented` / `license_note`（六张表一致）。
4. `LICENSE` 版权人写的是 `EudoraArcher (KananPond)`，同时覆盖 Gitee 与 GitHub 两个账号名。

---

## 三、与 PLATO《dnd》(1975) 的法律关系

这是本项目最需要说清楚、也最容易被人误判的一点。

| 问题 | 判断 |
|---|---|
| 用了原版的代码吗？ | **没有**。原版是 PLATO TUTOR 语言写的 lesson 文件，本仓库无一行来自它，也从未获取过其源码（`docs/research-dossier.md` 第六节记录了检索局限）。因此**不存在代码层面的演绎作品**。 |
| 用了原版的数值/怪物/法术表吗？ | **没有**。六张数据表全部标记 `confidence: invented`，`docs/research-dossier.md` 第四节把"原版数值"明确列为 C 类未确证项。 |
| 复刻玩法本身侵权吗？ | **不**。著作权保护表达，不保护玩法、规则、机制。俯视地牢、逐层下潜、掷骰战斗、永久死亡属于不受保护的思想/规则层。 |
| 用了原版的名称吗？ | 标题用了 `dnd`（作品名，见第四节）；正文与游戏内不出现原作者姓名以外的品牌标识，也没有把原作者的名义安到本项目上。**未声称是官方版本或原作者授权版本** —— README 首屏写明"非官方现代复刻、不做 1:1 还原"。 |
| 原作者有权主张吗？ | 1975 年的作品若仍在版权期内，其权利人可主张的是**原版代码与素材**本身，而不是玩法。本项目未复制前者。为稳妥，README 与本文档都明确标注来源与年代，不做"官方续作"暗示。 |

> 结论：**无需向原版权利人取得许可**即可开源本项目；但应保持"致敬 + 明确非官方"的表述，不使用原作素材。

---

## 四、商标风险与防护做法

`dnd` 与 *Dungeons & Dragons* 的通用缩写 D&D / "DnD" 在游戏软件类别上高度关联，WotC 在多个司法辖区持有该商标。
本项目的使用方式属于**描述性/致敬性使用**（用它指代"1975 年那款同名 PLATO 游戏"），风险低，做法如下：

1. **不出现完整商标**：仓库内不得出现 `Dungeons & Dragons`、`D&D`、`TSR`、`WotC`、`Wizards of the Coast`
   作为产品标识或卖点。当前这些词只出现在**必要的出处说明与合规叙述**里（README、`docs/`、检索报告、
   `dnd/data/monsters.json` 的 `_meta`），属于叙述性使用。**不要**把它们放进项目简介、包名、PyPI 描述或 GitHub topics。
2. **不用专有名词做内容**：43 个内容条目（4 职业 / 4 种族 / 12 怪物 / 18 物品 / 5 法术）已逐条核对，
   未出现任何 WotC 专有怪物、法术或设定名；法术名（魔法飞弹/护盾/闪电束/治疗轻伤/祝福）为通用描述性名称。
   **背景故事同理**（游戏内序章 `dnd/data/lore.json` + 完整设定 `docs/world-setting.md`）：
   阿瑟兰、银冠诸国、穹顶帝国、星核、织线、薇兰、深渊地牢等名号全部自造；写作前调研「被遗忘的国度」
   只用于学结构，落地的名词一个都没沿用（母题 → 改造对照见 `docs/research-dossier.md` 第八节）。
   这条线由 `tests/test_core.py::TestLore::test_story_text_has_no_wotc_proper_nouns` 自动守住。
   复核命令见第五节。后续新增内容时请沿用同一标准（通用奇幻词或自创名）。
3. **非官方声明**：README 的「许可与合规」一节已写明"本项目与原作者、PLATO/cyber1 社区及
   Wizards of the Coast 均无关联，未获其授权或背书"。

补充：如果将来担心 PyPI/GitHub 上的名称冲突，最省事的做法是**保留仓库名 `dnd`，但把包名/发布名换成非冲突标识**
（例如 `plato-dnd-remake`）。目前 `pyproject.toml` 的 `name = "dnd"` 与仓库名一致，便于本地 `pipx install .`；
若日后要上 PyPI，再改这一行即可。

---

## 五、本次合规检查的做法与证据

以下命令都是**可重复执行**的，输出为本文写作时的实测结果（排除 `.git`、`.mimosa`、`out`）。

**1) 商标/专有名词扫描**（本轮把背景故事层的设定名与「被遗忘的国度」相关词一并纳入）

```bash
grep -rniE "dungeons|dragons|d&d|tsr|wotc|wizards of the coast|beholder|mind flayer|illithid|tiamat|bahamut|vecna|greyhawk|faerun|faerûn|forgotten realms|d20 system|被遗忘的国度|费伦|耐色瑞尔|密斯特拉|幽暗地域|underdark|undermountain|netheril|mystra|menzoberranzan|lolth|elminster|drizzt|baldur|neverwinter|cormyr|toril|深水城|博德之门" \
  --include='*.py' --include='*.json' --include='*.md' --exclude-dir=.git --exclude-dir=.mimosa --exclude-dir=out .
```

命中集中在三类，**全部是叙述性使用，没有一处作为产品标识**：

- **合规叙述**：`README.md`、`docs/open-source-compliance.md`（本文）、`docs/reimplementation-plan.md`，
  `docs/world-setting.md`（引用守线测试的名字），以及 `docs/research-dossier.md` 第八节
  （背景故事层的调研对照——说明"借用了哪个母题、换成了什么自创名"）；
- **测试里的反向断言**：`tests/test_core.py` 的 `TestLore.FORBIDDEN` 是一份 denylist，命中是它**内容本身**；
- **史料叙述**：`dnd_PLATO_1975_检索报告.md`（1975 原作的正式名 *The Game of Dungeons* 与来源链接）；
- **数据表 `_meta` 的免责注释**：`dnd/data/monsters.json` 一处，写的是"不使用他方商标"。

**游戏代码（`dnd/**.py`、`tools/`）、游戏运行时文本与序章数据表 `dnd/data/lore.json` 零命中**。故事正文的专有名词单独由
`tests/test_core.py::TestLore::test_story_text_has_no_wotc_proper_nouns` 守住——它只扫故事正文
（`lore.plain_text`），不扫 `_meta` 与文档里的合规注释，避免"连免责声明一起扫掉"。

**2) 内容条目逐条目视核对**：43 条全部为公有领域通用奇幻词汇（哥布林/骷髅/巨魔/吸血鬼/食尸鬼/幽魂…）
或自创名（深渊守卫/深渊遗物）。

**3) 依赖审计**

```bash
grep -rhoE "^(from|import) [a-zA-Z_.]+" --include='*.py' dnd tests tools | sed -E 's/^(from|import) //' | cut -d. -f1 | sort -u
```

输出：`__future__ argparse collections contextlib curses dataclasses dnd functools hashlib io json os pathlib re statistics subprocess sys tempfile time unicodedata unittest`。
**全部是标准库 + 包内引用**；`math`/`random` 均未出现（内核刻意回避 `random`），`time` 只用于存档与名册盖时间戳。
唯一的第三方依赖 `PIL`（Pillow）只在 `tools/preview.py` 内部延迟导入，且未出现在本命令的输出里（因为它写在函数体内）。

**4) 凭据与隐私扫描**

```bash
grep -rniE "api[_-]?key|secret|token|password|BEGIN .*PRIVATE KEY|ghp_|sk-[A-Za-z0-9]" \
  --include='*.py' --include='*.md' --include='*.json' --exclude-dir=.git --exclude-dir=.mimosa --exclude-dir=out .
```

命中只出现在**本文档自身**：一处是第一节结论表里的说明文字（"无密钥、无 token…"），一处是上面这条命令的正则文本。
**受版本控制的其它文件零命中。** 被 `.gitignore` 忽略的 `.mimosa/`（本机审查工具的会话记录，不属于本项目、不入库）
里有一些看似命中的行，逐条看全部是 `sk-` 正则在单词 "ta**sk-**review" 上的误报，不是真实凭据。
`saves/*.json` 也已 ignore，且内容只有游戏状态（角色名/职业/深度/种子），无个人信息。

**5) 绝对路径扫描**

```bash
git ls-files | xargs grep -nE '(/mnt/[a-z]/|/home/[a-z]|C:\\|/Users/)'
```

无本机绝对路径命中（即不含用户名或本机目录）。命中该模式的只有两类**通用平台常量**：
本文档里的这条扫描命令自身，以及 `tools/preview.py` 里各平台"默认字体候选路径"
（`C:\Windows\Fonts\consola.ttf`、`/usr/share/fonts/...`、`/System/Library/Fonts/...`）。
文档里需要举例时一律用 `<仓库目录>` 或 `~/code/dnd` 这类通用写法。

**6) 资源文件**：`git ls-files` 中没有任何图片/音频/字体/地图；唯一非代码文本是 `LICENSE`。
`out/preview/*.png` 是本地渲染产物，已 ignore，且画面文字全部由代码生成。

**7) 无网络行为**：全部 import 中无 `socket`/`urllib`/`http`/`requests`；游戏不联网、不检查更新、不回传统计。
（说明：这里的"无网络行为"指**游戏运行时**。开发时用 `web_search` 做史料检索是另一回事，
见 `docs/research-dossier.md` 第六节。）

---

## 六、发布前清单（按优先级）

**必须（否则等同于没开源）**

- [x] `LICENSE`（MIT）放仓库根 —— 没有协议的开源项目默认"保留一切权利"，别人**不能合法使用**
- [x] 数据目录的 CC0 声明（`dnd/data/LICENSE-CC0.txt` + 六张表的 `_meta.license`，含序章文本 `lore.json`）
- [x] `pyproject.toml`（包元数据 + 协议 + 可选依赖 + 入口点 + Python 版本底线）
- [x] 跨平台启动脚本 `play.sh`（Linux / macOS / WSL2 统一入口）
- [x] `README.md` 许可、平台支持与启动章节
- [x] README 补"非官方、无关联"声明
- [x] 清掉文档里的本机绝对路径
- [ ] **git 提交作者改成公开可用身份**（当前最新提交仍是 `eudora@localhost`，会被写进提交历史；
      历史上另有两个远端账号身份 `EudoraArcher` 与 `KananPond` 的初始提交）

**建议（决定项目"看起来是否可协作"）**

- [ ] `CONTRIBUTING.md`：怎么跑测试、代码风格、提交信息语言、**贡献者许可**（MIT 入站=出站即可，无需 CLA；
      若坚持要 DCO，写明 `git commit -s`）
- [ ] GitHub/Gitee Issues 模板（bug 报告请附 `./play.sh --check` 输出 —— 这是收集环境信息最省事的方式）
- [ ] CI（例如 GitHub Actions 矩阵：ubuntu/macos × 3.10/3.14，跑
      `python3 -m unittest discover -s tests` + `tools/pty_smoke.py`；Windows runner 只跑 `--headless-demo`，
      因为原生 Python 没有 curses）
- [ ] `SECURITY.md`（本游戏无网络、无凭据，安全面很小；一页写清"存档是本地 JSON 文件，
      读档会执行 JSON 解析但不会执行代码"即可）
- [ ] `CHANGELOG.md`（版本已在 `dnd/__init__.py` 定为 0.1.0，建议打 `v0.1.0` tag）
- [ ] README 加英文摘要段（面向国际读者降低门槛；游戏界面本身是中文）
- [ ] 仓库文件权限统一（Windows 挂载盘下所有文件都显示 777，建议 `git update-index --chmod=+x play.sh`
      固化可执行位，避免 clone 后 `./play.sh` 不可执行）

**可选（能力增强，不是合规要求）**

- [ ] 把存档目录从"仓库内 `saves/`"改为"用户数据目录"（`$XDG_DATA_HOME/dnd` 或 `~/.local/share/dnd`），
      或支持 `DND_SAVE_DIR` 环境变量覆盖 —— 这样 `pipx install dnd` 之后也能正常存档（当前存档写在仓库/安装目录旁）
- [ ] Windows 原生支持：需要额外依赖 `windows-curses`，与"零第三方依赖"目标冲突，本项目已明确**不支持**，
      Windows 用户走 WSL2（`play.sh` 会检测并给出安装指引）

---

## 七、逐项证据：为什么每条"干净"结论成立

| 结论 | 依据 |
|---|---|
| 无第三方源码 | 仓库没有 vendor/ 目录，也没有 vendored 单文件库；41 个受版本控制的文件全部自研（`git ls-files`） |
| 无素材版权负担 | `git ls-files` 中无二进制资源；界面字符与配色由 `dnd/ui/theme.py` 代码生成 |
| 数据表可自由替换 | `dnd/content.py` 运行期读 `dnd/data/*.json`；`_meta.confidence` 全为 `invented`，无一处声称来自原版 |
| 背景故事为自创世界 | `dnd/data/lore.json` 的 `_meta` 标 `invented` + CC0；游戏内只放"世界/入井/须知"节选，细设定在 `docs/world-setting.md`；专有名词扫描由 `tests/test_core.py::TestLore` 自动执行；调研只借用公共母题，改造对照见 `docs/research-dossier.md` 第八节 |
| 存档不含隐私 | `dnd/save.py` 只序列化 `Game.to_json()`（种子/回合/角色属性/地图/RNG 状态）；`saves/*.json` 在 `.gitignore` |
| 无网络行为 | 全部 import 中无 `socket`/`urllib`/`http`/`requests`；游戏不联网、不检查更新、不回传统计 |
| 无本机路径泄漏 | 第五节第 5 条扫描：除"平台默认字体路径"与本条命令自身外无命中 |

---

## 八、免责声明

本文档是**技术性合规检查记录与协议说明**，不是法律意见。若本项目要商业化、进入应用商店、或收到任何权利主张，
请咨询执业律师。文档中的事实性判断（"未使用某商标""未复制源码"）基于本文写作时的仓库内容，
后续新增内容需重新核对。
