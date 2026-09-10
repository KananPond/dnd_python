"""内核单元测试（标准库 unittest，无第三方依赖）。

运行：python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dnd import dice, fov, replay, save  # noqa: E402

# 测试产物写到临时目录，避免污染工作区的 saves/
_TMP_DIR = pathlib.Path(tempfile.mkdtemp(prefix="dnd-tests-"))
save.SAVE_DIR = _TMP_DIR
save.ROSTER = _TMP_DIR / "roster.json"
from dnd.content import load as load_content  # noqa: E402
from dnd.entities import create_player  # noqa: E402
from dnd.game import Game  # noqa: E402
from dnd.level import MAX_DEPTH, generate, reachable  # noqa: E402
from dnd.rng import RNG  # noqa: E402


class TestRNG(unittest.TestCase):
    def test_deterministic(self):
        a, b = RNG(1234), RNG(1234)
        self.assertEqual([a.next_u64() for _ in range(50)], [b.next_u64() for _ in range(50)])

    def test_state_roundtrip(self):
        a = RNG(99)
        for _ in range(10):
            a.next_u64()
        b = RNG.from_json(a.to_json())
        self.assertEqual([a.next_u64() for _ in range(20)], [b.next_u64() for _ in range(20)])

    def test_bounds(self):
        r = RNG(5)
        for _ in range(2000):
            v = r.randint(3, 7)
            self.assertGreaterEqual(v, 3)
            self.assertLessEqual(v, 7)


class TestDice(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(dice.parse("2d6+1"), (2, 6, 1))
        self.assertEqual(dice.parse("d8"), (1, 8, 0))
        self.assertEqual(dice.parse("7"), (0, 0, 7))
        with self.assertRaises(ValueError):
            dice.parse("banana")

    def test_roll_range(self):
        r = RNG(3)
        for _ in range(500):
            v = dice.roll("2d6+1", r)
            self.assertGreaterEqual(v, 3)
            self.assertLessEqual(v, 13)

    def test_modifier(self):
        self.assertEqual(dice.modifier(10), 0)
        self.assertEqual(dice.modifier(18), 4)
        self.assertEqual(dice.modifier(3), -4)


class TestLevelGen(unittest.TestCase):
    def test_connected_and_populated(self):
        rng = RNG(2024)
        for depth in range(1, MAX_DEPTH + 1):
            level = generate(depth, rng)
            seen = reachable(level, level.up)
            walkable = {(x, y) for y in range(level.h) for x in range(level.w) if level.is_walkable(x, y)}
            self.assertEqual(walkable, seen, f"depth {depth}: 存在不可达区域")
            self.assertGreaterEqual(len(level.rooms), 4)
            self.assertGreater(len(level.monsters), 0)
            for m in level.monsters:
                self.assertTrue(level.is_walkable(m.x, m.y), "怪物不在可走瓦片上")
            for _item, x, y in level.ground:
                self.assertTrue(level.is_walkable(x, y), "物品不在可走瓦片上")
            if depth < MAX_DEPTH:
                self.assertIn(level.down, seen, "下楼梯不可达")
            else:
                self.assertTrue(any(it.kind == "relic" for it, _x, _y in level.ground), "第 10 层缺少遗物")

    def test_deterministic(self):
        a = generate(4, RNG(777))
        b = generate(4, RNG(777))
        self.assertEqual(a.tiles, b.tiles)
        self.assertEqual([(m.id, m.x, m.y, m.hp) for m in a.monsters], [(m.id, m.x, m.y, m.hp) for m in b.monsters])

    def test_depth10_guardian_always_guards_the_relic(self):
        """回归：房间中心被随机怪占住时，原实现会整段跳过 → 没有 boss、遗物随机乱丢。

        设计约束：守卫必须生成、遗物必须在守卫身边（看管），但**不能压在守卫脚下** ——
        深渊守卫正面硬拼几乎打不过，压在脚下等于"必须先杀 boss"，通关就变得不可能。
        """
        rng = RNG(20240910)
        for i in range(120):
            level = generate(MAX_DEPTH, rng)
            guards = [m for m in level.monsters if m.id == "deep_guardian"]
            relics = [(it, x, y) for it, x, y in level.ground if it.kind == "relic"]
            self.assertEqual(len(guards), 1, f"第 {i} 次：第 10 层必须有且只有一个深渊守卫")
            self.assertEqual(len(relics), 1, f"第 {i} 次：第 10 层必须有且只有一个遗物")
            gx, gy = guards[0].x, guards[0].y
            rx, ry = relics[0][1], relics[0][2]
            self.assertLessEqual(max(abs(gx - rx), abs(gy - ry)), 2,
                                 f"第 {i} 次：遗物应放在守卫身边（由它看管）")
            self.assertNotEqual((rx, ry), (gx, gy),
                                f"第 {i} 次：遗物不能压在守卫脚下（否则必须先杀掉打不过的 boss）")
            self.assertNotEqual((rx, ry), level.up, f"第 {i} 次：遗物不能落在上楼梯口")


class TestFOV(unittest.TestCase):
    def test_player_visible_and_walls_block(self):
        rng = RNG(11)
        level = generate(2, rng)
        start = level.up
        vis = fov.compute(level, *start, radius=9)
        self.assertIn(start, vis)
        for (x, y) in vis:
            self.assertLessEqual(abs(x - start[0]) + abs(y - start[1]), 18)

    def test_radius_limit(self):
        rng = RNG(12)
        level = generate(1, rng)
        vis = fov.compute(level, *level.up, radius=3)
        for (x, y) in vis:
            self.assertLessEqual(max(abs(x - level.up[0]), abs(y - level.up[1])), 3)


class TestGameFlow(unittest.TestCase):
    def test_character_creation(self):
        p = create_player("Test", "wizard", RNG(1))
        self.assertEqual(p.class_id, "wizard")
        self.assertGreater(p.hp, 0)
        self.assertTrue(p.weapon is not None, "法师应有初始武器")

    def test_save_roundtrip_preserves_hash(self):
        game = Game(4242, "Saver", "cleric")
        for cmd in [("move", 1, 0), ("move", 0, 1), ("wait",), ("move", -1, 0)]:
            game.command(cmd)
        path = save.save_game(game)
        loaded = save.load_game(path)
        self.assertEqual(game.state_hash(), loaded.state_hash())
        self.assertEqual(game.turn, loaded.turn)
        self.assertEqual(game.depth, loaded.depth)

    def test_replay_is_deterministic(self):
        cmds = [("move", 1, 0), ("move", 0, 1), ("wait",), ("move", 1, 1), ("move", -1, 0)]
        self.assertEqual(replay.digest(31337, cmds), replay.digest(31337, cmds))
        self.assertNotEqual(replay.digest(31337, cmds), replay.digest(31338, cmds))

    def test_blocked_move_does_not_consume_turn(self):
        game = Game(5, "Blocker", "warrior")
        game.player.x, game.player.y = 1, 1  # 生成保证外墙
        before = game.turn
        game.command(("move", -5, 0))
        self.assertEqual(before, game.turn)

    def test_combat_and_xp(self):
        game = Game(8, "Fighter", "warrior")
        level = game.level()
        monster = level.monsters[0]
        game.player.x, game.player.y = monster.x - 1, monster.y
        hp_before = monster.hp
        xp_before = game.player.xp
        for _ in range(60):
            if not monster.alive:
                break
            game.command(("move", 1, 0))
        self.assertLessEqual(monster.hp, hp_before)
        if not monster.alive:
            self.assertGreater(game.player.xp, xp_before)

    def test_descend_requires_stairs(self):
        game = Game(9, "Climber", "rogue")
        level = game.level()
        game.player.x, game.player.y = level.up
        game.command(("descend",))
        self.assertEqual(game.depth, 1, "不在下楼梯处不应能下潜")

    def test_relic_wins_game(self):
        game = Game(10, "Winner", "warrior")
        game.command(("teleport", MAX_DEPTH))
        level = game.level()
        relic = next(((it, x, y) for it, x, y in level.ground if it.kind == "relic"), None)
        self.assertIsNotNone(relic, "第 10 层应有遗物")
        item, x, y = relic
        level.monsters = [m for m in level.monsters if (m.x, m.y) != (x, y)]
        game.player.x, game.player.y = x, y
        game.command(("pickup",))
        self.assertEqual(game.state, "won")
        self.assertIn(item, game.player.inventory)

    def test_death_is_permanent(self):
        game = Game(11, "Doomed", "wizard")
        game.player.hp = 1
        level = game.level()
        monster = level.monsters[0]
        monster.attack_bonus = 50
        monster.damage = "10d10"
        monster.awake = True
        monster.seen = True
        game.player.x, game.player.y = monster.x - 1, monster.y
        for _ in range(8):
            if game.state != "playing":
                break
            game.command(("wait",))
        self.assertEqual(game.state, "dead")
        self.assertLessEqual(game.player.hp, 0)

    def test_stair_arrival_never_stacks_with_a_monster(self):
        """回归：楼梯口被怪物占着时，玩家落上去会与怪物同格（怪能打你、你打不到它）。"""
        game = Game(11, "Arriver", "warrior")
        bottom = game.level().down
        game.player.x, game.player.y = bottom
        game.command(("descend",))
        self.assertEqual(game.depth, 2)
        lower = game.level()
        monster = lower.monsters[0]
        monster.x, monster.y = lower.up          # 模拟它自己溜达到楼梯口

        game.command(("ascend",))
        self.assertEqual(game.depth, 1)
        monster.x, monster.y = lower.up          # 上楼期间下层冻结，它还在那儿
        game.command(("descend",))

        self.assertEqual((game.player.x, game.player.y), lower.up, "玩家应正常落在楼梯格")
        self.assertNotEqual((game.player.x, game.player.y), (monster.x, monster.y),
                            "玩家不能与怪物落在同一格")
        self.assertIsNone(lower.monster_at(game.player.x, game.player.y))
        self.assertTrue(lower.is_walkable(monster.x, monster.y), "被挤开的怪物仍应在可走格上")

    def test_debug_commands_stay_in_replay_log(self):
        """回归：reveal/teleport 改状态又被 pop 掉 → replay 复现不出原局。"""
        cmds = [("move", 1, 0), ("reveal",), ("teleport", 4), ("wait",),
                ("teleport", 6), ("move", 0, 1)]
        game = Game(7, "Debugger", "rogue")
        for cmd in cmds:
            game.command(cmd)
        self.assertIn(("reveal",), game.commands)
        self.assertIn(("teleport", 4), game.commands)
        self.assertEqual(game.depth, 6)
        replayed = replay.run(game.seed, game.commands, game.player.name, game.player.class_id)
        self.assertEqual(game.state_hash(), replayed.state_hash())

    def test_malformed_commands_are_rejected_gracefully(self):
        """脏存档 / 回放里的畸形命令不应让整局崩掉，也不应改变状态或进入回放记录。"""
        bad = [("move",), ("move", 1), ("move", 1, "y"), ("use",), ("use", 0, 1),
               ("cast",), ("cast", "x", "y"), ("teleport", "x"), ("nope",), (), (5,), "move"]
        game = Game(1, "Tolerant", "warrior")
        before = (game.turn, game.state_hash(), list(game.commands))
        for cmd in bad:
            game.command(cmd)  # 不应抛异常
        self.assertEqual(game.turn, before[0], "畸形指令不应消耗回合")
        self.assertEqual(game.state_hash(), before[1], "畸形指令不应改变状态")
        self.assertEqual(game.commands, before[2], "畸形指令不应进入回放记录")

    def test_equipment_is_relinked_to_inventory_after_load(self):
        """回归：读档后 weapon/armor 必须是背包里的同一对象，否则"已装备"标记消失。"""
        game = Game(12, "Equip", "warrior")
        self.assertIsNotNone(game.player.weapon)
        loaded = save.load_game(save.save_game(game))
        self.assertTrue(any(it is loaded.player.weapon for it in loaded.player.inventory))
        self.assertTrue(any(it is loaded.player.armor for it in loaded.player.inventory))
        self.assertEqual(game.state_hash(), loaded.state_hash())


class TestRaces(unittest.TestCase):
    def test_race_modifiers_and_bonuses(self):
        human = create_player("H", "warrior", RNG(321), "human")
        dwarf = create_player("D", "warrior", RNG(321), "dwarf")
        elf = create_player("E", "warrior", RNG(321), "elf")
        gnome = create_player("G", "wizard", RNG(321), "gnome")
        # 同一种子下，属性差异只来自种族调整（18 上限内）
        self.assertGreaterEqual(dwarf.attrs["CON"], human.attrs["CON"])
        self.assertLessEqual(dwarf.attrs["DEX"], human.attrs["DEX"])
        self.assertGreater(dwarf.max_hp, human.max_hp)          # 矮人起始生命 +2
        self.assertEqual(elf.fov_radius(), human.fov_radius() + 1)   # 精灵夜视
        self.assertGreaterEqual(gnome.max_mp, 2)                # 侏儒起始法力 +2

    def test_all_races_playable(self):
        content = load_content()
        for rid in content.races:
            game = Game(77, "Racer", "cleric", race_id=rid)
            self.assertEqual(game.player.race_id, rid)
            self.assertGreater(game.player.hp, 0)
            self.assertGreaterEqual(game.player.fov_radius(), 9)

    def test_race_survives_save_roundtrip(self):
        game = Game(555, "Elfie", "rogue", race_id="elf")
        path = save.save_game(game)
        loaded = save.load_game(path)
        self.assertEqual(loaded.player.race_id, "elf")
        self.assertEqual(game.state_hash(), loaded.state_hash())

    def test_unknown_race_falls_back_to_human(self):
        game = Game(556, "Nobody", "warrior", race_id="dragon")
        self.assertEqual(game.player.race_id, "human")


if __name__ == "__main__":
    unittest.main()
