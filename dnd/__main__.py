"""入口：python3 -m dnd [选项]

默认流程（不带参数时）：

    开始页 ──新的冒险──→ 建角界面 ──→ 序章（背景故事）──→ 地牢 ──Esc 菜单──→ 存档管理
      │                                ↑                    │
      ├──读取存档──→ 存档管理 ─────────┘←────读取────────────┘
      ├──名人堂──→ 名册浮层
      └──退出游戏

开始页、建角、序章、游戏、读档共用**同一个 curses 会话**（见 `session`）：每段各自
`curses.wrapper()` 会让终端反复复位，观感上就是进出一次闪一下。

命令行参数仍然是"老玩家快捷键"（也是 tools/pty_smoke.py 依赖的路径）：
--name/--class/--race 齐备 → 直接开局（仍会过一次序章，--no-prologue 可跳过）；
--load/--latest → 直接读档；--seed 仍然会先过开始页（种子在真正开局时才用得上）。
"""

from __future__ import annotations

import argparse
import os
import sys

from . import save as save_mod
from .content import load as load_content
from .game import Game


def parse_args(argv=None):
    ap = argparse.ArgumentParser(prog="dnd", description="PLATO(1975)《dnd》现代复刻 — 终端版")
    ap.add_argument("--seed", type=int, default=None, help="固定随机种子（可用于复现同一座地牢）")
    ap.add_argument("--name", default=None,
                    help="角色名（省略则进入开始页；--name/--class/--race 三个都给出时才直接开局）")
    ap.add_argument("--class", dest="class_id", default=None,
                    choices=["warrior", "wizard", "cleric", "rogue"], help="职业")
    ap.add_argument("--race", dest="race_id", default=None,
                    choices=["human", "elf", "dwarf", "gnome"], help="种族（省略则进入建角界面选择）")
    ap.add_argument("--load", default=None, help="读取存档文件")
    ap.add_argument("--latest", action="store_true", help="读取最近一次存档")
    ap.add_argument("--menu", action="store_true",
                    help="强制先进入开始页（不带任何参数时的默认行为，留作显式开关）")
    ap.add_argument("--modern", action="store_true", help="现代模式：可免死一次")
    ap.add_argument("--no-prologue", action="store_true",
                    help="跳过建角后的背景故事，直接进入地牢")
    ap.add_argument("--lore", action="store_true",
                    help="打印背景故事（世界/诸神/血脉/道路/使命），不启动界面")
    ap.add_argument("--debug", action="store_true", help="开启调试键（x 全图 / t 传送）")
    ap.add_argument("--no-color", action="store_true", help="关闭颜色")
    ap.add_argument("--ascii", action="store_true",
                    help="用纯 ASCII 画框线/进度条（东亚洲终端把 ─│ 当两格宽、版面错位时用）")
    ap.add_argument("--list-saves", action="store_true",
                    help="列出存档（脚本用；游戏里用开始页的「读取存档」界面）")
    ap.add_argument("--roster", action="store_true", help="打印名人堂名册")
    ap.add_argument("--headless-demo", type=int, default=0, metavar="TURNS",
                    help="无界面跑 N 个回合并打印状态（用于无终端环境自检）")
    return ap.parse_args(argv)


def headless_demo(turns: int, seed: int | None, class_id: str, race_id: str = "human") -> int:
    seed = seed if seed is not None else 1
    game = Game(seed, "Demo", class_id, race_id=race_id)
    dirs = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)]
    for _ in range(turns):
        if game.state != "playing":
            break
        level = game.level()
        adjacent = [m for m in level.monsters
                    if m.alive and max(abs(m.x - game.player.x), abs(m.y - game.player.y)) <= 1]
        if adjacent:
            game.command(("move", adjacent[0].x - game.player.x, adjacent[0].y - game.player.y))
        elif game.item_at_feet():
            game.command(("pickup",))
        elif (game.player.x, game.player.y) == level.down:
            game.command(("descend",))
        else:
            game.command(("move", *game.rng.choice(dirs)))
    st = game.status()
    print(f"seed={game.seed} state={game.state} depth={st['depth']} turn={st['turn']} "
          f"hp={st['hp']}/{st['max_hp']} level={st['level']} xp={st['xp']} gold={st['gold']}")
    print("hash:", game.state_hash()[:16])
    for text, _ in game.log[-6:]:
        print("  ·", text)
    return 0


def new_game(args, create) -> Game:
    """开一局新游戏。create 是"进建角界面拿 (name, class_id, race_id)"的回调。"""
    # 三个参数齐备才跳过建角；只给了一部分时照样进建角，把给过的值预填进去
    name, class_id, race_id = create()
    return make_game(args, name, class_id, race_id)


def make_game(args, name: str, class_id: str, race_id: str) -> Game:
    """组一局游戏：种子只有 --seed 给了才固定，否则取系统熵（每局地牢都不同）。"""
    seed = args.seed if args.seed is not None else int.from_bytes(os.urandom(4), "big")
    return Game(seed, name, class_id, modern=args.modern, race_id=race_id)


def load_or_report(path):
    """读档；把"读不动"翻译成玩家看得懂的一句话。返回 (game, 原因)，失败时 game 为 None。"""
    try:
        return save_mod.load_game(path), None
    except FileNotFoundError:
        return None, f"无法读取存档 {path}：文件不存在"
    except IsADirectoryError:
        return None, f"无法读取存档 {path}：这是个目录，不是存档文件"
    except (OSError, ValueError, KeyError, TypeError, IndexError, AttributeError) as exc:
        return None, f"无法读取存档 {path}：{exc}"


class session:
    """curses 会话：进入/退出 curses 模式，并在整个会话里复用同一个 stdscr。

    自己写而不是用 curses.wrapper，是因为开始页、建角、存档管理、游戏内界面必须
    共享同一个窗口；每次 wrapper 都会重新 initscr/endwin，终端会闪、颜色要重设。
    """

    def __init__(self, curses_mod):
        self.curses = curses_mod
        self.scr = None

    def __enter__(self):
        c = self.curses
        self.scr = c.initscr()
        c.noecho()
        c.cbreak()
        self.scr.keypad(True)
        try:
            c.start_color()
        except c.error:
            pass
        return self.scr

    def __exit__(self, *exc):
        c = self.curses
        try:
            c.nocbreak()
            self.scr.keypad(False)
            c.echo()
        finally:
            c.endwin()
        return False


def run_menu(curses, screens, tui_cls, args) -> int:
    """开始页主循环：开始页 →（建角 | 读档）→ 地牢 → 回到开始页，直到退出。"""
    with session(curses) as stdscr:
        return menu_loop(curses, screens, tui_cls, args, stdscr)


def show_prologue(screens, args, stdscr, name: str) -> None:
    """建角之后的序章（--no-prologue 跳过）：角色已经建好，这一屏只负责"读"。"""
    if args.no_prologue:
        return
    screens.prologue_screen(stdscr, name, args.no_color)


def create_game(screens, args, stdscr):
    """进建角界面组一局新游戏。

    命令行给过的 --name/--class/--race 会预填进去（用户写过的参数不该被丢掉）；
    建角里按 Esc 放弃这一局时抛 SystemExit，由调用方决定"回开始页还是退出程序"。
    名字定下来之后先过一次序章，再进地牢。
    """
    name, class_id, race_id = screens.creation_screen(
        stdscr, args.no_color, initial_name=args.name or "",
        initial_class=args.class_id, initial_race=args.race_id)
    show_prologue(screens, args, stdscr, name)
    return make_game(args, name, class_id, race_id)


def menu_loop(curses, screens, tui_cls, args, stdscr) -> int:
    """开始页 ↔（建角 | 读档）↔ 地牢，直到玩家选「退出游戏」。

    一个会话里反复进出这三屏：从地牢回到开始页（Esc → 返回开始页）时不会重建终端，
    所以没有闪烁，也不会丢掉刚保存的存档。
    """
    while True:
        choice = screens.start_screen(stdscr, args.no_color)
        if choice == "quit":
            return 0
        if choice == "load":
            game = screens.save_manager_screen(stdscr, args.no_color)
            if game is None:                     # Esc：返回开始页
                continue
        else:
            try:
                game = create_game(screens, args, stdscr)
            except SystemExit:                   # 建角界面里按 Esc = 放弃这一局
                continue
        if play(curses, tui_cls, args, stdscr, game) == "quit":
            return 0


def exit_after(curses, screens, tui_cls, args, stdscr, game) -> int:
    """命令行捷径开局后：玩家若在游戏里选「返回开始页」，就顺势回到开始页主循环。"""
    if play(curses, tui_cls, args, stdscr, game) == "menu":
        return menu_loop(curses, screens, tui_cls, args, stdscr)
    return 0


def play(curses, tui_cls, args, stdscr, game) -> str:
    """在既有会话里玩一局。返回 'quit'（结束程序）或 'menu'（回开始页）。"""
    tui = tui_cls(stdscr, game, debug=args.debug, no_color=args.no_color,
                  no_prologue=args.no_prologue)
    try:
        tui.run()
    except SystemExit:
        return "quit"
    except KeyboardInterrupt:
        return "quit"
    return "menu"


def main(argv=None) -> int:
    args = parse_args(argv)

    # 字形集走环境变量传给 theme：theme 模块级 import curses，而 Windows 原生
    # Python 没有 curses —— 在这里直接 import theme 会毁掉 --headless-demo 等无终端用法。
    if args.ascii:
        os.environ["DND_GLYPHS"] = "ascii"

    if args.list_saves:
        saves = sorted(save_mod.SAVE_DIR.glob("*.json")) if save_mod.SAVE_DIR.exists() else []
        saves = [s for s in saves if s.name != "roster.json"]
        if saves:
            print("saves:", *(s.name for s in saves), sep="\n  ")
        else:
            print("saves: (none)")
        return 0

    if args.roster:
        for entry in save_mod.read_roster():
            print(f"{entry['name']:<12} {entry.get('race', 'Human'):<8} {entry['class']:<8} "
                  f"Lv{entry['level']:<3} depth {entry['depth']:<3} "
                  f"{entry['result']:<5} {entry['gold']}g {entry['turns']}t {entry['date']}")
        return 0

    if args.lore:                                   # 纯文本序章：无终端也能看
        from . import lore as lore_mod
        print(lore_mod.plain_text(args.name or "冒险者"), end="")
        return 0

    if args.headless_demo:
        return headless_demo(args.headless_demo, args.seed, args.class_id or "warrior",
                             args.race_id or "human")

    load_content()  # 提前校验数据表

    try:
        import curses  # 延迟导入：Windows 原生 Python 没有 curses，但 --headless-demo 等仍可用
    except ImportError:
        print("dnd: 当前 Python 没有 curses 模块，TUI 无法运行（请用 Linux / macOS / WSL 终端）。",
              file=sys.stderr)
        return 2

    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print("dnd: 需要交互式终端才能运行 TUI。可用 --headless-demo 20 做无界面自检。", file=sys.stderr)
        return 2

    from .ui import screens
    from .ui.tui import Tui

    # --menu：即使命令行参数齐备也强制先过开始页（默认行为本来就是它，留作显式覆盖）
    if not args.menu and (args.load or args.latest):    # 捷径：直接续玩，不看开始页
        path = args.load or save_mod.latest_save()
        if not path:
            print("no save file found", file=sys.stderr)
            return 2
        loaded, error = load_or_report(path)
        if loaded is None:
            print(f"dnd: {error}", file=sys.stderr)
            return 2
        with session(curses) as stdscr:
            game = loaded
            return exit_after(curses, screens, Tui, args, stdscr, game)

    if not args.menu and args.name and args.class_id and args.race_id:   # 捷径：参数齐备，直接开局
        with session(curses) as stdscr:
            show_prologue(screens, args, stdscr, args.name)
            return exit_after(curses, screens, Tui, args, stdscr,
                              make_game(args, args.name, args.class_id, args.race_id))

    if not args.menu and (args.name or args.class_id or args.race_id):
        # 只给了一部分：跳过开始页直接进建角（命令行意图很明确），缺的那项留给玩家选。
        # 注意这里**不能**把没给的值填成默认值 —— 那正是"种族被静默钉成人类"的老 bug。
        with session(curses) as stdscr:
            try:
                game = create_game(screens, args, stdscr)
            except SystemExit:                   # 建角里按 Esc：改从开始页进
                return menu_loop(curses, screens, Tui, args, stdscr)
            return exit_after(curses, screens, Tui, args, stdscr, game)

    return run_menu(curses, screens, Tui, args)


if __name__ == "__main__":
    raise SystemExit(main())
