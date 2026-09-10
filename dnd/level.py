"""地牢层：瓦片、生成、连通性保证。

生成算法（L1 结构 / L3 数值）：
  房间+走廊 → 楼梯/目标物 → 怪物与物品按深度分层放置 → BFS 连通性校验（失败则重生成）。
"""

from __future__ import annotations

from . import dice
from .content import load as load_content
from .entities import make_item, make_monster

WALL, FLOOR, DOOR, STAIRS_DOWN, STAIRS_UP = 0, 1, 2, 3, 4
WALKABLE = (FLOOR, DOOR, STAIRS_DOWN, STAIRS_UP)
LEVEL_W, LEVEL_H = 48, 26
MAX_DEPTH = 10


class Level:
    def __init__(self, depth: int, w: int = LEVEL_W, h: int = LEVEL_H):
        self.depth = depth
        self.w = w
        self.h = h
        self.tiles = bytearray([WALL]) * (w * h)
        self.explored = bytearray(w * h)
        self.monsters = []
        self.ground = []  # list[tuple[Item, x, y]]
        self.up = (1, 1)
        self.down = None
        self.rooms = []

    # --- 基础访问 ---
    def idx(self, x: int, y: int) -> int:
        return y * self.w + x

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.w and 0 <= y < self.h

    def tile(self, x: int, y: int) -> int:
        if not self.in_bounds(x, y):
            return WALL
        return self.tiles[self.idx(x, y)]

    def set_tile(self, x: int, y: int, value: int) -> None:
        self.tiles[self.idx(x, y)] = value

    def is_walkable(self, x: int, y: int) -> bool:
        return self.in_bounds(x, y) and self.tiles[self.idx(x, y)] in WALKABLE

    def blocks_sight(self, x: int, y: int) -> bool:
        if not self.in_bounds(x, y):
            return True
        return self.tiles[self.idx(x, y)] == WALL

    def is_explored(self, x: int, y: int) -> bool:
        return self.in_bounds(x, y) and bool(self.explored[self.idx(x, y)])

    def mark_explored(self, tiles) -> None:
        for x, y in tiles:
            if self.in_bounds(x, y):
                self.explored[self.idx(x, y)] = 1

    def monster_at(self, x: int, y: int):
        for m in self.monsters:
            if m.alive and m.x == x and m.y == y:
                return m
        return None

    def items_at(self, x: int, y: int):
        return [it for (it, ix, iy) in self.ground if ix == x and iy == y]

    def take_ground_item(self, item) -> None:
        self.ground = [g for g in self.ground if g[0] is not item]

    def free_tile(self, rng, avoid=(), min_distance_from=None, min_distance=0):
        for _ in range(400):
            x = rng.randint(1, self.w - 2)
            y = rng.randint(1, self.h - 2)
            if not self.is_walkable(x, y):
                continue
            if (x, y) in avoid or self.monster_at(x, y) or self.items_at(x, y):
                continue
            if min_distance_from is not None:
                fx, fy = min_distance_from
                if abs(x - fx) + abs(y - fy) < min_distance:
                    continue
            return x, y
        return None

    # --- 序列化 ---
    def to_json(self) -> dict:
        return {
            "depth": self.depth, "w": self.w, "h": self.h,
            "tiles": list(self.tiles), "explored": list(self.explored),
            "monsters": [m.to_json() for m in self.monsters],
            "ground": [{"item": it.to_json(), "x": x, "y": y} for (it, x, y) in self.ground],
            "up": list(self.up), "down": list(self.down) if self.down else None,
            "rooms": [list(r) for r in self.rooms],
        }

    @classmethod
    def from_json(cls, d: dict) -> "Level":
        from .entities import Item, Monster
        lv = cls(d["depth"], d["w"], d["h"])
        lv.tiles = bytearray(d["tiles"])
        lv.explored = bytearray(d["explored"])
        lv.monsters = [Monster.from_json(m) for m in d["monsters"]]
        lv.ground = [(Item.from_json(g["item"]), g["x"], g["y"]) for g in d["ground"]]
        lv.up = tuple(d["up"])
        lv.down = tuple(d["down"]) if d["down"] else None
        lv.rooms = [tuple(r) for r in d["rooms"]]
        return lv


def _carve_room(level: Level, room) -> None:
    x, y, w, h = room
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            level.set_tile(xx, yy, FLOOR)


def _carve_corridor(level: Level, a, b, rng) -> None:
    (x1, y1), (x2, y2) = a, b
    if rng.chance(0.5):
        for x in range(min(x1, x2), max(x1, x2) + 1):
            if level.tile(x, y1) == WALL:
                level.set_tile(x, y1, FLOOR)
        for y in range(min(y1, y2), max(y1, y2) + 1):
            if level.tile(x2, y) == WALL:
                level.set_tile(x2, y, FLOOR)
    else:
        for y in range(min(y1, y2), max(y1, y2) + 1):
            if level.tile(x1, y) == WALL:
                level.set_tile(x1, y, FLOOR)
        for x in range(min(x1, x2), max(x1, x2) + 1):
            if level.tile(x, y2) == WALL:
                level.set_tile(x, y2, FLOOR)


def _rooms_overlap(a, b, margin: int = 1) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return (ax - margin < bx + bw and bx - margin < ax + aw and
            ay - margin < by + bh and by - margin < ay + ah)


def _center(room):
    x, y, w, h = room
    return (x + w // 2, y + h // 2)


def _beside(level: Level, spot, avoid=()):
    """spot 旁边（先看四邻+斜角，再看距离 2 一圈）第一个空着的可走格。

    找不到就退回 spot 本身（房间中心被围死这种极端情况）。
    """
    x0, y0 = spot
    ring1 = [(x0 + dx, y0 + dy) for dx, dy in
             ((0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1))]
    ring2 = [(x0 + dx, y0 + dy) for dx in range(-2, 3) for dy in range(-2, 3)
             if max(abs(dx), abs(dy)) == 2]
    for (x, y) in ring1 + ring2:
        if (x, y) in avoid or not level.is_walkable(x, y):
            continue
        if level.monster_at(x, y) is None and not level.items_at(x, y):
            return (x, y)
    return spot


def reachable(level: Level, start) -> set:
    """从 start 出发可走到的瓦片集合（BFS）。"""
    if not level.is_walkable(*start):
        return set()
    seen = {start}
    queue = [start]
    while queue:
        x, y = queue.pop()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if (nx, ny) in seen or not level.is_walkable(nx, ny):
                continue
            seen.add((nx, ny))
            queue.append((nx, ny))
    return seen


def generate(depth: int, rng, *, w: int = LEVEL_W, h: int = LEVEL_H) -> Level:
    content = load_content()
    for _attempt in range(40):
        level = Level(depth, w, h)
        target_rooms = 9 + depth // 2
        rooms = []
        for _ in range(160):
            rw = rng.randint(4, 8)
            rh = rng.randint(3, 5)
            rx = rng.randint(1, max(1, w - rw - 2))
            ry = rng.randint(1, max(1, h - rh - 2))
            cand = (rx, ry, rw, rh)
            if any(_rooms_overlap(cand, r) for r in rooms):
                continue
            rooms.append(cand)
            _carve_room(level, cand)
            if len(rooms) >= target_rooms:
                break
        if len(rooms) < 4:
            continue

        for i in range(1, len(rooms)):
            _carve_corridor(level, _center(rooms[i - 1]), _center(rooms[i]), rng)
        for _ in range(1 + depth // 4):
            a, b = rng.choice(rooms), rng.choice(rooms)
            if a is not b:
                _carve_corridor(level, _center(a), _center(b), rng)

        # 门：房间边界上被打通的瓦片
        for (rx, ry, rw, rh) in rooms:
            border = []
            for x in range(rx, rx + rw):
                border += [(x, ry - 1), (x, ry + rh)]
            for y in range(ry, ry + rh):
                border += [(rx - 1, y), (rx + rw, y)]
            for (x, y) in border:
                if level.tile(x, y) == FLOOR and rng.chance(0.22):
                    level.set_tile(x, y, DOOR)

        level.rooms = rooms
        level.up = _center(rooms[0])
        level.set_tile(*level.up, STAIRS_UP)
        if depth >= MAX_DEPTH:
            level.down = None
        else:
            level.down = _center(rooms[-1])
            level.set_tile(*level.down, STAIRS_DOWN)

        # --- 怪物 ---
        table = content.monsters_for_depth(depth)
        count = min(2 + depth + depth // 2, 12)
        for _ in range(count):
            if not table:
                break
            template = rng.weighted_choice(table)
            spot = level.free_tile(rng, avoid={level.up}, min_distance_from=level.up, min_distance=6)
            if not spot:
                continue
            level.monsters.append(make_monster(template, spot[0], spot[1], rng))

        # --- 物品 ---
        def drop(kind, n):
            pool = content.items_for_depth(depth, kind)
            if not pool:
                return
            for _ in range(n):
                template = rng.weighted_choice(pool)
                spot = level.free_tile(rng, avoid={level.up})
                if spot:
                    level.ground.append((make_item(template["id"], rng, depth), spot[0], spot[1]))

        drop("gold", 3 + depth // 2)
        drop("potion", 2 + depth // 3)
        drop("weapon", 1 + depth // 3)
        drop("armor", 1 + depth // 3)
        drop("scroll", 1 + depth // 4)
        drop("gem", depth // 3)

        # --- 第 10 层：遗物 + 守卫 ---
        # 两个坑都要避开：
        #  1) 守卫必须**必定生成**（原实现遇到房间中心被随机怪占住就整段跳过，boss 直接消失）；
        #  2) 遗物要放在守卫**身边**而不是脚下 —— 守卫正面硬拼几乎打不过（模拟胜率 <8%），
        #     放脚下等于"必须先杀 boss"，游戏实际无法通关；放身边则是"引开守卫再抢"的可玩终局。
        if depth >= MAX_DEPTH:
            anchor = _center(rooms[-1])
            occupant = level.monster_at(*anchor)
            if occupant is not None:  # 先请走占着房间中心的随机怪
                spot = level.free_tile(rng, avoid={anchor, level.up},
                                       min_distance_from=anchor, min_distance=3)
                if spot:
                    occupant.x, occupant.y = spot
            guard_spot = anchor if level.monster_at(*anchor) is None else level.free_tile(
                rng, avoid={level.up})
            guard_spot = guard_spot or anchor
            guardian = content.monsters["deep_guardian"]
            level.monsters.append(make_monster(guardian, guard_spot[0], guard_spot[1], rng))
            relic_spot = _beside(level, guard_spot, avoid={level.up})
            level.ground.append((make_item("relic", rng, depth), relic_spot[0], relic_spot[1]))

        # --- 连通性校验 ---
        seen = reachable(level, level.up)
        key = level.down if level.down else next(
            ((x, y) for (it, x, y) in level.ground if it.kind == "relic"), None)
        if key and key not in seen:
            continue
        walkable_tiles = {(x, y) for y in range(h) for x in range(w) if level.is_walkable(x, y)}
        if not walkable_tiles <= seen:
            continue
        return level
    raise RuntimeError(f"failed to generate a connected level at depth {depth}")
