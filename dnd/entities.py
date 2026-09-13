"""角色、怪物、物品。数值全部来自 content 数据表（可替换）。"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import dice
from .content import load as load_content

ATTR_ORDER = ("STR", "DEX", "CON", "INT", "WIS")
BASE_FOV_RADIUS = 9  # 基础视野半径；种族可加成（精灵/侏儒夜视 +1）
CLASS_PRIMARY = {
    "warrior": ("STR", "CON"),
    "wizard": ("INT", "WIS"),
    "cleric": ("WIS", "CON"),
    "rogue": ("DEX", "STR"),
}


@dataclass
class Item:
    id: str
    name: str
    kind: str
    glyph: str
    color: str
    damage: str | None = None
    ac_bonus: int = 0
    heal: str | None = None
    effect: str | None = None
    power: str | None = None
    value: int = 0
    confidence: str = "invented"

    @property
    def is_equipment(self) -> bool:
        return self.kind in ("weapon", "armor")

    def to_json(self) -> dict:
        return {
            "id": self.id, "name": self.name, "kind": self.kind, "glyph": self.glyph,
            "color": self.color, "damage": self.damage, "ac_bonus": self.ac_bonus,
            "heal": self.heal, "effect": self.effect, "power": self.power,
            "value": self.value, "confidence": self.confidence,
        }

    @classmethod
    def from_json(cls, d: dict) -> "Item":
        return cls(**d)


def make_item(item_id: str, rng, depth: int) -> Item:
    content = load_content()
    t = content.items[item_id]
    it = Item(
        id=t["id"], name=t["name"], kind=t["kind"], glyph=t["glyph"], color=t["color"],
        damage=t.get("damage"), ac_bonus=int(t.get("ac_bonus", 0)), heal=t.get("heal"),
        effect=t.get("effect"), power=t.get("power"), value=int(t.get("value", 0)),
        confidence=t.get("confidence") or content.meta["items"].get("confidence", "invented"),
    )
    if it.kind == "gold":
        it.value = dice.roll("5d10", rng) + depth * 10
    elif it.kind == "gem":
        it.value = dice.roll("3d6", rng) * 5 + depth * 10
    return it


@dataclass
class Monster:
    id: str
    name: str
    glyph: str
    color: str
    x: int
    y: int
    hp: int
    max_hp: int
    ac: int
    attack_bonus: int
    damage: str
    xp: int
    undead: bool = False
    boss: bool = False
    awake: bool = False
    seen: bool = False
    name_zh: str = ""
    confidence: str = "invented"

    @property
    def alive(self) -> bool:
        return self.hp > 0

    def to_json(self) -> dict:
        return {
            "id": self.id, "name": self.name, "glyph": self.glyph, "color": self.color,
            "x": self.x, "y": self.y, "hp": self.hp, "max_hp": self.max_hp, "ac": self.ac,
            "attack_bonus": self.attack_bonus, "damage": self.damage, "xp": self.xp,
            "undead": self.undead, "boss": self.boss, "awake": self.awake, "seen": self.seen,
            "name_zh": self.name_zh, "confidence": self.confidence,
        }

    @classmethod
    def from_json(cls, d: dict) -> "Monster":
        return cls(**d)


def make_monster(template: dict, x: int, y: int, rng) -> Monster:
    content = load_content()
    hp = max(1, dice.roll(template["hp"], rng))
    return Monster(
        id=template["id"], name=template["name"], name_zh=template.get("name_zh", ""),
        glyph=template["glyph"], color=template["color"], x=x, y=y, hp=hp, max_hp=hp,
        ac=int(template["ac"]), attack_bonus=int(template["attack_bonus"]),
        damage=template["damage"], xp=int(template["xp"]),
        undead=bool(template.get("undead")), boss=bool(template.get("boss")),
        confidence=template.get("confidence") or content.meta["monsters"].get("confidence", "invented"),
    )


def _relink_equipment(inventory: list, data: dict | None) -> "Item | None":
    """把存档里的装备数据还原成背包中的同一个对象（找不到才新建）。

    背包/装备是两份 JSON 字段，直接各建一份 Item 会造成"同一件剑有两个对象"，
    于是 `item is player.weapon` 之类的判断在读档后失效。
    """
    if not data:
        return None
    item = Item.from_json(data)
    for owned in inventory:
        if owned == item:  # dataclass 值相等即视为同一件装备
            return owned
    return item


@dataclass
class Player:
    name: str
    class_id: str
    race_id: str = "human"
    x: int = 0
    y: int = 0
    depth: int = 1
    level: int = 1
    xp: int = 0
    hp: int = 1
    max_hp: int = 1
    mp: int = 0
    max_mp: int = 0
    gold: int = 0
    attrs: dict = field(default_factory=dict)
    inventory: list = field(default_factory=list)
    weapon: Item | None = None
    armor: Item | None = None
    buffs: dict = field(default_factory=dict)  # name -> [amount, turns_left]
    kills: dict = field(default_factory=dict)

    # --- 派生属性 ---
    def ac(self) -> int:
        base = 10 + (self.armor.ac_bonus if self.armor else 0) + dice.modifier(self.attrs["DEX"])
        if "ac" in self.buffs:
            base += self.buffs["ac"][0]
        return base

    def attack_bonus(self) -> int:
        content = load_content()
        bonus = content.attack_bonus_for(self.class_id, self.level) + dice.modifier(self.attrs["STR"])
        if "attack" in self.buffs:
            bonus += self.buffs["attack"][0]
        return bonus

    def damage_expr(self) -> str:
        return self.weapon.damage if self.weapon and self.weapon.damage else "1d2"

    @property
    def alive(self) -> bool:
        return self.hp > 0

    def class_name(self) -> str:
        return load_content().klass(self.class_id)["name"]

    def race(self) -> dict:
        return load_content().race(self.race_id)

    def race_name(self) -> str:
        return self.race()["name"]

    def fov_radius(self) -> int:
        return BASE_FOV_RADIUS + int(self.race().get("fov_bonus", 0))

    def tick_buffs(self) -> list:
        """回合结束时递减增益，返回过期的增益名。"""
        expired = []
        for key in list(self.buffs):
            self.buffs[key][1] -= 1
            if self.buffs[key][1] <= 0:
                expired.append(key)
                del self.buffs[key]
        return expired

    def add_buff(self, key: str, amount: int, turns: int) -> None:
        self.buffs[key] = [amount, turns]

    def to_json(self) -> dict:
        return {
            "name": self.name, "class_id": self.class_id, "race_id": self.race_id,
            "x": self.x, "y": self.y,
            "depth": self.depth, "level": self.level, "xp": self.xp, "hp": self.hp,
            "max_hp": self.max_hp, "mp": self.mp, "max_mp": self.max_mp, "gold": self.gold,
            "attrs": self.attrs, "inventory": [i.to_json() for i in self.inventory],
            "weapon": self.weapon.to_json() if self.weapon else None,
            "armor": self.armor.to_json() if self.armor else None,
            "buffs": self.buffs, "kills": self.kills,
        }

    @classmethod
    def from_json(cls, d: dict) -> "Player":
        p = cls(name=d["name"], class_id=d["class_id"], race_id=d.get("race_id", "human"))
        p.x, p.y, p.depth = d["x"], d["y"], d["depth"]
        p.level, p.xp, p.hp, p.max_hp = d["level"], d["xp"], d["hp"], d["max_hp"]
        p.mp, p.max_mp, p.gold = d["mp"], d["max_mp"], d["gold"]
        p.attrs = dict(d["attrs"])
        p.inventory = [Item.from_json(x) for x in d["inventory"]]
        # 装备必须指回背包里的**同一个对象**：UI（背包浮层）用 `item is player.weapon`
        # 判断"已装备"，各建一份副本会让读档后的装备标记凭空消失。
        p.weapon = _relink_equipment(p.inventory, d["weapon"])
        p.armor = _relink_equipment(p.inventory, d["armor"])
        p.buffs = {k: list(v) for k, v in d["buffs"].items()}
        p.kills = dict(d["kills"])
        return p


def create_player(name: str, class_id: str, rng, race_id: str = "human") -> Player:
    content = load_content()
    klass = content.klass(class_id)
    race = content.race(race_id)
    # 3d6 掷属性，最低 6（L2 现代化：避免极端残废角色开局即可玩）
    attrs = {a: max(6, dice.roll("3d6", rng)) for a in ATTR_ORDER}
    for a in CLASS_PRIMARY.get(class_id, ()):
        attrs[a] = min(18, attrs[a] + 2)
    for a, delta in race.get("mods", {}).items():  # 种族属性调整
        attrs[a] = max(3, min(18, attrs.get(a, 10) + int(delta)))
    hp = max(1, klass["hit_die"] + dice.modifier(attrs["CON"]) + 3 + int(race.get("hp_bonus", 0)))
    caster_stat = attrs["INT"] if class_id == "wizard" else attrs["WIS"]
    if klass.get("spells"):
        mp = max(0, int(klass.get("mp_per_level", 0)) + dice.modifier(caster_stat)
                 + 2 + int(race.get("mp_bonus", 0)))
    else:
        mp = 0  # 不会施法的职业（战士/盗贼）不给法力：界面不必显示一条永远用不上的法力条
    player = Player(
        name=name, class_id=class_id, race_id=race["id"], hp=hp, max_hp=hp, mp=mp, max_mp=mp,
        attrs=attrs, gold=30,
    )
    for item_id in klass.get("start_items", []):
        player.inventory.append(make_item(item_id, rng, 1))
    auto_equip(player, quiet=True)
    return player


def auto_equip(player: Player, quiet: bool = False) -> list:
    """自动穿戴背包中更好的武器/护甲（用于建角与拾取）。返回提示文本列表。"""
    notes = []
    for item in list(player.inventory):
        if item.kind == "weapon":
            if player.weapon is None or dice.average(item.damage or "1d2") > dice.average(player.weapon.damage or "1d2"):
                player.weapon = item
                if not quiet:
                    notes.append(f"You wield the {item.name}.")
        elif item.kind == "armor":
            if player.armor is None or item.ac_bonus > player.armor.ac_bonus:
                player.armor = item
                if not quiet:
                    notes.append(f"You wear the {item.name}.")
    return notes
