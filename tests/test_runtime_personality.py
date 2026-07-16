from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QContextMenuEvent, QMouseEvent
from PySide6.QtWidgets import QApplication, QMenu

import lion_cub_pet.runtime as runtime
from lion_cub_pet.bubble import ThoughtBubble
from lion_cub_pet.config import PetConfig


class RecordingMenu(QMenu):
    def __init__(self) -> None:
        super().__init__()
        self.popup_position: QPoint | None = None

    def popup(self, pos: QPoint, action: object = None) -> None:  # type: ignore[override]
        del action
        self.popup_position = pos


def make_window(monkeypatch: object, config: PetConfig | None = None) -> runtime.PetWindow:
    QApplication.instance() or QApplication([])
    monkeypatch.setattr(runtime, "save_config", lambda _config: None)  # type: ignore[attr-defined]
    window = runtime.PetWindow(config or PetConfig(movement="stay"))
    window.animation_timer.stop()
    window.movement_timer.stop()
    window.dialogue_timer.stop()
    window.advice_timer.stop()
    window.pomodoro_timer.stop()
    window.rubber_duck_timer.stop()
    return window


def test_stationary_art_is_fifteen_percent_smaller(monkeypatch: object) -> None:
    window = make_window(monkeypatch)
    assert window.render_factor("idle") == 0.85
    assert window.render_factor("working") == 0.85
    assert window.render_factor("walk-left") == 1.0
    window.close()


def test_custom_modes_use_slower_animation_intervals(monkeypatch: object) -> None:
    window = make_window(monkeypatch)
    for mode in ("relax", "focus", "sleep", "motivate", "advice"):
        assert window.frame_count(mode) == 8
        assert window.animation_interval(mode) > runtime.DEFAULT_FRAME_INTERVAL
    window.close()


def test_motivate_returns_to_normal_only_for_current_generation(monkeypatch: object) -> None:
    window = make_window(monkeypatch)
    window.handle({"action": "mode", "value": "motivate"})
    generation = window.mode_generation
    window.finish_motivate(generation - 1)
    assert window.config.mode == "motivate"
    window.finish_motivate(generation)
    assert window.config.mode == "normal"
    assert window.animation_timer.interval() == runtime.DEFAULT_FRAME_INTERVAL
    window.close()


def test_size_is_clamped_to_safe_range(monkeypatch: object) -> None:
    window = make_window(monkeypatch)
    window.handle({"action": "set", "key": "scale", "value": 8.0})
    assert window.config.scale == runtime.MAX_SCALE
    window.handle({"action": "set", "key": "scale", "value": 0.1})
    assert window.config.scale == runtime.MIN_SCALE
    window.close()


def test_opacity_is_clamped_to_usable_range(monkeypatch: object) -> None:
    window = make_window(monkeypatch)
    window.handle({"action": "set", "key": "opacity", "value": 2.0})
    assert window.config.opacity == runtime.MAX_OPACITY
    window.handle({"action": "set", "key": "opacity", "value": 0.0})
    assert window.config.opacity == runtime.MIN_OPACITY
    window.close()


def test_dialogue_bubble_is_compact_and_cannot_take_focus(monkeypatch: object) -> None:
    window = make_window(monkeypatch)
    bubble = ThoughtBubble(window)
    bubble.show_message("Short line")
    assert bubble.width() < 200
    assert bubble.height() <= 48
    assert bubble.windowFlags() & Qt.WindowType.WindowDoesNotAcceptFocus
    assert bubble.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    assert not bubble.grab().isNull()
    bubble.close()
    window.close()


def test_corner_anchors_align_visible_pixels_with_screen(monkeypatch: object) -> None:
    window = make_window(monkeypatch)
    area = window.work_area()
    window.apply_anchor("top-left")
    content = window.scaled_content_rect().translated(window.pos())
    assert content.left() == area.left()
    assert content.top() == area.top()
    window.apply_anchor("bottom-right")
    content = window.scaled_content_rect().translated(window.pos())
    assert content.right() == area.right()
    assert content.bottom() == area.bottom()
    window.close()


def test_right_click_opens_shared_menu(monkeypatch: object) -> None:
    window = make_window(monkeypatch)
    assert window.label.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    menu = RecordingMenu()
    window.context_menu = menu
    event = QContextMenuEvent(
        QContextMenuEvent.Reason.Mouse,
        QPoint(4, 4),
        QPoint(44, 55),
    )
    window.contextMenuEvent(event)
    assert menu.popup_position == QPoint(44, 55)
    assert window.context_menu_open_count == 1
    menu.popup_position = None
    press = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(4, 4),
        QPointF(66, 77),
        Qt.MouseButton.RightButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    window.mousePressEvent(press)
    assert menu.popup_position == QPoint(66, 77)
    assert window.context_menu_open_count == 2
    window.close()


def test_pomodoro_cycles_focus_and_relax(monkeypatch: object) -> None:
    window = make_window(monkeypatch)
    window.handle(
        {
            "action": "pomodoro",
            "value": "start",
            "focus": 0.05,
            "break_minutes": 0.05,
        }
    )
    assert window.config.pomodoro_enabled
    assert window.config.mode == "focus"
    assert window.pomodoro_timer.isActive()
    window.advance_pomodoro()
    assert window.config.pomodoro_phase == "break"
    assert window.config.mode == "relax"
    window.handle({"action": "pomodoro", "value": "stop"})
    assert not window.config.pomodoro_enabled
    assert window.config.mode == "normal"
    window.close()


def test_quiet_hours_suppress_dialogue(monkeypatch: object) -> None:
    window = make_window(monkeypatch)
    window.handle({"action": "quiet-hours", "value": "on"})
    assert window.quiet_hours_active()
    assert not window.speak("idle", force=True)
    window.handle({"action": "quiet-hours", "value": "off"})
    assert not window.quiet_hours_active()
    window.close()


def test_treat_updates_mood_and_interaction_streak(monkeypatch: object) -> None:
    window = make_window(monkeypatch)
    before = window.config.mood
    window.handle({"action": "treat"})
    assert window.config.treats == 1
    assert window.config.mood == min(100, before + 8)
    assert window.config.interaction_streak == 1
    assert window.temporary_animation == "wave"
    window.close()


def test_rubber_duck_and_victory_use_temporary_animations(monkeypatch: object) -> None:
    window = make_window(monkeypatch)
    window.handle({"action": "rubber-duck", "value": "ask"})
    assert window.temporary_animation == "review"
    window.finish_temporary_animation(window.temporary_generation)
    window.handle({"action": "victory"})
    assert window.temporary_animation == "jump"
    window.close()
