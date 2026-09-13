"""把 curses TUI 渲染成 PNG，用于人工审阅界面（开发工具，需要 Pillow）。

为什么需要它：这是纯终端项目，改界面时没法"看一眼"，只能靠脑补。
本工具把 Tui 的绘制调用录下来，按**真实终端语义**重放到像素上：
CJK 占两格、右边界裁剪、后写覆盖先写。于是"这行字是不是溢出了"
"边框对不对得齐""浮层内部有没有透出地图"变成能直接看出来的事情。

它不是测试 —— `python3 -m unittest discover -s tests` 才是测试（断言布局关系）；
本工具提供的是观感：改完界面扫一眼这几张图，就知道是不是真的变好看了。

用法：
  python3 tools/preview.py                 # 渲染全部场景到 out/preview/*.png
  python3 tools/preview.py main inventory  # 只渲染指定场景
  python3 tools/preview.py --list          # 列出场景名

依赖 Pillow（只有本工具需要；游戏本体零第三方依赖）。
找不到等宽/中文字体时会退回 PIL 内置字体 —— 布局仍可看，但中文会变方块，
所以第一次用建议确认打印出来的字体路径。
"""

from __future__ import annotations

import argparse
import curses
import os
import pathlib
import sys
import unicodedata

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUT = ROOT / "out" / "preview"

# 各平台常见的等宽 / 中文无衬线字体，按顺序取第一个存在的
LATIN_FONTS = (
    r"C:\Windows\Fonts\consola.ttf",                          # Windows
    "/System/Library/Fonts/Menlo.ttc",                        # macOS
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",    # Debian / Ubuntu
    "/usr/share/fonts/dejavu/DejaVuSansMono.ttf",
)
LATIN_BOLD_FONTS = (
    r"C:\Windows\Fonts\consolab.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
)
CJK_FONTS = (
    r"C:\Windows\Fonts\msyh.ttc",                             # Windows 微软雅黑
    r"C:\Windows\Fonts\simhei.ttf",
    "/System/Library/Fonts/PingFang.ttc",                     # macOS
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",  # Linux
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
)

CELL_W, CELL_H = 9, 20          # 等宽字体 18px 下的步进
PAD = 14
DEFAULT_BG = (12, 10, 8)
FONT_OVERRIDE = [None, None]    # [拉丁, 中文]，由 --font / --cjk-font 设置


def find_font(candidates, override=None) -> str | None:
    """挑一个真实存在的字体文件；都没有就返回 None（调用方退回默认字体）。"""
    for path in ([override] if override else []) + list(candidates):
        if path and pathlib.Path(path).exists():
            return path
    return None


class RecordScreen:
    """记录绘制调用，而不是真的画到终端上。

    故意不像 tests 里的 FakeScreen 那样逐字符写入：这里保留"一次 addstr 写了一段
    带颜色的文字"这个事实，宽度换算留到渲染阶段做，才能忠实反映 CJK 占两格。
    """

    def __init__(self, h: int, w: int, keys=()):
        self.h, self.w = h, w
        self.keys = list(keys)
        self.ops: list[tuple[int, int, str, int]] = []

    def getmaxyx(self):
        return self.h, self.w

    def erase(self):
        self.ops = []

    def keypad(self, flag):
        pass

    def noutrefresh(self):
        pass

    def addstr(self, y, x, text, attr=0):
        if not (0 <= y < self.h and 0 <= x < self.w):
            raise curses.error(f"out of bounds: {y},{x}")
        self.ops.append((y, x, text, attr))

    def getch(self):
        return self.keys.pop(0) if self.keys else 27


def _patch_theme():
    """让 theme.attr 返回可直接解码的整数，而不是 curses 颜色对。"""
    from dnd.ui import theme

    def fake_attr(name, no_color=False, bold=False, muted=False, alt=False):
        if muted:
            name = f"{name}_muted"
        n = theme.PAIRS.get(name, 1)
        return n | (curses.A_BOLD if bold else 0) | (curses.A_REVERSE if alt else 0)

    theme.attr = fake_attr
    theme.init_colors = lambda no_color=False: None
    return {v: k for k, v in theme.PAIRS.items()}


def _cell_width(ch: str) -> int:
    """终端里这个字符占几格（W/F = 2 格）。"""
    if unicodedata.combining(ch):
        return 0
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1


def _rasterize(scr: RecordScreen, reverse: dict):
    """把绘制调用重放成 (字符, 颜色名, 加粗) 网格，并收集越界告警。

    越界告警是这个工具最有用的一半：终端里"悄悄越界"往往表现为折行或截断，
    而这里会明确告诉你哪一行写到了边界之外。
    """
    grid: list[list[tuple[str, str, bool]]] = [
        [(" ", None, False) for _ in range(scr.w)] for _ in range(scr.h)
    ]
    overflows: list[str] = []
    for y, x, text, attr in scr.ops:
        col = x
        for ch in text:
            cw = _cell_width(ch)
            if cw == 0:
                continue
            if col + cw > scr.w:
                overflows.append(f"第 {y} 行写到边界外（x={col}，{text!r}）")
                break
            name = reverse.get(attr & 0xFF)
            bold = bool(attr & curses.A_BOLD)
            grid[y][col] = (ch, name, bold)
            if cw == 2:
                grid[y][col + 1] = ("", name, bold)   # 右半格被宽字符占据
            col += cw
    return grid, overflows


def render_png(scr: RecordScreen, reverse: dict, path: pathlib.Path, title: str = ""):
    from PIL import Image, ImageDraw, ImageFont
    from dnd.ui import theme

    grid, overflows = _rasterize(scr, reverse)
    palette = theme.RGB

    def load(candidates, size, override=None):
        path_ = find_font(candidates, override)
        return ImageFont.truetype(path_, size) if path_ else ImageFont.load_default()

    head = CELL_H + 6 if title else 0
    img = Image.new("RGB", (scr.w * CELL_W + 2 * PAD, scr.h * CELL_H + 2 * PAD + head),
                    DEFAULT_BG)
    d = ImageDraw.Draw(img)
    lat = load(LATIN_FONTS, 18, FONT_OVERRIDE[0])
    latb = load(LATIN_BOLD_FONTS or LATIN_FONTS, 18, FONT_OVERRIDE[0])
    cjk = load(CJK_FONTS, 17, FONT_OVERRIDE[1])

    def color(name):
        return palette.get(name, ((210, 200, 180), None))

    if title:
        d.text((PAD, PAD - 2), f"{title}   {scr.w}x{scr.h}", fill=(200, 190, 170), font=latb)

    # 1) 先铺背景色块（反白栏、选中行）
    for y in range(scr.h):
        for x in range(scr.w):
            _ch, name, _b = grid[y][x]
            if color(name)[1]:
                d.rectangle([PAD + x * CELL_W, PAD + head + y * CELL_H,
                             PAD + (x + 1) * CELL_W - 1, PAD + head + (y + 1) * CELL_H - 1],
                            fill=color(name)[1])
    # 2) 再画字形：ASCII 用等宽字体，CJK 用中文字体（同格叠放，模拟字体回退）
    for y in range(scr.h):
        for x in range(scr.w):
            ch, name, bold = grid[y][x]
            if not ch or ch == " ":
                continue
            cx, cy = PAD + x * CELL_W, PAD + head + y * CELL_H
            if unicodedata.east_asian_width(ch) in ("W", "F"):
                d.text((cx, cy + 1), ch, fill=color(name)[0], font=cjk)
            else:
                d.text((cx, cy + 1), ch, fill=color(name)[0], font=latb if bold else lat)
    img.save(path)
    return overflows


# --------------------------------------------------------------------- 场景
def _scenario(seed=11):
    """一个有内容的局面：记忆雾 + 视野内敌人 + 各种日志 + 掉血 + 增益 + 已装备物品。"""
    from dnd import save as save_mod
    from dnd.entities import auto_equip, make_item
    from dnd.game import Game

    tmp = ROOT / "out" / "preview-saves"
    tmp.mkdir(parents=True, exist_ok=True)
    save_mod.SAVE_DIR = tmp
    save_mod.ROSTER = tmp / "roster.json"
    # 名册存的是已本地化的名字（见 save.record_roster），这里照样填
    save_mod.ROSTER.write_text(
        '[{"name":"Aria","race":"精灵","class":"法师","level":6,"depth":7,"result":"dead",'
        '"gold":412,"turns":1883,"date":"2026-09-08 21:14"},'
        '{"name":"Borin","race":"矮人","class":"战士","level":9,"depth":10,"result":"won",'
        '"gold":1204,"turns":3421,"date":"2026-09-09 02:40"},'
        '{"name":"Nix","race":"侏儒","class":"盗贼","level":4,"depth":5,"result":"dead",'
        '"gold":96,"turns":740,"date":"2026-09-09 19:02"}]', encoding="utf-8")

    g = Game(seed, "Aria", "wizard", race_id="elf")
    g.depth, g.turn = 3, 268
    g.command(("reveal",))                      # 整层变"记忆"，看得出雾效层次
    lvl, p = g.level(), g.player
    p.level, p.xp = 4, 152                      # 与 4 级匹配（阈值 100..190）
    p.hp, p.max_hp = 19, 31
    p.mp, p.max_mp = 4, 14                      # 法力 4：法术列表里能看到"法力不足"
    p.gold = 268
    p.attrs = {"STR": 9, "DEX": 15, "CON": 11, "INT": 17, "WIS": 12}
    p.add_buff("ac", 4, 7)
    p.add_buff("attack", 1, 3)
    p.kills = {"rat": 6, "goblin": 3, "skeleton": 2}
    for item_id in ("potion_healing", "potion_healing", "scroll_lightning", "scroll_firestorm",
                    "chain_mail", "battle_axe", "plate_mail"):
        p.inventory.append(make_item(item_id, g.rng, 3))
    auto_equip(p, quiet=True)   # 按内核自己的规则选装备，顺便验证"已装备"标记

    from dnd.content import load as load_content
    from dnd.entities import make_monster
    content = load_content()
    for dx, dy, mid in ((2, -1, "goblin"), (-3, 2, "skeleton"), (4, 3, "orc"),
                        (2, 4, "giant_rat"), (-4, -1, "ogre")):
        x, y = p.x + dx, p.y + dy
        if lvl.is_walkable(x, y) and (x, y) in g.visible:
            m = make_monster(content.monsters[mid], x, y, g.rng)
            m.hp = max(1, m.max_hp - 2)
            lvl.monsters.append(m)
    for dx, dy, iid in ((-2, -2, "gold"), (3, 1, "potion_healing"), (-4, 3, "chain_mail"),
                        (1, -3, "gem")):
        x, y = p.x + dx, p.y + dy
        if lvl.is_walkable(x, y):
            lvl.ground.append((make_item(iid, g.rng, 3), x, y))
    g._refresh_fov()
    for text, kind in [
        ("你踏入第 3 层。空气更冷了。", "info"),
        ("拾荒妖挥动短棍，命中你（-4 HP）。", "bad"),
        ("你捡到了 37 枚金币。", "gold"),
        ("你施放了 魔法飞弹，骷髅受到 9 点伤害。", "magic"),
        ("骷髅倒下了！获得 45 点经验。", "good"),
    ]:
        g.message(text, kind)
    return g


def build_scenes():
    """场景名 -> (标题, 渲染函数)。渲染函数画完后返回那张 RecordScreen。"""
    from dnd import save as save_mod
    from dnd.ui import tui as tui_mod

    def tui_for(g, h, w, keys=(), **kw):
        scr = RecordScreen(h, w, keys)
        return tui_mod.Tui(scr, g, **kw), scr

    g = _scenario()
    t, _ = tui_for(g, 32, 118, debug=True)
    scenes = {"main": ("主界面 · 记忆雾 / 侧栏 / 日志", lambda: (t.draw(), t.scr)[1])}

    def overlay(call):
        def run():
            t.scr.erase()
            t.draw()
            call()      # 浮层画在同一张缓冲上，才能看出"浮层压在游戏画面上"
            return t.scr
        return run

    scenes["inventory"] = ("背包浮层（已装备标记 / 列对齐）", overlay(t.inventory_screen))
    scenes["cast"] = ("法术浮层（含法力不足）", overlay(t.cast_screen))
    scenes["help"] = ("帮助浮层", overlay(t.help_screen))
    scenes["roster"] = ("名人堂浮层", overlay(t.roster_screen))

    def end():
        g2 = _scenario()
        g2.state, g2.player.hp = "dead", 0
        t2, s2 = tui_for(g2, 26, 100)
        t2.roster_recorded = True
        t2.end_screen()
        return s2
    scenes["end"] = ("阵亡结算", end)

    def creation():
        from dnd.ui.screens import creation_screen
        scr = RecordScreen(32, 104, keys=[10])
        creation_screen(scr, no_color=False, initial_name="Aria",
                        initial_class="wizard", initial_race="elf")
        return scr
    scenes["creation"] = ("建角界面", creation)

    def prologue():
        """建角之后的序章：翻到「入井」页，展示"你怎么进地牢 + 下井前须知"。"""
        from dnd.ui.screens import prologue_screen
        scr = RecordScreen(32, 104, keys=[curses.KEY_RIGHT, 27])
        prologue_screen(scr, "Aria", no_color=False)
        return scr
    scenes["prologue"] = ("序章 · 入井（建角后的背景故事）", prologue)

    def start_menu():
        """开始页：玩家看到的第一屏（↑↓ 选菜单，回车确认）。"""
        from dnd.ui.screens import start_screen
        scr = RecordScreen(32, 104, keys=[curses.KEY_DOWN, 27])
        start_screen(scr, no_color=False)
        return scr
    scenes["start"] = ("开始页（启动后的第一屏）", start_menu)

    def start_small():
        from dnd.ui.screens import start_screen
        scr = RecordScreen(20, 80, keys=[27])
        start_screen(scr, no_color=False)
        return scr
    scenes["start_small"] = ("开始页 · 矮窗口 80x20", start_small)

    def save_manager():
        """存档管理：左列表右档案，不用输命令就能看/读/删存档。"""
        from dnd.ui import screens
        from dnd.game import Game as GameCls
        tmp = ROOT / "out" / "preview-saves"
        save_mod.SAVE_DIR = tmp
        for name, klass, race, depth, mtime in (
                ("Aria", "wizard", "elf", 3, 300.0),
                ("Borin", "warrior", "dwarf", 9, 200.0),
                ("Nix", "rogue", "gnome", 5, 100.0)):
            game = GameCls(21, name, klass, race_id=race)
            game.depth, game.turn = depth, 400 + depth * 37
            game.player.level, game.player.gold = 4, 268
            game.player.hp, game.player.max_hp = 19, 31
            save_mod.save_game(game)
            os.utime(save_mod.save_path(name), (mtime, mtime))
        (tmp / "broken.json").write_text("{ 这不是 JSON", encoding="utf-8")
        scr = RecordScreen(24, 104, keys=[curses.KEY_DOWN, 27])
        screens.save_manager_screen(scr, no_color=False)
        return scr
    scenes["saves"] = ("存档管理（列表 + 角色档案）", save_manager)

    def save_manager_empty():
        """空状态：存档管理必须自己说清楚"怎么才会有存档"。"""
        from dnd.ui import screens
        empty = ROOT / "out" / "preview-saves-empty"
        empty.mkdir(parents=True, exist_ok=True)
        for stale in empty.glob("*.json"):
            stale.unlink()
        save_mod.SAVE_DIR = empty
        scr = RecordScreen(22, 96, keys=[27])
        screens.save_manager_screen(scr, no_color=False)
        return scr
    scenes["saves_empty"] = ("存档管理 · 还没有存档", save_manager_empty)

    def confirm_dialog():
        """删除确认框：危险操作默认停在「取消」，一路敲回车也不会误删。"""
        from dnd.ui import screens
        tmp = ROOT / "out" / "preview-saves"
        save_mod.SAVE_DIR = tmp
        scr = RecordScreen(24, 104, keys=[ord("d"), 27, 27])
        screens.save_manager_screen(scr, no_color=False)
        return scr
    scenes["confirm"] = ("删除确认框（默认「取消」）", confirm_dialog)

    def resume_menu():
        """游戏内 Esc 菜单：继续 / 保存 / 存档管理 / 回开始页 / 退出。"""
        t7, s7 = tui_for(_scenario(), 30, 118)
        t7.handle_key(27)
        return s7
    scenes["pause"] = ("游戏内 Esc 菜单", resume_menu)

    def sized(h, w, **kw):
        def run():
            t3, s3 = tui_for(_scenario(), h, w, **kw)
            t3.draw()
            return s3
        return run

    scenes["small"] = ("窗口过小提示 54x15", sized(15, 54))
    scenes["minsize"] = ("最小尺寸 62x18（无侧栏、无边框）", sized(18, 62))
    scenes["narrow"] = ("窄窗口 100x24", sized(24, 100))

    def ascii_mode():
        """ASCII 兜底：框线/进度条换成 - | + #，供把框线当两格宽的中文终端使用。"""
        from dnd.ui import theme
        with theme.glyph_override("ascii"):
            t6, s6 = tui_for(_scenario(), 24, 100)
            t6.draw()
        return s6
    scenes["ascii"] = ("ASCII 字形兜底 100x24", ascii_mode)
    return scenes


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="preview", description="把 TUI 渲染成 PNG 供人工审阅")
    ap.add_argument("scenes", nargs="*", help="要渲染的场景名（默认全部）")
    ap.add_argument("--list", action="store_true", help="列出所有场景名")
    ap.add_argument("--out", default=str(OUT), help=f"输出目录（默认 {OUT}）")
    ap.add_argument("--font", default=None, help="拉丁字体文件路径（覆盖自动探测）")
    ap.add_argument("--cjk-font", default=None, help="中文字体文件路径（覆盖自动探测）")
    args = ap.parse_args(argv)

    try:
        import PIL  # noqa: F401
    except ImportError:
        print("preview: 需要 Pillow（pip install pillow）。游戏本体不需要它。", file=sys.stderr)
        return 2

    FONT_OVERRIDE[0], FONT_OVERRIDE[1] = args.font, args.cjk_font
    reverse = _patch_theme()
    curses.curs_set = lambda *a, **k: None
    curses.doupdate = lambda *a, **k: None

    scenes = build_scenes()
    if args.list:
        for name, (label, _fn) in scenes.items():
            print(f"  {name:10s} {label}")
        return 0

    print(f"字体：拉丁 {find_font(LATIN_FONTS, args.font) or '(PIL 默认，中文会变方块)'}")
    print(f"      中文 {find_font(CJK_FONTS, args.cjk_font) or '(缺失！中文会变方块)'}")
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    names = args.scenes or list(scenes)
    for name in names:
        if name not in scenes:
            print(f"preview: 没有场景 {name}（--list 看可用场景）", file=sys.stderr)
            return 2
        label, fn = scenes[name]
        overflows = render_png(fn(), reverse, out / f"{name}.png", label)
        print(f"· {name:10s} -> {out / (name + '.png')}")
        for warn in sorted(set(overflows)):
            print(f"    ！{warn}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
