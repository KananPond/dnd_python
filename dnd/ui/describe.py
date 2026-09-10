"""把数值/内部字段翻译成玩家看得懂的一句话。

存在的理由：浮层里曾直接打印 `effect` 字段，于是背包里出现
"闪电卷轴 damage_nearest"——内部 id 泄漏到界面。所有面向玩家的
物品/法术说明都从这里出，数据表里加新 effect 时只改这一处。
"""

from __future__ import annotations

# 内部 effect id -> 说明模板（{power} 取 item.power）
EFFECT_TEXT = {
    "damage_nearest": "对最近的敌人造成 {power} 伤害",
    "damage_all": "对视野内所有敌人造成 {power} 伤害",
    "heal": "恢复 {power} 生命",
    "buff_ac": "护甲 +{amount}",
    "buff_attack": "命中 +{amount}",
}


def effect_text(effect: str | None, power: str | None = None,
                amount: int | None = None, turns: int | None = None) -> str:
    """effect id -> 中文说明；不认识的效果原样返回，不吞掉信息。"""
    if not effect:
        return ""
    tmpl = EFFECT_TEXT.get(effect)
    if not tmpl:
        return effect
    text = tmpl.format(power=power or "?", amount=amount if amount is not None else "?")
    if turns:
        text += f"（{turns} 回合）"
    return text


def item_summary(item) -> str:
    """背包/侧栏里跟在物品名后面的那截说明。"""
    if item.kind == "weapon" and item.damage:
        return f"伤害 {item.damage}"
    if item.kind == "armor" and item.ac_bonus:
        return f"护甲 +{item.ac_bonus}"
    if item.kind == "potion" and item.heal:
        return effect_text("heal", item.heal)
    if item.kind == "scroll":
        return effect_text(item.effect, item.power)
    if item.kind == "relic":
        return "深渊遗物"
    if item.kind in ("gold", "gem") and item.value:
        return f"价值 {item.value} 金"
    return effect_text(item.effect, item.power)


def item_long(item) -> str:
    """物品的一行完整描述（给浮层用）：说明 + 价值。"""
    bits = [item_summary(item)]
    if item.value and item.kind not in ("gold", "gem"):
        bits.append(f"价值 {item.value} 金")
    return "   ".join(b for b in bits if b)


def item_compact(item) -> str:
    """侧栏用的极简说明——侧栏只有 22 格，写全会被截掉半句。"""
    if item.kind == "weapon" and item.damage:
        return item.damage
    if item.kind == "armor" and item.ac_bonus:
        return f"AC+{item.ac_bonus}"
    if item.kind == "potion" and item.heal:
        return f"回血 {item.heal}"
    if item.kind == "scroll":
        return f"伤害 {item.power}" if item.power else "卷轴"
    if item.kind == "relic":
        return "遗物"
    return item_summary(item)


def spell_summary(spell: dict) -> str:
    return effect_text(spell.get("effect"), spell.get("power"),
                       spell.get("amount"), spell.get("turns"))
