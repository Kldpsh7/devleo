from lion_cub_pet.cli import main, parser


def test_all_documented_command_groups_parse() -> None:
    cases = [
        ["install", "--autostart", "--start"],
        ["anchor", "bottom-right"],
        ["move", "10", "20"],
        ["speed", "fast"],
        ["size", "1.2"],
        ["size", "tiny"],
        ["transparency", "35"],
        ["pomodoro", "start", "--focus", "25", "--break", "5"],
        ["rubber-duck", "ask"],
        ["quiet-hours", "schedule", "22:00", "08:00"],
        ["dialogue-pack", "load", "/tmp/leo-dialogues.json"],
        ["victory"],
        ["treat"],
        ["mood"],
        ["mode", "focus"],
        ["dialogues", "off"],
        ["say", "hello", "human"],
        ["play", "working"],
        ["look", "270"],
        ["autostart", "status"],
        ["config", "set", "run_chance", "50"],
        ["event", "waiting", "--source", "test", "--ttl", "10"],
        ["showcase", "--seconds-per-state", "0.5"],
    ]
    for argv in cases:
        assert parser().parse_args(argv).command == argv[0]


def test_json_option_is_accepted_after_command(capsys: object) -> None:
    assert main(["version", "--json"]) == 0
