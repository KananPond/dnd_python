"""curses 主界面：状态栏 / 地图视口 / 侧栏 / 消息日志 / 各类浮层。

布局（自上而下）：
  row 0            标题与状态栏
  row 1..map_end   地图视口（以玩家为中心滚动，显示视野与记忆）
  row log_start..  消息日志（最近 5 条）
  最后一行          按键提示
  右侧（宽度足够时）角色卡 / 可见敌人 / 背包 / 出处说明
"""

from __future__ import annotations

import curses

from .. import save as save_mod
from ..game import Game
from ..level import FLOOR, MAX_DEPTH
from . import theme
from .widgets import box, center, hline, put

MIN_W, MIN_H = 62, 18
LOG_LINES = 5
SIDE_W = 26

MOVE_KEYS = {
    # 主键位：WASD；同时保留方向键、hjkl 与 yubn（斜向）
    ord("w"): (0, -1), ord("a"): (-1, 0), ord("s"): (0, 1), ord("d"): (1, 0),
    curses.KEY_UP: (0, -1), curses.KEY_DOWN: (0, 1),
    curses.KEY_LEFT: (-1, 0), curses.KEY_RIGHT: (1, 0),
    ord("k"): (0, -1), ord("j"): (0, 1), ord("h"): (-1, 0), ord("l"): (1, 0),
    ord("y"): (-1, -1), ord("u"): (1, -1), ord("b"): (-1, 1), ord("n"): (1, 1),
    curses.KEY_HOME: (-1, -1), curses.KEY_NPAGE: (1, 1),
}


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
    def a(self, name: str, bold: bool = False):
        return theme.attr(name, self.no_color, bold)

    def layout(self):
        h, w = self.scr.getmaxyx()
        side = SIDE_W if w >= 100 else 0
        map_w = w - side - (2 if side else 0)
        map_h = h - 1 - LOG_LINES - 2
        return h, w, side, map_w, max(6, map_h)

    # ------------------------------------------------------------- 主循环
    def run(self) -> None:
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
            path = save_mod.save_game(g)
            g.message(f"Game saved to {path.name}.", "good")
        elif ch == "x" and self.debug:
            g.command(("reveal",))
        elif ch == "t" and self.debug:
            self.teleport_screen()
        elif ch in ("Q",):
            if self.confirm("不保存并退出？"):
                raise SystemExit(0)
        elif key == 27:
            self.message = ""

    # ---------------------------------------------------------------- 绘制
    def draw(self) -> None:
        self.scr.erase()
        h, w, side, map_w, map_h = self.layout()
        if w < MIN_W or h < MIN_H:
            center(self.scr, h // 2, "终端窗口太小", self.a("bad", True))
            center(self.scr, h // 2 + 1, f"需要 {MIN_W}x{MIN_H}，当前 {w}x{h}", self.a("amber"))
            self.scr.noutrefresh()
            curses.doupdate()
            return
        self.draw_status(w)
        self.draw_map(1, 0, map_h, map_w)
        if side:
            self.draw_side(1, map_w, map_h, side)
        self.draw_log(h - LOG_LINES - 1, w)
        self.draw_hint(h - 1, w)
        if self.message:
            put(self.scr, h - LOG_LINES - 1, 2, self.message, self.a("gold", True))
        self.scr.noutrefresh()
        curses.doupdate()

    def draw_status(self, w: int) -> None:
        st = self.game.status()
        line = (f" DND · 深渊地牢   {st['name']} · {st['class']} {st['level']}级   "
            f"生命 {st['hp']}/{st['max_hp']}  法力 {st['mp']}/{st['max_mp']}  护甲 {st['ac']}  "
            f"经验 {st['xp']}  金币 {st['gold']}  深度 {st['depth']}/{MAX_DEPTH}  回合 {st['turn']} ")
        hline(self.scr, 0, 0, w, " ", self.a("title"))
        put(self.scr, 0, 0, line, self.a("title", True))

    def draw_map(self, top: int, left: int, height: int, width: int) -> None:
        g = self.game
        level = g.level()
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
                if (x, y) == (g.player.x, g.player.y):
                    put(self.scr, top + sy, left + sx, "@", self.a("bright", True))
                    continue
                visible = (x, y) in g.visible
                if not visible and not level.is_explored(x, y):
                    continue
                monster = level.monster_at(x, y) if visible else None
                if monster:
                    put(self.scr, top + sy, left + sx, monster.glyph,
                        self.a(theme.MONSTER_COLOR.get(monster.color, "bad"), True))
                    continue
                items = level.items_at(x, y) if visible else []
                if items:
                    item = items[0]
                    put(self.scr, top + sy, left + sx, item.glyph, self.a(theme.item_color(item), True))
                    continue
                tile = level.tile(x, y)
                glyph = theme.TERRAIN.get(tile, "?")
                name = "amber" if visible else "dim"
                bold = tile in (3, 4)
                put(self.scr, top + sy, left + sx, glyph, self.a(name, bold))

    def draw_side(self, top: int, left: int, height: int, width: int) -> None:
        g = self.game
        p = g.player
        box(self.scr, top, left, height, width, "冒险者档案", self.a("amber"))
        row = top + 1
        put(self.scr, row, left + 2, f"{p.name}", self.a("bright", True)); row += 1
        put(self.scr, row, left + 2,
            f"{p.race().get('name_zh', p.race_name())}·{p.class_name()}  {p.level}级",
            self.a("amber")); row += 1
        put(self.scr, row, left + 2, f"生命 {p.hp}/{p.max_hp}   法力 {p.mp}/{p.max_mp}", self.a("good")); row += 1
        put(self.scr, row, left + 2, f"护甲 {p.ac()}   经验 {p.xp}", self.a("amber")); row += 1
        put(self.scr, row, left + 2, f"金币 {p.gold}", self.a("gold")); row += 1
        put(self.scr, row, left + 2, f"武器：{p.weapon.name if p.weapon else '无'}", self.a("info")); row += 1
        put(self.scr, row, left + 2, f"护甲：{p.armor.name if p.armor else '无'}", self.a("info")); row += 1
        attr_items = list(p.attrs.items())
        for start in range(0, len(attr_items), 3):
            chunk = attr_items[start:start + 3]
            prefix = "属性 " if start == 0 else "     "
            put(self.scr, row, left + 2,
                prefix + " ".join(f"{k}{v}" for k, v in chunk), self.a("dim"))
            row += 1
        row += 1
        if p.buffs:
            put(self.scr, row, left + 2, "临时效果", self.a("magic")); row += 1
            for key, (amount, turns) in p.buffs.items():
                label = {"ac": "护甲", "attack": "命中"}.get(key, key)
                put(self.scr, row, left + 4, f"{label} +{amount}（{turns}回合）", self.a("magic")); row += 1
            row += 1
        put(self.scr, row, left + 2, "视野内", self.a("amber", True)); row += 1
        monsters = g.visible_monsters()
        if not monsters:
            put(self.scr, row, left + 4, "目前没有敌人", self.a("dim")); row += 1
        for m in monsters[:6]:
            put(self.scr, row, left + 4, f"{m.glyph} {m.name[:16]} {m.hp}/{m.max_hp}", self.a("bad"))
            row += 1
        row += 1
        if row < top + height - 3:
            put(self.scr, row, left + 2, "背包", self.a("amber", True)); row += 1
            for i, item in enumerate(p.inventory[:6]):
                put(self.scr, row, left + 4, f"{chr(97 + i)}) {item.name[:18]}", self.a(theme.item_color(item)))
                row += 1
        if self.show_provenance:
            put(self.scr, top + height - 2, left + 2, "出处：L1 / L2 / L3", self.a("magic"))

    def draw_log(self, top: int, width: int) -> None:
        hline(self.scr, top, 0, width, "-", self.a("dim"))
        entries = self.game.log[-LOG_LINES:]
        for i, (text, kind) in enumerate(entries):
            put(self.scr, top + 1 + i, 2, text[: width - 4], self.a(theme.KIND_COLOR.get(kind, "amber")))

    def draw_hint(self, row: int, width: int) -> None:
        hint = " WASD/方向键 移动  [i]背包 [c]施法 [g]拾取 [>]下楼 [<]上楼 [?]帮助 [F5]存档 [R]名册 [Q]退出 "
        hline(self.scr, row, 0, width, " ", self.a("title"))
        put(self.scr, row, 0, hint, self.a("title"))

    # --------------------------------------------------------------- 浮层
    def _overlay(self, title: str, lines, footer: str = "按任意键关闭", wait: bool = True) -> None:
        h, w = self.scr.getmaxyx()
        box_w = min(w - 4, max(46, max(len(x[0]) for x in lines) + 6 if lines else 46))
        box_h = min(h - 2, len(lines) + 4)
        top = (h - box_h) // 2
        left = (w - box_w) // 2
        box(self.scr, top, left, box_h, box_w, title, self.a("amber"))
        for i, (text, color) in enumerate(lines[: box_h - 3]):
            put(self.scr, top + 1 + i, left + 2, text, self.a(color))
        put(self.scr, top + box_h - 2, left + 2, footer, self.a("dim"))
        self.scr.noutrefresh()
        curses.doupdate()
        if wait:
            self.scr.getch()

    def _prompt_key(self, prompt: str) -> int:
        h, w = self.scr.getmaxyx()
        put(self.scr, h - 1, 0, " " * (w - 1), self.a("title"))
        put(self.scr, h - 1, 1, prompt, self.a("title", True))
        self.scr.noutrefresh()
        curses.doupdate()
        return self.scr.getch()

    def help_screen(self) -> None:
        lines = [
            ("DND · PLATO（1975）复刻版", "bright"),
            ("", "amber"),
            ("移动  W A S D（也可用方向键 / hjkl / yubn 斜向）", "info"),
            ("等待  . 或 5        下楼梯  >        上楼梯  <", "info"),
            ("拾取  g 或 ,        背包  i        施法  c", "info"),
            ("存档  F5 或 Shift+S 名册  R        退出  Q", "info"),
            ("帮助  ?             出处说明开关  P", "info"),
            ("", "amber"),
            ("目标：下到第 10 层夺取「深渊遗物」，活着回来即为胜利。", "good"),
            ("死亡即永久消失；现代模式可免死一次。", "warn"),
            ("", "amber"),
            ("考据：单屏地牢、逐层下潜、掷骰战斗、永久死亡", "magic"),
            ("属 L1 忠实层；键位/界面/视野/存档属 L2 现代化层；", "magic"),
            ("职业、法术、怪物和数值属于 L3 再创作层（原版不可考）。", "magic"),
        ]
        if self.debug:
            lines.append(("调试：x 显示全图  t 传送（仅 --debug）", "bad"))
        self._overlay("帮助", lines)

    def inventory_screen(self) -> None:
        p = self.game.player
        if not p.inventory:
            self._overlay("背包", [("背包是空的。", "dim")])
            return
        lines = [("esc 关闭", "dim"), ("", "amber")]
        for i, item in enumerate(p.inventory):
            tag = ""
            if item is p.weapon:
                tag = "（已装备武器）"
            elif item is p.armor:
                tag = "（已装备护甲）"
            extra = item.damage or (f"AC +{item.ac_bonus}" if item.kind == "armor" else item.heal or item.effect or "")
            lines.append((f"{chr(97 + i)}) {item.name} {extra}{tag}", theme.item_color(item)))
        self._overlay("背包 · 按字母使用或装备", lines,
                  footer="按字母使用   Esc 关闭", wait=False)
        key = self.scr.getch()
        if 0 <= key < 256 and 97 <= key < 97 + len(p.inventory):
            self.game.command(("use", key - 97))

    def cast_screen(self) -> None:
        spells = self.game.spellbook()
        if not spells:
            self._overlay("法术", [("你不会任何法术。", "dim")])
            return
        lines = [("esc 关闭", "dim"), ("", "amber")]
        for i, sp in enumerate(spells):
            flag = "" if self.game.player.mp >= sp["cost"] else "  （法力不足）"
            lines.append((f"{chr(97 + i)}) {sp['name']}  消耗 {sp['cost']}{flag}", "magic"))
            lines.append((f"     {sp.get('desc', '')}", "dim"))
        self._overlay("法术 · 按字母施放", lines, footer="按字母施放   Esc 关闭", wait=False)
        key = self.scr.getch()
        if 0 <= key < 256 and 97 <= key < 97 + len(spells):
            self.game.command(("cast", spells[key - 97]["id"]))

    def teleport_screen(self) -> None:
        key = self._prompt_key("传送到第几层（1-9）？ ")
        if 0 <= key < 256 and chr(key).isdigit():
            self.game.command(("teleport", int(chr(key))))

    def roster_screen(self) -> None:
        entries = save_mod.read_roster()
        lines = []
        if not entries:
            lines.append(("还没有冒险者留下战绩。", "dim"))
        for e in entries[-12:]:
            color = "good" if e["result"] == "won" else "bad"
            result = "胜利" if e["result"] == "won" else "阵亡"
            lines.append((f"{e['name']:<10} {e['class']:<4} {e['level']}级  深度 {e['depth']:<2} "
                          f"{result:<2}  {e['gold']}金  {e['turns']}回合", color))
        self._overlay("名人堂", lines)

    def confirm(self, question: str) -> bool:
        key = self._prompt_key(question + " [y/N] ")
        return key in (ord("y"), ord("Y"))

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
        h, w = self.scr.getmaxyx()
        title = "胜利" if g.state == "won" else "你已阵亡"
        color = "good" if g.state == "won" else "bad"
        lines = [
            (f"{g.player.name} · {g.player.class_name()} · {g.player.level}级", "bright"),
            (f"到达深度：{g.depth}/{MAX_DEPTH}    回合：{g.turn}", "amber"),
            (f"金币：{g.player.gold}    击杀：{sum(g.player.kills.values())}", "gold"),
            (f"种子：{g.seed}（可用来复现这座地牢）", "dim"),
        ]
        if g.state == "won":
            lines.insert(0, ("你带着深渊遗物重返光明！", "good"))
        else:
            lines.insert(0, (f"你在地牢第 {g.depth} 层倒下了。", "bad"))
        box(self.scr, h // 2 - 5, max(2, w // 2 - 32), 12, min(w - 4, 64), title, self.a(color, True))
        for i, (text, col) in enumerate(lines):
            put(self.scr, h // 2 - 3 + i, max(4, w // 2 - 30), text, self.a(col))
        put(self.scr, h // 2 + 5, max(4, w // 2 - 30), "[n] 新游戏   [Q] 退出", self.a("amber", True))
        self.scr.noutrefresh()
        curses.doupdate()
        if key in (ord("n"), ord("N")):
            name, class_id, race_id = creation_screen(self.scr, self.no_color)
            import os
            seed = int.from_bytes(os.urandom(4), "big")
            self.game = Game(seed, name, class_id, modern=self.game.modern, race_id=race_id)
            self.roster_recorded = False
            return False
        if key in (ord("q"), ord("Q"), 27):
            return True
        return False


def creation_screen(stdscr, no_color: bool = False):
    """建角：输入姓名，↑↓ 选择职业与种族。返回 (name, class_id, race_id)。"""
    from ..content import load as load_content
    content = load_content()
    class_ids = ["warrior", "wizard", "cleric", "rogue"]
    race_ids = ["human", "elf", "dwarf", "gnome"]

    def label(entry: dict) -> str:
        """中文名优先；若数据表里另有英文名则附在后面。"""
        zh = entry.get("name_zh") or entry.get("name", "")
        en = entry.get("name", "")
        return f"{zh}（{en}）" if en and en != zh and en.isascii() else zh
    a = lambda n, b=False: theme.attr(n, no_color, b)
    name = ""
    focus = 0  # 0 = 职业栏，1 = 种族栏
    ci = ri = 0
    curses.curs_set(1)
    while True:
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        box(stdscr, 1, 2, h - 3, w - 5, "DND · 创建冒险者", a("amber"))
        put(stdscr, 3, 4, "姓名：" + name + "_", a("bright", True))
        put(stdscr, 5, 6, "职业（↑↓ 选择）", a("amber", focus == 0))
        put(stdscr, 5, 42, "种族（↑↓ 选择）", a("amber", focus == 1))
        for i, cid in enumerate(class_ids):
            k = content.klass(cid)
            selected = i == ci
            col = "bright" if (selected and focus == 0) else ("amber" if selected else "dim")
            put(stdscr, 7 + i * 2, 4,
                f"{'>' if selected else ' '} {i + 1}. {label(k)}", a(col, selected))
        for i, rid in enumerate(race_ids):
            r = content.race(rid)
            selected = i == ri
            col = "bright" if (selected and focus == 1) else ("amber" if selected else "dim")
            put(stdscr, 7 + i * 2, 40,
                f"{'>' if selected else ' '} {i + 1}. {label(r)}", a(col, selected))
        klass = content.klass(class_ids[ci])
        race = content.race(race_ids[ri])
        info_row = 7 + max(len(class_ids), len(race_ids)) * 2 + 1
        put(stdscr, info_row, 4, klass["blurb"][:34], a("dim"))
        put(stdscr, info_row + 1, 4, race["blurb"][:34], a("dim"))
        mods = " ".join(f"{k}{v:+d}" for k, v in race.get("mods", {}).items()) or "属性无调整"
        preview = (f"{label(race)}·{label(klass)}  |  "
                   f"生命骰 d{klass['hit_die']}  初始生命 +{3 + int(race.get('hp_bonus', 0))}  "
                   f"每级法力 {klass.get('mp_per_level', 0)}  视野 {9 + int(race.get('fov_bonus', 0))}  |  {mods}")
        put(stdscr, info_row + 3, 4, preview[: w - 10], a("info"))
        put(stdscr, h - 3, 4,
            "↑↓ 选择    Tab / ←→ 切换职业与种族    1-4 直选    回车开始    Esc 退出", a("dim"))
        stdscr.noutrefresh()
        curses.doupdate()
        key = stdscr.getch()
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
        elif key in (curses.KEY_LEFT, curses.KEY_RIGHT, ord("\t"), 9):
            focus = 1 - focus
        elif 0 <= key < 256 and chr(key) in "1234":
            if focus == 0:
                ci = int(chr(key)) - 1
            else:
                ri = int(chr(key)) - 1
        elif key in (curses.KEY_BACKSPACE, 127, 8):
            name = name[:-1]
        elif key in (10, 13, curses.KEY_ENTER):
            curses.curs_set(0)
            return (name.strip() or "冒险者"), class_ids[ci], race_ids[ri]
        elif key == 27:
            raise SystemExit(0)
        elif 0 <= key < 256 and chr(key).isprintable() and len(name) < 14:
            name += chr(key)
