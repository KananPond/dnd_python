"""绘制辅助：安全写字符串、画框、居中文本。"""

from __future__ import annotations

import curses


def put(win, y: int, x: int, text: str, attr=0) -> None:
    """带边界保护与截断的写字符串（curses 在右下角写字会抛错）。"""
    if y < 0 or x < 0:
        return
    h, w = win.getmaxyx()
    if y >= h or x >= w:
        return
    room = w - x - 1
    if room <= 0:
        return
    try:
        win.addstr(y, x, text[:room], attr)
    except curses.error:
        pass


def hline(win, y: int, x: int, length: int, ch: str = "-", attr=0) -> None:
    if length <= 0:
        return
    put(win, y, x, ch * length, attr)


def box(win, y: int, x: int, h: int, w: int, title: str = "", attr=0) -> None:
    if h < 2 or w < 4:
        return
    put(win, y, x, "+" + "=" * (w - 2) + "+", attr)
    for i in range(1, h - 1):
        put(win, y + i, x, "|", attr)
        put(win, y + i, x + w - 1, "|", attr)
    put(win, y + h - 1, x, "+" + "=" * (w - 2) + "+", attr)
    if title:
        put(win, y, x + 2, f" {title} ", attr | curses.A_BOLD)


def center(win, y: int, text: str, attr=0) -> None:
    h, w = win.getmaxyx()
    put(win, y, max(0, (w - len(text)) // 2), text, attr)
