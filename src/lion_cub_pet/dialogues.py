from __future__ import annotations

import json
import random
from collections.abc import Mapping, Sequence
from pathlib import Path

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
    "pomodoro_focus": (
        "Focus sprint. Let’s ship something good.",
        "Deep work mode: activated.",
        "One task. Zero squirrels.",
        "Timer started. I brought the headband.",
    ),
    "pomodoro_break": (
        "Break time. Your brain earned snacks.",
        "Step away before the code starts talking back.",
        "Five minutes of professional lounging.",
        "Save file. Stretch human.",
    ),
    "rubber_duck": (
        "What did you expect this value to be?",
        "What changed immediately before it broke?",
        "Can you reproduce it with one smaller input?",
        "Which assumption have we not verified?",
        "What would the simplest failing test look like?",
        "Is the state wrong, or only the rendering of it?",
    ),
    "victory": (
        "Tests green. Mane magnificent.",
        "That deserves a tiny roar!",
        "Bug defeated. Snacks pending.",
        "Commit it before reality changes its mind.",
    ),
    "treat": (
        "Excellent. I accept this compensation.",
        "Treat received. Morale restored.",
        "You may continue coding now.",
        "Crunch-driven development works.",
    ),
}

MAX_DIALOGUE_PACK_BYTES = 256 * 1024
MAX_LINES_PER_CATEGORY = 100
MAX_LINE_LENGTH = 220


def load_dialogue_pack(path: str | Path | None) -> dict[str, tuple[str, ...]]:
    merged = dict(DIALOGUES)
    if path is None:
        return merged
    pack_path = Path(path).expanduser().resolve()
    if not pack_path.is_file():
        raise ValueError(f"dialogue pack does not exist: {pack_path}")
    if pack_path.stat().st_size > MAX_DIALOGUE_PACK_BYTES:
        raise ValueError("dialogue pack exceeds 256 KiB")
    raw = json.loads(pack_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("dialogue pack must be a JSON object")
    for category, lines in raw.items():
        if category not in DIALOGUES:
            raise ValueError(f"unknown dialogue category: {category}")
        if not isinstance(lines, list) or not 1 <= len(lines) <= MAX_LINES_PER_CATEGORY:
            raise ValueError(f"{category} must contain 1-{MAX_LINES_PER_CATEGORY} lines")
        normalized: list[str] = []
        for line in lines:
            if not isinstance(line, str) or not line.strip():
                raise ValueError(f"{category} contains an invalid line")
            text = line.strip()
            if len(text) > MAX_LINE_LENGTH:
                raise ValueError(f"{category} contains a line longer than {MAX_LINE_LENGTH} chars")
            normalized.append(text)
        merged[category] = (*DIALOGUES[category], *normalized)
    return merged


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
