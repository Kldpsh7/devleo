import json
import random
from pathlib import Path

import pytest

from lion_cub_pet.dialogues import DIALOGUES, DialogueDeck, load_dialogue_pack


def test_dialogues_do_not_repeat_until_category_is_exhausted() -> None:
    lines = ("one", "two", "three")
    deck = DialogueDeck({"idle": lines}, random.Random(7))
    first_round = [deck.next("idle") for _ in lines]
    assert len(set(first_round)) == len(lines)
    assert deck.next("idle") != first_round[-1]


def test_custom_dialogue_pack_merges_valid_lines(tmp_path: Path) -> None:
    path = tmp_path / "dialogues.json"
    path.write_text(json.dumps({"victory": ["Custom roar!"]}), encoding="utf-8")
    loaded = load_dialogue_pack(path)
    assert loaded["victory"] == (*DIALOGUES["victory"], "Custom roar!")


def test_custom_dialogue_pack_rejects_unknown_categories(tmp_path: Path) -> None:
    path = tmp_path / "dialogues.json"
    path.write_text(json.dumps({"unknown": ["Nope"]}), encoding="utf-8")
    with pytest.raises(ValueError, match="unknown dialogue category"):
        load_dialogue_pack(path)
