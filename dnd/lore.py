"""游戏内序章（L3 再创作）：世界背景 + 玩家如何进入地牢 + 下井前的必要信息。

内容全部在 `dnd/data/lore.json`（CC0-1.0）。序章刻意**只写玩家进场必须知道的东西**，
神系、种族、职业、遗物细设定不放进来——完整世界观见 `docs/world-setting.md`，
母题来源与"改造对照"见 `docs/research-dossier.md#八`。名词一律自创，不沿用任何他方商标。

这个模块刻意**不 import curses**：
  · `python3 -m dnd --lore` 在没有终端的机器上（Windows 原生 Python）也要能打印；
  · 界面层（`ui/screens.py`）只消费 `pages()` 返回的结构，排版与配色留在界面里。
"""

from __future__ import annotations

import json
import pathlib
from functools import lru_cache

DATA_FILE = pathlib.Path(__file__).with_name("data") / "lore.json"

# 每页里的每一行是 (文本, 颜色名)：颜色名即 theme.PALETTE 的语义键。
Line = tuple[str, str]


@lru_cache(maxsize=1)
def load() -> dict:
    with open(DATA_FILE, "r", encoding="utf-8") as fh:
        return json.load(fh)


def pages(name: str) -> list[dict]:
    """组装成两页，每页 `{"title": str, "lines": [(文本, 颜色), ...]}`。

    页序固定为：**世界**（这一切是怎么来的）→ **入井**（你怎么进地牢、进去前要知道什么）。
    第二页会点名角色（数据里的 `{name}`）。
    """
    data = load()
    char_name = (name or "").strip() or "冒险者"

    def blank() -> Line:
        return ("", "dim")

    def para(text: str, color: str = "bright") -> Line:
        return (text, color)

    world = data["world"]
    world_lines: list[Line] = [(world["tagline"], "magic"), blank()]
    for text in world["paragraphs"]:
        world_lines += [para(text), blank()]

    descent = data["descent"]
    descent_lines: list[Line] = []
    for text in descent["paragraphs"]:
        descent_lines += [para(text.replace("{name}", char_name)), blank()]
    descent_lines += [(f"· {item}", "info") for item in descent["briefing"]]

    return [
        {"title": "序章 · 世界", "lines": world_lines},
        {"title": "序章 · 入井", "lines": descent_lines},
    ]


def plain_text(name: str) -> str:
    """纯文本版（`--lore` 与测试用）：页面标题 + 正文，不含任何终端控制字符。"""
    out: list[str] = []
    for page in pages(name):
        out.append(f"── {page['title']} ──")
        out += [text for text, _color in page["lines"] if text]
        out.append("")
    return "\n".join(out).rstrip() + "\n"
