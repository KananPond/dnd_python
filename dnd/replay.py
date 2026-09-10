"""确定性回放：seed + 命令序列 → 状态哈希。

用途：回归测试、bug 复现、机器人对局存档。
"""

from __future__ import annotations

from .game import Game


def run(seed: int, commands, name: str = "Tester", class_id: str = "warrior", *,
        modern: bool = False, race_id: str = "human") -> Game:
    game = Game(seed, name, class_id, modern=modern, race_id=race_id)
    for cmd in commands:
        if game.state != "playing":
            break
        game.command(cmd)
    return game


def digest(seed: int, commands, **kwargs) -> str:
    return run(seed, commands, **kwargs).state_hash()
