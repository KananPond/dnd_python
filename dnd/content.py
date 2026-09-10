"""数据驱动内容加载：职业/种族/怪物/物品/法术表。

所有表都带 _meta（出处与可信度分级）：
  documented —— 有公开来源可查的机制骨架
  inferred   —— 依据史料推断的合理取值
  invented   —— 原版数据不可得，复刻自定（L3 自由发挥层）
"""

from __future__ import annotations

import json
import pathlib
from functools import lru_cache

DATA_DIR = pathlib.Path(__file__).with_name("data")

_FILES = ("classes", "races", "monsters", "items", "spells")


class Content:
    def __init__(self, blobs: dict):
        self.blobs = blobs
        self.meta = {k: blobs[k].get("_meta", {}) for k in blobs}
        self.classes = {c["id"]: c for c in blobs["classes"]["classes"]}
        self.xp_thresholds = blobs["classes"]["xp_thresholds"]
        self.attack_progressions = blobs["classes"]["attack_progressions"]
        self.races = {r["id"]: r for r in blobs["races"]["races"]}
        self.monsters = {m["id"]: m for m in blobs["monsters"]["monsters"]}
        self.items = {i["id"]: i for i in blobs["items"]["items"]}
        self.spells = {s["id"]: s for s in blobs["spells"]["spells"]}

    # --- 查询 ---
    def klass(self, class_id: str) -> dict:
        return self.classes[class_id]

    def race(self, race_id: str) -> dict:
        return self.races.get(race_id) or self.races["human"]

    def attack_bonus_for(self, class_id: str, level: int) -> int:
        prog = self.attack_progressions.get(class_id, [0])
        return prog[min(max(level, 1), len(prog)) - 1]

    def xp_for_level(self, level: int) -> int:
        th = self.xp_thresholds
        if level - 1 < len(th):
            return th[level - 1]
        return th[-1] + (level - len(th)) * 1500

    def monsters_for_depth(self, depth: int):
        out = []
        for m in self.monsters.values():
            lo, hi = m.get("depth", [1, 10])
            if lo <= depth <= hi and m.get("weight", 0) > 0:
                out.append((m, m["weight"]))
        return out

    def items_for_depth(self, depth: int, kind: str | None = None):
        out = []
        for it in self.items.values():
            if kind and it["kind"] != kind:
                continue
            lo, hi = it.get("depth", [1, 10])
            if lo <= depth <= hi and it.get("weight", 0) > 0:
                out.append((it, it["weight"]))
        return out

    def spells_for(self, class_id: str):
        k = self.klass(class_id)
        return [self.spells[s] for s in k.get("spells", [])]

    def confidence(self, kind: str, entry_id: str) -> str:
        table = {"classes": self.classes, "races": self.races, "monsters": self.monsters,
                 "items": self.items, "spells": self.spells}[kind]
        entry = table.get(entry_id, {})
        return entry.get("confidence") or self.meta.get(kind, {}).get("confidence", "invented")


@lru_cache(maxsize=1)
def load() -> Content:
    blobs = {}
    for name in _FILES:
        with open(DATA_DIR / f"{name}.json", "r", encoding="utf-8") as fh:
            blobs[name] = json.load(fh)
    return Content(blobs)
