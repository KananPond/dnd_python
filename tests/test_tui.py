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
import os
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
from dnd.ui import screens as screens_mod  # noqa: E402
from dnd.ui import tui as tui_mod  # noqa: E402
from dnd.ui.widgets import _width  # noqa: E402

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

    def resize(self, h: int, w: int):
        """模拟终端被缩放（KEY_RESIZE 之后调用方会重画）。"""
        self.h, self.w = h, w
        self.buf = [[" "] * w for _ in range(h)]
        self.attrs = {}

    def row(self, y: int) -> str:
        return "".join(self.buf[y])

    def text(self) -> str:
        return "\n".join(self.row(y) for y in range(self.h))


def row_of(scr: FakeScreen, needle: str) -> int:
    rows = [y for y in range(scr.h) if needle in scr.row(y)]
    return rows[0] if rows else -1


def is_pressed(scr: FakeScreen, y: int, col: int) -> bool:
    """(y, col) 这格是不是"反白"的（选中行的底色）。"""
    attr = scr.attr_at(y, col)
    return attr is not None and bool(attr & curses.A_REVERSE)


def highlight_row(scr: FakeScreen, text: str) -> bool:
    """菜单里 `text` 那一项是否处于反白的选中行。

    做法：先找出这一行的第一个反白格（= 光标行的底色起点），跳过底色上的空格与
    光标标记，再看 text 是否正好从这里开始。两个坑：面板左边框也压在反白底色上
    （不能拿"行内首个非空格"当起点），以及中文占两格（不能用 `str.index` 的字符下标当列号）。
    """
    for y in range(scr.h):
        row = scr.row(y)
        if text not in row:
            continue
        revs = [x for x in range(scr.w) if is_pressed(scr, y, x)]
        if not revs:
            return False
        col = revs[0]
        while col < scr.w and (row[col] == " " or row[col] == theme.G["sel"]):
            col += 1
        return row[col:col + len(text)] == text
    return False


def selected_rows(scr: FakeScreen) -> list:
    """光标所在行（= 反白底色横跨整行的那一行）。用于断言"只有一行被选中"。

    判据：该行的最左与最右反白格之间被反白铺满 —— 面板边框压在反白上仍算选中行。
    """
    out = []
    for y in range(scr.h):
        row = scr.row(y)
        revs = [x for x in range(scr.w) if is_pressed(scr, y, x)]
        if not revs or revs[-1] - revs[0] < 8:
            continue
        if all(is_pressed(scr, y, x) for x in range(revs[0], revs[-1] + 1)):
            out.append(y)
    return out


def only_selected_row(scr: FakeScreen) -> int:
    rows = selected_rows(scr)
    assert len(rows) == 1, f"菜单里应该恰好有一行反白，实际 {rows}"
    return rows[0]


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


class TestPrologueScreen(unittest.TestCase):
    """建角之后的序章：必定展示、能翻页读完、且必定能回到游戏。"""

    NAME = "Aria"

    def _run(self, h, w, keys):
        scr = FakeScreen(h, w, keys=keys)
        screens_mod.prologue_screen(scr, self.NAME, True)
        return scr

    def test_shows_world_background_and_key_hints(self):
        scr = self._run(32, 100, [27])
        text = scr.text()
        self.assertIn("序章", text, "标题要写清楚这是背景故事")
        self.assertIn("阿瑟兰", text, "第一页要交代世界")
        self.assertIn("深渊地牢", text, "标题栏保持和游戏一致的称谓")
        for hint in ("滚动", "翻页", "进入地牢", "跳过"):
            self.assertIn(hint, text, f"提示栏应告诉玩家「{hint}」")
        self.assertIn("1/2 页", text, "要显示读到第几页")

    def test_initialises_colors_and_keypad(self):
        """建角之后紧接着就是它，同样跑在 Tui 之前：配色与 keypad 都得自己开。"""
        calls = []
        original = screens_mod.theme.init_colors
        screens_mod.theme.init_colors = lambda no_color=False: calls.append(no_color)
        try:
            scr = self._run(32, 100, [27])
        finally:
            screens_mod.theme.init_colors = original
        self.assertTrue(calls, "序章要先初始化配色")
        self.assertIn(True, scr.keypad_calls, "序章要自己开 keypad，否则方向键会变成 ESC")

    def test_arrow_key_reaches_the_descent_page(self):
        """宽屏下两页都放得下：→ 翻一次就是「入井」页（讲怎么进地牢 + 下井须知）。"""
        scr = self._run(40, 110, [curses.KEY_RIGHT, 27])
        text = scr.text()
        self.assertIn("2/2 页", text, "翻页后应停在最后一页")
        self.assertIn("深渊之门", text, "入井页要讲清楚玩家怎么进地牢")
        self.assertIn(self.NAME, text, "入井页要按名字称呼角色")
        self.assertIn("十层", text, "入井页要留下井前须知")

    def test_enter_walks_the_whole_story_and_then_returns(self):
        """回车一路读到底必须**回到游戏**（不是卡住，也不是退出）。"""
        scr = FakeScreen(30, 100, keys=[10] * 8)
        self.assertIsNone(screens_mod.prologue_screen(scr, self.NAME, True))

    def test_escape_skips_without_cancelling_the_run(self):
        scr = FakeScreen(30, 100, keys=[27])
        self.assertIsNone(screens_mod.prologue_screen(scr, self.NAME, True))

    def test_borders_stay_intact_at_every_supported_size(self):
        for h, w in ((18, 62), (20, 80), (24, 100), (36, 120)):
            with self.subTest(size=(h, w)):
                scr = self._run(h, w, [27])
                text = scr.text()
                self.assertIn("序章", text, f"{w}x{h}：看不到序章标题")
                # 上下边框与左右竖线都要完整：正文不能把框顶破
                top = row_of(scr, "序章")
                bottom = max(y for y in range(h) if theme.G["bl"] in scr.row(y))
                self.assertGreater(bottom, top, f"{w}x{h}：找不到完整边框")
                left = scr.row(top).index(theme.G["tl"])
                right = scr.row(top).rindex(theme.G["tr"])
                self.assertGreater(right - left, 20, f"{w}x{h}：面板太窄")
                for y in range(top + 1, bottom):
                    row = scr.row(y)
                    self.assertEqual(row[left], theme.G["v"], f"{w}x{h}：第 {y} 行左边框被冲掉")
                    self.assertEqual(row[right], theme.G["v"], f"{w}x{h}：第 {y} 行右边框被冲掉")
                self.assertIn("页", scr.row(bottom), f"{w}x{h}：页脚应写在下边框上")

    def test_ascii_mode_swaps_box_drawing_and_arrows(self):
        """--ascii 是给"把框线/箭头当两格宽"的终端用的：序章自己画的部分也要跟着换。"""
        with theme.glyph_override("ascii"):
            scr = FakeScreen(18, 62, keys=[27])
            screens_mod.prologue_screen(scr, self.NAME, True)
            self.assertEqual(theme.G["tl"], "+")
            self.assertEqual(theme.G["down"], "v")
        text = "\n".join(scr.row(y) for y in range(scr.h - 1))
        for unicode_only in ("─", "│", "┌", "┐", "└", "┘", "↑", "↓"):
            self.assertNotIn(unicode_only, text, f"ASCII 模式仍画出了 {unicode_only}")
        self.assertIn("+", text, "ASCII 模式的边框应是 +")
        self.assertIn("v", text, "内容放不下时应有向下滚动提示")

    def test_too_small_returns_instead_of_crashing_or_quitting(self):
        """窗口太小时角色已经建好了：给提示并按任意键进场，不能抛 SystemExit。"""
        scr = FakeScreen(12, 50, keys=[10])
        self.assertIsNone(screens_mod.prologue_screen(scr, self.NAME, True))
        self.assertIn("终端窗口太小", scr.text())


class TestBackgroundKey(unittest.TestCase):
    """游戏内按 B 重看序章：和建角后的序章共用同一个界面。"""

    def test_b_opens_the_prologue(self):
        game = Game(21, "Aria", "wizard", race_id="elf")
        scr = FakeScreen(30, 100, keys=[27])
        tui_mod.Tui(scr, game, no_color=True).background_screen()
        text = scr.text()
        self.assertIn("序章", text)
        self.assertIn("阿瑟兰", text, "B 打开的应该是那份世界背景，而不是空屏")

    def test_hint_bar_advertises_the_background_key(self):
        game = Game(21, "Aria", "warrior")
        scr = render(game, 36, 120)
        self.assertIn("背景", scr.row(35), "按键提示栏要告诉玩家 B 能看背景")


class TestStartScreen(unittest.TestCase):
    """开始页：启动后先看到它，↑↓ 选菜单，回车确认。"""

    def test_shows_logo_items_and_key_hints(self):
        scr = FakeScreen(30, 100, keys=[27])
        self.assertEqual(screens_mod.start_screen(scr, True), "quit")
        text = scr.text()
        self.assertIn("深渊地牢", text)
        for item in ("新的冒险", "读取存档", "名人堂", "退出游戏"):
            self.assertIn(item, text, f"开始页应该看得到「{item}」")
        self.assertIn("PLATO（1975）", text, "副标题是这一屏的门面")
        self.assertIn("↑↓", text, "必须提示方向键可用")

    def test_arrow_keys_move_the_highlight(self):
        """回归重点：菜单必须是**看得见**的光标，不能只有底部一行提示。"""
        scr = FakeScreen(30, 100, keys=[27])
        screens_mod.start_screen(scr, True)
        self.assertTrue(highlight_row(scr, "新的冒险"), "默认选中第一项")
        self.assertIn(f"{theme.G['sel']} 新的冒险", scr.text(), "选中行要有光标标记")

        scr = FakeScreen(30, 100, keys=[curses.KEY_DOWN, 27])
        screens_mod.start_screen(scr, True)
        self.assertTrue(highlight_row(scr, "读取存档"), "↓ 之后光标应在第二项")
        self.assertFalse(highlight_row(scr, "新的冒险"), "光标必须离开第一项")

        scr = FakeScreen(30, 100, keys=[curses.KEY_DOWN, curses.KEY_DOWN, curses.KEY_UP, 27])
        screens_mod.start_screen(scr, True)
        self.assertTrue(highlight_row(scr, "读取存档"), "↑ 应该能退回去")

    def test_only_the_selected_row_is_reversed(self):
        """反白必须只有一行：多行反白就看不出方向键会动哪一项。"""
        scr = FakeScreen(30, 100, keys=[27])
        screens_mod.start_screen(scr, True)
        self.assertEqual(len(selected_rows(scr)), 1, f"反白行：{selected_rows(scr)}")

    def test_menu_does_not_shift_when_the_selection_moves(self):
        """光标只应该"换行"，不该让面板长高/变宽（否则一按方向键整屏就跳）。"""
        scr = FakeScreen(30, 100, keys=[27])
        screens_mod.start_screen(scr, True)
        before = (row_of(scr, "新的冒险"), row_of(scr, "退出游戏"))
        scr = FakeScreen(30, 100, keys=[curses.KEY_DOWN, curses.KEY_DOWN, 27])
        screens_mod.start_screen(scr, True)
        after = (row_of(scr, "新的冒险"), row_of(scr, "退出游戏"))
        self.assertNotEqual(before, (-1, -1), "选项没画出来")
        self.assertEqual(before, after, "选项行位置不该随光标移动而变化")

    def test_arrow_keys_wrap_around(self):
        scr = FakeScreen(30, 100, keys=[curses.KEY_UP, 27])
        screens_mod.start_screen(scr, True)
        self.assertTrue(highlight_row(scr, "退出游戏"), "在首项按 ↑ 应绕到末项")

    def test_enter_selects_new_game_and_load(self):
        scr = FakeScreen(30, 100, keys=[10])
        self.assertEqual(screens_mod.start_screen(scr, True), "new", "回车应选择当前项")
        scr = FakeScreen(30, 100, keys=[curses.KEY_DOWN, 10])
        self.assertEqual(screens_mod.start_screen(scr, True), "load", "↓ + 回车 → 读取存档")
        scr = FakeScreen(30, 100, keys=[ord("2"), 10])
        self.assertEqual(screens_mod.start_screen(scr, True), "load", "1-4 直选也应生效")

    def test_load_row_counts_the_saves(self):
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="dnd-menu-count-"))
        old = save.SAVE_DIR
        save.SAVE_DIR = tmp
        try:
            for name in ("A", "B"):
                save.save_game(Game(1, f"Menu{name}", "warrior"))
            scr = FakeScreen(30, 100, keys=[27])
            screens_mod.start_screen(scr, True)
            text = scr.text()
        finally:
            save.SAVE_DIR = old
        self.assertIn("2 个存档", text, "「读取存档」旁应写明有几个存档")

    def test_start_screen_enables_keypad_and_colors(self):
        """回归：没开 keypad 时方向键会以 ESC 序列到达 —— 按一下 ↑ 就把游戏退了。"""
        calls = []
        original = screens_mod.theme.init_colors
        screens_mod.theme.init_colors = lambda no_color=False: calls.append(no_color)
        try:
            scr = FakeScreen(30, 100, keys=[27])
            screens_mod.start_screen(scr, True)
        finally:
            screens_mod.theme.init_colors = original
        self.assertIn(True, scr.keypad_calls, "开始页自己要开 keypad")
        self.assertTrue(calls, "开始页也要初始化配色（它跑在 Tui 之前）")

    def test_too_small_shows_hint_and_can_still_exit(self):
        scr = FakeScreen(12, 50, keys=[27])
        self.assertEqual(screens_mod.start_screen(scr, True), "quit")
        self.assertIn("终端窗口太小", scr.text())
        scr = FakeScreen(12, 50, keys=[curses.KEY_RESIZE, curses.KEY_RESIZE, 27])
        self.assertEqual(screens_mod.start_screen(scr, True), "quit",
                         "堆叠的 KEY_RESIZE 要被吞掉，不能卡住")


def _make_save(scr_dir, name: str, *, klass: str = "warrior", race: str = "human",
               depth: int = 2, turn: int = 120, gold: int = 88, hp: int = 9,
               date: str = "2026-09-10 20:00", mtime: float | None = None):
    """造一份**真能读回来**的存档，再把摘要字段钉成测试要的值。

    刻意不用手写 JSON：手写的假存档一旦和 Game.from_json 的要求脱节，
    "回车读档"这条路径就测不到了（读的是测试自己的错，不是产品的错）。
    """
    import json
    game = Game(5, name, klass, race_id=race)
    game.depth, game.turn = depth, turn
    game.player.level = 3
    game.player.gold, game.player.hp = gold, hp
    path = save.save_game(game)                    # 文件名由角色名决定
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["_meta"].update({"level": 3, "depth": depth, "turn": turn, "gold": gold,
                         "hp": hp, "max_hp": 21, "date": date})
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    if mtime is not None:                          # index() 按 mtime 排序
        os.utime(path, (mtime, mtime))
    return path


class FrameScreen(FakeScreen):
    """每按一次键就记下当前画面 —— "提示曾经出现过"这类断言用它。

    界面会在玩家按键后重画（例如删除成功后就切回列表），所以"最后停在退出那一帧"
    并不包含刚才的提示。断言"某一帧里出现过这句话"才是真正想测的东西。
    """

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.frames: list[str] = []

    def getch(self):
        self.frames.append(self.text())
        return super().getch()

    def ever(self, needle: str) -> bool:
        return any(needle in frame for frame in self.frames)


class TestSaveManagerScreen(unittest.TestCase):
    """存档管理界面：不用输命令就能看存档、读存档、删存档。"""

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="dnd-savemgr-"))
        self._old_dir = save.SAVE_DIR
        save.SAVE_DIR = self.tmp

    def tearDown(self):
        save.SAVE_DIR = self._old_dir

    def test_empty_state_explains_itself(self):
        scr = FakeScreen(28, 100, keys=[27])
        self.assertIsNone(screens_mod.save_manager_screen(scr, True))
        text = scr.text()
        self.assertIn("存档管理", text)
        self.assertIn("F5", text, "空列表要告诉玩家怎么产生存档")
        self.assertIn("暂无存档", text)
        self.assertIn("↑↓", text)

    def test_lists_every_save_and_navigates_with_arrows(self):
        # 文件名由 save.safe_name(角色名) 决定 → 小写；_make_save 会把它返回
        aria = _make_save(self.tmp, "Aria", klass="wizard", race="elf", depth=3, mtime=1.0)
        borin = _make_save(self.tmp, "Borin", klass="warrior", race="dwarf", depth=7, mtime=2.0)
        scr = FakeScreen(28, 100, keys=[27])
        screens_mod.save_manager_screen(scr, True)
        text = scr.text()
        self.assertIn("Aria", text)
        self.assertIn("Borin", text)
        self.assertIn("共 2 个存档", text, "面板页脚应写明总数")
        # 最近保存的排在前面（mtime=2.0 的 Borin）
        self.assertLess(row_of(scr, "Borin"), row_of(scr, "Aria"))
        self.assertTrue(highlight_row(scr, "Borin"), "默认选中最近一条")
        self.assertEqual(len(selected_rows(scr)), 1, "存档列表只应有一行反白")
        self.assertIn("矮人·战士 3级", text, "右栏应显示选中角色的档案")
        self.assertIn(borin.name, text, "右栏应写明存档文件名")

        scr = FakeScreen(28, 100, keys=[curses.KEY_DOWN, 27])
        screens_mod.save_manager_screen(scr, True)
        self.assertTrue(highlight_row(scr, "Aria"), "↓ 应把光标移到下一条")
        self.assertIn("精灵·法师 3级", scr.text(), "右栏应跟着光标换成 Aria")
        self.assertNotEqual(aria.name, borin.name, "两个存档不该互相覆盖")

    def test_enter_loads_the_selected_save(self):
        path = _make_save(self.tmp, "Loader", klass="cleric", depth=5)
        scr = FakeScreen(28, 100, keys=[10])
        game = screens_mod.save_manager_screen(scr, True)
        self.assertIsNotNone(game, "回车应该读出存档")
        self.assertEqual(game.player.name, "Loader")
        self.assertEqual(game.player.class_id, "cleric")
        self.assertEqual(game.depth, 5)
        self.assertTrue(path.exists(), "读档不该删掉存档文件")

    def test_corrupt_save_is_listed_and_never_crashes_the_screen(self):
        """回归：一个读不动的 JSON 不能让整个界面崩掉 —— 否则玩家只能回命令行删文件。"""
        broken = self.tmp / "broken.json"
        broken.write_text("{ 这不是 JSON", encoding="utf-8")
        scr = FakeScreen(28, 100, keys=[27])
        self.assertIsNone(screens_mod.save_manager_screen(scr, True))
        text = scr.text()
        self.assertIn("broken", text, "坏存档也要列出来，玩家才有机会删它")
        self.assertIn("损坏", text, "列表里要标出这条读不动")
        self.assertIn("读取失败", text, "选中坏存档时右栏要写明原因")
        self.assertIn("D", text, "要提示可以用 D 删掉它")

    def test_entering_a_corrupt_save_reports_instead_of_loading(self):
        broken = self.tmp / "broken.json"
        broken.write_text("{ 这不是 JSON", encoding="utf-8")
        scr = FrameScreen(28, 100, keys=[10, curses.KEY_UP, 27])
        self.assertIsNone(screens_mod.save_manager_screen(scr, True), "坏存档不该被读进来")
        self.assertTrue(scr.ever("读不动"))

    def test_delete_asks_first_and_defaults_to_cancel(self):
        """危险操作默认停在「取消」：一路敲回车的人不该删掉存档。"""
        path = _make_save(self.tmp, "Doomed")
        scr = FrameScreen(28, 100, keys=[ord("d"), 10, curses.KEY_UP, 27])
        self.assertIsNone(screens_mod.save_manager_screen(scr, True))
        self.assertTrue(path.exists(), "确认框默认停在「取消」，回车不该删文件")
        self.assertTrue(scr.ever("请确认"), "删除前必须先问一句")
        self.assertTrue(scr.ever("Doomed"), "确认框要点名是哪个角色")

    def test_delete_removes_the_file_when_confirmed(self):
        doomed = _make_save(self.tmp, "Doomed")
        keeper = _make_save(self.tmp, "Keeper", mtime=1.0)
        scr = FrameScreen(28, 100, keys=[ord("d"), curses.KEY_RIGHT, 10, curses.KEY_UP, 27])
        screens_mod.save_manager_screen(scr, True)
        self.assertFalse(doomed.exists(), "选中「确定」后回车应真的删除")
        self.assertTrue(keeper.exists(), "另一个存档不该受影响")
        self.assertTrue(scr.ever("已删除"), "删除结果要写回界面")

    def test_delete_failure_is_reported_not_raised(self):
        _make_save(self.tmp, "Locked")
        scr = FrameScreen(28, 100, keys=[ord("d"), curses.KEY_RIGHT, 10, curses.KEY_UP, 27])
        with patch.object(screens_mod.save_mod, "delete_save",
                          side_effect=PermissionError("拒绝访问")):
            screens_mod.save_manager_screen(scr, True)
        self.assertTrue(scr.ever("删除失败：拒绝访问"))

    def test_delete_can_be_cancelled_with_escape(self):
        path = _make_save(self.tmp, "Safe")
        scr = FakeScreen(28, 100, keys=[ord("d"), 27, 27])
        screens_mod.save_manager_screen(scr, True)
        self.assertTrue(path.exists(), "确认框里按 Esc 应取消删除")

    def test_load_failure_is_reported_not_raised(self):
        """文件在列表之后被删/被改坏：读档失败要回到界面并提示，不能抛异常。"""
        _make_save(self.tmp, "Vanishing")
        scr = FrameScreen(28, 100, keys=[10, curses.KEY_UP, 27])
        with patch.object(screens_mod.save_mod, "load_game",
                          side_effect=ValueError("JSON 损坏")):
            self.assertIsNone(screens_mod.save_manager_screen(scr, True))
        self.assertTrue(scr.ever("读取失败"))

class TestRosterScreens(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="dnd-roster-"))
        self._old = save.ROSTER
        save.ROSTER = self.tmp / "roster.json"
        save.ROSTER.write_text(
            '[{"name":"Aria","race":"精灵","class":"法师","level":6,"depth":7,'
            '"result":"dead","gold":412,"turns":1883,"date":"2026-09-08 21:14"},'
            '{"name":"Borin","race":"矮人","class":"战士","level":9,"depth":10,'
            '"result":"won","gold":1204,"turns":3421,"date":"2026-09-09 02:40"}]',
            encoding="utf-8")

    def tearDown(self):
        save.ROSTER = self._old

    def test_lobby_lists_roster_entries(self):
        scr = FakeScreen(30, 100, keys=[27])
        screens_mod.lobby_screen(scr, True)
        text = scr.text()
        self.assertIn("名人堂", text)
        self.assertIn("Aria", text)
        self.assertIn("Borin", text)
        self.assertIn("胜利", text)
        self.assertIn("阵亡", text)

    def test_lobby_handles_empty_roster(self):
        save.ROSTER.unlink()
        scr = FakeScreen(30, 100, keys=[27])
        screens_mod.lobby_screen(scr, True)
        self.assertIn("还没有冒险者", scr.text())

    def test_game_roster_overlay_shows_the_same_rows(self):
        game = Game(3, "Roster", "warrior")
        scr = FakeScreen(30, 100, keys=[27])
        tui = tui_mod.Tui(scr, game, no_color=True)
        tui.roster_screen()
        text = scr.text()
        self.assertIn("Aria", text)
        self.assertIn("Borin", text)


class TestPauseMenu(unittest.TestCase):
    """游戏内 Esc 菜单：继续 / 存档 / 存档管理 / 返回开始页 / 退出。"""

    def test_escape_opens_the_menu_and_shows_actions(self):
        game = Game(21, "Pause", "warrior")
        scr = FakeScreen(30, 110, keys=[27])
        tui = tui_mod.Tui(scr, game, no_color=True)
        tui.handle_key(27)
        text = scr.text()
        self.assertIn("已暂停", text)
        for item in ("继续游戏", "保存进度", "存档管理", "返回开始页", "退出游戏"):
            self.assertIn(item, text, f"菜单里应该有「{item}」")
        self.assertTrue(highlight_row(scr, "继续游戏"), "默认选中「继续游戏」")

    def test_arrow_keys_walk_the_menu(self):
        game = Game(21, "Pause", "warrior")
        scr = FakeScreen(30, 110, keys=[curses.KEY_DOWN, curses.KEY_DOWN, 27])
        tui = tui_mod.Tui(scr, game, no_color=True)
        tui.handle_key(27)
        self.assertTrue(highlight_row(scr, "存档管理"), "↓↓ 应停在「存档管理」")

    def test_save_from_the_menu_writes_the_file(self):
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="dnd-pause-save-"))
        old = save.SAVE_DIR
        save.SAVE_DIR = tmp
        try:
            game = Game(21, "PauseSaver", "warrior")
            scr = FakeScreen(30, 110, keys=[curses.KEY_DOWN, 10])
            tui = tui_mod.Tui(scr, game, no_color=True)
            tui.handle_key(27)                      # ↓ 到「保存进度」+ 回车
            self.assertTrue((tmp / "pausesaver.json").exists(), "「保存进度」应真的写盘")
            self.assertIn("已保存", game.log[-1][0], "存档结果要写进消息日志")
        finally:
            save.SAVE_DIR = old

    def test_return_to_title_confirms_first(self):
        """回归：回开始页会丢掉未保存的进度，必须先问一句，而且默认停在「取消」。"""
        game = Game(21, "Pause", "warrior")
        scr = FrameScreen(30, 110, keys=[curses.KEY_DOWN, curses.KEY_DOWN, curses.KEY_DOWN,
                                         10, curses.KEY_DOWN, 27])
        tui = tui_mod.Tui(scr, game, no_color=True)
        tui.handle_key(27)                          # ↓↓↓ 到「返回开始页」+ 回车
        self.assertTrue(scr.ever("返回开始页？"), "回开始页要先问一句（未保存会丢）")
        self.assertTrue(scr.ever("请确认"), "确认框要看得见")

    def test_confirm_dialog_cancel_keeps_playing(self):
        """默认停在「取消」：敲回车不该把这一局丢掉。"""
        game = Game(21, "Pause", "warrior")
        scr = FrameScreen(30, 110, keys=[curses.KEY_DOWN, curses.KEY_DOWN, curses.KEY_DOWN,
                                         10, 10, 27])
        tui = tui_mod.Tui(scr, game, no_color=True)
        tui.handle_key(27)                          # 回车落在「取消」上 → 回到暂停菜单
        self.assertTrue(scr.ever("菜单 · 已暂停"), "取消后应留在暂停菜单里")

    def test_in_game_save_manager_loads_a_game(self):
        game = Game(21, "Pause", "warrior")
        loaded = Game(99, "Loaded", "wizard")
        scr = FakeScreen(30, 110)
        tui = tui_mod.Tui(scr, game, no_color=True)
        with patch.object(screens_mod, "save_manager_screen", return_value=loaded) as mgr:
            tui.saves_screen()
        self.assertTrue(mgr.called, "游戏内应复用开始页那个存档管理界面")
        self.assertIs(tui.game, loaded, "读档后当前这一局应换成存档里的角色")

    def test_escape_is_advertised_in_the_hint_bar(self):
        game = Game(21, "Pause", "warrior")
        scr = render(game, 30, 110)
        self.assertIn("Esc", scr.row(29), "按键提示栏要写明 Esc 是菜单")


class TestPanelGeometry(unittest.TestCase):
    """面板排版公式（screens.panel_rect）：它同时喂给 draw_panel 和调用方，算错就是全屏错。"""

    def test_panel_width_follows_the_window_width_not_the_height(self):
        """回归：panel_rect 只收了高度当"可用宽度"，于是 24 行高的窗口里
        所有面板都被压到 22 格宽 —— 确认框窄成一条缝，文字被截断。"""
        _, _, wide = screens_mod.panel_rect(24, 120, items=2, desc=True, width=60, min_w=34)
        self.assertEqual(wide, 60, "宽窗口下面板宽度应等于请求的宽度")
        for h in (18, 24, 40):
            _, _, box_w = screens_mod.panel_rect(h, 120, items=2, desc=True,
                                                 width=60, min_w=34)
            self.assertEqual(box_w, 60, f"面板宽度不该随窗口高度 {h} 变化")

    def test_panel_width_is_clamped_by_the_region(self):
        """游戏内浮层只在游玩区里居中：region_w 变窄时必须跟着变窄，不能越到侧栏上。"""
        _, _, box_w = screens_mod.panel_rect(30, 118, items=2, desc=True, width=60,
                                             min_w=34, region_w=89)
        self.assertEqual(box_w, 60)
        _, _, narrow = screens_mod.panel_rect(30, 118, items=2, desc=True, width=60,
                                              min_w=34, region_w=48)
        self.assertEqual(narrow, 46, "region_w - 2 是硬上限")
        _, _, floored = screens_mod.panel_rect(30, 118, items=2, desc=True, width=60,
                                               min_w=34, region_w=30)
        self.assertEqual(floored, 34, "再窄也不低于 min_w")

    def test_height_grows_with_rows_and_extra_padding(self):
        _, base, _ = screens_mod.panel_rect(30, 100, items=2, desc=True, width=40)
        _, taller, _ = screens_mod.panel_rect(30, 100, items=2, desc=True, width=40,
                                              extra_rows=4)
        self.assertEqual(taller, base + 4, "extra_rows 应原样加进高度")

    def test_draw_panel_returns_the_predicted_size(self):
        """draw_panel 的实际边框必须落在 panel_rect 预测的位置上（不然测试定位全错）。"""
        scr = FakeScreen(30, 100)
        top, box_h, box_w = screens_mod.panel_rect(
            30, 100, items=4, desc=True, hint_rows=["a"], width=46, min_w=46)
        got_w, got_left = screens_mod.draw_panel(
            scr, title="T", items=[("一", ""), ("二", ""), ("三", ""), ("四", "")],
            width=46, select=0, desc="说明", hint_rows=["a"], foot="f", min_w=46, boot=True)
        self.assertEqual(got_w, box_w)
        self.assertEqual(scr.row(top)[got_left], theme.G["tl"], "上边框不在预测的位置上")
        self.assertEqual(scr.row(top + box_h - 1)[got_left], theme.G["bl"], "下边框不在预测的位置上")

    def test_tall_panel_does_not_spill_over_the_hint_bar(self):
        """浮层再高也要留住最下面一行提示栏（否则玩家看不到 Esc）。"""
        for h, w in ((18, 62), (20, 80), (24, 100), (30, 118)):
            scr = FakeScreen(h, w)
            screens_mod.draw_panel(scr, title="T", items=[("一", ""), ("二", "")],
                                   width=44, select=0, desc="说明",
                                   hint_rows=["hint"], foot="f", min_w=34, boot=True)
            self.assertLess(scr.row(h - 1).strip(), "z", f"{w}x{h}：提示栏被面板盖住了")


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

    def test_wrap_breaks_after_punctuation_and_never_exceeds_width(self):
        text = "你好，世界。再见。"
        rows = widgets.wrap(text, 6)
        self.assertEqual("".join(rows), text, "折行不能丢字")
        self.assertTrue(all(_width(r) <= 6 for r in rows), rows)
        self.assertEqual(rows[0], "你好，", "中文没有词间空格，应断在标点之后")

    def test_wrap_hard_breaks_text_without_any_break_point(self):
        rows = widgets.wrap("A" * 25, 10)
        self.assertEqual([len(r) for r in rows], [10, 10, 5])
        self.assertEqual(widgets.wrap("", 10), [])

    def test_wrap_uses_display_width_for_cjk(self):
        rows = widgets.wrap("银冠诸国的孩子", 10)
        self.assertTrue(all(_width(r) <= 10 for r in rows), rows)
        self.assertGreater(len(rows), 1, "20 格的文本装进 10 格应至少折成两行")

    def test_wrap_never_starts_a_line_with_closing_punctuation(self):
        """回归：断在「」之后会让下一行以「：」开头，读起来像排版坏了。"""
        text = ("被那个没有在断裂之夜死去的疯法师奥兰一层层改造成陷阱与魔物盘踞的竖井。"
                "人们叫它「深渊地牢」：整整十层，越深越靠近当年帝国的核心。")
        for width in range(6, 32):
            for row in widgets.wrap(text, width):
                self.assertNotIn(row[0], "，。、；：！？）》」』】",
                                 f"宽 {width}：这一行以收尾标点开头：{row!r}")

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
