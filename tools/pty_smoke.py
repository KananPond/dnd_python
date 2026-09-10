#!/usr/bin/env python3
"""在真实伪终端里跑 TUI 的冒烟测试（使用 tmux，无需人工介入）。

覆盖：启动 → 建角界面（↑↓ 选职业/种族）→ 进入游戏 → WASD 移动 → 浮层 → 存档 → 退出。
用法：python3 tools/pty_smoke.py
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
SESSION = "dnd_smoke"
COLS, ROWS = 120, 36
SAVE_FILE = ROOT / "saves" / "smoke.json"   # 建角名字叫 Smoke → 存档名 smoke.json


def tmux(*args: str) -> str:
    out = subprocess.run(["tmux", *args], capture_output=True, text=True)
    return out.stdout


def capture() -> str:
    return tmux("capture-pane", "-p", "-t", SESSION)


def send(name: str) -> None:
    """发送具名按键，如 Down / Tab / Enter / Escape / F5。"""
    tmux("send-keys", "-t", SESSION, name)
    time.sleep(0.3)


def type_text(text: str) -> None:
    """发送字面字符（'?'、'.'、'i' 等）。"""
    tmux("send-keys", "-l", "-t", SESSION, text)
    time.sleep(0.3)


def start(args: str = "") -> None:
    tmux("kill-session", "-t", SESSION)
    cmd = f"cd {ROOT} && TERM=xterm-256color python3 -m dnd {args}"
    tmux("new-session", "-d", "-s", SESSION, "-x", str(COLS), "-y", str(ROWS), cmd)
    time.sleep(2.5)


def run_checks() -> dict:
    checks: dict[str, bool] = {}

    # ---------- 阶段 A：建角界面（↑↓ 选择职业与种族） ----------
    start("--seed 7")
    screen = capture()
    print("--- 建角界面 ---")
    print("\n".join(screen.splitlines()[:14]))
    checks["建角界面标题"] = "创建冒险者" in screen
    checks["职业栏"] = "职业" in screen
    checks["种族栏"] = "种族" in screen
    checks["种族选项"] = all(zh in screen for zh in ("人类", "精灵", "矮人", "侏儒"))

    type_text("Smoke")          # 输入姓名
    send("Down")                # 职业：warrior -> wizard
    send("Tab")                 # 切到种族栏
    send("Down")                # 种族：human -> elf
    after_select = capture()
    checks["↑↓+Tab 生效"] = "精灵" in after_select
    send("Enter")
    time.sleep(0.6)

    screen = capture()
    print("--- 进入游戏（前 6 行）---")
    print("\n".join(screen.splitlines()[:6]))
    checks["游戏已开始"] = "Smoke" in screen and "深度 1/10" in screen
    checks["种族已应用"] = "精灵" in screen
    checks["玩家字形"] = "@" in screen
    checks["墙体"] = "#" in screen
    checks["状态栏"] = "深渊地牢" in screen
    checks["侧栏"] = "冒险者档案" in screen
    checks["按键提示(WASD)"] = "WASD" in screen

    def turn_now() -> int:
        line = capture().splitlines()[0]
        digits = [t for t in line.replace("回合", "回合 ").split() if t.isdigit()]
        return int(digits[-1]) if digits else -1

    # ---------- 阶段 B：WASD 移动 ----------
    before = turn_now()
    for key in ["d", "s", "w", "a"]:
        type_text(key)
    after = turn_now()
    checks[f"WASD 移动（回合 {before} -> {after}）"] = after > before

    # ---------- 阶段 C：浮层与存档 ----------
    type_text("?")
    help_screen = capture()
    checks["帮助浮层"] = "PLATO（1975）复刻版" in help_screen and "W A S D" in help_screen
    send("Escape")
    type_text("i")
    pack_screen = capture()
    # 侧栏也有"背包"标题，必须断言浮层独有的文字，否则永远通过
    checks["背包浮层"] = "按字母使用" in pack_screen
    send("Escape")
    send("F5")                  # 注意：F5 是具名按键，必须用 send；用 type_text 发的是字面 'F''5'
    saved = capture()
    checks["F5 存档"] = ("Game saved" in saved) and SAVE_FILE.exists()

    # ---------- 阶段 D：退出 ----------
    type_text("Q")
    type_text("y")
    time.sleep(0.6)
    alive = subprocess.run(["tmux", "has-session", "-t", SESSION], capture_output=True).returncode == 0
    checks["可退出"] = not alive
    tmux("kill-session", "-t", SESSION)

    # ---------- 阶段 E：CLI 直开（--name/--class/--race） ----------
    start("--seed 8 --name Cli --class cleric --race dwarf")
    screen = capture()
    checks["CLI 指定种族"] = "矮人" in screen and "Cli" in screen
    type_text("Q")
    type_text("y")
    time.sleep(0.4)
    tmux("kill-session", "-t", SESSION)

    # ---------- 阶段 F：读档续玩（--latest；回归"UnboundLocalError 崩溃"） ----------
    start("--latest")
    latest_screen = capture()
    checks["--latest 可续玩"] = "Smoke" in latest_screen and "深渊地牢" in latest_screen
    type_text("Q")
    type_text("y")
    time.sleep(0.4)
    tmux("kill-session", "-t", SESSION)

    return checks


def main() -> int:
    # 冒烟会真的写 saves/smoke.json：先备份，跑完还原/删除，别弄脏玩家的存档目录
    backup = SAVE_FILE.read_bytes() if SAVE_FILE.exists() else None
    try:
        checks = run_checks()
    finally:
        if backup is None:
            SAVE_FILE.unlink(missing_ok=True)
        else:
            SAVE_FILE.write_bytes(backup)

    print("--- 检查结果 ---")
    ok = True
    for name, passed in checks.items():
        print(f"  [{'OK ' if passed else 'FAIL'}] {name}")
        ok = ok and passed
    print(f"SMOKE {'PASS' if ok else 'FAIL'}（{sum(checks.values())}/{len(checks)}）")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
