"""掷骰表达式：'2d6+1' / 'd8' / '3' 。"""

from __future__ import annotations

import re

_BONUS_RE = re.compile(r"([+-]\d+)\s*$")


def parse(expr: str):
    """返回 (count, sides, bonus)。'd8' -> (1, 8, 0)；'2d6+1' -> (2, 6, 1)；'7' -> (0, 0, 7)。"""
    text = (expr or "").replace(" ", "")
    if not text:
        raise ValueError(f"bad dice expression: {expr!r}")
    bonus = 0
    m = _BONUS_RE.search(text)
    if m:
        bonus = int(m.group(1))
        text = text[: m.start()]
    pos = max(text.find("d"), text.find("D"))
    if pos >= 0:
        left, right = text[:pos], text[pos + 1:]
        if not right.isdigit():
            raise ValueError(f"bad dice expression: {expr!r}")
        count = int(left) if left.isdigit() else (1 if left == "" else -1)
        sides = int(right)
        if count < 1 or sides < 1:
            raise ValueError(f"bad dice expression: {expr!r}")
        return count, sides, bonus
    if text.isdigit():
        return 0, 0, int(text) + bonus
    raise ValueError(f"bad dice expression: {expr!r}")


def roll(expr: str, rng) -> int:
    count, sides, bonus = parse(expr)
    total = bonus
    for _ in range(count):
        total += rng.randint(1, sides)
    return total


def average(expr: str) -> float:
    count, sides, bonus = parse(expr)
    return count * (sides + 1) / 2.0 + bonus


def modifier(score: int) -> int:
    """属性调整值（现代规则风格）。"""
    return (score - 10) // 2
