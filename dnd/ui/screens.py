"""开局三屏：开始页 / 存档管理 / 建角。全部用 ↑↓←→ 操作，不需要记命令。

流程：
    开始页（start_screen）
      ├─ 新的冒险 → 建角（creation_screen）→ 序章（prologue_screen）→ 进游戏
      ├─ 读取存档 → 存档管理（save_manager_screen）→ 进游戏
      ├─ 名人堂   → 名册浮层（lobby_screen）
      └─ 退出游戏

为什么单独一个模块：tui.py 已经承载"游戏内界面"，再把开局三屏塞进去会让那个文件既长又难改。
这里只依赖 widgets/theme（不 import tui），所有面板都走 `draw_panel` —— 面板怎么排、光标行
怎么反白收敛成一份实现（还带一份不落笔的 `panel_rect` 供调用方对齐），测试也就不必去嗅探属性位。

三条界面铁律（沿用 tui.py 的经验）：
  · 所有文本走 widgets.put（按**显示宽度**裁剪）：中文占两格，按字符数裁剪会越界；
  · 选项行整行反白时文字必须左右各留一格 —— 宽度算错就会顶掉面板右边框；
  · 任何一屏都要能只用 ↑↓ + 回车走完，方向键在每一屏都是"移动光标"。
"""

from __future__ import annotations

import curses

from .. import save as save_mod
from ..entities import BASE_FOV_RADIUS as BASE_FOV
from ..level import MAX_DEPTH
from . import theme
from .widgets import (_width, bar, center, clip, fill, frame, hint_bar, pad_to, put,
                      rule, wrap)

# 与 tui.py 保持一致的最小窗口与中文属性名（两边都不 import 对方，避免循环依赖）
MIN_W, MIN_H = 62, 18
ATTR_ZH = {"STR": "力量", "DEX": "敏捷", "CON": "体质", "INT": "智力", "WIS": "感知"}

# 建角界面切换"职业栏 / 种族栏"的键。KEY_BTAB = Shift+Tab（终端发 \x1b[Z），
# 很多终端/多路复用器把它当"上一栏"，原先漏了它，种族栏就只剩 Tab 和 ←→ 三条路。
FOCUS_KEYS = frozenset({ord("\t"), curses.KEY_BTAB, curses.KEY_LEFT, curses.KEY_RIGHT})

# 菜单里的上下移动：方向键为主（用户要求），WASD / hjkl 是顺手加的备选
MENU_UP = frozenset({curses.KEY_UP, ord("k"), ord("w"), ord("K"), ord("W")})
MENU_DOWN = frozenset({curses.KEY_DOWN, ord("j"), ord("s"), ord("J"), ord("S")})
ENTER_KEYS = frozenset({10, 13, curses.KEY_ENTER})

# 开始页的 ASCII logo：只用 ASCII 是因为中文终端把 ─│┌ 之类的框线字母当两格宽，
# 用他们拼图案很容易歪；用 # 拼字则任何终端都对齐。'%' 是 PLATO 终端的琥珀辉光感。
LOGO = (
    "#####   ##   #  #####",
    "#    #  ###  #  #    ",
    "#    #  #  ###  #  ##",
    "#####   #   ##  #####",
)
LOGO_COMPACT = ("#  #  #  #####", "#  ## #  #    ", "#  # ##  #  ##", "#  #  #  #####")

TITLE = "深渊地牢"
SUBTITLE = "PLATO（1975）《dnd》现代复刻 · 零依赖终端版"
TAGLINE = f"下到第 {MAX_DEPTH} 层夺取「深渊遗物」，再活着回来。"

START_ITEMS = ("新的冒险", "读取存档", "名人堂", "退出游戏")
START_CHOICES = ("new", "load", "roster", "quit")


def _clip_key(text: str, limit: int) -> str:
    """把"键 说明"裁成不超过 limit 格，且尽量不把说明切成半个词。"""
    text = clip(text, limit)
    return text.rstrip()


def _hint_cells(pairs, max_units: int = 8):
    """挑几个能在窄终端里放下的提示（超宽的说明先缩短，再整条丢弃）。"""
    cells = []
    for key, label in pairs:
        if _width(label) > max_units:
            label = clip(label, max_units - 1)
        if sum(_width(k) + _width(v) + 3 for k, v in cells) + _width(key) + _width(label) + 2 > 56:
            break
        cells.append((key, label))
    return cells


def _hint_rows(pairs, max_w: int):
    """把 [(键, 说明), ...] 折成若干行提示，按显示宽度换行。

    页脚写死一行很容易在窄终端里被裁掉半截；折行后无论多窄都至少能看见前面的键。
    """
    rows, line = [], ""
    for key, label in pairs:
        piece = f"{key} {label}"
        if line and _width(line) + 3 + _width(piece) > max_w:
            rows.append(line)
            line = piece
        else:
            line = f"{line}   {piece}" if line else piece
    if line:
        rows.append(line)
    return rows


# --------------------------------------------------------------------- 通用面板
def panel_rect(h: int, w: int, *, items=0, desc: bool = False, hint_rows=(),
               extra_rows: int = 0, width: int = 44, min_w: int = 44,
               region_w: int = 0) -> tuple[int, int, int]:
    """不落笔地算出面板将占的 (top, box_h, box_w)。

    `draw_panel` 自己用它排版；调用方（如游戏内确认框要跟暂停菜单对齐）也用它算尺寸 ——
    复制一份公式迟早会算错。

    注意 **h 和 w 都是必须的**：早先只收 h，`region` 就退化成高度，于是窗口高 24 时
    所有面板的宽度都被压到 22 格 —— 表现为"确认框窄得像条缝、文字被截断"。
    """
    head = 2
    rows = head + items + max(0, extra_rows) + (1 if desc else 0) + len(hint_rows)
    box_h = rows + 2
    region = min(w, region_w) if region_w else w
    box_w = max(min_w, min(width, region - 2))
    return max(0, (h - box_h) // 2), box_h, box_w


def draw_panel(win, *, title: str, items, width: int, select: int = 0,
               desc: str = "", foot: str = "", hint_rows=(), extra_rows: int = 0,
               min_w: int = 44, boot: bool = False,
               region_w: int | None = None) -> tuple[int, int]:
    """居中的面板菜单：先刷空面板内部 → 逐项上色 → 最后画边框（边框永远压在最上层）。

    items 每项是 `(文本, 副文本)`：副文本右对齐，只给当前选中项上色。
    `select` 是 **items 的下标**（不含标题那两行）—— 曾经把它和"含标题的行号"比，
    结果光标行永远匹配不上、整屏没有一处反白；行号与下标在这里分开算，别再合并。
    `region_w` 限定"在哪块地方居中"：游戏内在游玩区里居中（不跨到侧栏上，否则会
    擦掉侧栏左边框却留下它的内容，看起来就是"金币"变"币"）。
    返回 (面板宽度, 左边界)，测试与调用方都靠它定位（不硬编码 ±1）。
    行数超出窗口时**从选中的那一项开始截**，光标永远留在画面里。
    """
    h, w = win.getmaxyx()
    region = min(w, region_w) if region_w else w
    head = 2                                    # 标题下的两行留白
    items = [(it[0], it[1] if len(it) > 1 else "") for it in items]

    start = 0                                   # 窗口太矮时滚动：只在 items 里滚
    avail = max(1, h - head - 4)                # 边框 + 分隔线 + 说明/提示各留一行
    if len(items) > avail:
        start = min(max(0, select - avail + 1), len(items) - avail)
        items = items[start:start + avail]

    body = ([("", "")] * head + items + [("", "")] * max(0, extra_rows)
            + ([("", "")] if desc else []) + [("", "") for _ in hint_rows])
    top, box_h, box_w = panel_rect(h, w, items=len(items), desc=bool(desc),
                                   hint_rows=hint_rows, extra_rows=extra_rows,
                                   width=width, min_w=min_w, region_w=region_w)
    left = max(0, (region - box_w) // 2)

    for i in range(max(0, box_h - 2)):          # 先清内部：否则下层的字形会透出来
        fill(win, top + 1 + i, left + 1, box_w - 2, " ", 0)   # put 自带越界保护

    for i, (text, note) in enumerate(body):
        if not text and not note:
            continue                            # 空行：只占位置，不落笔
        row = top + 1 + i
        if i - head + start == select:
            fill(win, row, left + 1, box_w - 2, " ", theme.attr("sel", boot))
            put(win, row, left + 2,
                clip(f"{theme.G['sel']} {text}", box_w - 6), theme.attr("sel", boot, True))
            if note:
                put(win, row, left + box_w - 3 - _width(note), clip(note, box_w - 6),
                    theme.attr("sel", boot))
        else:
            put(win, row, left + 2, clip(f"  {text}", box_w - 6), theme.attr("bright", boot))
            if note:
                put(win, row, left + box_w - 3 - _width(note), clip(note, box_w - 6),
                    theme.attr("dim", boot))

    inner = top + 1 + head + len(items) + max(0, extra_rows)   # 选项之后：说明 / 提示
    if desc:
        put(win, inner, left + 2, clip(desc, box_w - 4), theme.attr("info", boot))
        inner += 1
    for text in hint_rows:
        put(win, inner, left + 2, clip(text, box_w - 4), theme.attr("dim", boot))
        inner += 1

    frame(win, top, left, box_h, box_w, title, theme.attr("frame", boot),
          foot=foot, foot_attr=theme.attr("dim", boot))
    # 分隔线画在边框之后：它的两端是 ├ ┤，正好接到左右边框上
    rule(win, top + 2, left, box_w, "", theme.attr("frame", boot), ends=("lt", "rt"))
    return box_w, left


def _drain(win) -> int:
    """取一个有效按键：吞掉重画期间堆积的 KEY_RESIZE（拖动窗口会灌进一长串）。"""
    key = win.getch()
    guard = 0
    while key == curses.KEY_RESIZE and guard < 64:
        key = win.getch()
        guard += 1
    return key


def _too_small(win, need: str, no_color: bool, extra: str = "Esc 退出") -> None:
    h, w = win.getmaxyx()
    center(win, h // 2, "终端窗口太小", theme.attr("bad", no_color, True))
    center(win, h // 2 + 1, f"{need}需要 {MIN_W}x{MIN_H}，当前 {w}x{h}",
           theme.attr("amber", no_color))
    if h > 4:
        center(win, h - 1, extra, theme.attr("dim", no_color))
    win.noutrefresh()
    curses.doupdate()


def _vital(meta: dict) -> str:
    """存档摘要里的"生命 19/31"，以及它在生命条上的颜色。

    新存档直接存了 hp/max_hp；旧存档没有，就按建角规则重算一份满血值 —— 显示"满血"
    是个善意的近似，总比空着或显示 0/0 强。
    """
    hp, max_hp = int(meta.get("hp") or 0), int(meta.get("max_hp") or 0)
    if max_hp <= 0:
        from ..content import load as load_content
        try:
            content = load_content()
            klass = content.klass(meta.get("class_id") or "warrior")
            race = content.race(meta.get("race_id") or "human")
        except (KeyError, OSError, ValueError):
            return "", "good"
        max_hp = int(klass.get("hit_die", 8)) + int(race.get("hp_bonus", 0)) + 3
        hp = max_hp
    return f"生命 {hp}/{max_hp}", theme.hp_color(hp, max_hp)


# --------------------------------------------------------------------- 开始页
def start_screen(stdscr, no_color: bool = False, *, title: str = TITLE) -> str:
    """开始页。返回 'new' | 'load' | 'roster' | 'quit'。

    ↑↓ 移动、回车确认（也接受 W/S、j/k 与 1-4 直选）。每一屏都能只用方向键走完，
    所以玩家不必先学键位就能进游戏。
    """
    theme.init_colors(no_color)
    stdscr.keypad(True)
    curses.curs_set(0)
    hint_rows = _hint_rows([("↑↓", "选择"), ("回车", "确认"), ("1-4", "直选"),
                            ("Esc", "退出")], 44)
    select = 0
    while True:
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        if w < MIN_W or h < MIN_H:
            _too_small(stdscr, "开始页", no_color)
            if _drain(stdscr) == 27:
                return "quit"
            continue

        saves = save_mod.index()
        items = [
            ("新的冒险", "选择职业与种族，进入地牢"),
            ("读取存档", f"{len(saves)} 个存档" if saves else "暂无存档"),
            ("名人堂", f"{len(save_mod.read_roster())} 位冒险者"),
            ("退出游戏", "Esc"),
        ]
        logo = LOGO if h >= 26 or w >= 100 else LOGO_COMPACT
        top = max(1, h // 2 - (len(logo) + len(items) + 11))
        for i, line in enumerate(logo):
            center(stdscr, top + i, line, theme.attr("amber", no_color, True))
        center(stdscr, top + len(logo) + 1, title, theme.attr("bright", no_color, True))
        center(stdscr, top + len(logo) + 2, SUBTITLE, theme.attr("dim", no_color))
        center(stdscr, top + len(logo) + 3, TAGLINE, theme.attr("magic", no_color))

        draw_panel(stdscr, title=f" {title} · 开始 ", items=items, width=46,
                   select=select, desc=items[select][1], foot="回车开始",
                   hint_rows=hint_rows, min_w=46, boot=no_color)

        key = _drain(stdscr)
        if key in MENU_UP:
            select = (select - 1) % len(items)
        elif key in MENU_DOWN:
            select = (select + 1) % len(items)
        elif 0 <= key < 256 and chr(key) in "1234":
            select = int(chr(key)) - 1
        elif key in ENTER_KEYS or (0 <= key < 256 and chr(key) == " "):
            choice = START_CHOICES[select]
            if choice == "roster":
                lobby_screen(stdscr, no_color)
                continue
            return choice
        elif key == 27:
            return "quit"


# ------------------------------------------------------------------ 存档管理
def save_list_rows(entries, select: int, rows: int) -> tuple[int, int]:
    """列表可见窗口 (start, end)：跟随选中项滚动（滚动提示也由它推）。"""
    rows = max(1, rows)
    if len(entries) <= rows:
        return 0, len(entries)
    start = min(max(0, select - rows + 1), len(entries) - rows)
    return start, start + rows


def _draw_save_list(scr, top: int, left: int, height: int, width: int,
                    entries, select: int, boot: bool) -> None:
    """左栏：一行一个存档（名字 · 等级 · 时间），选中行整行反白。

    宽度够时在行尾显示滚动提示；不够时整条丢掉 —— 宁可少一句提示，也不能顶破边框。
    """
    if not entries:
        # 空状态只在右栏讲一遍：两栏说同一句话会显得界面"喊了两嗓子"
        put(scr, top, left, clip("（空）", width), theme.attr("mem", boot))
        return
    start, end = save_list_rows(entries, select, height)
    note_w = 3 if width >= 34 else 0
    for i, e in enumerate(entries[start:end]):
        row, idx = top + i, start + i
        name = e["name"] + (f"  Lv{e['level']}" if e["level"] else "")
        if e["error"]:
            name = f"{e['name'] or e['file']}  损坏"
        date = (e.get("date") or "")[5:]        # 只留"月-日 时:分"
        text = f"{pad_to(clip(name, width - note_w - 12), width - note_w - 12)} {date:<11}"
        if idx == select:
            fill(scr, row, left - 1, width + 1, " ", theme.attr("sel", boot))
            put(scr, row, left, clip(text, width + 1), theme.attr("sel", boot, True))
        else:
            put(scr, row, left, clip(text, width), theme.attr("bad" if e["error"] else "bright",
                                                             boot))
    if not note_w:
        return
    if start:
        put(scr, top, left + width - note_w, f"↑{start}", theme.attr("dim", boot))
    if end < len(entries):
        put(scr, top + height - 1, left + width - note_w, f"↓{len(entries) - end}",
            theme.attr("dim", boot))


def _detail_lines(entry, width: int, boot: bool):
    """右栏内容：`(文本, 颜色, 加粗)` 或 `("bar", 比例, 颜色, 数值文本)`。"""
    if entry is None:
        return [("左边还没有存档。", "mem", False), ("", "", False),
                ("开始新游戏后按 F5 存档，", "dim", False),
                ("存档就会出现在这里。", "dim", False)]
    if entry["error"]:
        return [(entry["file"], "bad", True), ("读取失败（文件损坏或结构不认识）", "bad", False),
                ("", "", False), (clip(f"原因：{entry['error']}", width), "dim", False),
                ("", "", False), ("按 D 删除这个文件，", "amber", False),
                ("或回车看别的存档。", "amber", False)]

    lines = [(entry["name"], "bright", True),
             (f"{entry['race']}·{entry['klass']} {entry['level']}级", "amber", False)]
    hp, hp_color = _vital(entry)
    if hp:
        lines.append((hp, hp_color, False))
    lines.append(("", "", False))
    depth = entry["depth"] or 1
    lines.append(("bar", min(MAX_DEPTH, max(0, depth)) / MAX_DEPTH, "bright",
                  f"{depth}/{MAX_DEPTH}"))
    lines.append((f"回合 {entry['turn']}    金币 {entry['gold']}", "gold", False))
    lines.append(("", "", False))
    lines.append((clip(f"存档 {entry['file']}", width), "info", False))
    lines.append((f"时间 {entry.get('date') or '—'}", "dim", False))
    if entry["depth"] >= MAX_DEPTH:
        lines.append(("已抵达最深处", "magic", False))
    return lines


def _draw_save_detail(scr, top: int, left: int, height: int, width: int,
                      entry, boot: bool) -> None:
    for i, item in enumerate(_detail_lines(entry, width, boot)):
        if i >= height:
            break
        if item[0] == "bar":
            _, frac, color, text = item
            put(scr, top + i, left, "深度", theme.attr("dim", boot))
            bar_w = 10
            used = bar(scr, top + i, left + 5, bar_w, frac, color,
                       attr_fn=lambda n, b=False: theme.attr(n, boot, b))
            put(scr, top + i, left + 5 + used + 1, text, theme.attr("bright", boot))
            continue
        text, color, bold = item
        put(scr, top + i, left, clip(text, width), theme.attr(color, boot, bold))


def _draw_save_manager(scr, no_color: bool, entries, select: int, message: str) -> tuple[int, int]:
    """画存档管理整屏，返回 (box_w, list_right_x)，供测试定位。"""
    h, w = scr.getmaxyx()
    box_h = max(9, min(h - 2, 22))
    box_w = max(76, min(96, w - 4))
    top = max(0, (h - box_h) // 2)
    left = max(0, (w - box_w) // 2)
    list_w = max(32, min(46, box_w // 2))
    for i in range(box_h - 2):
        fill(scr, top + 1 + i, left + 1, box_w - 2, " ", 0)

    _draw_save_list(scr, top + 2, left + 3, box_h - 4, list_w - 4,
                    entries, select, no_color)
    _draw_save_detail(scr, top + 2, left + list_w + 2,
                      box_h - 4, box_w - list_w - 5,
                      entries[select] if entries else None, no_color)

    frame(scr, top, left, box_h, box_w, "存档管理", theme.attr("frame", no_color),
          foot=f"共 {len(entries)} 个存档" if entries else "暂无存档",
          foot_attr=theme.attr("dim", no_color))
    rule(scr, top + 1, left, box_w, "", theme.attr("frame", no_color), ends=("lt", "rt"))
    rule(scr, top + 2, left + list_w, box_h - 3, "", theme.attr("frame", no_color),
         ends=("tt", "bt"))
    return box_w, left + list_w


def save_manager_screen(stdscr, no_color: bool = False):
    """存档管理：↑↓ 选、回车读、D 删、Esc 返回。返回 Game 或 None。

    这个界面存在的意义就是"不用输命令也能看存档"：`--list-saves` 仍然留给脚本，
    但玩家在开始页选「读取存档」、或在游戏里按 Esc →「存档管理」就能进来。
    """
    theme.init_colors(no_color)
    stdscr.keypad(True)
    curses.curs_set(0)
    select, message = 0, ""
    while True:
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        if w < MIN_W or h < MIN_H:
            _too_small(stdscr, "存档管理", no_color, extra="Esc 返回")
            if _drain(stdscr) == 27:
                return None
            continue

        entries = save_mod.index()
        if select >= len(entries):
            select = max(0, len(entries) - 1)
        _draw_save_manager(stdscr, no_color, entries, select, message)
        hint_bar(stdscr, h - 1, w,
                 _hint_cells([("↑↓", "选择"), ("回车", "读取"), ("D", "删除"),
                              ("Esc", "返回")]), attr_fn=theme.attr)
        if message:                     # 必须画在 hint_bar **之后**：它会整行刷底色
            put(stdscr, h - 1, max(1, w - _width(message) - 2), message,
                theme.attr("gold", no_color, True))
        stdscr.noutrefresh()
        curses.doupdate()

        key = _drain(stdscr)
        if key in MENU_UP or key in MENU_DOWN or key in (curses.KEY_HOME, curses.KEY_END):
            message = ""                # 移动光标就收掉上一条提示（其余动作会重设它）
        if key in MENU_UP:
            select = max(0, select - 1)
        elif key in MENU_DOWN:
            select = min(max(0, len(entries) - 1), select + 1)
        elif key == curses.KEY_HOME:
            select = 0
        elif key == curses.KEY_END:
            select = max(0, len(entries) - 1)
        elif key in ENTER_KEYS:
            if not entries:
                message = "还没有存档：开始新游戏后按 F5 保存。"
                continue
            if entries[select]["error"]:
                message = "这个存档读不动，按 D 可以删掉。"
                continue
            game = load_screen(stdscr, entries[select], no_color)
            if game is None:
                message = "读取失败：文件可能已被移动或损坏。"
                continue
            return game
        elif key in (ord("d"), ord("D")):
            if not entries:
                continue
            entry = entries[select]
            stdscr.erase()          # 清掉列表再问：确认框不与列表叠在一起
            stdscr.noutrefresh()
            curses.doupdate()
            if confirm_choice(stdscr, f"删除存档「{entry['name']}」？",
                              detail="删除后无法恢复。", no_color=no_color):
                try:
                    save_mod.delete_save(entry["path"])
                except OSError as exc:
                    message = f"删除失败：{exc}"
                else:
                    message = f"已删除 {entry['file']}"
                    select = max(0, select - 1)
        elif key == 27 or (0 <= key < 256 and chr(key) in "qQ"):
            return None


def load_screen(stdscr, entry, no_color: bool = False):
    """读档中转屏：大存档要花一点时间，给个明确的提示（失败返回 None）。"""
    stdscr.erase()
    h, w = stdscr.getmaxyx()
    center(stdscr, max(0, h // 2 - 2), "正在读取存档…", theme.attr("bright", no_color, True))
    center(stdscr, max(0, h // 2 - 1), clip(str(entry.get("name", "")), max(4, w - 4)),
           theme.attr("amber", no_color))
    center(stdscr, max(0, h // 2 + 1),
           clip(f"第 {entry.get('depth') or 1} 层 · {entry.get('turn') or 0} 回合",
                max(4, w - 4)), theme.attr("dim", no_color))
    stdscr.noutrefresh()
    curses.doupdate()
    return load_game(entry["path"])


def load_game(path):
    """读存档；失败返回 None（界面上给提示，不把异常抛给玩家）。

    除了 IO/JSON/缺字段，还兜住 IndexError/AttributeError：结构"看着像存档、
    其实缺斤少两"的文件（手工改过、别的版本写的）会在这两种异常上炸出来。
    """
    try:
        return save_mod.load_game(path)
    except (OSError, ValueError, KeyError, TypeError, IndexError, AttributeError):
        return None


def confirm_choice(stdscr, question: str, *, detail: str = "", footer: str = "←→ 选择 · 回车确认",
                   no_color: bool = False, yes: str = "确定", no: str = "取消",
                   boot: bool = False) -> bool:
    """[确定 / 取消] 居中确认框 —— ←→（或 Tab）切换，回车确认，Esc 当作取消。

    调用方负责**先画好自己的背景**（列表/游戏画面），这里只补一块面板上去：
    确认框不叠在另一块面板上 —— 两个错位的框叠在一起，看起来就是界面坏了。
    危险操作默认停在「取消」上：一路上都在敲回车的人不会误删存档。
    """
    theme.init_colors(no_color)
    h, w = stdscr.getmaxyx()
    body = clip(question + (f"    {detail}" if detail else ""), max(16, min(46, w - 12)))
    select = 1                              # 默认停在「取消」
    while True:
        draw_panel(stdscr, title="请确认", items=[(yes, ""), (no, "")],
                   width=min(_width(body) + 10, w - 2), select=select, desc=body,
                   foot=footer, min_w=34, boot=no_color or boot)
        stdscr.noutrefresh()
        curses.doupdate()
        key = _drain(stdscr)
        if key in (curses.KEY_LEFT, curses.KEY_RIGHT, ord("\t"), curses.KEY_BTAB,
                   ord("h"), ord("l")):
            select = 1 - select
        elif key in ENTER_KEYS or (0 <= key < 256 and chr(key) in "yY"):
            return select == 0
        elif key in (27, ord("n"), ord("N")):
            return False


# --------------------------------------------------------------------- 名人堂
ROSTER_HEAD = (pad_to("名字", 12) + pad_to("种族", 7) + pad_to("职业", 7)
               + pad_to("等级", 6) + pad_to("深度", 6) + pad_to("结果", 6)
               + pad_to("金币", 8) + "回合")


def roster_rows(entries, limit: int = 14):
    """名人堂行：表头 + 最近 limit 条（游戏内 R 浮层与开始页共用）。"""
    rows = [(ROSTER_HEAD, "frame")]
    for e in entries[-limit:]:
        won = e.get("result") == "won"
        rows.append((pad_to(str(e.get("name", "—")), 12)
                     + pad_to(str(e.get("race", "—")), 7)
                     + pad_to(str(e.get("class", "—")), 7)
                     + pad_to(f"{e.get('level', 0)}级", 6)
                     + pad_to(str(e.get("depth", 0)), 6)
                     + pad_to("胜利" if won else "阵亡", 6)
                     + pad_to(str(e.get("gold", 0)), 8)
                     + str(e.get("turns", 0)),
                     "good" if won else "bad"))
    return rows


def lobby_screen(stdscr, no_color: bool = False) -> None:
    """名人堂面板：从开始页进来的只读名册（游戏内按 R 看的是同一份数据）。"""
    theme.init_colors(no_color)
    stdscr.keypad(True)
    while True:
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        if w < MIN_W or h < MIN_H:
            _too_small(stdscr, "名人堂", no_color)
            if _drain(stdscr) == 27:
                return
            continue
        entries = save_mod.read_roster()
        body = [("还没有冒险者留下战绩。", "mem")] if not entries else roster_rows(entries)
        if entries:
            body += [("", ""), (f"共 {len(entries)} 位冒险者（显示最近 14 位）", "dim")]
        body_w = max([_width(t) for t, _ in body] + [24])
        box_w = max(44, min(body_w + 6, w - 4))
        box_h = min(h - 2, len(body) + 2)
        top = max(0, (h - box_h) // 2)
        left = max(0, (w - box_w) // 2)
        for i in range(box_h - 2):
            fill(stdscr, top + 1 + i, left + 1, box_w - 2, " ", 0)
        for i, (text, color) in enumerate(body[:box_h - 2]):
            put(stdscr, top + 1 + i, left + 2, clip(text, box_w - 4),
                theme.attr(color, no_color))
        frame(stdscr, top, left, box_h, box_w, "名人堂", theme.attr("frame", no_color),
              foot="任意键返回", foot_attr=theme.attr("dim", no_color))
        stdscr.noutrefresh()
        curses.doupdate()
        key = _drain(stdscr)
        if key == curses.KEY_RESIZE:
            continue
        return


# ------------------------------------------------------------------ 建角界面
def _creation_layout(h: int, w: int) -> dict:
    """建角界面的分行（自适应终端高度）。

    硬性要求：4 个职业/种族选项必须完整可见，页脚不许盖住列表。
    空间不够时依次舍弃：提示 → 预览 → 说明，但"姓名 + 两个选项栏 + 页脚"永远保留。
    """
    name_row = 3
    panel_top = name_row + 2
    panel_h = 6                      # 上下边框 + 4 个选项
    blurb = panel_top + panel_h + 1
    footer = h - 4                   # 框内最后一行（下边框在 h-3）
    preview_top = blurb + 2
    return {
        "name": name_row, "panel_top": panel_top, "panel_h": panel_h,
        "blurb": blurb, "footer": footer,
        "preview_top": preview_top,
        "show_blurb": blurb + 1 < footer,
        "show_preview": preview_top + 3 < footer,
        "show_tips": preview_top + 3 + 3 < footer,
    }


def creation_screen(stdscr, no_color: bool = False, *, initial_name: str = "",
                    initial_class: str | None = None, initial_race: str | None = None):
    """建角：输入姓名，↑↓ 选择职业与种族。返回 (name, class_id, race_id)。

    initial_* 用来预填命令行（--name/--class/--race）给的值，避免用户已经写过的参数被丢掉。
    """
    from ..content import load as load_content
    content = load_content()
    class_ids = ["warrior", "wizard", "cleric", "rogue"]
    race_ids = ["human", "elf", "dwarf", "gnome"]

    def label(entry: dict) -> str:
        """中文名优先；若数据表里另有英文名则附在后面。"""
        zh = entry.get("name_zh") or entry.get("name", "")
        en = entry.get("name", "")
        return f"{zh}（{en}）" if en and en != zh and en.isascii() else zh

    theme.init_colors(no_color)  # 建角界面在 Tui 之前就要用配色
    a = lambda n, b=False: theme.attr(n, no_color, b)  # noqa: E731

    name = (initial_name or "").strip()[:14]
    focus = 0  # 0 = 职业栏，1 = 种族栏
    ci = class_ids.index(initial_class) if initial_class in class_ids else 0
    ri = race_ids.index(initial_race) if initial_race in race_ids else 0
    # 建角跑在 Tui 之前，别指望调用方开过 keypad：没开时方向键会以 ESC 序列到达，
    # 命中下面 `key == 27` 的分支直接把游戏退出。这里自己开一次（幂等）。
    stdscr.keypad(True)
    curses.curs_set(1)
    while True:
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        if w < MIN_W or h < MIN_H:  # 太小就别画半截界面（游戏内也是同样的提示）
            _too_small(stdscr, "建角", no_color)
            if _drain(stdscr) == 27:
                raise SystemExit(0)
            continue
        R = _creation_layout(h, w)
        frame(stdscr, 1, 2, h - 3, w - 5, "DND · 创建冒险者", a("frame"))
        put(stdscr, R["name"], 4, "姓名", a("dim"))
        put(stdscr, R["name"], 4 + 5, name + "_", a("bright", True))

        # 两栏选项：职业 / 种族
        col_w = min(30, (w - 14) // 2)
        boxes = [(4, "职业", class_ids, ci, focus == 0, content.klass),
                 (4 + col_w + 4, "种族", race_ids, ri, focus == 1, content.race)]
        for bx, head, ids, sel, active, lookup in boxes:
            # 活动栏用最亮的琥珀 + 加粗，非活动栏落到最暗一档。
            # 这里不能拿 "far" 当非活动色：它(205,140,0)比 "frame"(150,110,55)还亮，
            # 会把光标所在的那一栏衬得比非活动栏更不起眼 —— 焦点就"看不见"了。
            frame(stdscr, R["panel_top"], bx, R["panel_h"], col_w, head,
                  a("amber" if active else "mem", active))
            for i, oid in enumerate(ids):
                row = R["panel_top"] + 1 + i
                item = f"{i + 1}. {label(lookup(oid))}"
                if i != sel:
                    put(stdscr, row, bx + 2, clip(f"  {item}", col_w - 4), a("dim"))
                elif active:
                    # 光标行：整行反白 + ▸。全屏只有活动栏会出现这个标记，一眼可辨。
                    fill(stdscr, row, bx + 1, col_w - 2, " ", a("sel"))
                    put(stdscr, row, bx + 2,
                        clip(f"{theme.G['sel']} {item}", col_w - 4), a("sel", True))
                else:
                    # 非活动栏只标出"当前选的是哪个"（·），不反白：
                    # 两栏都反白时用户看不出 ↑↓ 会动哪一栏，就会以为种族栏选不了。
                    put(stdscr, row, bx + 2,
                        clip(f"{theme.G['dot']} {item}", col_w - 4), a("amber"))

        klass = content.klass(class_ids[ci])
        race = content.race(race_ids[ri])
        if R["show_blurb"]:
            put(stdscr, R["blurb"], 5, clip(klass["blurb"], w - 12), a("dim"))
            put(stdscr, R["blurb"] + 1, 5, clip(race["blurb"], w - 12), a("dim"))
        if R["show_preview"]:
            mods = " ".join(f"{ATTR_ZH.get(k, k)} {v:+d}" for k, v in race.get("mods", {}).items())
            frame(stdscr, R["preview_top"], 4, 4, w - 9, "预览", a("mem"))
            put(stdscr, R["preview_top"] + 1, 6,
                clip(f"{label(race)}·{label(klass)}     生命骰 d{klass['hit_die']}     "
                     f"初始生命 +{3 + int(race.get('hp_bonus', 0))}    "
                     f"每级法力 {klass.get('mp_per_level', 0)}", w - 13), a("info"))
            put(stdscr, R["preview_top"] + 2, 6,
                clip(f"视野 {BASE_FOV + int(race.get('fov_bonus', 0))}    {mods or '属性无调整'}",
                     w - 13), a("magic"))
        if R["show_tips"]:
            for i, (text, color) in enumerate(creation_tips()):
                put(stdscr, R["preview_top"] + 4 + i, 5, clip(text, w - 12), a(color))
        put(stdscr, R["footer"], 5,
            "↑↓ 选择    Tab / ←→ 切换职业与种族    1-4 直选    回车开始    Esc 退出", a("dim"))
        stdscr.noutrefresh()
        curses.doupdate()
        key = _drain(stdscr)
        if key == curses.KEY_RESIZE:
            continue
        if key == curses.KEY_UP:
            if focus == 0:
                ci = (ci - 1) % len(class_ids)
            else:
                ri = (ri - 1) % len(race_ids)
        elif key == curses.KEY_DOWN:
            if focus == 0:
                ci = (ci + 1) % len(class_ids)
            else:
                ri = (ri + 1) % len(race_ids)
        elif key in FOCUS_KEYS:
            focus = 1 - focus
        elif 0 <= key < 256 and chr(key) in "1234":
            if focus == 0:
                ci = int(chr(key)) - 1
            else:
                ri = int(chr(key)) - 1
        elif key in (curses.KEY_BACKSPACE, 127, 8):
            name = name[:-1]
        elif key in ENTER_KEYS:
            curses.curs_set(0)
            return (name.strip() or "冒险者"), class_ids[ci], race_ids[ri]
        elif key == 27:
            raise SystemExit(0)
        elif 0 <= key < 256 and chr(key).isprintable() and len(name) < 14:
            name += chr(key)


# ---------------------------------------------------------------- 背景故事
PROLOGUE_TITLE = "序章 · 被遗忘的深渊"


def _flowed_lines(page: dict, width: int) -> list[tuple[str, str]]:
    """把一页的段落折成屏幕行；空行原样保留（段落之间靠它留白）。"""
    out: list[tuple[str, str]] = []
    for text, color in page["lines"]:
        if not text:
            out.append(("", color))
            continue
        for piece in wrap(text, max(8, width)):
            out.append((piece, color))
    return out


def prologue_screen(stdscr, name: str, no_color: bool = False) -> None:
    """建角之后展示序章：**世界**（这一切是怎么来的）→ **入井**（你怎么进地牢、要知道什么）。

    ↑↓ 滚动、←→ / PgUp/PgDn 翻页、回车/空格 进入地牢、Esc 跳过。
    这一屏是"读"不是"选"：没有反白光标，任何一键都能走完全程，而且**必定回到游戏**
    —— 角色已经建好了，Esc 在这里只能跳过故事，不能取消这一局。
    """
    from .. import lore

    theme.init_colors(no_color)
    stdscr.keypad(True)
    curses.curs_set(0)
    book = lore.pages(name)
    page, scroll = 0, 0
    while True:
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        if w < MIN_W or h < MIN_H:
            _too_small(stdscr, "序章", no_color, extra="按任意键进入地牢")
            if _drain(stdscr) == curses.KEY_RESIZE:
                continue
            return

        box_w = max(40, min(96, w - 4))
        box_h = max(6, h - 2)
        top, left = 1, max(0, (w - box_w) // 2)
        inner_x, inner_w = left + 3, box_w - 6
        view = box_h - 2

        lines = _flowed_lines(book[page], inner_w)
        max_scroll = max(0, len(lines) - view)
        scroll = min(scroll, max_scroll)

        for i in range(view):
            idx = scroll + i
            if idx >= len(lines):
                break
            text, color = lines[idx]
            if text:
                put(stdscr, top + 1 + i, inner_x, clip(text, inner_w),
                    theme.attr(color, no_color))
        # 还有内容在框外时，在右边框内侧点一个箭头（不压正文）
        if scroll > 0:
            put(stdscr, top + 1, left + box_w - 3, theme.G["up"], theme.attr("dim", no_color))
        if scroll < max_scroll:
            put(stdscr, top + box_h - 2, left + box_w - 3, theme.G["down"],
                theme.attr("dim", no_color))

        frame(stdscr, top, left, box_h, box_w,
              f"深渊地牢 · {book[page]['title']}", theme.attr("frame", no_color),
              foot=f"{page + 1}/{len(book)} 页", foot_attr=theme.attr("dim", no_color))
        hint_bar(stdscr, h - 1, w, _hint_cells([
            ("↑↓", "滚动"), ("←→", "翻页"), ("回车", "进入地牢"), ("Esc", "跳过"),
        ]), attr_fn=lambda n, b=False: theme.attr(n, no_color, b))
        stdscr.noutrefresh()
        curses.doupdate()

        key = _drain(stdscr)
        if key == curses.KEY_RESIZE:
            continue
        if key == curses.KEY_UP:
            scroll = max(0, scroll - 1)
        elif key == curses.KEY_DOWN:
            scroll = min(max_scroll, scroll + 1)
        elif key in (curses.KEY_LEFT, curses.KEY_PPAGE):
            if scroll > 0:
                scroll = max(0, scroll - view)
            elif page > 0:                       # 回到上一页并停在它的末尾
                page, scroll = page - 1, 1 << 30
        elif key in (curses.KEY_RIGHT, curses.KEY_NPAGE):
            if scroll < max_scroll:
                scroll = min(max_scroll, scroll + view)
            elif page < len(book) - 1:
                page, scroll = page + 1, 0
        elif key in ENTER_KEYS or (0 <= key < 256 and chr(key) == " "):
            if scroll < max_scroll:              # 先读完整页，再翻页，读完才进场
                scroll = min(max_scroll, scroll + view)
            elif page < len(book) - 1:
                page, scroll = page + 1, 0
            else:
                return
        elif key == 27:
            return


def creation_tips():
    """建角页底部的三行提示（preview 与真实界面共用，改文案只改这一处）。"""
    return [
        (f"目标：下到第 {MAX_DEPTH} 层夺取「深渊遗物」，活着回来。", "good"),
        ("操作：WASD / 方向键移动 · g 拾取 · i 背包 · c 施法 · > 下楼", "dim"),
        ("地牢：走过的地方会留暗色记忆，敌人只在视野内可见。", "dim"),
    ]
