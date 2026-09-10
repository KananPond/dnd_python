"""PLATO 风味配色与字形。

原版 PLATO IV 终端是 512×512 气体等离子屏、64×32 字符网格、黑底橙辉光（见 docs/research-dossier.md 第一节）。
我们在终端里用"琥珀色前景 + 暗色记忆格 + 框线"来近似这种观感。
"""

from __future__ import annotations

import curses

# 语义配色 -> curses 颜色对编号
PAIRS = {
    "amber": 1,   # 主色：墙体、标签
    "bright": 2,  # 玩家、强调
    "bad": 3,     # 受伤、怪物
    "good": 4,    # 拾取、命中
    "info": 5,    # 提示
    "dim": 6,     # 记忆中的地形
    "gold": 7,    # 金币
    "magic": 8,   # 法术
    "title": 9,   # 标题栏
}

# 地图字形（ASCII，兼容一切终端；原版用的是 PLATO 专用字符图形）
TERRAIN = {0: "#", 1: ".", 2: "+", 3: ">", 4: "<"}
KIND_COLOR = {
    "info": "amber", "good": "good", "bad": "bad", "warn": "gold",
    "gold": "gold", "item": "info", "magic": "magic", "level": "bright",
}
MONSTER_COLOR = {
    "brown": "gold", "green": "good", "white": "bright", "red": "bad",
    "magenta": "magic", "cyan": "info", "yellow": "gold",
}


def item_color(item) -> str:
    if item.kind in ("gold", "gem", "relic"):
        return "gold"
    if item.kind == "potion":
        return "good"
    if item.kind == "scroll":
        return "magic"
    return "info"


def init_colors(no_color: bool = False) -> None:
    if no_color or not curses.has_colors():
        return
    curses.start_color()
    try:
        curses.use_default_colors()
    except curses.error:
        pass
    amber = 214 if curses.COLORS >= 256 else curses.COLOR_YELLOW
    pairs = [
        (PAIRS["amber"], amber, -1),
        (PAIRS["bright"], curses.COLOR_WHITE, -1),
        (PAIRS["bad"], curses.COLOR_RED, -1),
        (PAIRS["good"], curses.COLOR_GREEN, -1),
        (PAIRS["info"], curses.COLOR_CYAN, -1),
        (PAIRS["dim"], 240 if curses.COLORS >= 256 else curses.COLOR_BLUE, -1),
        (PAIRS["gold"], curses.COLOR_YELLOW, -1),
        (PAIRS["magic"], curses.COLOR_MAGENTA, -1),
        (PAIRS["title"], curses.COLOR_BLACK, amber),
    ]
    for idx, fg, bg in pairs:
        try:
            curses.init_pair(idx, fg, bg)
        except curses.error:
            pass


def attr(name: str, no_color: bool = False, bold: bool = False):
    a = 0
    if bold:
        a |= curses.A_BOLD
    if no_color or not curses.has_colors():
        return a | (curses.A_REVERSE if name == "title" else 0)
    pair = PAIRS.get(name, 1)
    return a | curses.color_pair(pair)
