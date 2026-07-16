import random

from lion_cub_pet.dialogues import DialogueDeck


def test_dialogues_do_not_repeat_until_category_is_exhausted() -> None:
    lines = ("one", "two", "three")
    deck = DialogueDeck({"idle": lines}, random.Random(7))
    first_round = [deck.next("idle") for _ in lines]
    assert len(set(first_round)) == len(lines)
    assert deck.next("idle") != first_round[-1]
