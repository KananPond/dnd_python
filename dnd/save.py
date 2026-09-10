"""存档：JSON 快照（角色 + 地牢 + RNG 状态），以及名人堂名册。"""

from __future__ import annotations

import json
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


def save_game(game: Game) -> pathlib.Path:
    _ensure_dir()
    path = save_path(game.player.name)
    path.write_text(json.dumps(game.to_json(), ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def load_game(path) -> Game:
    data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    return Game.from_json(data)


def latest_save():
    _ensure_dir()
    files = sorted(SAVE_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    files = [f for f in files if f.name != "roster.json"]
    return files[0] if files else None


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
    ROSTER.write_text(json.dumps(roster, ensure_ascii=False, indent=1), encoding="utf-8")
    return entry


def read_roster() -> list:
    if not ROSTER.exists():
        return []
    try:
        return json.loads(ROSTER.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
