"""绘制辅助：框线、分隔线、进度条、标签行、按键提示。

所有函数都通过 `put()` 落笔，而 `put()` 会**按显示宽度**裁剪：中文一个字占两格，
按字符数裁剪会让长中文行在真终端上越过右边界（curses 会报错或被终端折行）。
项目里凡是画进界面的文本都走这里，就不必各写一份宽度判断。
"""

from __future__ import annotations

import unicodedata

import curses

from . import theme


def _width(text: str) -> int:
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in text)


def _room(win, y: int, x: int) -> int:
    """这一行从 x 起还能写几格。右下角那格留给 curses（写它会抛错）。"""
    h, w = win.getmaxyx()
    return max(0, w - x - (1 if y == h - 1 else 0))


def clip(text: str, room: int) -> str:
    """按显示宽度截断（放不下的宽字符整字丢弃，不劈成半格）。"""
    if room <= 0:
        return ""
    out, used = [], 0
    for ch in text:
        cw = 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
        if used + cw > room:
            break
        out.append(ch)
        used += cw
    return "".join(out)


def put(win, y: int, x: int, text: str, attr=0) -> None:
    """带边界保护与宽度裁剪的写字符串。"""
    if y < 0 or x < 0:
        return
    h, w = win.getmaxyx()
    if y >= h or x >= w:
        return
    text = clip(text, _room(win, y, x))
    if not text:
        return
    try:
        win.addstr(y, x, text, attr)
    except curses.error:
        pass


def fill(win, y: int, x: int, width: int, ch: str = " ", attr=0) -> None:
    """用单字符铺满一段（宽度按格算）。"""
    put(win, y, x, ch * max(0, width), attr)


def hline(win, y: int, x: int, length: int, ch: str, attr=0) -> None:
    put(win, y, x, ch * max(0, length), attr)


def vline(win, x: int, y: int, length: int, ch: str, attr=0) -> None:
    for i in range(max(0, length)):
        put(win, y + i, x, ch, attr)


def center(win, y: int, text: str, attr=0) -> None:
    h, w = win.getmaxyx()
    put(win, y, max(0, (w - _width(text)) // 2), text, attr)


def frame(win, y: int, x: int, h: int, w: int, title: str = "", attr=0,
          foot: str = "", foot_attr=None) -> None:
    """画一个方框，标题嵌在上边框里（而不是压在内容上）。

         ┌─ 冒险者档案 ─────────┐
         │ ...                  │
         └─────── # 墙  · 地面 ┘
    """
    if h < 2 or w < 4:
        return
    g = theme.G
    put(win, y, x, g["tl"] + g["h"] * (w - 2) + g["tr"], attr)
    vline(win, x, y + 1, h - 2, g["v"], attr)
    vline(win, x + w - 1, y + 1, h - 2, g["v"], attr)
    put(win, y + h - 1, x, g["bl"] + g["h"] * (w - 2) + g["br"], attr)
    if title:
        put(win, y, x + 2, f" {title} ", attr | curses.A_BOLD)
    if foot:
        fa = attr if foot_attr is None else foot_attr
        put(win, y + h - 1, max(x + 2, x + w - 3 - _width(foot)), f" {foot} ", fa)


def rule(win, y: int, x: int, w: int, label: str = "", attr=0, label_attr=None,
         ends: tuple[str, str] | None = None) -> None:
    """带标题的横向分隔线：├─ 消息 ───────────┤。

    ends 给了左右端字符时画成"框内分隔线"（带 T 形接口），
    正好接在竖边框上，视觉上把面板分成几段。
    """
    g = theme.G
    if w < 4:
        return
    if ends:
        put(win, y, x, g[ends[0]] + g["h"] * (w - 2) + g[ends[1]], attr)
    else:
        put(win, y, x, g["h"] * w, attr)
    if label:
        text = f" {label} "
        la = attr if label_attr is None else label_attr
        put(win, y, x + 2, text, la)
        put(win, y, x + 2 + _width(text), g["h"] * max(0, w - 4 - _width(text)), attr)


def pad_to(text: str, width: int) -> str:
    """按显示宽度右补空格（中文算两格，用它才能对齐）。"""
    return text + " " * max(0, width - _width(text))


def bar(win, y: int, x: int, width: int, frac: float, color: str,
        empty_color: str = "mem", attr_fn=None) -> int:
    """方块进度条，返回用了多少格。数值由调用方写在条右侧（见 tui._draw_seg）。

    压在条上需要在条内逐格换色，8 色终端里容易糊成一团，分开写反而更清楚。
    """
    g = theme.G
    width = max(1, width)
    frac = 0.0 if frac < 0 else (1.0 if frac > 1 else frac)
    full = int(round(frac * width))
    a = attr_fn or theme.attr
    fill(win, y, x, full, g["bar_full"], a(color))
    fill(win, y, x + full, width - full, g["bar_empty"], a(empty_color))
    return width


def hint_bar(win, y: int, width: int, items, attr_fn=None) -> None:
    """底部按键提示：按键用亮色、说明用暗色，扫一眼就能找到键。

    items: [(按键, 说明), ...]
    """
    a = attr_fn or theme.attr
    fill(win, y, 0, width, " ", a("title"))
    x = 1
    for key, label in items:
        if x >= width - 2:
            break
        put(win, y, x, key, a("title_bright", True))
        x += _width(key)
        put(win, y, x, " " + label + " ", a("title"))
        x += _width(label) + 2
