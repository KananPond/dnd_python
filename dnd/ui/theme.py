"""PLATO 风味配色与字形。

原版 PLATO IV 终端是 512×512 气体等离子屏、64×32 字符网格、黑底橙辉光
（见 docs/research-dossier.md 第一节）。我们在终端里用"琥珀色前景 + 暗色记忆格 +
框线"来近似这种观感。

三件事在这里统一定义：

1. **调色板**只写 RGB（`PALETTE`），256 色 / 8 色的索引在 `init_colors()` 里按
   色彩距离自动推导 —— 只有一个事实来源，改配色不用同步四张表。
   同一份 RGB 也被 out/preview.py 用来把界面渲染成 PNG 供人工审阅。
2. **字形**按终端能力在 Unicode / ASCII 两套之间切换（`configure_glyphs`）。
   注意框线、方块、`·`、`●` 这些字符在东亚洲终端里属于 "Ambiguous width"，
   可能被当成两格宽而撑破版面；`DND_ASCII=1`（或 `--ascii`）可整套退回 ASCII。
   地形字形（# . + > <）刻意保持 ASCII，避免落到 ambiguous 上，文档图解也就不用改。
3. **光照层次**（`light`）：visible 分近/远两档、记忆地形一档，形成"火把"纵深感。
"""

from __future__ import annotations

import contextlib
import curses
import os
import sys

# --------------------------------------------------------------------- 调色板
# 唯一的色彩事实来源：语义名 -> RGB。(bg=None 表示沿用终端默认背景)
PALETTE: dict[str, tuple[tuple[int, int, int], tuple[int, int, int] | None]] = {
    "amber":  ((255, 175, 0), None),      # 主色：墙体、标签、地面
    "bright": ((255, 247, 214), None),    # 热辉光：玩家、强调
    "bad":    ((255, 95, 95), None),      # 受伤、敌人
    "good":   ((135, 215, 135), None),    # 命中、拾取、恢复
    "info":   ((95, 175, 215), None),     # 提示、物品说明
    "gold":   ((255, 215, 95), None),     # 金币、警告
    "magic":  ((175, 135, 255), None),    # 法术、出处标记
    "dim":    ((150, 120, 70), None),     # 次要文本
    "far":    ((205, 140, 0), None),      # 视野内但离得远
    "mem":    ((112, 88, 48), None),      # 记忆中的地形（最暗的可见层）
    "frame":  ((150, 110, 55), None),     # 框线（压过内容会抢视线，故偏暗）
    "title":  ((28, 18, 4), (255, 175, 0)),   # 反白状态栏：黑字压琥珀底
    "title_bright": ((255, 247, 214), (255, 175, 0)),  # 反白栏里的高亮（深度进度条/按键）
    "panel":  ((150, 120, 70), (26, 20, 12)),  # 面板正文（薄底）
    "sel":    ((28, 18, 4), (255, 175, 0)),    # 选中行：反白
}

PANEL_BG = (26, 20, 12)

# 需要"褪色"版本的语义色（日志旧行用它做渐隐）
MUTED = ("amber", "bright", "bad", "good", "info", "gold", "magic", "dim")


def _mute(rgb: tuple[int, int, int], factor: float = 0.45) -> tuple[int, int, int]:
    """朝面板底色方向压暗，得到同一语义色的"旧消息"版本。"""
    return tuple(int(c * factor + b * (1 - factor)) for c, b in zip(rgb, PANEL_BG))


def _nearest_256(rgb: tuple[int, int, int]) -> int:
    """把 RGB 映射到 xterm-256 里最接近的颜色号（不使用除法的近似公式，直接比距离）。"""
    levels = (0, 95, 135, 175, 215, 255)
    cube = {}
    for r in range(6):
        for g in range(6):
            for b in range(6):
                cube[16 + 36 * r + 6 * g + b] = (levels[r], levels[g], levels[b])
    for i in range(24):  # 灰阶 232..255，步长 10 起
        v = 8 + i * 10
        cube[232 + i] = (v, v, v)
    return min(cube, key=lambda i: sum((a - b) ** 2 for a, b in zip(cube[i], rgb)))


_BASIC = [
    (curses.COLOR_BLACK, (0, 0, 0)), (curses.COLOR_RED, (205, 0, 0)),
    (curses.COLOR_GREEN, (0, 205, 0)), (curses.COLOR_YELLOW, (205, 205, 0)),
    (curses.COLOR_BLUE, (0, 0, 238)), (curses.COLOR_MAGENTA, (205, 0, 205)),
    (curses.COLOR_CYAN, (0, 205, 205)), (curses.COLOR_WHITE, (229, 229, 229)),
]


def _nearest_basic(rgb: tuple[int, int, int]) -> int:
    return min(_BASIC, key=lambda p: sum((a - b) ** 2 for a, b in zip(p[1], rgb)))[0]


def _pair_ids() -> dict[str, int]:
    """PAIRS 与 panel_* / *_muted 派生色的颜色对编号（1 起，0 留给默认）。"""
    names = list(PALETTE) + [f"{n}_muted" for n in MUTED]
    return {name: i + 1 for i, name in enumerate(names)}


PAIRS = _pair_ids()

# 供 out/preview.py 等外部消费者使用的 RGB 查询表（含 muted 派生色）
RGB: dict[str, tuple[tuple[int, int, int], tuple[int, int, int] | None]] = dict(PALETTE)
for _n in MUTED:
    RGB[f"{_n}_muted"] = (_mute(PALETTE[_n][0]), PALETTE[_n][1])

# --------------------------------------------------------------------- 字形
UNICODE_GLYPHS = {
    "tl": "┌", "tr": "┐", "bl": "└", "br": "┘",
    "h": "─", "v": "│", "lt": "├", "rt": "┤", "tt": "┬", "bt": "┴",
    "heavy_h": "━", "heavy_v": "┃",
    "bar_full": "█", "bar_half": "▓", "bar_empty": "░",
    "sel": "▸", "dot": "·", "sep": "·",
    "up": "↑", "down": "↓",
}
ASCII_GLYPHS = {
    "tl": "+", "tr": "+", "bl": "+", "br": "+",
    "h": "-", "v": "|", "lt": "+", "rt": "+", "tt": "+", "bt": "+",
    "heavy_h": "=", "heavy_v": "|",
    "bar_full": "#", "bar_half": "+", "bar_empty": "-",
    "sel": ">", "dot": ".", "sep": "|",
    "up": "^", "down": "v",
}

G: dict[str, str] = UNICODE_GLYPHS
_GLYPH_MODE: str | None = None


def _terminal_is_utf8() -> bool:
    enc = (getattr(sys.stdout, "encoding", "") or "").lower()
    return "utf" in enc


def configure_glyphs(mode: str | None = None) -> str:
    """选择字形集：auto | unicode | ascii。返回实际生效的模式。

    auto 只在两种情况下退回 ASCII：显式设了 DND_ASCII，或终端编码不是 UTF-8
    （东亚洲终端把框线当两格宽的情况无法自动探测，留给 --ascii 手动兜底）。

    显式指定的模式会被"钉住"：init_colors() 里也会调本函数，若每次都重新探测，
    调用方刚设好的 ascii 会被悄悄改回 unicode。
    """
    global G, _GLYPH_MODE
    want = mode or os.environ.get("DND_GLYPHS")
    if want == "auto":
        _GLYPH_MODE = None            # 显式要求重新探测
    elif want:
        _GLYPH_MODE = want            # 钉住显式选择
    if _GLYPH_MODE is None:
        _GLYPH_MODE = "ascii" if (os.environ.get("DND_ASCII") or not _terminal_is_utf8()) else "unicode"
    G = ASCII_GLYPHS if _GLYPH_MODE == "ascii" else UNICODE_GLYPHS
    return _GLYPH_MODE


def glyph_mode() -> str:
    return _GLYPH_MODE or "auto"


@contextlib.contextmanager
def glyph_override(mode: str):
    """临时切换字形集，退出时还原。

    存在的理由：`configure_glyphs(x)` 返回的是**切换后**的模式，
    调用方若写 `old = configure_glyphs("ascii")` 拿到的就是 "ascii"，
    还原时等于把 ascii 又设了一遍 —— 之后所有渲染都被悄悄钉在 ASCII。
    """
    previous = glyph_mode()
    configure_glyphs(mode)
    try:
        yield
    finally:
        configure_glyphs(previous)


# --------------------------------------------------------------------- 语义映射
KIND_COLOR = {
    "info": "amber", "good": "good", "bad": "bad", "warn": "gold",
    "gold": "gold", "item": "info", "magic": "magic", "level": "bright",
}
MONSTER_COLOR = {
    "brown": "gold", "green": "good", "white": "bright", "red": "bad",
    "magenta": "magic", "cyan": "info", "yellow": "gold",
}
# 地形字形保持 ASCII：这些字符在任何终端都是 1 格宽，不会踩 ambiguous 陷阱
TERRAIN = {0: "#", 1: ".", 2: "+", 3: ">", 4: "<"}
TERRAIN_COLOR = {0: "amber", 1: "far", 2: "gold", 3: "bright", 4: "info"}


def item_color(item) -> str:
    if item.kind in ("gold", "gem", "relic"):
        return "gold"
    if item.kind == "potion":
        return "good"
    if item.kind == "scroll":
        return "magic"
    return "info"


def light(distance: int, *, visible: bool = True) -> str:
    """火把光照：按到玩家的距离挑一档颜色名。

    视野边缘比脚下暗，形成纵深；看不见的地方落到"记忆"档（雾）。
    """
    if not visible:
        return "mem"
    if distance <= 4:
        return "amber"
    if distance <= 7:
        return "far"
    return "mem"


def hp_color(hp: int, max_hp: int) -> str:
    """生命条/数值按剩余比例变色：健康绿 -> 警戒金 -> 濒死红。"""
    if max_hp <= 0:
        return "bad"
    ratio = hp / max_hp
    if ratio > 0.6:
        return "good"
    if ratio > 0.25:
        return "gold"
    return "bad"


# --------------------------------------------------------------------- 颜色对
def init_colors(no_color: bool = False) -> None:
    configure_glyphs()
    if no_color or not curses.has_colors():
        return
    try:
        curses.start_color()
    except curses.error:
        return
    try:
        curses.use_default_colors()
    except curses.error:
        pass
    rich = curses.COLORS >= 256
    for name, pair in PAIRS.items():
        fg_rgb, bg_rgb = RGB[name]
        fg = _nearest_256(fg_rgb) if rich else _nearest_basic(fg_rgb)
        bg = -1
        if bg_rgb is not None:
            bg = _nearest_256(bg_rgb) if rich else _nearest_basic(bg_rgb)
        try:
            curses.init_pair(pair, fg, bg)
        except curses.error:  # 终端颜色对不够用：宁缺勿崩，缺的退回默认色
            pass


# no_color 模式下用属性位模拟"反白/变暗"，保住层次感
_NOCOLOR = {
    "title": curses.A_REVERSE,
    "sel": curses.A_REVERSE,
    "panel": 0,
    "dim": curses.A_DIM,
    "mem": curses.A_DIM,
    "far": curses.A_DIM,
}


def attr(name: str, no_color: bool = False, bold: bool = False, muted: bool = False,
         alt: bool = False):
    """取属性值。muted=旧消息渐隐；alt=强制反白（浮层选中行）。"""
    if muted:
        name = f"{name}_muted"
    a = curses.A_BOLD if bold else 0
    if alt:
        a |= curses.A_REVERSE
    if no_color or not curses.has_colors():
        base = _NOCOLOR.get(name.replace("_muted", ""), 0)
        if muted:
            base |= curses.A_DIM
        return a | base
    return a | curses.color_pair(PAIRS.get(name, 1))
