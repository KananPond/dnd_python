"""存档：JSON 快照（角色 + 地牢 + RNG 状态），以及名人堂名册。

存档文件顶层多了一个 `_meta` 字段（角色名/职业/深度/回合/时间戳），给**存档管理界面**
列表用 —— 只为了不必为了显示一行摘要就把整份地牢反序列化。`_meta` 是附加信息：
`Game.from_json` 只读它认识的键，旧存档（没有 `_meta`）照样能读，`index()` 会退回文件
自身的信息（mtime / 文件名）补一份摘要。
"""

from __future__ import annotations

import json
import os
import pathlib
import time

from .game import Game

ROOT = pathlib.Path(__file__).resolve().parent.parent
SAVE_DIR = ROOT / "saves"
ROSTER = SAVE_DIR / "roster.json"


def _ensure_dir() -> None:
    SAVE_DIR.mkdir(parents=True, exist_ok=True)


def safe_name(name: str) -> str:
    keep = [c for c in name.strip().lower() if c.isalnum() or c in "-_"]
    return "".join(keep) or "adventurer"


def save_path(name: str) -> pathlib.Path:
    return SAVE_DIR / f"{safe_name(name)}.json"


def save_meta(game: Game) -> dict:
    """存档摘要（写进 `_meta`，存档管理界面直接拿它显示，不必反序列化整份地牢）。

    时间戳只写"年月日 时:分"给玩家看；排序用的是文件自身的 mtime（`index()`），
    不存进 JSON —— 存了也会立刻过时。
    """
    return {
        "name": game.player.name,
        "class": game.player.class_name(),
        "class_id": game.player.class_id,
        "race": game.player.race_name(),
        "race_id": game.player.race_id,
        "level": game.player.level,
        "depth": game.depth,
        "turn": game.turn,
        "gold": game.player.gold,
        "hp": game.player.hp,
        "max_hp": game.player.max_hp,
        "date": time.strftime("%Y-%m-%d %H:%M"),
    }


def save_game(game: Game) -> pathlib.Path:
    """原子写：先写同目录临时文件再 os.replace，避免写一半崩溃把存档写坏。"""
    _ensure_dir()
    path = save_path(game.player.name)
    blob = json.dumps({**game.to_json(), "_meta": save_meta(game)},
                      ensure_ascii=False, indent=1)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(blob, encoding="utf-8")
    os.replace(tmp, path)
    return path


def load_game(path) -> Game:
    data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    return Game.from_json(data)


def _plain_saves() -> list[pathlib.Path]:
    """saves/ 下的存档（排除名人堂 roster.json 与正在写的 .tmp）。"""
    if not SAVE_DIR.exists():
        return []
    return [p for p in SAVE_DIR.glob("*.json")
            if p.name not in ("roster.json",) and not p.name.endswith(".tmp")]


def latest_save():
    _ensure_dir()
    files = sorted(_plain_saves(), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def _zh(kind: str, oid) -> str:
    """把 class_id / race_id 翻成本地化名字（旧存档的摘要用）。查不到就原样返回。"""
    if not oid:
        return "—"
    try:
        from .content import load as load_content
        table = load_content()
        entry = table.klass(oid) if kind == "class" else table.race(oid)
        return entry.get("name_zh") or entry.get("name") or str(oid)
    except (KeyError, OSError, ValueError):
        return str(oid)


def save_summary(path) -> dict:
    """读一份存档的摘要；损坏或结构不认识时返回带 `error` 的条目，而不是抛异常。

    存档管理界面必须能**列出坏存档并让用户删掉它** —— 一个读不动的 JSON 若让整个
    界面崩掉，玩家就只能回命令行手动删文件，那正是这个界面要消灭的体验。
    """
    path = pathlib.Path(path)
    entry = {"path": path, "file": path.name, "error": None}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("存档不是 JSON 对象")
        meta = data.get("_meta")
        player = data.get("player") if isinstance(data.get("player"), dict) else {}
    except (OSError, ValueError, TypeError) as exc:
        entry.update(name=path.stem, klass="—", race="—", level=0, depth=0, turn=0, gold=0)
        entry["error"] = str(exc)
    else:
        if not isinstance(meta, dict):
            # 旧存档（没有 _meta）：从 player 段补出来，缺字段一律给中性默认值
            meta = {
                "name": player.get("name") or path.stem,
                "class": _zh("class", player.get("class_id")),
                "class_id": player.get("class_id"),
                "race": _zh("race", player.get("race_id")),
                "race_id": player.get("race_id"),
                "level": player.get("level") or 0,
                "gold": player.get("gold") or 0,
                "hp": player.get("hp") or 0,
                "max_hp": player.get("max_hp") or 0,
            }
        entry.update(
            name=meta.get("name") or path.stem,
            klass=meta.get("class") or "—",
            race=meta.get("race") or "—",
            class_id=meta.get("class_id"),
            race_id=meta.get("race_id"),
            level=int(meta.get("level") or 0),
            depth=int(meta.get("depth") or (data.get("depth") or 0)),
            turn=int(meta.get("turn") or (data.get("turn") or 0)),
            gold=int(meta.get("gold") or 0),
            hp=int(meta.get("hp") or 0),
            max_hp=int(meta.get("max_hp") or 0),
        )
        entry["date"] = meta.get("date") or ""
    try:
        entry["mtime"] = path.stat().st_mtime
    except OSError:
        entry["mtime"] = 0.0
    if not entry.get("date") and entry["mtime"]:
        entry["date"] = time.strftime("%Y-%m-%d %H:%M", time.localtime(entry["mtime"]))
    return entry


def index() -> list[dict]:
    """按最近保存排序的存档列表（存档管理界面的数据源）。"""
    entries = [save_summary(p) for p in _plain_saves()]
    entries.sort(key=lambda e: e["mtime"], reverse=True)
    return entries


def delete_save(path) -> None:
    pathlib.Path(path).unlink()


def record_roster(game: Game, result: str) -> dict:
    """游戏结束时登记名册（仅在结束后调用，且不影响内核确定性）。"""
    _ensure_dir()
    entry = {
        "name": game.player.name, "class": game.player.class_name(),
        "race": game.player.race_name(),
        "level": game.player.level, "depth": game.depth, "gold": game.player.gold,
        "turns": game.turn, "result": result, "seed": game.seed,
        "kills": sum(game.player.kills.values()),
        "date": time.strftime("%Y-%m-%d %H:%M"),
    }
    roster = read_roster()
    roster.append(entry)
    tmp = ROSTER.with_name(ROSTER.name + ".tmp")
    tmp.write_text(json.dumps(roster, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, ROSTER)
    return entry


def read_roster() -> list:
    if not ROSTER.exists():
        return []
    try:
        data = json.loads(ROSTER.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []
