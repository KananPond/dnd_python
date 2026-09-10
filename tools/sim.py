#!/usr/bin/env python3
"""无头机器人跑批：平衡性与稳定性验证。

策略（greedy）：优先攻击相邻敌人 → 捡东西 → 血少喝药 → 能施法就施法 → BFS 走向最近的未探索区域 → 无未探索则走向下楼梯。

用法：
  python3 tools/sim.py --runs 200 --max-turns 3000 --class warrior
  python3 tools/sim.py --runs 50 --seeds 1-50 --json out/sim.json
"""

from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys
from statistics import mean

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dnd.game import Game  # noqa: E402

DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1))


def bfs_step(level, start, goals, blocked) -> tuple | None:
    """从 start 出发找到 goal 集合的下一步方向（返回 (dx, dy)）。"""
    if not goals:
        return None
    seen = {start: None}
    queue = collections.deque([start])
    while queue:
        cur = queue.popleft()
        if cur in goals and cur != start:
            node = cur
            while seen[node] is not None and seen[node] != start:
                node = seen[node]
            return (node[0] - start[0], node[1] - start[1])
        x, y = cur
        for dx, dy in DIRS:
            nxt = (x + dx, y + dy)
            if nxt in seen or nxt in blocked:
                continue
            if not level.is_walkable(*nxt):
                continue
            seen[nxt] = cur
            queue.append(nxt)
    return None


def play_one(seed: int, class_id: str, max_turns: int = 4000, modern: bool = False,
             race_id: str = "human") -> dict:
    game = Game(seed, f"Bot{seed}", class_id, modern=modern, race_id=race_id)
    potion_threshold = 0.45
    while game.state == "playing" and game.turn < max_turns:
        level = game.level()
        p = game.player
        adjacent = [m for m in level.monsters
                    if m.alive and max(abs(m.x - p.x), abs(m.y - p.y)) <= 1]
        here = level.items_at(p.x, p.y)
        if adjacent:
            target = min(adjacent, key=lambda m: m.hp)
            game.command(("move", target.x - p.x, target.y - p.y))
            continue
        if here:
            game.command(("pickup",))
            continue
        if p.hp <= p.max_hp * potion_threshold:
            idx = next((i for i, it in enumerate(p.inventory) if it.kind == "potion"), None)
            if idx is not None:
                game.command(("use", idx))
                continue
        if p.mp > 0 and game.spellbook():
            enemies = game.visible_monsters()
            if enemies:
                spells = [s for s in game.spellbook() if s["cost"] <= p.mp]
                offensive = [s for s in spells if s["effect"] in ("damage_nearest", "damage_all")]
                if offensive:
                    game.command(("cast", offensive[-1]["id"]))
                    continue
        blocked = {(m.x, m.y) for m in level.monsters if m.alive}
        walkable = [(x, y) for y in range(level.h) for x in range(level.w) if level.is_walkable(x, y)]
        goals = {(x, y) for (x, y) in walkable if not level.is_explored(x, y)}
        explored_ratio = 1 - len(goals) / max(1, len(walkable))
        if level.down and (p.x, p.y) == level.down and explored_ratio > 0.5:
            game.command(("descend",))
            continue
        step = bfs_step(level, (p.x, p.y), goals, blocked)
        if step is None and level.down:
            step = bfs_step(level, (p.x, p.y), {level.down}, blocked)
        if step is None:
            step = game.rng.choice(DIRS)
        game.command(("move", *step))

    return {
        "seed": seed, "class": class_id, "race": game.player.race_id,
        "state": game.state, "depth": game.depth,
        "turns": game.turn, "level": game.player.level, "xp": game.player.xp,
        "gold": game.player.gold, "kills": sum(game.player.kills.values()),
        "hp": game.player.hp, "max_hp": game.player.max_hp,
        "top_kill": max(game.player.kills.items(), key=lambda kv: kv[1])[0] if game.player.kills else None,
    }


def parse_seeds(spec: str | None, runs: int) -> list:
    if not spec:
        return list(range(1, runs + 1))
    if "-" in spec:
        lo, hi = spec.split("-", 1)
        return list(range(int(lo), int(hi) + 1))
    return [int(x) for x in spec.split(",")]


def main() -> int:
    ap = argparse.ArgumentParser(description="dnd 机器人跑批")
    ap.add_argument("--runs", type=int, default=100)
    ap.add_argument("--seeds", default=None)
    ap.add_argument("--class", dest="class_id", default="warrior",
                    choices=["warrior", "wizard", "cleric", "rogue"])
    ap.add_argument("--max-turns", type=int, default=4000)
    ap.add_argument("--race", dest="race_id", default="human",
                    choices=["human", "elf", "dwarf", "gnome"])
    ap.add_argument("--modern", action="store_true")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    seeds = parse_seeds(args.seeds, args.runs)
    results = [play_one(s, args.class_id, args.max_turns, args.modern, args.race_id) for s in seeds]

    depths = collections.Counter(r["depth"] for r in results)
    states = collections.Counter(r["state"] for r in results)
    kills = collections.Counter(r["top_kill"] for r in results if r["top_kill"])
    print(f"runs={len(results)} class={args.class_id} race={args.race_id} modern={args.modern}")
    print(f"  outcomes      : {dict(states)}")
    print(f"  mean depth    : {mean(r['depth'] for r in results):.2f}   max={max(r['depth'] for r in results)}")
    print(f"  mean turns    : {mean(r['turns'] for r in results):.0f}")
    print(f"  mean character level: {mean(r['level'] for r in results):.2f}")
    print(f"  reached depth>=3: {sum(1 for r in results if r['depth'] >= 3) / len(results):.0%}"
          f"   >=6: {sum(1 for r in results if r['depth'] >= 6) / len(results):.0%}"
          f"   ==10: {depths.get(10, 0) / len(results):.0%}")
    print(f"  depth histogram: {dict(sorted(depths.items()))}")
    print(f"  top killers    : {kills.most_common(5)}")
    if args.json:
        out = pathlib.Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
