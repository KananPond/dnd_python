"""curses 主界面：状态栏 / 地图视口 / 侧栏 / 消息日志 / 各类浮层。

布局（自上而下）：
  row 0            标题栏（反白）：身份 + 深度进度 + 回合
  row 1            体征栏：生命/法力/经验条、护甲、金币
  row 2..map_end   地图视口（以玩家为中心滚动，火把光照 + 记忆雾）
  右 侧（宽度 ≥ 100）冒险者档案面板，与地图共用上下边框
  row log_rule     消息分隔线
  row log_top..    消息日志（最近 5 条，越旧越暗）
  最后一行          按键提示

视觉约定：
  · 框线一律走 widgets.frame/rule，标题嵌在边框里，不压内容；
  · 所有文本走 widgets.put（按显示宽度裁剪），中文长行不会越界；
  · 地图地形字形保持 ASCII（# . + > <），配色承担"远/近/记忆"的层次。
"""

from __future__ import annotations

import curses
import os
from dataclasses import dataclass

from .. import save as save_mod
from ..game import Game
from ..level import MAX_DEPTH
from . import describe, screens, theme
from .screens import _creation_layout, creation_screen  # noqa: F401  （对外保留旧路径）
from .widgets import (_width, bar, center, clip, fill, frame, hint_bar, pad_to,
                      put, rule)

MIN_W, MIN_H = screens.MIN_W, screens.MIN_H
PAUSE_W = 44          # 暂停面板固定这个宽度（确认框要盖住它，宽高必须一致）
PAUSE_HINT = "↑↓ 选择    回车确认    Esc 返回"
LOG_LINES = 5
SIDE_W = 26
HEADER_ROWS = 2
_BOTTOM_ROWS = LOG_LINES + 2     # 分隔线 + 日志 + 提示栏

ATTR_ZH = screens.ATTR_ZH

MOVE_KEYS = {
    # 主键位：WASD；同时保留方向键、hjkl 与 yubn（斜向）
    ord("w"): (0, -1), ord("a"): (-1, 0), ord("s"): (0, 1), ord("d"): (1, 0),
    curses.KEY_UP: (0, -1), curses.KEY_DOWN: (0, 1),
    curses.KEY_LEFT: (-1, 0), curses.KEY_RIGHT: (1, 0),
    ord("k"): (0, -1), ord("j"): (0, 1), ord("h"): (-1, 0), ord("l"): (1, 0),
    ord("y"): (-1, -1), ord("u"): (1, -1), ord("b"): (-1, 1), ord("n"): (1, 1),
    curses.KEY_HOME: (-1, -1), curses.KEY_NPAGE: (1, 1),
}

HINTS = [
    ("WASD", "移动"), ("i", "背包"), ("c", "施法"), ("g", "拾取"),
    (">", "下楼"), ("<", "上楼"), ("?", "帮助"), ("F5", "存档"),
    ("R", "名册"), ("Esc", "菜单"), ("Q", "退出"),
]

# 浮层菜单（暂停菜单 / 存读档列表）里的上下移动与确认键
MENU_UP = screens.MENU_UP
MENU_DOWN = screens.MENU_DOWN
ENTER_KEYS = screens.ENTER_KEYS


@dataclass
class Layout:
    """一屏的分区。所有绘制都从这里取坐标，测试也用它定位（避免到处硬编码 ±1）。"""
    h: int
    w: int
    side: int          # 侧栏宽度（0 = 不显示）
    map_top: int
    map_left: int
    map_h: int
    map_w: int
    framed: bool       # 地图/侧栏是否带边框（窗口太矮时不画，省下两行给内容）
    log_rule: int
    log_top: int
    hint: int


class Tui:
    def __init__(self, stdscr, game: Game, *, debug: bool = False, no_color: bool = False):
        self.scr = stdscr
        self.game = game
        self.debug = debug
        self.no_color = no_color
        self.show_provenance = False
        self.roster_recorded = False
        self.message = ""
        theme.init_colors(no_color)
        curses.curs_set(0)
        self.scr.keypad(True)

    # ------------------------------------------------------------------ 属性
    def a(self, name: str, bold: bool = False, muted: bool = False, alt: bool = False):
        return theme.attr(name, self.no_color, bold, muted, alt)

    def layout(self) -> Layout:
        h, w = self.scr.getmaxyx()
        side = SIDE_W if w >= 100 else 0
        map_w = w - (side + 2 if side else 0)
        map_h = max(6, h - HEADER_ROWS - _BOTTOM_ROWS)
        return Layout(
            h=h, w=w, side=side,
            map_top=HEADER_ROWS, map_left=0, map_h=map_h, map_w=map_w,
            framed=map_h >= 12,
            log_rule=h - _BOTTOM_ROWS, log_top=h - _BOTTOM_ROWS + 1, hint=h - 1,
        )

    # ------------------------------------------------------------- 主循环
    def run(self) -> None:
        """跑一局（或读档后的一局）。返回 = 回到开始页（见 pause_screen 的返回值）。"""
        while True:
            self.draw()
            key = self.scr.getch()
            if key == curses.KEY_RESIZE:
                continue
            if self.game.state != "playing":
                if self.end_screen(key):
                    return
                continue
            self.handle_key(key)

    def handle_key(self, key: int) -> None:
        g = self.game
        if key in MOVE_KEYS:
            dx, dy = MOVE_KEYS[key]
            g.command(("move", dx, dy))
            return
        ch = chr(key) if 0 <= key < 256 else ""
        if ch in (".", "5", " "):
            g.command(("wait",))
        elif ch == ">":
            g.command(("descend",))
        elif ch == "<":
            g.command(("ascend",))
        elif ch in ("g", ","):
            g.command(("pickup",))
        elif ch == "i":
            self.inventory_screen()
        elif ch == "c":
            self.cast_screen()
        elif ch == "?":
            self.help_screen()
        elif ch == "R":
            self.roster_screen()
        elif ch == "P":
            self.show_provenance = not self.show_provenance
        elif key == curses.KEY_F5 or ch == "S":
            self.save_game_here()
        elif key == 27:                    # Esc：暂停菜单（原先只清一句提示，太浪费）
            self.pause_screen()
        elif ch == "x" and self.debug:
            g.command(("reveal",))
        elif ch == "t" and self.debug:
            self.teleport_screen()
        elif ch in ("Q",):
            if self.confirm("不保存并退出？"):
                raise SystemExit(0)

    def save_game_here(self) -> None:
        """存档并把路径写进消息日志（失败只报错，绝不打断这一局）。"""
        try:
            path = save_mod.save_game(self.game)
        except (OSError, TypeError, ValueError) as exc:
            self.game.message(f"保存失败：{exc}", "bad")
        else:
            self.game.message(f"已保存：{path}", "good")

    # ---------------------------------------------------------------- 绘制
    def draw(self) -> None:
        self.scr.erase()
        L = self.layout()
        if L.w < MIN_W or L.h < MIN_H:
            self.draw_too_small(L)
            return
        self.draw_header(L)
        self.draw_map(L)
        if L.side:
            self.draw_side(L)
        self.draw_log(L)
        self.draw_hint(L)
        if self.message:  # 瞬时提示：压在消息分隔线右端，不挡日志
            put(self.scr, L.log_rule, max(2, L.w - _width(self.message) - 2),
                self.message, self.a("gold", True))
        self.scr.noutrefresh()
        curses.doupdate()

    def draw_too_small(self, L: Layout) -> None:
        lines = [
            ("终端窗口太小", self.a("bad", True)),
            (f"需要 {MIN_W}x{MIN_H}，当前 {L.w}x{L.h}", self.a("amber")),
        ]
        top = max(0, L.h // 2 - 2)
        for i, (text, attr) in enumerate(lines):
            center(self.scr, top + i, text, attr)
        self.scr.noutrefresh()
        curses.doupdate()

    # ------------------------------------------------------------ 顶部两条
    def _vitals(self, L: Layout):
        """第 1 行的段落表：窗口太窄时从右往左整段丢弃，不会留下半截字。"""
        st = self.game.status()
        segs: list[tuple] = [
            ("text", st["name"], "bright", True),
            ("text", f"{st['race']}·{st['class']} {st['level']}级", "amber", False),
            ("bar", "生命", st["hp"], st["max_hp"], theme.hp_color(st["hp"], st["max_hp"])),
        ]
        if st["max_mp"]:
            segs.append(("bar", "法力", st["mp"], st["max_mp"], "magic"))
        segs.append(("text", f"护甲 {st['ac']}", "amber", False))
        segs.append(("bar", "经验", st["xp"], self._xp_next(), "info"))
        segs.append(("text", f"金币 {st['gold']}", "gold", False))
        return segs

    def draw_header(self, L: Layout) -> None:
        """第 0 行反白标题栏（身份 + 深度进度 + 回合）；第 1 行体征。

        注：第 0 行末尾必须是"回合 N"——tools/pty_smoke.py 靠它读回合数来判断
        移动是否真的发生了，改版时别把它挪到别处。
        """
        st = self.game.status()
        fill(self.scr, 0, 0, L.w, " ", self.a("title"))
        put(self.scr, 0, 2, "DND", self.a("title_bright", True))
        left = f" · 深渊地牢   第 {st['depth']} 层"
        put(self.scr, 0, 5, left, self.a("title", True))
        if self.debug:  # 放在左段末尾，避免和右对齐的回合数撞在一起
            put(self.scr, 0, 5 + _width(left) + 1, "[调试]", self.a("title_bright", True))
        # 深度进度条：反白底上用"亮块=已下潜 / 暗块=剩余"。
        # 空槽也用实心块（而不是 ░）—— ░ 在琥珀底上几乎看不见，进度条会像被截断。
        strip_used = theme.G["bar_full"] * min(MAX_DEPTH, max(0, st["depth"]))
        strip_left = theme.G["bar_full"] * max(0, MAX_DEPTH - st["depth"])
        right = f"深度 {st['depth']}/{MAX_DEPTH} "
        rx = max(3, L.w - _width(right) - MAX_DEPTH - _width(f"   回合 {st['turn']} ") - 1)
        put(self.scr, 0, rx, right, self.a("title"))
        put(self.scr, 0, rx + _width(right), strip_used, self.a("title_bright"))
        put(self.scr, 0, rx + _width(right) + _width(strip_used), strip_left, self.a("title"))
        put(self.scr, 0, rx + _width(right) + MAX_DEPTH,
            f"   回合 {st['turn']} ", self.a("title"))

        # 第 1 行：段落之间固定两格，扫读时不会粘在一起
        bar_w = 10 if L.w >= 100 else 6
        x = 2
        for seg in self._vitals(L):
            need = self._seg_width(seg, bar_w)
            if x + need >= L.w - 2:
                break
            self._draw_seg(seg, x, bar_w)
            x += need + 2

    def _seg_width(self, seg, bar_w: int) -> int:
        if seg[0] == "text":
            return _width(seg[1])
        _, label, value, maximum, _color = seg
        return _width(label) + 1 + bar_w + 1 + _width(f"{value}/{maximum}")

    def _draw_seg(self, seg, x: int, bar_w: int) -> None:
        if seg[0] == "text":
            _, text, color, bold = seg
            put(self.scr, 1, x, text, self.a(color, bold))
            return
        _, label, value, maximum, color = seg
        put(self.scr, 1, x, label, self.a("dim"))
        x += _width(label) + 1
        used = bar(self.scr, 1, x, bar_w, value / max(1, maximum), color, attr_fn=self.a)
        put(self.scr, 1, x + used + 1, f"{value}/{maximum}", self.a("bright"))

    def _xp_next(self) -> int:
        from ..content import load as load_content
        p = self.game.player
        return max(1, load_content().xp_for_level(p.level + 1))

    # ---------------------------------------------------------------- 地图
    def draw_map(self, L: Layout) -> None:
        g = self.game
        level = g.level()
        if L.framed:
            frame(self.scr, L.map_top, L.map_left, L.map_h, L.map_w,
                  f"地牢 · 第 {g.depth} 层", self.a("frame"),
                  foot=self._map_legend(), foot_attr=self.a("mem"))
            top, left = L.map_top + 1, L.map_left + 1
            height, width = L.map_h - 2, L.map_w - 2
        else:
            top, left, height, width = L.map_top, L.map_left, L.map_h, L.map_w
        # 视口：以玩家为中心，并夹在地图边界内
        vx = min(max(0, g.player.x - width // 2), max(0, level.w - width))
        vy = min(max(0, g.player.y - height // 2), max(0, level.h - height))
        for sy in range(height):
            y = vy + sy
            if y >= level.h:
                break
            for sx in range(width):
                x = vx + sx
                if x >= level.w:
                    break
                self._draw_cell(top + sy, left + sx, x, y, level)
        if L.framed:  # 玩家被视口夹住时，边框上标出"目标在框外"的方向
            self._map_hints(L, level, vx, vy)

    def _map_legend(self) -> str:
        return (f" {theme.TERRAIN[0]} 墙  {theme.TERRAIN[1]} 地面  {theme.TERRAIN[2]} 门  "
                f"{theme.TERRAIN[3]} 下楼  {theme.TERRAIN[4]} 上楼 ")

    def _map_hints(self, L: Layout, level, vx: int, vy: int) -> None:
        """把框外的关键目标（上下楼梯）指到边框上，避免满图找不到路。"""
        for spot, glyph, color in ((level.down, theme.TERRAIN[3], "bright"),
                                   (level.up, theme.TERRAIN[4], "info")):
            if not spot or not level.is_explored(*spot):
                continue
            sx, sy = spot[0] - vx, spot[1] - vy
            if 0 <= sx < L.map_w - 2 and 0 <= sy < L.map_h - 2:
                continue  # 已经在框里，不用提示
            if sx < 0:
                put(self.scr, L.map_top + L.map_h // 2, L.map_left, glyph, self.a(color, True))
            elif sx >= L.map_w - 2:
                put(self.scr, L.map_top + L.map_h // 2, L.map_left + L.map_w - 1, glyph, self.a(color, True))
            elif sy < 0:
                put(self.scr, L.map_top, L.map_left + max(1, min(L.map_w - 2, sx + 1)), glyph, self.a(color, True))
            else:
                put(self.scr, L.map_top + L.map_h - 1,
                    L.map_left + max(1, min(L.map_w - 2, sx + 1)), glyph, self.a(color, True))

    def _draw_cell(self, row: int, col: int, x: int, y: int, level) -> None:
        g = self.game
        if (x, y) == (g.player.x, g.player.y):
            put(self.scr, row, col, "@", self.a("bright", True))
            return
        visible = (x, y) in g.visible
        if not visible and not level.is_explored(x, y):
            return
        if visible:
            monster = level.monster_at(x, y)
            if monster:
                color = "bad" if monster.boss else theme.MONSTER_COLOR.get(monster.color, "bad")
                put(self.scr, row, col, monster.glyph, self.a(color, True))
                return
            items = level.items_at(x, y)
            if items:
                put(self.scr, row, col, items[0].glyph, self.a(theme.item_color(items[0]), True))
                return
        tile = level.tile(x, y)
        glyph = theme.TERRAIN.get(tile, "?")
        if tile in (3, 4):  # 楼梯：导航目标，始终用自己的颜色
            name = theme.TERRAIN_COLOR[tile] if visible else "mem"
            put(self.scr, row, col, glyph, self.a(name, visible))
            return
        dist = max(abs(x - g.player.x), abs(y - g.player.y))
        name = theme.light(dist, visible=visible)
        put(self.scr, row, col, glyph,
            self.a(name, bold=(visible and tile == 0 and dist <= 4)))

    # ---------------------------------------------------------------- 侧栏
    def _side_rows(self):
        """侧栏内容按"重要度"先后排列成 row 列表。

        行模型（draw_side 负责渲染）：
          ("sec", 标题)                     分段线：├─ 标题 ─┤
          ("line", 文本, 颜色, 加粗)         文本行
          ("bar", 标签, 比例, 颜色, 数值)     进度条行
          ("gap",)                          空行
        窗口太矮时从后往前被截掉，不会把边框顶掉。
        """
        g, p = self.game, self.game.player
        rows: list[tuple] = []
        rows.append(("line", p.name, "bright", True))
        race = p.race().get("name_zh") or p.race_name()
        rows.append(("line", f"{race}·{p.class_name()} {p.level}级", "amber", False))
        rows.append(("bar", "生命", p.hp / max(1, p.max_hp),
                     theme.hp_color(p.hp, p.max_hp), f"{p.hp}/{p.max_hp}"))
        if p.max_mp:
            rows.append(("bar", "法力", p.mp / max(1, p.max_mp), "magic", f"{p.mp}/{p.max_mp}"))
        rows.append(("bar", "经验", p.xp / self._xp_next(), "info", f"{p.xp}/{self._xp_next()}"))
        rows.append(("line", f"护甲 {p.ac()}    命中 +{p.attack_bonus()}", "amber", False))
        rows.append(("line", f"金币 {p.gold}", "gold", False))

        rows.append(("sec", "视野内"))
        monsters = g.visible_monsters()
        if not monsters:
            rows.append(("line", "没有敌人", "mem", False))
        for m in monsters[:6]:
            rows.append(("line", f"{m.glyph} {m.name_zh or m.name} {m.hp}/{m.max_hp}",
                         "bad", m.boss))

        if p.weapon or p.armor:
            rows.append(("sec", "装备"))
            if p.weapon:
                rows.append(("line", pad_to(p.weapon.name, 8) + describe.item_compact(p.weapon),
                             theme.item_color(p.weapon), False))
            if p.armor:
                rows.append(("line", pad_to(p.armor.name, 8) + describe.item_compact(p.armor),
                             theme.item_color(p.armor), False))

        rows.append(("sec", "属性"))
        attrs = list(p.attrs.items())
        for i in range(0, len(attrs), 2):
            rows.append(("line", "  ".join(f"{ATTR_ZH.get(k, k)} {v}" for k, v in attrs[i:i + 2]),
                         "dim", False))

        if p.buffs:
            rows.append(("sec", "状态"))
            for key, (amount, turns) in p.buffs.items():
                label = {"ac": "护甲", "attack": "命中"}.get(key, key)
                rows.append(("line", f"{label} +{amount}   {turns} 回合", "magic", False))

        rows.append(("sec", "背包"))
        for i, item in enumerate(p.inventory[:7]):
            tag = " ·已装备" if item is p.weapon or item is p.armor else ""
            rows.append(("line", f"{chr(97 + i)}) {item.name}{tag}",
                         theme.item_color(item), False))
        if self.show_provenance:
            rows.append(("gap",))
            rows.append(("line", "出处：L1 忠实 / L2 现代化", "magic", False))
            rows.append(("line", "      L3 再创作（原版不可考）", "magic", False))
        return rows

    def draw_side(self, L: Layout) -> None:
        x, y, w, h = L.map_left + L.map_w, L.map_top, L.side, L.map_h
        if L.framed:
            frame(self.scr, y, x, h, w, "冒险者档案", self.a("frame"))
            inner_x, inner_w = x + 2, w - 4
            top, limit = y + 1, y + h - 1     # 不越过下边框
        else:
            inner_x, inner_w = x + 1, w - 1
            top, limit = y, y + h
        row = top
        for entry in self._side_rows():
            if row >= limit:
                break
            if entry[0] == "gap":
                row += 1
                continue
            if entry[0] == "sec":
                if row + 2 > limit:
                    break
                rule(self.scr, row, x, w, entry[1], self.a("frame"), self.a("far"),
                     ends=("lt", "rt") if L.framed else None)
                row += 1
                continue
            if entry[0] == "bar":
                _, label, frac, color, text = entry
                self._side_bar(row, inner_x, inner_w, label, frac, color, text)
                row += 1
                continue
            _, text, color, bold = entry
            put(self.scr, row, inner_x, clip(text, inner_w), self.a(color, bold))
            row += 1

    def _side_bar(self, row: int, x: int, w: int, label: str, frac: float,
                  color: str, text: str) -> None:
        """侧栏里的"标签 + 条 + 数值"一行。空间不够就退化成纯文本。"""
        bar_w = w - _width(label) - _width(text) - 2
        if bar_w >= 4:
            put(self.scr, row, x, label, self.a("dim"))
            bx = x + _width(label) + 1
            used = bar(self.scr, row, bx, bar_w, frac, color, attr_fn=self.a)
            put(self.scr, row, bx + used + 1, text, self.a("bright"))
        else:
            put(self.scr, row, x, f"{label} {text}", self.a(color))

    # ------------------------------------------------------------ 日志与提示
    def draw_log(self, L: Layout) -> None:
        rule(self.scr, L.log_rule, 0, L.w, "消息", self.a("mem"), self.a("frame"))
        entries = self.game.log[-LOG_LINES:]
        for i, (text, kind) in enumerate(entries):
            age = len(entries) - 1 - i
            color = theme.KIND_COLOR.get(kind, "amber")
            put(self.scr, L.log_top + i, 2, clip(text, L.w - 4),
                self.a(color, bold=(age == 0), muted=age > 0))

    def draw_hint(self, L: Layout) -> None:
        hint_bar(self.scr, L.hint, L.w, HINTS, attr_fn=self.a)

    # --------------------------------------------------------------- 浮层
    def _modal_box(self, L: Layout, content_w: int, min_w: int) -> tuple[int, int]:
        """算浮层的宽与左边界。

        浮层只在**游玩区**里居中，不跨到侧栏上：跨过去会擦掉侧栏的左边框却留下
        它的内容，看起来就是"金币"变"币"、"骷髅"变"髅"——一副坏掉的界面。
        （把角色卡留在旁边也正好：选装备时还看得见自己的属性。）
        """
        region_w = (L.map_left + L.map_w - 1) if L.side else L.w
        box_w = min(region_w - 4, max(min_w, content_w + 6))
        left = max(1, (region_w - box_w) // 2)
        return box_w, left

    def _overlay(self, title: str, rows, footer: str = "按任意键关闭", *,
                 wait: bool = True, min_w: int = 44):
        """居中的浮层面板。

        rows 里每项是 (文本, 颜色) 或 (文本, 颜色, 尾标, 尾标颜色)；
        三件容易踩的事在这里一次做对：
          1. 先把面板内部刷成空格 —— 否则地图上的 # 会从浮层里透出来；
          2. 页脚写在**下边框上**（frame 的 foot），而不是压在最后一行内容上；
          3. 宽度按游玩区算 —— 不许跨到侧栏上（见 _modal_box）。
        """
        L = self.layout()
        body = [r for r in rows if r[0] != "gap"]
        content_w = max([_width(r[0]) + (2 + _width(r[2]) if len(r) > 2 else 0)
                         for r in body] + [_width(footer), _width(title)])
        box_w, left = self._modal_box(L, content_w, min_w)
        max_rows = max(1, L.h - 6)
        truncated = len(rows) > max_rows
        rows = rows[:max_rows - (1 if truncated else 0)]
        if truncated:
            rows = rows + [("…… 还有更多（窗口太小）", "mem")]
        box_h = len(rows) + 2
        top = max(0, (L.h - box_h) // 2)
        for i in range(box_h - 2):  # 清内部：必须做，否则下层的字形会透上来
            fill(self.scr, top + 1 + i, left + 1, box_w - 2, " ", 0)
        frame(self.scr, top, left, box_h, box_w, title, self.a("panel"),
              foot=footer, foot_attr=self.a("dim"))
        for i, row in enumerate(rows):
            text, color = row[0], row[1]
            put(self.scr, top + 1 + i, left + 2, clip(text, box_w - 4), self.a(color))
            if len(row) > 2 and row[2]:
                put(self.scr, top + 1 + i, left + 2 + _width(text) + 1,
                    clip(row[2], box_w - 4 - _width(text) - 1), self.a(row[3], True))
        self.scr.noutrefresh()
        curses.doupdate()
        if wait:
            return self.scr.getch()
        return None

    def _prompt_key(self, prompt: str) -> int:
        L = self.layout()
        put(self.scr, L.hint, 0, " " * max(0, L.w - 2), self.a("title"))
        put(self.scr, L.hint, 1, prompt, self.a("title", True))
        self.scr.noutrefresh()
        curses.doupdate()
        return self.scr.getch()

    # ------------------------------------------------------------ 暂停菜单
    PAUSE_ITEMS = [
        ("继续游戏", "回到地牢"),
        ("保存进度", "F5"),
        ("存档管理", "读取 / 删除已有存档"),
        ("返回开始页", "未保存的进度会丢"),
        ("退出游戏", "直接结束进程"),
    ]

    def pause_screen(self) -> None:
        """Esc 打开的暂停菜单：↑↓ 选择、回车确认、Esc 返回游戏。

        「存档管理」就是开始页那个界面（screens.save_manager_screen）——游戏内外同一个
        入口，读档、删档都不需要回命令行。
        """
        items = self.PAUSE_ITEMS
        actions = ("resume", "save", "saves", "title", "quit")
        select = 0
        while True:
            region, _panel_h, panel_w = self._pause_rect()
            screens.draw_panel(
                self.scr, title="菜单 · 已暂停", items=items, width=panel_w, select=select,
                desc=items[select][1], hint_rows=[PAUSE_HINT],
                foot="Esc 返回游戏", min_w=PAUSE_W, boot=self.no_color,
                region_w=region)
            self.scr.noutrefresh()
            curses.doupdate()
            key = self.scr.getch()
            if key == curses.KEY_RESIZE:
                continue                            # 下一轮重算 layout，面板跟着挪
            if key in MENU_UP:
                select = (select - 1) % len(items)
            elif key in MENU_DOWN:
                select = (select + 1) % len(items)
            elif key in ENTER_KEYS or (0 <= key < 256 and chr(key) == " "):
                action = actions[select]
                if action == "resume":
                    self.message = ""
                    return
                if action == "save":
                    self.save_game_here()
                    return
                if action == "saves":
                    self.saves_screen()
                    continue
                if action == "title":
                    self.draw()          # 先退回地牢画面：确认框不叠在菜单面板上
                    if self.confirm("返回开始页？（未保存的进度会丢失）"):
                        return
                    continue
                if action == "quit":
                    self.draw()
                    if self.confirm("不保存并退出？"):
                        raise SystemExit(0)
                    continue
            elif key == 27:
                self.message = ""
                return

    def _pause_rect(self) -> tuple[int, int, int]:
        """(游玩区宽度, 暂停面板外高, 暂停面板外宽)。

        尺寸只在这里算一次：画暂停菜单和（需要时）跟它对齐的浮层都用同一份公式。
        必须返回**游玩区**宽度而不是窗口宽度 —— 面板跨到侧栏上会擦掉它的左边框却
        留下内容，看起来就是"金币"变成"币"这种坏掉的界面。
        """
        L = self.layout()
        region = (L.map_left + L.map_w - 1) if L.side else L.w
        _, box_h, box_w = screens.panel_rect(
            L.h, region, items=len(self.PAUSE_ITEMS), desc=True, hint_rows=[1],
            width=PAUSE_W, min_w=PAUSE_W, region_w=region)
        return region, box_w, box_h

    def saves_screen(self) -> None:
        """游戏内的存档管理：读档成功就换掉当前这一局。"""
        game = screens.save_manager_screen(self.scr, self.no_color)
        if game is None:
            return
        self.game = game
        self.roster_recorded = False
        self.message = ""

    def roster_screen(self) -> None:
        # 名册里存的是**已本地化的名字**（record_roster 写的是 class_name()/race_name()），
        # 所以这里直接显示，不要再拿它去查数据表——content.race() 对未知 id 会静默退回"人类"，
        # 一旦数据表换了 id 就会把精灵显示成人类。
        entries = save_mod.read_roster()
        rows = ([(("还没有冒险者留下战绩。", "mem"))]
                if not entries else screens.roster_rows(entries))
        self._overlay("名人堂", rows)

    def help_screen(self) -> None:
        def keys(*pairs) -> str:
            """两个"键位 说明"列，按显示宽度补齐 —— 中文说明也能对齐。"""
            out = ""
            for i in range(0, len(pairs), 2):
                label, desc = pairs[i]
                out += pad_to(f"{label}  {desc}", 32)
                if i + 1 < len(pairs) and pairs[i + 1][0]:
                    label, desc = pairs[i + 1]
                    out += f"{label}  {desc}"
            return out.rstrip()

        rows = [
            ("DND · PLATO（1975）复刻版", "bright"),
            ("", "amber"),
            ("── 操作", "frame"),
            (keys(("移动", "W A S D / 方向键"), ("斜向", "y u b n")), "info"),
            (keys(("等待", ". 或 5 或 空格"), ("拾取", "g 或 ,")), "info"),
            (keys(("下楼梯", ">"), ("上楼梯", "<")), "info"),
            (keys(("背包", "i"), ("施法", "c")), "info"),
            (keys(("存档", "F5 或 Shift+S"), ("名册", "R")), "info"),
            (keys(("菜单", "Esc（存档/读档/退出）"), ("帮助", "?")), "info"),
            (keys(("出处", "P 标出处层"), ("退出", "Q（直接退出）")), "info"),
            ("", "amber"),
            ("── 目标", "frame"),
            ("下到第 10 层夺取「深渊遗物」，活着回来即为胜利。", "good"),
            ("死亡即永久消失；现代模式可免死一次。", "warn"),
            ("", "amber"),
            ("── 考据", "frame"),
            ("单屏地牢、逐层下潜、掷骰战斗、永久死亡属 L1 忠实层；", "magic"),
            ("键位/界面/视野/存档属 L2 现代化层；", "magic"),
            ("职业、法术、怪物和数值属 L3 再创作层（原版不可考）。", "magic"),
        ]
        if self.debug:
            rows.append(("调试：x 显示全图  t 传送（仅 --debug）", "bad"))
        self._overlay("帮助", rows)

    def inventory_screen(self) -> None:
        p = self.game.player
        if not p.inventory:
            self._overlay("背包", [("背包是空的。", "mem")])
            return
        name_w = max(_width(it.name) for it in p.inventory)
        sum_w = max(_width(describe.item_summary(it)) for it in p.inventory)
        rows = []
        for i, item in enumerate(p.inventory):
            tag = "已装备" if item in (p.weapon, p.armor) else ""
            value = (f"价值 {item.value} 金"
                     if item.value and item.kind not in ("gold", "gem") else "")
            text = (f"{chr(97 + i)}) {pad_to(item.name, name_w)}  "
                    f"{pad_to(describe.item_summary(item), sum_w)}  {pad_to(value, 9)}")
            rows.append((text, theme.item_color(item), tag, "good"))
        self._overlay("背包 · 按字母使用或装备", rows,
                      footer="按字母使用   Esc 关闭", wait=False)
        key = self.scr.getch()
        if 0 <= key < 256 and 97 <= key < 97 + len(p.inventory):
            self.game.command(("use", key - 97))

    def cast_screen(self) -> None:
        spells = self.game.spellbook()
        if not spells:
            self._overlay("法术", [("你不会任何法术。", "mem")])
            return
        name_w = max(_width(sp["name"]) for sp in spells)
        rows = []
        for i, sp in enumerate(spells):
            enough = self.game.player.mp >= sp["cost"]
            flag = "" if enough else "   法力不足"
            rows.append((f"{chr(97 + i)}) {pad_to(sp['name'], name_w)}  "
                         f"消耗 {sp['cost']}  {describe.spell_summary(sp)}{flag}",
                         "magic" if enough else "mem"))
        self._overlay("法术 · 按字母施放", rows, footer="按字母施放   Esc 关闭", wait=False)
        key = self.scr.getch()
        if 0 <= key < 256 and 97 <= key < 97 + len(spells):
            self.game.command(("cast", spells[key - 97]["id"]))

    def teleport_screen(self) -> None:
        key = self._prompt_key("传送到第几层（1-9）？ ")
        if 0 <= key < 256 and chr(key).isdigit():
            self.game.command(("teleport", int(chr(key))))

    def roster_screen(self) -> None:
        # 名册里存的是**已本地化的名字**（record_roster 写的是 class_name()/race_name()），
        # 所以这里直接显示，不要再拿它去查数据表——content.race() 对未知 id 会静默退回"人类"，
        # 一旦数据表换了 id 就会把精灵显示成人类。
        # 行格式与开始页的名人堂共用 screens.roster_rows，两处不会各写一份而对不齐。
        entries = save_mod.read_roster()
        rows = ([("还没有冒险者留下战绩。", "mem")]
                if not entries else screens.roster_rows(entries))
        self._overlay("名人堂", rows)

    def confirm(self, question: str) -> bool:
        """[确定 / 取消] 确认框，画在游戏画面上（调用方先重画一帧，别叠在菜单面板上）。"""
        return screens.confirm_choice(self.scr, question, no_color=self.no_color)

    def end_screen(self, key: int) -> bool:
        """返回 True 表示退出程序。"""
        g = self.game
        if not self.roster_recorded:
            result = "won" if g.state == "won" else "dead"
            save_mod.record_roster(g, result)
            if not g.modern:
                path = save_mod.save_path(g.player.name)
                if path.exists():
                    path.unlink()
            self.roster_recorded = True
        won = g.state == "won"
        title = "胜利" if won else "你已阵亡"
        color = "good" if won else "bad"
        p = g.player
        rows = [
            (("你带着深渊遗物重返光明！" if won else f"你在地牢第 {g.depth} 层倒下了。"), color),
            ("", "amber"),
            (f"{p.name} · {p.race().get('name_zh') or p.race_name()}·{p.class_name()} {p.level}级", "bright"),
            (f"到达深度  {g.depth}/{MAX_DEPTH}        回合  {g.turn}", "amber"),
            (f"金币  {p.gold}            击杀  {sum(p.kills.values())}", "gold"),
            (f"种子  {g.seed}（可用来复现这座地牢）", "dim"),
            ("", "amber"),
            ("[n] 新游戏     [Q] 退出", "amber"),
        ]
        self._overlay(title, rows, footer="种子可复现这座地牢（--seed）", min_w=52)
        if key in (ord("n"), ord("N")):
            name, class_id, race_id = creation_screen(self.scr, self.no_color)
            seed = int.from_bytes(os.urandom(4), "big")
            self.game = Game(seed, name, class_id, modern=self.game.modern, race_id=race_id)
            self.roster_recorded = False
            return False
        if key in (ord("q"), ord("Q"), 27):
            return True
        return False

