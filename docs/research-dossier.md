# 资料档案：PLATO《dnd》(1975) —— 复刻用数据底稿

> **用途**：这是本项目的"史料底座"。复刻里哪些是原版就有的骨架、哪些是我们自己定的，
> 全部以本文的可信度分级为准；落地方式见 [`reimplementation-plan.md`](reimplementation-plan.md)。
> **采集方式**：联网检索（`web_search`）+ 公开通说。**本机 shell 的网络实测结果**见第六节 —— 它决定了
> 哪些结论只能停留在"检索元数据"层面。
> 每条数据都标注可信度：**A = 多来源确证 / B = 通行说法 / C = 未确证（复刻时必须自己定或进一步核实）**。

---

## 一、平台与技术底座（复刻的"物理约束"）

| 项 | 数据 | 可信度 |
|---|---|---|
| 硬件 | PLATO IV 终端：**512×512 像素气体等离子（plasma）显示屏** | A |
| 字符网格 | **64 列 × 32 行**，每字符 8×16 像素 → 复刻渲染的黄金约束 | A- |
| 主色调 | 等离子橙／琥珀单色辉光，黑底 | A- |
| 主机 | CDC（Control Data）大型机 + CERL（UIUC）分时网络，多校区终端共享同一系统 | A |
| 语言 | **TUTOR**（PLATO 自带教学语言），程序以 lesson 文件组织 | A |
| 输入 | PLATO 专用键盘：方向/字母键外还有 **NEXT / BACK / HELP / LAB / DATA / SHIFT** 等功能键，游戏大量使用"单键命令" | A- |
| 存储 | 角色/进度存于 PLATO 用户（学生）记录 → **跨会话持久化角色**是本作的先天特性 | B+ |
| 现代访问 | cyber1.org（社区复原的 PLATO 系统）+ **Pterm** 终端模拟器；可实际运行 dnd / pedit5 / Moria / Oubliette / Avatar | A |

> **复刻含义**：一个 64×32 的字符屏就是"原生分辨率"。本项目用 48×26 的逻辑地图装进
> 64×32 级别的终端（再让两侧/上下容纳状态栏、日志与提示栏），既贴年代感，又不必逐像素还原。

## 二、作品身份（A 类事实）

| 项 | 数据 | 来源 |
|---|---|---|
| 名称 | `dnd`（小写；亦称 *The Game of Dungeons*） | 英文/中文/日文/俄文维基 |
| 年份 | **1975**（维基条目名历史上在 "Dnd (1974)" / "dnd (1975)" 间变动过，开工可能早至 1974） | 维基 + uvlist |
| 作者 | **Gary Whisenhunt** 与 **Ray Wood** | 维基 + 访谈 |
| 机构 | 归属常标为 **Southern Illinois University** 的 PLATO 游戏（uvlist 条目名即如此）；网络中枢在 UIUC/CERL | uvlist |
| 语言 | TUTOR | 维基 |
| 类型 | 单人地牢爬行（dungeon crawl）CRPG，俯视地图 | 维基 |
| 灵感 | TSR 1974 年桌上游戏《Dungeons & Dragons》（名字即取自它） | 维基 |
| 历史定位 | 最早的 CRPG / 最早的地牢爬行游戏之一；与 pedit5（Rusty Rutherford，1975-05，UIUC）同期 | 维基 + Kotaku 五十周年 |
| 后续维护 | **Dirk Pellett** 与 **Flint Pellett** 兄弟接手扩展；cyber1 上流传的可玩版本为 **v5.4**，另有更晚的 **v8** 见诸记录 | 维基 + crpgadventures 系列 |
| 影响 | 与 PLATO 同类游戏一起被视为 Rogue(1980) → roguelike 一脉的远祖 | roguelike 史料 |
| 现状 | 原服务终止；cyber1.org 上仍可游玩 | A |

## 三、玩法（B 类：通行说法，细节需核实）

- **俯视字符地图 + 局部视野**：只显示角色周边一小片区域，墙体/门/楼梯/怪物都用 PLATO 字符图形绘制
  （不是后来 Rogue 那种滚动文本行）。
- **角色养成**：建角 → 属性 → 职业/等级/经验 → 打怪拾宝成长。
- **多层地牢**：沿楼梯逐层下潜，越深越危险，宝物越好。
- **战斗与法术**：近战 + 法术（施法职业），有武器/护甲/魔法物品/药水等。
- **永久死亡倾向**：角色死亡即作废。
- **角色持久化 + 社群**：同一账号可长期续玩，PLATO 网络上有跨校区玩家圈与"名人堂"式文化。
- **目标**：深入底层取得终极宝物 / 击败首领后生还（各版本条件不同）。

## 四、C 类：**未确证**的具体数据（复刻必须自行定义，并标记为 inferred/invented）

1. 建角细节：可选**职业/种族**清单、属性集合（力量/智力/体质/敏捷/魅力？）、初始装备、掷骰方式。
2. **法术表**：名称、环阶、耗魔/记忆规则、效果与射程。
3. **怪物表**：名称、层级分布、生命/攻击/经验/掉落。
4. **物品表**：武器护甲数值、魔法物品、消耗品、宝物换算。
5. **地牢结构**：层数（通说 10 层？）、单层尺寸、房间/走廊生成算法、楼梯与门的规则、陷阱。
6. **进度曲线**：经验表、等级上限、怪物强度随层数增长的公式。
7. **胜负条件**：终极宝物/首领是否唯一、是否有"回程"机制、通关后是否有传承。
8. 是否存在城镇/商店/光源与饥饿等外围系统。

> 本项目对上述 C 类项的处置：**自己定义，并在数据文件里显式标注** `confidence: "invented"` 与
> `source: "docs/research-dossier.md#四"`。当前 43 条内容（4 职业 / 4 种族 / 12 怪物 / 18 物品 / 5 法术）
> 全部属于这一类，没有一条声称来自原版。因此它们可以在**不改任何代码**的前提下被整体替换
> —— 这也是数据表单独采用 CC0-1.0 的原因（见 `open-source-compliance.md`）。

## 五、核实路线（把 C 类升级为 A 类）

| 手段 | 能拿到什么 | 备注 |
|---|---|---|
| 注册 cyber1.org + Pterm 实机游玩 dnd v5.4 | 最直接：职业、法术、怪物、层数、胜负条件、按键 | 需要账号；须在本机操作或提供截图/日志 |
| 读 CRPG Addict 两篇（2012 / 2019）+ CRPG Adventures 系列 | 逐回合实机记录与截图，含界面布局 | 链接见下 |
| 多语言维基对照（英/中/日/俄） | 细节互补（俄语条目篇幅较长） | 直接打开即可 |
| 作者访谈（N4G 转载） | 创作动机、时间线、校园背景 | 链接见下 |
| 搜索/档案站找 TUTOR 源码或复制品 | 原版数值（若存在） | 需要能访问 GitHub / archive.org |
| **把页面正文粘贴进本工作区** | 可据此把数据从 inferred 升级为 documented | 最省事的协作方式 |

### 主要链接

- 英文维基 dnd (1975 video game)：https://en.wikipedia.org/?curid=1064371
- 中文维基：https://zh.wikipedia.org/wiki/Dnd_(%E7%94%B5%E5%AD%90%E6%B8%B8%E6%88%8F)
  ｜ 日文：https://ja.m.wikipedia.org/wiki/Dnd_(PLATO)
  ｜ 俄文：https://ru.wikipedia.org/wiki/Dnd_(%D0%BA%D0%BE%D0%BC%D0%BF%D1%8C%D1%8E%D1%82%D0%B5%D1%80%D0%BD%D0%B0%D1%8F_%D0%B8%D0%B3%D1%80%D0%B0)
- CRPG Addict：#69 dnd (2012) http://crpgaddict.blogspot.com/2012/02/game-69-game-of-dungeonsdnd-1975.html
  ｜ 重访 (2019) https://crpgaddict.blogspot.com/2019/01/revisiting-game-of-dungeons-1975.html
  ｜ 1970 年代大型机 RPG 综述 http://crpgaddict.blogspot.com/2021/06/brief-everything-we-know-about-1970s.html
- CRPG Adventures：pedit5 https://crpgadventures.blogspot.com/2014/04/the-dungeon-aka-pedit5-1975.html
  ｜ dnd v5.4 https://crpgadventures.blogspot.com/2014/05/the-game-of-dungeons-aka-dnd-1975.html
  ｜ dnd v8 http://crpgadventures.blogspot.com/2016/02/the-game-of-dungeons-v8-of-course-you.html
- 访谈：https://n4g.com/news/1065670/interview-with-fathers-of-videogame-rpg-industry-gary-whisenhunt-and-ray-wood
  ｜ https://n4g.com/news/1958118/interview-with-the-creators-of-dnd-plato
- 平台背景（PLATO 游戏史 PDF，PlayWrite #3）：https://kcgl.aau.at/wp-content/uploads/2023/03/PlayWrite_3.pdf
- uvlist 条目（标注 Southern Illinois University）：https://www.uvlist.net/game-160118
- Kotaku 五十周年：https://kotaku.com/50-years-ago-one-of-the-most-important-video-game-genres-was-born-2000641056
- 实机/模拟器：cyber1.org + Pterm；Speedrun.com 的 The Dungeon 论坛有 Pterm 按键说明

## 六、检索局限（务必知悉）

1. **`web_search` 只回传标题/链接与偶发摘要**，不能当作数值来源；本档案的 B 类因此只能算"设计参考"，
   C 类则是"必须由我们定义并标注来源等级"的空白位。
2. **shell 网络时通时不通**：立项那一轮实测 `curl` 直连与常见本地代理端口（7890/10809/1080…）全部失败，
   `npm`/`pip` 也不可达，因此当时把"零第三方依赖"当作硬约束。
   **本轮（文档重写时）实测**：`https://github.com`、`https://gitee.com`、`https://registry.npmjs.org`
   均返回 200，而 `https://pypi.org/simple/` 在 20 秒内无响应。可见约束会随环境变化，
   但"只用标准库"已经是本项目的既定设计，不因网络恢复而改变。
3. 因此本档案中凡标注 B/C 的内容，都**不能**直接当作原版事实引用；引用时请连可信度一起引用。
4. **`web_fetch` 对多数站点不可达，能用的只有 `web_search` 的元数据**（第八节调研那一轮实测）：
   同一环境下 `https://example.com` 返回 200，而 wikipedia、fandom、wikiwand 全部
   `fetch failed`，`baike.baidu.com` 与 `britannica.com` 返回 403 验证页；本机 `curl` 直连同样超时。
   所以第八节只能给出"标题/链接/通行说法"，凡涉及"原设定里长这样"的判断一律标 **B**，
   并且只用于**设计灵感**，不作为本项目的事实断言。

## 七、这份档案如何影响实现（速查）

| 档案结论 | 对实现的约束 | 落地位置 |
|---|---|---|
| 64×32 字符屏是原生分辨率（A-） | 逻辑地图 48×26，整体装进 64×32 级别的终端 | `level.py`、`ui/tui.py` |
| 等离子橙单色辉光（A-） | 黑底琥珀调色板 + 光照层次 + 三级配色降级 | `ui/theme.py` |
| TUTOR lesson + PLATO 功能键（A/A-） | 不还原语言；数据驱动内容 + 单键命令 + 按键提示栏 + 帮助页 | `content.py`、`ui/tui.py` |
| 局部视野、俯视地图（B） | 递归阴影投射 FOV + 记忆雾 | `fov.py` |
| 逐层下潜、深度学习曲线（B） | 10 层，怪物/物品按深度加权 | `level.py`、`data/*.json` |
| 角色持久化、永久死亡、名人堂文化（B/B+） | JSON 存档 + 名人堂名册 + 删档 | `save.py` |
| 职业/法术/怪物/数值（C） | 全部自定，标 `invented`，可整体替换 | `data/*.json` |
| 胜负条件（C） | 第 10 层守卫 + 遗物：**取得即胜利** | `level.py`、`game.py` |
| 背景故事（C） | 借用公共母题、名词全部自创，标 `invented`，可整体替换；游戏内只展示节选 | `data/lore.json`、`lore.py`、`ui/screens.py`、`docs/world-setting.md` |

---

## 八、「被遗忘的国度」调研与改造对照

> **用途**：这是背景故事层（`dnd/data/lore.json`）的调研底稿。第二节明确了 1975 原版的职业/剧情
> 均不可考，所以本项目的世界观只能自己写。写作前调研了 D&D 最知名的战役设定
> **「被遗忘的国度」（Forgotten Realms）**，学它的**结构**（一个失落帝国 + 一条维系魔法的源流 +
> 一片地下世界 + 一座疯法师的地牢），再全部换成自创名词落地。

### 8.1 借用了哪些母题、改成了什么

| 母题 | 原设定里的样子 | 本项目的改造 | 可信度 |
|---|---|---|---|
| 失落的浮空魔法帝国 | 耐色瑞尔（Netheril）的浮空城，靠 `mythallar` 悬浮 | 穹顶帝国的七座浮空城，靠「星核」悬浮 | B |
| 维系法术的世界源流 | 魔网（the Weave），由魔法女神密斯特拉照看 | 「织线」，由织法者薇兰照看 | B |
| 帝国因窃取神权而崩落 | 卡萨斯之愚行（Karsus's Folly，−339 DR）：法师试图取代女神，魔网崩溃、浮空城坠落 | 「断裂之夜」：大法师奥兰试图攫取薇兰的权柄，织线崩断、七城坠地 | B |
| 灾后"后魔法"的凡间 | 法术瘟疫（Spellplague，1385 DR）与第二次大分裂之后的诸国 | 织线断裂后的银冠诸国：法术变成需要登记的东西 | B |
| 地下幽暗世界 | 幽暗地域（Underdark）：卓尔、灰矮人、地底侏儒与无光生态 | 坠城埋进地底后形成的「深渊地牢」，逐层向下 | B |
| 疯法师的巨型地牢 | 深水城地下的 Undermountain，由 Halaster Blackcloak 不断扩建 | 深渊地牢由没有死去的疯法师奥兰一层层改造 | B |
| 世外之地被"遗忘" | 设定名本身的来历：因通往外界的门扉，此地在别处成了传说 | 「遗忘之陆」：断裂之夜后门扉闭合，阿瑟兰从地图上消失 | B |
| 各司其职的神系 | 密斯特拉（魔法）/ 兰森德尔（黎明）/ 莎尔（暗影）/ 摩拉丁（矮人）/ 柯瑞隆（精灵）/ 加尔·闪金（侏儒）/ 太摩拉（幸运） | 薇兰 / 艾尔登 / 娜芮 / 瓦尔格 / 伊瑟兰 / 班德尔 / 蒂拉 | B |
| 看守终极宝物的守卫 | 地牢深处的 boss 与神器（各版不同） | 打不死、只能引开的「深渊守卫」，守着「星核之心」 | C（本项目自定） |

**没有采用的**：诸神化为化身行走人间（动荡之年，Time of Troubles，1358 DR）——本项目的剧情只需要
"灾变之后的凡间"，不需要神祇下凡，所以省掉了这一层。

### 8.2 为什么不直接用原设定名词

「被遗忘的国度」及其专有名词（费伦、耐色瑞尔、魔网、密斯特拉、幽暗地域、Undermountain……）
是 Wizards of the Coast 的商标与受保护设定，而本仓库的既定立场是**内容里不出现他方专有名词**
（见 `open-source-compliance.md` 第四节）。所以本节的用法是**描述性引用**（说明"学的是什么"），
落地到 `dnd/data/lore.json` 时全部换成自创名，并由
`tests/test_core.py::TestLore::test_story_text_has_no_wotc_proper_nouns` 自动守住这条线。

### 8.3 主要链接

- Forgotten Realms（维基总览）：https://en.wikipedia.org/wiki/Forgotten_Realms
- 幽暗地域 Underdark：https://en.wikipedia.org/wiki/Underdark
- 耐色瑞尔 Netheril：https://forgottenrealms.fandom.com/wiki/Netheril
- 动荡之年 Time of Troubles：https://forgottenrealms.fandom.com/wiki/Time_of_Troubles
- 幽暗深渊 Undermountain：https://forgottenrealms.fandom.com/wiki/Undermountain
- 设定史（The Grand History of the Realms）：https://en.wikipedia.org/wiki/The_Grand_History_of_the_Realms
- 中文条目（耐色瑞尔）：https://baike.baidu.com/item/耐色瑞尔/5215771
- 中文条目（密斯特拉）：https://baike.baidu.com/item/密斯特拉/64482599
- 创作源流（Ed Greenwood 与设定的由来）：https://www.wizardtower.com/blog/general/the-forgotten-realms-origins/

> **可信度说明**：以上条目在本次调研中只拿到了**检索元数据（标题/链接/摘要）**——
> `web_fetch` 对 wikipedia / fandom / baike 三个域全部超时或返回 403（见第六节），
> 本机 `curl` 也连不出去。因此 8.1 表里"原设定里的样子"这一栏只能标 **B = 通行说法**：
> 它们只用于**设计灵感**，不作为本项目的事实断言；真正落地的名词与情节全部是 **C = 本项目自定**。

### 8.4 这份调研如何影响实现

| 调研结论 | 对实现的约束 | 落地位置 |
|---|---|---|
| 世界观需要"可替换"而不是写死 | 游戏内序章进 JSON，代码只负责取页/排版；完整设定写文档 | `dnd/data/lore.json`、`dnd/lore.py`、`docs/world-setting.md` |
| 背景要与"十层地牢 + 遗物 + 守卫"对上 | 坠城 = 十层竖井；守卫打不死 = 只能引开；遗物 = 星核之心 | `lore.json`、`level.py`（既有设计） |
| 玩家要在**建角之后**读到它 | 建角返回后先过 `prologue_screen`（只放世界/入井/须知），再进地牢；随时按 `B` 重看 | `dnd/__main__.py`、`ui/screens.py`、`ui/tui.py` |
| 无终端也要能看 | `--lore` 打印纯文本；`--no-prologue` 跳过 | `dnd/__main__.py`、`dnd/lore.py` |
| 不许夹带他方专有名词 | 自动扫描故事正文 | `tests/test_core.py::TestLore` |

