from lion_cub_pet.config import PetConfig, parse_value, set_value


def test_parse_values() -> None:
    assert parse_value("on") is True
    assert parse_value("17") == 17
    assert parse_value("1.25") == 1.25
    assert parse_value("playful") == "playful"


def test_set_known_value() -> None:
    config = PetConfig()
    set_value(config, "speed", 140)
    assert config.speed == 140.0


def test_screen_bounds_default_to_full_screen() -> None:
    assert PetConfig().bounds == "full-screen"
