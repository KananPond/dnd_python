"""游戏内核：状态机 + 回合循环 + 战斗/物品/法术/升级。

内核不依赖任何终端/UI，也不使用 random/time —— 同一种子 + 同一命令序列必然得到同一结果，
因此可以被 TUI 前端、无头机器人（tools/sim.py）与回放测试（tests/）共用。
"""

from __future__ import annotations

import hashlib
import json

from . import dice, fov
from .content import load as load_content
from .entities import BASE_FOV_RADIUS, Monster, auto_equip, create_player, make_item
from .level import MAX_DEPTH, STAIRS_DOWN, STAIRS_UP, Level, generate
from .rng import RNG

FOV_RADIUS = BASE_FOV_RADIUS  # 基础视野半径（种族可加成，见 Player.fov_radius）
REGEN_TURNS = 12   # 每 N 回合恢复 1 点生命（L2）
AGGRO_RANGE = 7    # 怪物追击半径：超出后不再穷追（L2，避免全层同时扑上）
FORCE_FIGHT = None  # 预留：强制攻击方向


def attack_roll(attack_bonus: int, target_ac: int, rng) -> tuple:
    """返回 (是否命中, 是否暴击, d20 点数)。"""
    roll = rng.randint(1, 20)
    if roll == 20:
        return True, True, roll
    if roll == 1:
        return False, False, roll
    return roll + attack_bonus >= target_ac, False, roll


class Game:
    def __init__(self, seed: int, name: str = "Adventurer", class_id: str = "warrior", *,
                 modern: bool = False, race_id: str = "human"):
        self.seed = int(seed)
        self.rng = RNG(self.seed)
        self.player = create_player(name, class_id, self.rng, race_id)
        self.depth = 1
        self.turn = 0
        self.levels: dict[int, Level] = {}
        self.log: list[tuple[str, str]] = []
        self.state = "playing"  # playing | dead | won
        self.modern = bool(modern)
        self.second_wind_used = False
        self.commands: list[tuple] = []
        self.visible: set = set()
        level = self.level()
        self.player.x, self.player.y = level.up
        self._refresh_fov()
        self.message(f"{self.player.name}（{self.player.class_name()}）踏入了地牢。", "good")
        self.message("按 ? 查看帮助；方向键或 hjkl 移动，> 下楼。", "info")

    # ------------------------------------------------------------------ 基础
    def level(self) -> Level:
        if self.depth not in self.levels:
            self.levels[self.depth] = generate(self.depth, self.rng)
        return self.levels[self.depth]

    def message(self, text: str, kind: str = "info") -> None:
        self.log.append((text, kind))
        if len(self.log) > 300:
            del self.log[:100]

    def _refresh_fov(self) -> None:
        level = self.level()
        self.visible = fov.compute(level, self.player.x, self.player.y, self.player.fov_radius())
        level.mark_explored(self.visible)

    def state_hash(self) -> str:
        payload = {
            "depth": self.depth, "turn": self.turn, "state": self.state,
            "player": self.player.to_json(), "rng": self.rng.to_json(),
            "level": self.level().to_json(),
        }
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    # ------------------------------------------------------------- 命令入口
    def command(self, cmd) -> None:
        """执行一条命令；命令会被记入 commands 以支持回放。"""
        cmd = tuple(cmd)
        if self.state != "playing":
            return
        self.commands.append(cmd)
        name = cmd[0]
        handler = getattr(self, f"_cmd_{name}", None)
        if handler is None:
            self.message(f"未知指令：{name}", "bad")
            self.commands.pop()
            return
        handler(*cmd[1:])

    # --- 移动 ---
    def _cmd_move(self, dx: int, dy: int) -> None:
        level = self.level()
        nx, ny = self.player.x + dx, self.player.y + dy
        monster = level.monster_at(nx, ny)
        if monster:
            self._player_attacks(monster)
            self._end_turn()
            return
        if not level.is_walkable(nx, ny):
            self.message("前方是墙，无法通行。", "warn")
            self.commands.pop()
            return
        self.player.x, self.player.y = nx, ny
        self._end_turn()

    def _cmd_wait(self) -> None:
        self._end_turn()

    def _cmd_descend(self) -> None:
        level = self.level()
        if (self.player.x, self.player.y) != level.down:
            self.message("这里没有向下的楼梯。", "warn")
            self.commands.pop()
            return
        self.depth = min(MAX_DEPTH, self.depth + 1)
        self.player.depth = self.depth
        new_level = self.level()
        self.player.x, self.player.y = new_level.up
        self.message(f"你下到了地牢第 {self.depth} 层。", "good")
        self._end_turn()

    def _cmd_ascend(self) -> None:
        level = self.level()
        if (self.player.x, self.player.y) != level.up:
            self.message("这里没有向上的楼梯。", "warn")
            self.commands.pop()
            return
        if self.depth == 1:
            self.message("你已经在地面层了。", "warn")
            self.commands.pop()
            return
        self.depth -= 1
        self.player.depth = self.depth
        upper = self.level()
        self.player.x, self.player.y = upper.down or upper.up
        self.message(f"你回到了地牢第 {self.depth} 层。", "info")
        self._end_turn()

    def _cmd_pickup(self) -> None:
        level = self.level()
        items = level.items_at(self.player.x, self.player.y)
        if not items:
            self.message("脚下没有可以拾取的东西。", "warn")
            self.commands.pop()
            return
        for item in list(items):
            level.take_ground_item(item)
            if item.kind == "relic":
                self.player.inventory.append(item)
                self.message("你夺得了深渊遗物！光芒照亮了整座地牢。", "good")
                self.state = "won"
                return
            if item.kind in ("gold", "gem"):
                self.player.gold += item.value
                self.message(f"你拾取了{item.name}，价值 {item.value} 金。", "gold")
            else:
                self.player.inventory.append(item)
                self.message(f"你拾取了{item.name}。", "item")
                for note in auto_equip(self.player):
                    self.message(note, "good")
        self._end_turn()

    def _cmd_use(self, index: int) -> None:
        inv = self.player.inventory
        if not (0 <= index < len(inv)):
            self.message("没有这个物品。", "warn")
            self.commands.pop()
            return
        item = inv[index]
        if item.kind == "potion":
            healed = dice.roll(item.heal or "1d8", self.rng)
            before = self.player.hp
            self.player.hp = min(self.player.max_hp, self.player.hp + healed)
            self.message(f"你喝下{item.name}，恢复了 {self.player.hp - before} 点生命。", "good")
        elif item.kind == "scroll":
            self._apply_offensive_effect(item.effect, item.power or "2d6")
            self.message(f"你阅读了{item.name}。", "magic")
        elif item.kind in ("weapon", "armor"):
            for note in auto_equip(self.player):
                self.message(note, "good")
            self.message(f"你装备了{item.name}。", "item")
        else:
            self.message(f"{item.name}现在无法使用。", "warn")
            self.commands.pop()
            return
        if item.kind in ("potion", "scroll") and item in inv:
            inv.remove(item)
        self._end_turn()

    def _cmd_cast(self, spell_id: str) -> None:
        content = load_content()
        known = {s["id"] for s in content.spells_for(self.player.class_id)}
        spell = content.spells.get(spell_id)
        if not spell or spell_id not in known:
            self.message("你不会这个法术。", "warn")
            self.commands.pop()
            return
        if self.player.mp < spell["cost"]:
            self.message("法力不足。", "warn")
            self.commands.pop()
            return
        self.player.mp -= spell["cost"]
        effect = spell["effect"]
        if effect in ("damage_nearest", "damage_all"):
            self._apply_offensive_effect(effect, spell.get("power", "1d6"), spell.get("range", 8), spell_name=spell["name"])
        elif effect == "heal":
            healed = dice.roll(spell.get("power", "1d8"), self.rng)
            before = self.player.hp
            self.player.hp = min(self.player.max_hp, self.player.hp + healed)
            self.message(f"{spell['name']}恢复了 {self.player.hp - before} 点生命。", "good")
        elif effect == "buff_ac":
            self.player.add_buff("ac", int(spell.get("amount", 2)), int(spell.get("turns", 10)))
            self.message(f"{spell['name']}环绕着你，护甲 +{spell.get('amount', 2)}。", "magic")
        elif effect == "buff_attack":
            self.player.add_buff("attack", int(spell.get("amount", 1)), int(spell.get("turns", 10)))
            self.message(f"{spell['name']}指引你的手，命中 +{spell.get('amount', 1)}。", "magic")
        self._end_turn()

    # --- 调试 / 考据工具 ---
    def _cmd_reveal(self) -> None:
        level = self.level()
        level.explored = bytearray([1]) * (level.w * level.h)
        self.message("[调试] 已显示整层地图。", "warn")
        self.commands.pop()

    def _cmd_teleport(self, depth: int) -> None:
        self.depth = max(1, min(MAX_DEPTH, int(depth)))
        self.player.depth = self.depth
        level = self.level()
        self.player.x, self.player.y = level.up
        self.message(f"[调试] 已传送到第 {self.depth} 层。", "warn")
        self._refresh_fov()
        self.commands.pop()

    # ------------------------------------------------------------ 战斗结算
    def _apply_offensive_effect(self, effect: str, power: str, rng_range: int = 8, spell_name: str = "") -> None:
        level = self.level()
        targets = [m for m in level.monsters if m.alive and (m.x, m.y) in self.visible]
        if not targets:
            self.message("魔法没有找到目标。", "warn")
            return
        if effect == "damage_all":
            targets = list(targets)
        else:
            targets.sort(key=lambda m: abs(m.x - self.player.x) + abs(m.y - self.player.y))
            nearest = targets[0]
            dist = abs(nearest.x - self.player.x) + abs(nearest.y - self.player.y)
            if dist > rng_range:
                self.message("目标超出了施法距离。", "warn")
                return
            targets = [nearest]
        for m in targets:
            dmg = dice.roll(power, self.rng)
            m.hp -= dmg
            m.awake = True
            label = spell_name or "魔法"
            self.message(f"{label}击中了{m.name}，造成 {dmg} 点伤害。", "magic")
            if m.hp <= 0:
                self._kill_monster(m)

    def _player_attacks(self, monster: Monster) -> None:
        bonus = self.player.attack_bonus()
        if monster.undead and self.player.class_id == "cleric":
            bonus += 2
        hit, crit, roll = attack_roll(bonus, monster.ac, self.rng)
        if not hit:
            self.message(f"你没有击中{monster.name}。（掷出 {roll}）", "warn")
            return
        dmg = dice.roll(self.player.damage_expr(), self.rng)
        if crit:
            dmg *= 2
        monster.hp -= dmg
        monster.awake = True
        self.message(f"你{('暴击' if crit else '击中')}{monster.name}，造成 {dmg} 点伤害。", "good" if crit else "info")
        if monster.hp <= 0:
            self._kill_monster(monster)

    def _kill_monster(self, monster: Monster) -> None:
        self.message(f"{monster.name}倒下了！", "good")
        self.player.xp += monster.xp
        self.player.kills[monster.id] = self.player.kills.get(monster.id, 0) + 1
        self._check_level_up()

    def _check_level_up(self) -> None:
        content = load_content()
        klass = content.klass(self.player.class_id)
        while self.player.xp >= content.xp_for_level(self.player.level + 1):
            self.player.level += 1
            gain = max(1, dice.roll(f"1d{klass['hit_die']}", self.rng) + dice.modifier(self.player.attrs["CON"]))
            self.player.max_hp += gain
            self.player.hp += gain
            mp_gain = int(klass.get("mp_per_level", 0))
            self.player.max_mp += mp_gain
            self.player.mp += mp_gain
            self.message(f"你升到了 {self.player.level} 级！（生命上限 +{gain}）", "level")

    def _monsters_act(self) -> None:
        level = self.level()
        for m in list(level.monsters):
            if not m.alive or self.state != "playing":
                continue
            if (m.x, m.y) in self.visible:
                m.awake = True
                m.seen = True
            if not m.awake:
                if self.rng.chance(0.04):
                    self._wander(m)
                continue
            dist = max(abs(m.x - self.player.x), abs(m.y - self.player.y))
            if dist <= 1:
                self._monster_attacks(m)
            elif dist <= AGGRO_RANGE:
                self._step_toward(m)
            elif self.rng.chance(0.1):
                self._wander(m)

    def _wander(self, monster: Monster) -> None:
        level = self.level()
        for _ in range(4):
            dx, dy = self.rng.choice(((0, 1), (0, -1), (1, 0), (-1, 0), (0, 0)))
            nx, ny = monster.x + dx, monster.y + dy
            if level.is_walkable(nx, ny) and not level.monster_at(nx, ny) and (nx, ny) != (self.player.x, self.player.y):
                monster.x, monster.y = nx, ny
                return

    def _step_toward(self, monster: Monster) -> None:
        level = self.level()
        dx = (self.player.x > monster.x) - (self.player.x < monster.x)
        dy = (self.player.y > monster.y) - (self.player.y < monster.y)
        candidates = [(dx, dy), (dx, 0), (0, dy)]
        if self.rng.chance(0.2):
            candidates.append(self.rng.choice(((1, 0), (-1, 0), (0, 1), (0, -1))))
        for cx, cy in candidates:
            if cx == 0 and cy == 0:
                continue
            nx, ny = monster.x + cx, monster.y + cy
            if not level.is_walkable(nx, ny):
                continue
            if level.monster_at(nx, ny):
                continue
            if (nx, ny) == (self.player.x, self.player.y):
                continue
            monster.x, monster.y = nx, ny
            return

    def _monster_attacks(self, monster: Monster) -> None:
        hit, crit, roll = attack_roll(monster.attack_bonus, self.player.ac(), self.rng)
        if not hit:
            self.message(f"{monster.name}没有击中你。（掷出 {roll}）", "info")
            return
        dmg = dice.roll(monster.damage, self.rng)
        if crit:
            dmg *= 2
        self.player.hp -= dmg
        self.message(f"{monster.name}击中了你，造成 {dmg} 点伤害。", "bad")
        if self.player.hp <= 0:
            self._player_dies(monster)

    def _player_dies(self, killer: Monster) -> None:
        if self.modern and not self.second_wind_used:
            self.second_wind_used = True
            self.player.hp = 1
            self.message("你本应死去，但现代模式赐予你最后一口气。", "level")
            return
        self.player.hp = 0
        self.state = "dead"
        self.message(f"你在第 {self.depth} 层被{killer.name}杀死了……", "bad")

    # --------------------------------------------------------------- 回合
    def _end_turn(self) -> None:
        self._refresh_fov()
        self._monsters_act()
        if self.state == "playing":
            expired = self.player.tick_buffs()
            for key in expired:
                self.message(f"你的{key}效果消退了。", "info")
            self.turn += 1
            # 自然恢复：每 REGEN_TURNS 回合 +1 HP（L2 现代化层；原版是否有此机制不可考）
            if self.turn % REGEN_TURNS == 0 and self.player.hp < self.player.max_hp:
                self.player.hp = min(self.player.max_hp, self.player.hp + 1)
            self._refresh_fov()

    # ------------------------------------------------------------ 序列化
    def to_json(self) -> dict:
        return {
            "version": 1, "seed": self.seed, "turn": self.turn, "depth": self.depth,
            "state": self.state, "modern": self.modern, "second_wind_used": self.second_wind_used,
            "player": self.player.to_json(),
            "levels": {str(d): lv.to_json() for d, lv in self.levels.items()},
            "rng": self.rng.to_json(),
            "log": [list(entry) for entry in self.log[-40:]],
            "commands": [list(c) for c in self.commands],
        }

    @classmethod
    def from_json(cls, d: dict) -> "Game":
        game = cls.__new__(cls)
        game.seed = int(d["seed"])
        game.rng = RNG.from_json(d["rng"])
        from .entities import Player
        game.player = Player.from_json(d["player"])
        game.depth = int(d["depth"])
        game.turn = int(d["turn"])
        game.state = d["state"]
        game.modern = bool(d.get("modern"))
        game.second_wind_used = bool(d.get("second_wind_used"))
        game.levels = {int(k): Level.from_json(v) for k, v in d["levels"].items()}
        game.log = [tuple(x) for x in d.get("log", [])]
        game.commands = [tuple(c) for c in d.get("commands", [])]
        game.visible = set()
        game._refresh_fov()
        return game

    # --- 供 UI 使用的派生信息 ---
    def item_at_feet(self):
        return self.level().items_at(self.player.x, self.player.y)

    def visible_monsters(self):
        return sorted(
            (m for m in self.level().monsters if m.alive and (m.x, m.y) in self.visible),
            key=lambda m: abs(m.x - self.player.x) + abs(m.y - self.player.y),
        )

    def spellbook(self):
        content = load_content()
        return content.spells_for(self.player.class_id)

    def status(self) -> dict:
        p = self.player
        return {
            "name": p.name, "class": p.class_name(), "race": p.race_name(), "level": p.level, "hp": p.hp,
            "max_hp": p.max_hp, "mp": p.mp, "max_mp": p.max_mp, "ac": p.ac(),
            "xp": p.xp, "gold": p.gold, "depth": self.depth, "turn": self.turn,
            "weapon": p.weapon.name if p.weapon else "-",
            "armor": p.armor.name if p.armor else "-",
        }
