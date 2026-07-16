from __future__ import annotations

import random
from collections.abc import Mapping, Sequence

DIALOGUES: dict[str, tuple[str, ...]] = {
    "idle": (
        "Compiling thoughts…",
        "I’m sitting on a breakthrough.",
        "This bug looks suspicious.",
        "Quiet. I’m judging the architecture.",
    ),
    "working": (
        "This is really hard.",
        "One more commit… probably.",
        "My tail is handling QA.",
        "I have entered the code cave.",
    ),
    "waiting": (
        "Your move, keyboard wizard.",
        "I require a human decision.",
        "I’m waiting very productively.",
        "Approval would be pawsome.",
    ),
    "review": (
        "Squinting improves code quality.",
        "Hmm. This line has vibes.",
        "Approved by one tiny lion.",
        "I found a semicolon in the wild.",
    ),
    "failure": (
        "I meant to test that.",
        "That bug had plot armor.",
        "We call this exploratory coding.",
        "The laptop started it.",
    ),
    "departing": (
        "My work here is done.",
        "Deploying myself elsewhere.",
        "Catch me if you can.",
        "New corner, same bugs.",
    ),
    "clicked": (
        "What do you want?",
        "Hey—I’m debugging here.",
        "Boop acknowledged.",
        "Yes, human?",
    ),
    "relax": (
        "Great weather for zero meetings.",
        "I’m on paws.",
        "This cola is production-grade.",
        "My calendar says: absolutely not.",
    ),
    "focus": (
        "Gotta work hard.",
        "Do not disturb the tiny architect.",
        "Entering deep paw mode.",
        "Distractions have been deprecated.",
    ),
    "sleep": (
        "Dreaming in Python…",
        "Zzz… zero bugs detected.",
        "Wake me for deployment.",
        "Running sleep tests.",
    ),
    "motivate": (
        "You can do it!",
        "You’ve got this.",
        "One small step, one clean commit.",
        "Your future self says thanks.",
        "Keep going—I believe in you.",
    ),
    "advice": (
        "Hydration check: drink some water.",
        "Tiny walk? Your brain will thank you.",
        "Unclench your jaw. Yes, that one.",
        "Look away from the screen for 20 seconds.",
        "Stretch your paws—uh, hands.",
    ),
}


class DialogueDeck:
    """Shuffled dialogue bags that avoid repeats until a category is exhausted."""

    def __init__(
        self,
        dialogues: Mapping[str, Sequence[str]] = DIALOGUES,
        rng: random.Random | None = None,
    ) -> None:
        self.dialogues = dialogues
        self.rng = rng or random.Random()
        self._bags: dict[str, list[str]] = {}
        self._last: dict[str, str] = {}

    def next(self, category: str) -> str:
        choices = list(self.dialogues.get(category, self.dialogues["idle"]))
        bag = self._bags.get(category, [])
        if not bag:
            bag = choices.copy()
            self.rng.shuffle(bag)
            previous = self._last.get(category)
            if previous and len(bag) > 1 and bag[-1] == previous:
                bag[0], bag[-1] = bag[-1], bag[0]
            self._bags[category] = bag
        line = bag.pop()
        self._last[category] = line
        return line
