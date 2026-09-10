# 检索报告：PLATO 系统上的《dnd》（1975）

> 检索时间：本次会话；检索手段：联网搜索（web_search）。当前 shell 无外网，**只取到了搜索结果的标题/链接元数据，未能抓取正文**，因此下文对"通说事实"与"需核实的细节"做了明确区分。

## 一、结论速览

《dnd》（小写，常被称作 *The Game of Dungeons*）是 1975 年运行在美国 **PLATO IV** 大型机分时系统上的**单人地牢爬行（dungeon crawl）游戏**，由 **Gary Whisenhunt** 与 **Ray Wood** 用 PLATO 的 **TUTOR** 语言编写。它被公认为**最早的电脑角色扮演游戏（CRPG）之一**、**最早的地牢爬行类游戏之一**，与同年（1975 年 5 月，伊利诺伊大学厄巴纳-香槟分校）Rusty Rutherford 的 **pedit5** 并列，是后来 Rogue（1980）与整个 roguelike 谱系的远祖。

## 二、基本档案

| 项目 | 内容 | 可信度 |
|---|---|---|
| 名称 | dnd（亦作 DND / The Game of Dungeons；后续版本称 dnd5.x） | 高 |
| 年代 | 通行记为 **1975 年**；有资料把开工年份写成 1974（维基条目名历史上在 "Dnd (1974)" 与 "dnd (1975)" 之间变动，uvlist 亦标 1974） | 高（年份）/中（1974 开工说） |
| 平台 | PLATO IV（CERL/UIUC 的 CDC 大型机 + PLATO 分时网络，终端为 512×512 气体等离子显示屏，支持可寻址字符图形） | 高 |
| 开发语言 | TUTOR（PLATO 的教学用编程语言），配合 PLATO 的 lesson 文件与用户/学生记录存储 | 高 |
| 作者 | Gary Whisenhunt、Ray Wood（学生/爱好者身份） | 高 |
| 所属机构 | 通说为 **南伊利诺伊大学（Southern Illinois University）**，经终端接入 UIUC 的 PLATO 网络；也有资料只笼统写作 PLATO 网络 | 中（待核实校名与校区） |
| 类型 | 单人地牢爬行 CRPG，俯视字符地图，灵感直接来自 TSR 1974 年的桌上游戏《Dungeons & Dragons》 | 高 |
| 命名 | 取自《Dungeons & Dragons》；小写写法常被解释为与 D&D 商标做区分，也是 PLATO 上的短文件名习惯 | 中 |
| 后续维护 | 由 **Dirk Pellett** 与 **Flint Pellett** 兄弟等人接手扩展、长期维护 | 高 |
| 现状 | 原始 PLATO 服务已终止；游戏在社区复原的 PLATO 系统 **cyber1.org** 上仍可实际运行/游玩（需注册） | 高 |

## 三、玩法与设计特征（通说层面）

- **俯视字符地图 + 局部视野**：屏幕只显示角色周围一小片区域，墙、门、楼梯、怪物都用 PLATO 字符集自绘的图形符号表示，而不是文本行滚动（这是它与后来 Rogue 的纯 ASCII 风格的区别）。
- **角色养成**：创建角色后拥有属性、职业/等级与经验值体系，靠打怪与拾取宝物成长；不同版本可选职业与规则有差异（具体职业名与法术表需查原始资料，本次检索未取到正文）。
- **多层地牢**：沿楼梯向下逐层深入，层数、房间/走廊布局、陷阱、怪物与宝物随深度增强；最终目标是抵达深层、取得终极宝物并击败/避开首领，把角色带回来（各版本胜利条件不同，细节待核实）。
- **永久死亡倾向**：角色一旦死亡，通常意味着存档角色作废（与 PLATO 同类地牢游戏一致）。**中可信度，待核实。**
- **持久化角色**：角色数据保存在 PLATO 的用户记录里，因此可以退出后下次登录继续玩——这在 1975 年是相当超前"存档"概念，也让 PLATO 网络上的玩家形成跨校区的玩家社群与排行榜文化。

## 四、历史位置：PLATO 地下城游戏谱系

1975—1979 年的 PLATO 网络上出现了一批地下城/RPG 游戏，dnd 是其中承上启下的关键一环：

- **pedit5**（1975，Rusty Rutherford，UIUC）—— 通常被认为是第一个地牢爬行游戏，据传曾被 PLATO 管理员以"非教学用途"删除，后由用户从备份恢复。
- **dnd**（1975，Whisenhunt & Wood）—— 与 pedit5 同期、长期更流行、被持续维护扩展的经典。
- **Moria**（1975—）—— 同期的 PLATO 地牢游戏，名字后来也被其他平台的作品沿用。
- **Oubliette**（1977 起）、**Avatar**（1977—1979）—— 把 PLATO 的网络能力用于**多人同乐**，把这一脉推向高峰。
- 下游影响：Rogue（1980，Michael Toy、Glenn Wichman 等）被公认为受到 PLATO 地牢游戏传统的启发，其后形成 "roguelike" 类型；因此 dnd 也是 roguelike 家谱上的重要祖先之一。

另有一条常被引用的轶事：1976 年厄巴纳-香槟的校方/管理层曾试图清除 PLATO 上某个"顽固存在"的非教学程序（检索到的 PlayWrite 第 3 期 PDF 片段提到此事）。这类"校方删游戏、玩家抢救"的故事通常与 pedit5 挂钩，是否也发生在 dnd 上**需要读原文确认**。

## 五、主要资料入口（可点击核实）

- 英文维基：dnd (1975 video game) — https://en.wikipedia.org/?curid=1064371
- 中文维基：dnd (电子游戏) — https://zh.wikipedia.org/wiki/Dnd_(%E7%94%B5%E5%AD%90%E6%B8%B8%E6%88%8F)
- 俄文维基（内容较细）：https://ru.wikipedia.org/wiki/Dnd_(%D0%BA%D0%BE%D0%BC%D0%BF%D1%8C%D1%8E%D1%82%D0%B5%D1%80%D0%BD%D0%B0%D1%8F_%D0%B8%D0%B3%D1%80%D0%B0)
- CRPG Addict 实机长文：Game 69: The Game of Dungeons/dnd (1975) — http://crpgaddict.blogspot.com/2012/02/game-69-game-of-dungeonsdnd-1975.html
- CRPG Addict 重访（2019）：https://crpgaddict.blogspot.com/2019/01/revisiting-game-of-dungeons-1975.html
- CRPG Addict：1970 年代大型机 RPG 综述 — http://crpgaddict.blogspot.com/2021/06/brief-everything-we-know-about-1970s.html
- 作者访谈（Whisenhunt & Wood）：https://n4g.com/news/1065670/interview-with-fathers-of-videogame-rpg-industry-gary-whisenhunt-and-ray-wood
- 开发者访谈（PLATO dnd）：https://n4g.com/news/1958118/interview-with-the-creators-of-dnd-plato
- Kotaku 五十周年回顾：https://kotaku.com/50-years-ago-one-of-the-most-important-video-game-genres-was-born-2000641056
- Roguelike 历史（含 PLATO 一脉）：https://web.archive.org/web/20201111220249/http://en.wikipedia.org/wiki/Roguelike
- PLATO 游戏史 PDF（PlayWrite #3）：https://kcgl.aau.at/wp-content/uploads/2023/03/PlayWrite_3.pdf
- 实际游玩入口（复原的 PLATO 系统）：cyber1.org（需注册；系统内可运行 dnd、Moria、Oubliette、Avatar 等）

## 六、本次检索的局限与待核实清单

1. 未能抓取页面正文（shell 无外网，web_search 仅返回链接与少量摘要），**玩法细节（职业名、法术表、层数、胜利条件）均需以原始资料复核**。
2. 作者所属学校/校区（Southern Illinois University Carbondale？）与"1974 开工、1975 成型"的确切时间线。
3. dnd 是否也有被管理员删除/抢救的经历，还是该轶事仅属 pedit5。
4. 版本号谱系（v1→v5.x）与 Pellett 兄弟各自贡献的具体范围。
