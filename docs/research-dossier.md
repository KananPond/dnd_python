# 资料档案：PLATO《dnd》(1975) —— 复刻用数据底稿

> 采集方式：联网检索（web_search）＋既有公开通说。**本机 shell 无外网**（curl/pip/npm 全部不通，已实测），因此无法抓取页面正文；
> 每条数据都标注可信度：**A=多来源确证 / B=通行说法 / C=未确证（复刻时必须自己定或进一步核实）**。

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
| 现代访问 | cyber1.org（社区复原的 PLATO 系统）＋ **Pterm** 终端模拟器；可实际运行 dnd / pedit5 / Moria / Oubliette / Avatar | A |

> 复刻含义：一个 64×32 的字符屏就是"原生分辨率"。把游戏做成 64×32 逻辑网格 + 无插值放大，可以在不做 1:1 还原的前提下拿到最强的年代感。

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
| 影响 | 与 PLATO 同类游戏一起被视为 Rogue(1980)→roguelike 一脉的远祖 | roguelike 史料 |
| 现状 | 原服务终止；cyber1.org 上仍可游玩 | A |

## 三、玩法（B 类：通行说法，细节需核实）

- **俯视字符地图 + 局部视野**：只显示角色周边一小片区域，墙体/门/楼梯/怪物都用 PLATO 字符图形绘制（不是后来 Rogue 那种滚动文本行）。
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
7. **胜负条件**：终极宝物/首领是否唯一、是否有"回程"机制、通关后是否有传承（roster/续档）。
8. 是否存在城镇/商店/光源与饥饿等外围系统。

## 五、核实路线（把 C 类升级为 A 类）

| 手段 | 能拿到什么 | 备注 |
|---|---|---|
| 注册 cyber1.org + Pterm 实机游玩 dnd v5.4 | 最直接：职业、法术、怪物、层数、胜负条件、按键 | 需要账号；我这边无外网，须由你在本机操作或提供截图/日志 |
| 读 CRPG Addict 两篇（2012 / 2019）+ CRPG Adventures 系列（pedit5、dnd v5.4、dnd v8） | 逐回合实机记录与截图，含界面布局 | 链接见下 |
| 多语言维基对照（英/中/日/俄） | 细节互补（俄语条目篇幅较长） | 直接打开即可 |
| 作者访谈（N4G 转载） | 创作动机、时间线、校园背景 | 链接见下 |
| 搜索/档案站找 TUTOR 源码或复制品 | 原版数值（若存在） | 我这边无法访问 GitHub/archive.org |
| **把页面正文粘贴进本工作区** | 我可据此把数据从 inferred 升级为 documented | 最省事的协作方式 |

### 主要链接
- 英文维基 dnd (1975 video game)：https://en.wikipedia.org/?curid=1064371
- 中文维基：https://zh.wikipedia.org/wiki/Dnd_(%E7%94%B5%E5%AD%90%E6%B8%B8%E6%88%8F) ｜ 日文：https://ja.m.wikipedia.org/wiki/Dnd_(PLATO) ｜ 俄文：https://ru.wikipedia.org/wiki/Dnd_(%D0%BA%D0%BE%D0%BC%D0%BF%D1%8C%D1%8E%D1%82%D0%B5%D1%80%D0%BD%D0%B0%D1%8F_%D0%B8%D0%B3%D1%80%D0%B0)
- CRPG Addict：#69 dnd (2012) http://crpgaddict.blogspot.com/2012/02/game-69-game-of-dungeonsdnd-1975.html ｜ 重访 (2019) https://crpgaddict.blogspot.com/2019/01/revisiting-game-of-dungeons-1975.html ｜ 1970s 大型机 RPG 综述 http://crpgaddict.blogspot.com/2021/06/brief-everything-we-know-about-1970s.html
- CRPG Adventures：pedit5 https://crpgadventures.blogspot.com/2014/04/the-dungeon-aka-pedit5-1975.html ｜ dnd v5.4 https://crpgadventures.blogspot.com/2014/05/the-game-of-dungeons-aka-dnd-1975.html ｜ dnd v8 http://crpgadventures.blogspot.com/2016/02/the-game-of-dungeons-v8-of-course-you.html
- 访谈：https://n4g.com/news/1065670/interview-with-fathers-of-videogame-rpg-industry-gary-whisenhunt-and-ray-wood ｜ https://n4g.com/news/1958118/interview-with-the-creators-of-dnd-plato
- 平台背景（PLATO 游戏史 PDF）：https://kcgl.aau.at/wp-content/uploads/2023/03/PlayWrite_3.pdf
- uvlist 条目（标注 Southern Illinois University）：https://www.uvlist.net/game-160118
- Kotaku 五十周年：https://kotaku.com/50-years-ago-one-of-the-most-important-video-game-genres-was-born-2000641056
- 实机/模拟器：cyber1.org + Pterm；Speedrun.com 的 The Dungeon 论坛有 Pterm 按键说明

## 六、检索局限（务必知悉）

1. 本机无外网：`curl` 直连与常见本地代理端口（7890/10809/1080…）全部失败，`npm/pip` 也不可达；npm 缓存里只有 DSH 自身的包 → **复刻不能依赖任何第三方依赖**。
2. web_search 只回传标题/链接与偶发摘要，**不能当作数值来源**。
3. 因此本档案的 B 类为"设计参考"，C 类为"必须由我们定义并标注来源等级"的空白位。
