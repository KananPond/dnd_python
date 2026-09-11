"""入口：python3 -m dnd [选项]"""

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
                    help="角色名（省略则进入建角界面；--name/--class/--race 三个都给出时才跳过建角）")
    ap.add_argument("--class", dest="class_id", default=None,
                    choices=["warrior", "wizard", "cleric", "rogue"], help="职业")
    ap.add_argument("--race", dest="race_id", default=None,
                    choices=["human", "elf", "dwarf", "gnome"], help="种族（省略则进入建角界面选择）")
    ap.add_argument("--load", default=None, help="读取存档文件")
    ap.add_argument("--latest", action="store_true", help="读取最近一次存档")
    ap.add_argument("--modern", action="store_true", help="现代模式：可免死一次")
    ap.add_argument("--debug", action="store_true", help="开启调试键（x 全图 / t 传送）")
    ap.add_argument("--no-color", action="store_true", help="关闭颜色")
    ap.add_argument("--ascii", action="store_true",
                    help="用纯 ASCII 画框线/进度条（东亚洲终端把 ─│ 当两格宽、版面错位时用）")
    ap.add_argument("--list-saves", action="store_true", help="列出存档")
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

    if args.load or args.latest:
        path = args.load or save_mod.latest_save()
        if not path:
            print("no save file found", file=sys.stderr)
            return 2
        try:
            game = save_mod.load_game(path)
        except (OSError, ValueError, KeyError) as exc:  # 路径不存在 / JSON 损坏 / 结构不兼容
            print(f"dnd: 无法读取存档 {path}：{exc}", file=sys.stderr)
            return 2
    else:
        def _create(stdscr):
            from .ui.tui import creation_screen
            # 命令行给了什么就预填什么，避免 --name/--race 被静默丢弃
            return creation_screen(stdscr, args.no_color, initial_name=args.name or "",
                                   initial_class=args.class_id, initial_race=args.race_id)

        # 三个参数齐备才跳过建角；只给了 --name/--class 时照样进建角，把命令行给过的
        # 值预填进去、种族留给用户选 —— 否则--race 的帮助文字（"省略则进入建角界面选择"）
        # 就是假的，种族会被静默钉成 human。
        if args.name and args.class_id and args.race_id:
            name, class_id, race_id = args.name, args.class_id, args.race_id
        else:
            name, class_id, race_id = curses.wrapper(_create)
        seed = args.seed if args.seed is not None else int.from_bytes(os.urandom(4), "big")
        game = Game(seed, name, class_id, modern=args.modern, race_id=race_id)

    def _run(stdscr):
        from .ui.tui import Tui
        Tui(stdscr, game, debug=args.debug, no_color=args.no_color).run()

    try:
        curses.wrapper(_run)
    except SystemExit:
        return 0
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
