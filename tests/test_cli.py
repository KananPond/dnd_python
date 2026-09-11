"""CLI 路径回归测试。

重点回归：`--load` / `--latest` 曾经因为 `curses` 未绑定而在启动瞬间抛
UnboundLocalError（读档功能完全不可用）。这里用真实伪终端把 TUI 拉起来验证。
"""

from __future__ import annotations

import contextlib
import io
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import unittest

try:  # 伪终端相关模块只有 POSIX 有（Windows 原生 Python 没有 pty/fcntl）
    import fcntl
    import pty
    import select
    import struct
    import termios
except ImportError:  # pragma: no cover - Windows 下走这里
    fcntl = pty = select = struct = termios = None

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dnd import save  # noqa: E402
from dnd.__main__ import main  # noqa: E402
from dnd.game import Game  # noqa: E402

_TMP = pathlib.Path(tempfile.mkdtemp(prefix="dnd-cli-tests-"))
save.SAVE_DIR = _TMP
save.ROSTER = _TMP / "roster.json"

_TITLE = "深渊地牢"


def run_in_pty(args, cols: int = 120, rows: int = 36, timeout: float = 20.0,
               stop_when: str | None = None) -> tuple[str, int]:
    """在伪终端里跑命令，返回 (输出, 退出码)。终端尺寸在 fork 前设好，避免与 curses 抢跑。"""
    if pty is None:  # 直接调用也要给出明确原因，而不是 NoneType 报错
        raise unittest.SkipTest("需要 POSIX 伪终端（pty/fcntl）")
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
    env = {**os.environ, "TERM": "xterm-256color", "PYTHONPATH": str(ROOT)}
    proc = subprocess.Popen([sys.executable, *args], cwd=ROOT, env=env,
                            stdin=slave, stdout=slave, stderr=slave, close_fds=True)
    os.close(slave)
    buf = b""
    needle = stop_when.encode("utf-8") if stop_when else None
    deadline = time.time() + timeout
    try:
        while time.time() < deadline:
            r, _, _ = select.select([master], [], [], 0.3)
            if r:
                try:
                    chunk = os.read(master, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                buf += chunk
                if needle and needle in buf:
                    break
            if proc.poll() is not None and not r:
                break
    finally:
        if proc.poll() is None:
            proc.kill()
        code = proc.wait(timeout=5)
        os.close(master)
    return buf.decode("utf-8", "replace"), code


class TestListSaves(unittest.TestCase):
    def test_empty_directory(self):
        empty = pathlib.Path(tempfile.mkdtemp(prefix="dnd-empty-saves-"))
        old = save.SAVE_DIR
        save.SAVE_DIR = empty
        try:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = main(["--list-saves"])
        finally:
            save.SAVE_DIR = old
        self.assertEqual(rc, 0)
        self.assertEqual(out.getvalue().strip(), "saves: (none)")

    def test_lists_files_but_not_roster(self):
        (save.SAVE_DIR / "aria.json").write_text("{}", encoding="utf-8")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            main(["--list-saves"])
        self.assertIn("aria.json", out.getvalue())
        self.assertNotIn("roster.json", out.getvalue())


@unittest.skipIf(os.name != "posix", "需要 pty + curses")
class TestCreationEntryPoint(unittest.TestCase):
    """建角入口的取舍：只有 --name/--class/--race 三个都给了才跳过建角界面。"""

    def test_name_and_class_without_race_still_opens_creation(self):
        """回归：--name/--class 齐了但没给 --race 时，曾经直接跳过建角并把种族静默钉成 human。"""
        out, _code = run_in_pty(["-m", "dnd", "--name", "CliPart", "--class", "warrior"],
                               stop_when="Tab")   # 页脚最后写：等到它出现，整屏（含姓名）就画完了
        self.assertNotIn("Traceback", out)
        self.assertIn("创建冒险者", out, "没给 --race 就应该进建角界面，种族让用户自己选")
        self.assertIn("CliPart", out, "命令行给的名字要预填进建角界面")

    def test_all_three_args_skip_creation(self):
        out, _code = run_in_pty(["-m", "dnd", "--name", "CliAll", "--class", "cleric",
                                 "--race", "dwarf"], stop_when="CliAll")
        self.assertNotIn("Traceback", out)
        self.assertNotIn("创建冒险者", out, "三个参数齐备时应直接开局")
        self.assertIn(_TITLE, out, "TUI 应该正常起来")


@unittest.skipIf(os.name != "posix", "需要 pty + curses")
class TestLoadStartsTui(unittest.TestCase):
    def test_load_enters_game(self):
        game = Game(4242, "CliLoad", "warrior")
        path = save.save_game(game)
        # 等到角色名出现再停：标题栏先于体征栏写出，只等标题会拿到"半屏"输出（曾因此偶发失败）
        out, _code = run_in_pty(["-m", "dnd", "--load", str(path)], stop_when="CliLoad")
        self.assertNotIn("Traceback", out)
        self.assertNotIn("UnboundLocalError", out)
        self.assertIn(_TITLE, out, "TUI 应该正常起来")
        self.assertIn("CliLoad", out, "应该加载到存档里的角色")

    def test_load_missing_file_reports_error(self):
        out, code = run_in_pty(["-m", "dnd", "--load", str(_TMP / "nope.json")], timeout=10)
        self.assertNotIn("Traceback", out)
        self.assertIn("无法读取存档", out)
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
