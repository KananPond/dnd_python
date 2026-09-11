"""TUI 布局回归测试（用假 curses 屏幕渲染，不需要真实终端）。

覆盖布局 bug：
  1. 日志区少一行 —— 最新一条消息被底部按键提示栏盖掉；
  2. 侧栏在矮窗口下越界 —— 正文冲掉自己的边框并溢进日志区；
  3. 浮层不清内部 —— 地图的 # 从浮层面板里透出来；
  4. 中文按字符数裁剪 —— 长中文行越过右边界。

断言一律走 Tui.layout() 取坐标，不再硬编码 ±1 或具体框线字符：
框线字符会随字形集（Unicode / ASCII）变化，布局关系不会。
"""

from __future__ import annotations

import curses
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# 非 tty 环境下这些 curses 调用会失败，测试里替换成 no-op
curses.curs_set = lambda *a, **k: None
curses.doupdate = lambda *a, **k: None
curses.has_colors = lambda: False

from dnd import save  # noqa: E402
from dnd.entities import make_item  # noqa: E402
from dnd.game import Game  # noqa: E402
from dnd.ui import describe, theme, widgets  # noqa: E402
from dnd.ui import tui as tui_mod  # noqa: E402

_TMP = pathlib.Path(tempfile.mkdtemp(prefix="dnd-tui-tests-"))
save.SAVE_DIR = _TMP
save.ROSTER = _TMP / "roster.json"


class FakeScreen:
    """足以骗过 Tui 的假屏幕：记录每个字符，越界写入直接报错。"""

    def __init__(self, h: int, w: int, keys=()):
        self.h, self.w = h, w
        self.keys = list(keys)
        self.buf = [[" "] * w for _ in range(h)]
        self.attrs = {}          # (y, x) -> attr：建角焦点/配色断言用（字符记不出属性）
        self.keypad_calls = []

    def getmaxyx(self):
        return self.h, self.w

    def erase(self):
        self.buf = [[" "] * self.w for _ in range(self.h)]
        self.attrs = {}

    def keypad(self, flag):
        self.keypad_calls.append(flag)

    def noutrefresh(self):
        pass

    def addstr(self, y, x, text, attr=0):
        if not (0 <= y < self.h and 0 <= x < self.w):
            raise curses.error(f"out of bounds: {y},{x}")
        for i, ch in enumerate(text):
            if x + i >= self.w:
                raise curses.error("line overflow")
            self.buf[y][x + i] = ch
            self.attrs[(y, x + i)] = attr

    def attr_at(self, y: int, x: int):
        """某个格子上最后落笔的属性（没写过返回 None）。"""
        return self.attrs.get((y, x))

    def getch(self):
        return self.keys.pop(0) if self.keys else 27

    def row(self, y: int) -> str:
        return "".join(self.buf[y])

    def text(self) -> str:
        return "\n".join(self.row(y) for y in range(self.h))


def render(game: Game, h: int, w: int) -> FakeScreen:
    scr = FakeScreen(h, w)
    tui_mod.Tui(scr, game, debug=True, no_color=True).draw()
    return scr


def layout_of(game: Game, h: int, w: int):
    return tui_mod.Tui(FakeScreen(h, w), game, debug=True, no_color=True).layout()


class TestLayout(unittest.TestCase):
    def test_every_log_line_is_visible(self):
        game = Game(6, "Logs", "warrior")
        for i in range(12):
            game.message(f"消息-{i}", "info")
        h, w = 36, 120
        scr = render(game, h, w)
        text = scr.text()
        newest = [f"消息-{i}" for i in range(12 - tui_mod.LOG_LINES, 12)]
        for msg in newest:
            self.assertIn(msg, text, f"{msg} 应该可见（日志区不许被提示栏覆盖）")
        self.assertIn("WASD", scr.row(h - 1), "最后一行应留给按键提示")
        rows = [y for y in range(h) if f"消息-{12 - tui_mod.LOG_LINES}" in scr.row(y)]
        self.assertTrue(rows and rows[0] < h - 1, "日志不能写到提示栏那一行")

    def test_shift_various_sizes_still_show_all_log_lines(self):
        for h, w in ((18, 62), (24, 100), (36, 120), (50, 200)):
            game = Game(6, "Logs", "warrior")
            for i in range(12):
                game.message(f"消息-{i}", "info")
            scr = render(game, h, w)
            text = scr.text()
            for msg in [f"消息-{i}" for i in range(12 - tui_mod.LOG_LINES, 12)]:
                self.assertIn(msg, text, f"{h}x{w} 下 {msg} 不可见")

    def test_log_never_collides_with_hint_bar(self):
        """日志最后一行必须严格在提示栏上方（曾经的 off-by-one 回归）。"""
        for h, w in ((18, 62), (20, 100), (32, 118)):
            L = layout_of(Game(3, "L", "warrior"), h, w)
            self.assertEqual(L.log_top + tui_mod.LOG_LINES - 1, L.hint - 1,
                             f"{h}x{w}：日志区与提示栏之间不能有空隙或重叠")
            self.assertEqual(L.log_rule, L.log_top - 1, f"{h}x{w}：日志分隔线应在日志上方")


    def test_sidebar_keeps_its_border(self):
        game = Game(7, "Panel", "wizard", race_id="gnome")
        game.player.add_buff("ac", 4, 3)
        for _ in range(8):
            game.player.inventory.append(make_item("potion_healing", game.rng, 3))
        for h, w in ((18, 100), (20, 100), (24, 100), (30, 100)):
            L = layout_of(game, h, w)
            scr = render(game, h, w)
            left = L.map_left + L.map_w
            self.assertEqual(left, w - tui_mod.SIDE_W - 2, f"{h}x{w}：侧栏位置变了")
            if L.framed:
                # 带边框时：上下边框完整（不被正文冲掉）
                corners = ((L.map_top, "tl", "tr"), (L.map_top + L.map_h - 1, "bl", "br"))
                for y, lc, rc in corners:
                    seg = scr.row(y)[left:left + tui_mod.SIDE_W]
                    self.assertTrue(seg.startswith(theme.G[lc]) and seg.endswith(theme.G[rc]),
                                    f"{h}x{w}：第 {y} 行侧栏边框被覆盖（{seg!r}）")
            # 侧栏内容不得溢到日志区（分隔线以下）
            for y in range(L.log_rule, h):
                self.assertNotIn("没有敌人", scr.row(y)[left:],
                                 f"{h}x{w}：侧栏内容溢出到第 {y} 行")

    def test_overlay_clears_its_own_interior(self):
        """浮层内部必须清干净：否则地图的 # 会从面板里透出来。"""
        game = Game(11, "Modal", "warrior")
        game.command(("reveal",))          # 整层铺满墙体/地面字形
        h, w = 30, 110
        scr = FakeScreen(h, w)
        tui = tui_mod.Tui(scr, game, debug=True, no_color=True)
        tui.draw()
        tui.inventory_screen()
        L = tui.layout()
        # 找出浮层范围：背包面板居中，标题行含"背包"
        title_rows = [y for y in range(h) if "背包 · 按字母使用或装备" in scr.row(y)]
        self.assertTrue(title_rows, "背包浮层没画出来")
        left = scr.row(title_rows[0]).index("背包") - 2
        self.assertGreater(left, 0, "浮层应该居中，不该贴左边界")
        for y in range(title_rows[0] + 1, title_rows[0] + 3):
            inside = scr.row(y)[left + 1:left + 20]
            self.assertNotIn("#", inside, f"浮层第 {y} 行内部混进了地图字形（{inside!r}）")
        self.assertLess(title_rows[0], L.log_rule, "浮层不该压到日志区")

    def test_overlay_never_touches_the_sidebar(self):
        """回归：浮层按整屏宽度居中会跨到侧栏上——擦掉左边框却留下内容，
        屏幕上就出现"金币"变"币"、"骷髅"变"髅"这种坏掉的界面。"""
        for h, w in ((32, 118), (28, 104)):
            game = Game(17, "Modal", "wizard")
            game.player.gold = 12345
            scr = FakeScreen(h, w)
            tui = tui_mod.Tui(scr, game, debug=True, no_color=True)
            tui.draw()
            before = [scr.row(y) for y in range(h)]
            tui.inventory_screen()
            L = tui.layout()
            left = L.map_left + L.map_w
            for y in range(L.map_top, L.log_rule):
                self.assertEqual(scr.row(y)[left:], before[y][left:],
                                 f"{w}x{h} 第 {y} 行：浮层动到了侧栏")

    def test_map_viewport_fits_level(self):
        game = Game(8, "Map", "warrior")
        for h, w in ((18, 62), (36, 120), (60, 240)):
            scr = render(game, h, w)
            self.assertEqual(len(scr.text().splitlines()), h)
            self.assertIn("@", scr.text(), f"{h}x{w} 下应能看到玩家")


class TestSaveInput(unittest.TestCase):
    def test_f5_and_shift_s_save_and_report_path(self):
        game = Game(12, "SaveInput", "warrior")
        tui = tui_mod.Tui(FakeScreen(24, 100), game, no_color=True)
        path = _TMP / "save-input.json"
        with patch.object(tui_mod.save_mod, "save_game", return_value=path) as save_game:
            tui.handle_key(curses.KEY_F5)
            tui.handle_key(ord("S"))

        self.assertEqual(save_game.call_count, 2)
        self.assertEqual(game.log[-2:], [(f"已保存：{path}", "good")] * 2)

    def test_save_error_stays_in_game_and_is_reported(self):
        game = Game(12, "SaveError", "warrior")
        tui = tui_mod.Tui(FakeScreen(24, 100), game, no_color=True)
        with patch.object(tui_mod.save_mod, "save_game", side_effect=PermissionError("拒绝访问")):
            tui.handle_key(ord("S"))

        self.assertEqual(game.state, "playing")
        self.assertEqual(game.log[-1], ("保存失败：拒绝访问", "bad"))


class TestCreationScreen(unittest.TestCase):
    def test_prefills_cli_values_and_initialises_colors(self):
        """回归：建角界面要先初始化配色，并且不能丢掉 --name/--class/--race 给的值。"""
        calls = []
        original = tui_mod.theme.init_colors
        tui_mod.theme.init_colors = lambda no_color=False: calls.append(no_color)
        try:
            scr = FakeScreen(30, 100, keys=[10])  # 回车确认
            result = tui_mod.creation_screen(scr, True, initial_name="Prefilled",
                                             initial_class="wizard", initial_race="elf")
        finally:
            tui_mod.theme.init_colors = original
        self.assertTrue(calls, "creation_screen 必须先初始化配色，否则建角界面没有主题色")
        self.assertEqual(result, ("Prefilled", "wizard", "elf"))
        self.assertIn("Prefilled", scr.text(), "姓名应预填在界面上")
        # 初始焦点在职业栏：种族栏是"非活动栏"，只能看到弱化标记 ·，不能出现光标 ▸
        self.assertIn(f"{theme.G['dot']} 2. 精灵", scr.text(), "非活动栏也要标出命令行预选的种族")
        self.assertNotIn(f"{theme.G['sel']} 2. 精灵", scr.text(), "光标不该出现在非活动的种族栏")

    def test_only_the_active_column_shows_the_cursor(self):
        """回归：两栏的选中行都整行反白 → 看不出 ↑↓ 会动哪一栏，用户以为种族栏选不了。"""
        scr = FakeScreen(30, 100, keys=[10])
        tui_mod.creation_screen(scr, True)
        text = scr.text()
        self.assertIn(f"{theme.G['sel']} 1. 战士", text, "职业栏应有光标标记")
        self.assertNotIn(f"{theme.G['sel']} 1. 人类", text, "非活动栏不该出现光标标记")
        self.assertIn(f"{theme.G['dot']} 1. 人类", text, "非活动栏仍要标出当前选择")

        scr = FakeScreen(30, 100, keys=[9, 10])   # Tab → 焦点到种族栏
        tui_mod.creation_screen(scr, True)
        text = scr.text()
        self.assertIn(f"{theme.G['sel']} 1. 人类", text, "切栏后光标应移到种族栏")
        self.assertNotIn(f"{theme.G['sel']} 1. 战士", text, "光标应离开职业栏")

    def test_focus_switches_with_tab_shift_tab_and_arrows(self):
        """回归：切栏只认 Tab / ←→，Shift+Tab（KEY_BTAB）被吞掉，种族栏就进不去。"""
        for key in (9, curses.KEY_BTAB, curses.KEY_LEFT, curses.KEY_RIGHT):
            with self.subTest(key=key):
                scr = FakeScreen(30, 100, keys=[key, curses.KEY_DOWN, 10])
                self.assertEqual(tui_mod.creation_screen(scr, True),
                                 ("冒险者", "warrior", "elf"), f"{key=} 应能切到种族栏")
                # 再切一次应回到职业栏：↑↓ 改的是职业
                scr = FakeScreen(30, 100, keys=[key, key, curses.KEY_DOWN, 10])
                self.assertEqual(tui_mod.creation_screen(scr, True),
                                 ("冒险者", "wizard", "human"), f"{key=} 应能切回职业栏")

    def test_active_column_is_drawn_brighter_than_the_inactive_one(self):
        """回归：焦点靠"非活动栏更亮"来暗示（far 比 frame 亮），等于把光标栏藏了起来。"""
        scr = FakeScreen(30, 100, keys=[10])
        tui_mod.creation_screen(scr, True)
        top = tui_mod._creation_layout(30, 100)["panel_top"]
        class_border, race_border = scr.attr_at(top, 4), scr.attr_at(top, 38)  # col_w=30
        self.assertEqual(class_border, theme.attr("amber", True, True), "活动栏边框应最亮 + 加粗")
        self.assertEqual(race_border, theme.attr("mem", True), "非活动栏边框应落到最暗一档")
        self.assertNotEqual(class_border, race_border, "两栏边框必须能分辨出焦点")

        scr = FakeScreen(30, 100, keys=[9, 10])
        tui_mod.creation_screen(scr, True)
        self.assertEqual(scr.attr_at(top, 38), theme.attr("amber", True, True), "切栏后亮边框应跟着走")

    def test_creation_enables_keypad(self):
        """回归：建角跑在 Tui 之前，没开 keypad 时方向键是 ESC 序列，会直接退出游戏。"""
        scr = FakeScreen(30, 100, keys=[10])
        tui_mod.creation_screen(scr, True)
        self.assertIn(True, scr.keypad_calls, "creation_screen 自己要开 keypad，别指望调用方")

    def test_empty_name_falls_back(self):
        scr = FakeScreen(30, 100, keys=[10])
        name, class_id, race_id = tui_mod.creation_screen(scr, True)
        self.assertEqual(name, "冒险者")
        self.assertEqual((class_id, race_id), ("warrior", "human"))

    def test_all_classes_visible_at_every_supported_size(self):
        """回归：选项行号写死 + 页脚写死在 h-3，矮窗口下第 4 个职业会被页脚盖掉。"""
        for h, w in ((18, 62), (20, 80), (22, 80), (24, 80), (30, 100), (36, 120)):
            scr = FakeScreen(h, w, keys=[10])
            tui_mod.creation_screen(scr, True)
            footer = [y for y in range(h) if "Tab" in scr.row(y)]
            self.assertTrue(footer, f"{w}x{h}：找不到页脚行")
            for cls in ("战士", "法师", "牧师", "盗贼"):
                rows = [y for y in range(h) if f". {cls}" in scr.row(y)]
                self.assertTrue(rows, f"{w}x{h}：看不到职业 {cls}")
                self.assertLess(max(rows), footer[0], f"{w}x{h}：职业 {cls} 被页脚盖住")
            for race in ("人类", "精灵", "矮人", "侏儒"):
                rows = [y for y in range(h) if f". {race}" in scr.row(y)]
                self.assertTrue(rows, f"{w}x{h}：看不到种族 {race}")
                self.assertLess(max(rows), footer[0], f"{w}x{h}：种族 {race} 被页脚盖住")

    def test_too_small_shows_hint_instead_of_broken_layout(self):
        for h, w in ((16, 62), (14, 50), (10, 40)):
            scr = FakeScreen(h, w, keys=[])  # 空队列 → getch 返回 Esc → SystemExit
            with self.assertRaises(SystemExit):
                tui_mod.creation_screen(scr, True)
            self.assertIn("终端窗口太小", scr.text(), f"{w}x{h} 应提示窗口太小")
            self.assertIn("62x18", scr.text(), f"{w}x{h} 应提示需要多大")


class TestGlyphFallback(unittest.TestCase):
    def test_ascii_mode_uses_only_ascii_box_drawing(self):
        """东亚洲终端把 ─│ 当两格宽会撑破版面：--ascii / DND_ASCII 必须能整套退回。"""
        with theme.glyph_override("ascii"):
            self.assertEqual(theme.glyph_mode(), "ascii")
            game = Game(9, "Ascii", "cleric")
            L = tui_mod.Tui(FakeScreen(24, 100), game).layout()
            boxed = render(game, 24, 100).row(L.map_top)
            # 只查框线与进度条字形；· 是两种模式下共用的文本分隔符，不算漏网
            keys = ("tl", "tr", "bl", "br", "h", "v", "lt", "rt", "tt", "bt",
                    "heavy_h", "heavy_v", "bar_full", "bar_half", "bar_empty", "sel")
            uni = {theme.UNICODE_GLYPHS[k] for k in keys}
            self.assertEqual(set(boxed) & uni, set(),
                             f"ASCII 模式漏了 Unicode 框线：{boxed!r}")
            self.assertIn("+", boxed, "ASCII 模式应该用 + 画角")

    def test_glyph_override_restores_previous_mode(self):
        """回归：configure_glyphs(x) 返回的是切换**后**的模式，
        曾有人 old = configure_glyphs("ascii") 再还原，等于把 ascii 又设一遍，
        之后整场渲染都被钉在 ASCII。"""
        theme.configure_glyphs("unicode")
        with theme.glyph_override("ascii"):
            self.assertEqual(theme.glyph_mode(), "ascii")
        self.assertEqual(theme.glyph_mode(), "unicode", "退出 with 后应还原，而不是停在 ascii")

    def test_explicit_glyph_mode_is_not_clobbered_by_init_colors(self):
        """回归：init_colors() 里也会探测字形，曾把刚设好的 ascii 悄悄改回 unicode。"""
        with theme.glyph_override("ascii"):
            theme.init_colors(no_color=True)
            self.assertEqual(theme.glyph_mode(), "ascii", "init_colors 覆盖了显式字形模式")

    def test_unicode_mode_uses_unicode_box_drawing(self):
        with theme.glyph_override("unicode"):
            game = Game(9, "Uni", "cleric")
            L = tui_mod.Tui(FakeScreen(24, 100), game).layout()
            scr = render(game, 24, 100)
            self.assertIn(theme.UNICODE_GLYPHS["tl"], scr.row(L.map_top))
            self.assertNotIn("+--", scr.row(L.map_top), "Unicode 模式不该出现 ASCII 框线")


class TestWidgets(unittest.TestCase):
    """绘制辅助的单元测试（这些函数是所有界面文本的必经之路）。"""

    def test_clip_counts_display_width_not_characters(self):
        """回归：按字符数裁剪会让长中文行越过右边界（终端报错或被折行）。"""
        self.assertEqual(widgets.clip("你好世界", 4), "你好")
        self.assertEqual(widgets.clip("你好世界", 5), "你好")   # 放不下的宽字符整字丢弃
        self.assertEqual(widgets.clip("abc你", 4), "abc")
        self.assertEqual(widgets.clip("anything", 0), "")

    def test_pad_to_aligns_cjk(self):
        self.assertEqual(widgets._width(widgets.pad_to("你好", 10)), 10)
        self.assertEqual(widgets._width(widgets.pad_to("abc", 10)), 10)
        self.assertEqual(widgets.pad_to("abcdef", 3), "abcdef")  # 已超宽就不再补

    def test_bar_clamps_fraction_and_keeps_width(self):
        scr = FakeScreen(3, 20)
        widgets.bar(scr, 0, 0, 10, 5.0, "good")     # >1 不该画出 50 格
        self.assertEqual(scr.row(0)[:10], theme.G["bar_full"] * 10)
        widgets.bar(scr, 1, 0, 10, -3.0, "good")    # <0 不该画负格
        self.assertEqual(scr.row(1)[:10], theme.G["bar_empty"] * 10)
        widgets.bar(scr, 2, 0, 10, 0.5, "good")
        self.assertEqual(scr.row(2)[:10], theme.G["bar_full"] * 5 + theme.G["bar_empty"] * 5)

    def test_frame_footer_sits_on_the_border_not_on_content(self):
        """回归：页脚曾经压在最后一行内容上，把边框和文字一起糊掉。"""
        scr = FakeScreen(8, 30)
        widgets.frame(scr, 1, 0, 6, 28, "标题", 0, foot="页脚")
        self.assertIn("标题", scr.row(1), "标题应嵌在上边框里")
        self.assertIn("页脚", scr.row(6), "页脚应写在下边框上")
        self.assertNotIn("页脚", scr.row(5), "页脚不该压到内容行")
        border = scr.row(6)[:28]
        self.assertTrue(border.startswith(theme.G["bl"]) and border.endswith(theme.G["br"]))
        self.assertEqual(scr.row(6)[:7], theme.G["bl"] + theme.G["h"] * 6)
        self.assertEqual(scr.row(5)[:28].count(theme.G["br"]), 0, "内容行不该有右边框残留")

    def test_put_never_writes_past_the_right_edge(self):
        scr = FakeScreen(4, 10)
        widgets.put(scr, 0, 9, "中文", 0)      # 只剩 1 格，宽字符整个放弃
        self.assertEqual(scr.row(0), " " * 10)
        widgets.put(scr, 1, 8, "中文", 0)      # 刚好 2 格，能放下
        self.assertEqual(scr.row(1)[8:], "中 ")
        widgets.put(scr, 1, 6, "ab中文", 0)    # 只有 4 格：ab 之后只放得下一个宽字符
        self.assertEqual(scr.row(1)[6:], "ab中 ")
        # 最后一行的最后一格要留给 curses（写它会抛错），其余列都能写
        widgets.put(scr, 3, 9, "x", 0)
        self.assertEqual(scr.row(3)[9], " ")
        widgets.put(scr, 3, 8, "xy", 0)
        self.assertEqual(scr.row(3)[:10], " " * 8 + "x ")


class TestDescribe(unittest.TestCase):
    def test_effect_ids_never_leak_to_players(self):
        """回归：背包里曾经直接打印 effect 字段，出现"闪电卷轴 damage_nearest"。"""
        game = Game(13, "Desc", "wizard")
        for item_id in ("scroll_lightning", "scroll_firestorm", "potion_healing", "sword",
                        "chain_mail"):
            item = make_item(item_id, game.rng, 3)
            text = describe.item_summary(item)
            self.assertNotIn("_", text, f"{item.name} 的说明里漏了内部字段：{text!r}")
            self.assertTrue(text, f"{item.name} 应该有说明")
        self.assertEqual(describe.item_summary(make_item("sword", game.rng, 1)), "伤害 1d8")
        self.assertEqual(describe.item_summary(make_item("chain_mail", game.rng, 1)), "护甲 +5")

    def test_unknown_effect_falls_back_to_raw_value(self):
        """数据表加新 effect 时宁可在界面上露出原名，也不要静默丢信息。"""
        self.assertEqual(describe.effect_text("brand_new_thing", "2d6"), "brand_new_thing")
        self.assertEqual(describe.effect_text(None), "")


if __name__ == "__main__":
    unittest.main()
