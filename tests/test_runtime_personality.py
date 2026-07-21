import math

from PySide6.QtCore import QEvent, QObject, QPoint, QPointF, QRect, Qt
from PySide6.QtGui import QContextMenuEvent, QMouseEvent
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

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


class FakeScreen:
    def __init__(self, geometry: QRect, available: QRect | None = None) -> None:
        self._geometry = geometry
        self._available = available or geometry

    def geometry(self) -> QRect:
        return self._geometry

    def availableGeometry(self) -> QRect:  # noqa: N802
        return self._available


class MenuOwner(QObject):
    def __init__(self, window: runtime.PetWindow) -> None:
        super().__init__()
        self.window = window
        self.menu: QMenu | None = None


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


def test_standard_states_use_approved_atlas_with_state_specific_timing(
    monkeypatch: object,
) -> None:
    window = make_window(monkeypatch)
    expected_frames = {
        "idle": 6,
        "wave": 4,
        "jump": 5,
        "waiting": 6,
        "working": 6,
        "review": 6,
    }
    assert set(window.animation_frames) == {"walk-left", "walk-right"}
    assert window.frame_count("walk-left") == 16
    assert window.frame_count("walk-right") == 16
    assert window.animation_interval("walk-left") == 85
    assert window.animation_interval("walk-right") == 85
    for state, frame_count in expected_frames.items():
        assert window.frame_count(state) == frame_count
        assert window.animation_interval(state) > runtime.DEFAULT_FRAME_INTERVAL
    window.close()


def test_manual_stationary_animation_does_not_roam(monkeypatch: object) -> None:
    window = make_window(monkeypatch, PetConfig(movement="roam", animation="working"))
    window.target = window.pos() + QPoint(100, 0)
    before = window.pos()
    window.move_tick()
    assert window.pos() == before
    window.close()


def test_gaze_override_does_not_roam(monkeypatch: object) -> None:
    window = make_window(monkeypatch, PetConfig(movement="roam"))
    window.target = window.pos() + QPoint(100, 0)
    window.look_override = (9, 0)
    before = window.pos()
    window.move_tick()
    assert window.pos() == before
    window.close()


def test_auto_roaming_can_leave_idle(monkeypatch: object) -> None:
    window = make_window(
        monkeypatch,
        PetConfig(movement="roam", animation="auto", x=0, y=0),
    )
    window.target = None
    window.wait_until = 0.0
    window.move_tick()
    assert window.target is not None
    window.close()


def test_roaming_chooses_inward_targets_at_screen_edges(monkeypatch: object) -> None:
    window = make_window(monkeypatch, PetConfig(movement="roam", animation="auto"))
    min_x, max_x, min_y, _max_y = window.roaming_position_limits()
    monkeypatch.setattr(runtime.random, "randint", lambda low, _high: low)

    window.move(min_x, min_y)
    window.choose_target()
    assert window.target is not None
    assert window.target.x() > window.x()
    assert window.target.y() > window.y()

    _min_x, _max_x, _min_y, max_y = window.roaming_position_limits()
    window.move(max_x, max_y)
    window.choose_target()
    assert window.target is not None
    assert window.target.x() < window.x()
    assert window.target.y() < window.y()
    window.close()


def test_roaming_replans_an_unreachable_edge_target(monkeypatch: object) -> None:
    window = make_window(
        monkeypatch,
        PetConfig(movement="roam", animation="auto", x=0, y=0),
    )
    min_x, _max_x, min_y, _max_y = window.roaming_position_limits()
    window.move(min_x, min_y)
    window.target = QPoint(min_x - 100, min_y)
    monkeypatch.setattr(runtime.random, "randint", lambda low, _high: low)

    window.move_tick()

    assert window.target is not None
    assert window.target.x() > window.x()
    window.close()


def test_roaming_tilts_for_upward_and_downward_travel(monkeypatch: object) -> None:
    window = make_window(
        monkeypatch,
        PetConfig(movement="roam", animation="auto", x=0, y=0),
    )
    min_x, max_x, min_y, max_y = window.roaming_position_limits()
    window.move((min_x + max_x) // 2, (min_y + max_y) // 2)
    window.target = window.pos() + QPoint(100, -100)
    window.move_tick()
    assert -runtime.MAX_ROAM_TILT_DEGREES <= window.movement_tilt_degrees < 0

    window.target = window.pos() + QPoint(-100, -100)
    window.move_tick()
    assert 0 < window.movement_tilt_degrees <= runtime.MAX_ROAM_TILT_DEGREES

    window.target = window.pos() + QPoint(100, 100)
    window.move_tick()
    assert 0 < window.movement_tilt_degrees <= runtime.MAX_ROAM_TILT_DEGREES

    window.target = window.pos() + QPoint(-100, 100)
    window.move_tick()
    assert -runtime.MAX_ROAM_TILT_DEGREES <= window.movement_tilt_degrees < 0
    window.close()


def test_target_planner_rejects_short_and_nearly_vertical_trips(monkeypatch: object) -> None:
    screen = FakeScreen(QRect(0, 0, 800, 600))
    monkeypatch.setattr(runtime, "application_screens", lambda: [screen])
    window = make_window(
        monkeypatch,
        PetConfig(movement="roam", animation="auto", x=300, y=200),
    )
    monkeypatch.setattr(runtime.random, "randint", lambda low, high: (low + high) // 2)

    window.choose_target()

    assert window.target is not None
    dx = window.target.x() - window.x()
    dy = window.target.y() - window.y()
    distance = math.hypot(dx, dy)
    assert distance >= runtime.MIN_ROAM_TRAVEL * window.config.scale
    assert abs(dx) / distance >= runtime.MIN_HORIZONTAL_TRAVEL_RATIO
    window.close()


def test_cursor_avoidance_replans_away_from_nearby_cursor(monkeypatch: object) -> None:
    screen = FakeScreen(QRect(0, 0, 800, 600))
    monkeypatch.setattr(runtime, "application_screens", lambda: [screen])
    window = make_window(
        monkeypatch,
        PetConfig(
            movement="roam",
            animation="auto",
            avoid_cursor=True,
            x=300,
            y=200,
        ),
    )
    cursor = window.pet_center_at(window.pos())
    monkeypatch.setattr(runtime, "cursor_position", lambda: cursor)
    monkeypatch.setattr(runtime.random, "randint", lambda _low, high: high)
    monkeypatch.setattr(runtime.random, "random", lambda: 1.0)
    window.target = window.pos() + QPoint(80, 0)

    window.move_tick()

    assert window.target is not None
    assert window.distance_from_cursor(window.target, cursor) >= (
        runtime.CURSOR_AVOIDANCE_RADIUS * window.config.scale
    )
    window.close()


def test_run_chance_changes_roaming_gait_speed_and_cadence(monkeypatch: object) -> None:
    window = make_window(
        monkeypatch,
        PetConfig(movement="roam", animation="auto", run_chance=100, x=0, y=0),
    )
    monkeypatch.setattr(runtime.random, "random", lambda: 0.0)
    window.choose_target()
    assert window.roaming_run
    assert window.animation_interval("walk-right") == round(
        runtime.FRAME_INTERVALS["walk-right"] * runtime.RUN_FRAME_INTERVAL_FACTOR
    )

    window.config.run_chance = 0
    window.choose_target()
    assert not window.roaming_run
    assert window.animation_interval("walk-right") == runtime.FRAME_INTERVALS["walk-right"]
    window.close()


def test_roaming_speed_eases_at_start_and_destination(monkeypatch: object) -> None:
    window = make_window(
        monkeypatch,
        PetConfig(movement="roam", animation="auto", x=100, y=100),
    )
    window.roam_leg_start = QPointF(window.pos())
    window.target = window.pos() + QPoint(300, 0)

    start = window.roam_easing_factor(300)
    middle = window.roam_easing_factor(150)
    finish = window.roam_easing_factor(1)

    assert start == runtime.MIN_ROAM_SPEED_FACTOR
    assert middle == 1.0
    assert runtime.MIN_ROAM_SPEED_FACTOR < finish < middle
    window.close()


def test_movement_debug_overlay_and_status(monkeypatch: object) -> None:
    window = make_window(
        monkeypatch,
        PetConfig(movement="roam", animation="auto", x=100, y=100),
    )
    window.target = window.pos() + QPoint(200, 80)

    response = window.handle({"action": "set", "key": "debug_movement", "value": True})

    assert not window.debug_label.isHidden()
    assert window.debug_label.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    assert "B " in window.debug_label.text()
    assert "T " in window.debug_label.text()
    debug = response["runtime"]["movement_debug"]
    assert debug["enabled"] is True
    assert debug["target"] == [window.target.x(), window.target.y()]
    assert debug["direction"] == "down-right"

    window.handle({"action": "set", "key": "debug_movement", "value": False})
    assert window.debug_label.isHidden()
    window.close()


def test_roam_clears_manual_stationary_animation(monkeypatch: object) -> None:
    window = make_window(monkeypatch, PetConfig(movement="stay", animation="working"))
    window.handle({"action": "roam"})
    assert window.config.movement == "roam"
    assert window.config.animation == "auto"
    assert window.config.mode == "normal"
    window.close()


def test_showcase_covers_all_runtime_modes_without_changing_config(monkeypatch: object) -> None:
    window = make_window(monkeypatch, PetConfig(movement="roam", animation="auto"))
    before = (window.config.movement, window.config.animation, window.config.mode)
    window.start_showcase(0.5)
    generation = window.showcase_generation
    labels = [label for label, _kind, _value in runtime.SHOWCASE_STEPS]
    assert labels == [
        "Idle",
        "Walk right",
        "Walk left",
        "Wave",
        "Jump",
        "Failure",
        "Waiting",
        "Working",
        "Active work",
        "Review",
        "Relax",
        "Focus",
        "Sleep",
        "Motivate",
        "Advice",
        "Gaze up",
        "Gaze right",
        "Gaze down",
        "Gaze left",
    ]
    window.apply_showcase_step(generation, runtime.SHOWCASE_STEPS[7])
    assert window.current_animation() == "working"
    assert (window.config.movement, window.config.animation, window.config.mode) == before
    window.finish_showcase(generation)
    assert window.current_animation() == "idle"
    assert window.showcase_step_label is None
    window.close()


def test_motivate_returns_to_normal_only_for_current_generation(monkeypatch: object) -> None:
    window = make_window(monkeypatch)
    window.handle({"action": "mode", "value": "motivate"})
    generation = window.mode_generation
    window.finish_motivate(generation - 1)
    assert window.config.mode == "motivate"
    window.finish_motivate(generation)
    assert window.config.mode == "normal"
    assert window.animation_timer.interval() == runtime.FRAME_INTERVALS["idle"]
    window.close()


def test_size_is_clamped_to_safe_range(monkeypatch: object) -> None:
    window = make_window(monkeypatch)
    window.handle({"action": "set", "key": "scale", "value": 8.0})
    assert window.config.scale == runtime.MAX_SCALE
    window.handle({"action": "set", "key": "scale", "value": 0.1})
    assert window.config.scale == runtime.MIN_SCALE
    window.close()


def test_size_change_refreshes_roaming_edges_and_target(monkeypatch: object) -> None:
    screen = FakeScreen(QRect(0, 0, 800, 600))
    monkeypatch.setattr(runtime, "application_screens", lambda: [screen])
    window = make_window(
        monkeypatch,
        PetConfig(
            movement="roam",
            animation="auto",
            scale=runtime.MIN_SCALE,
            x=0,
            y=0,
        ),
    )
    _small_min_x, small_max_x, _small_min_y, small_max_y = window.roaming_position_limits()
    window.move(small_max_x, small_max_y)
    window.target = QPoint(small_max_x, small_max_y)

    window.handle({"action": "set", "key": "scale", "value": runtime.MAX_SCALE})

    min_x, max_x, min_y, max_y = window.roaming_position_limits()
    assert max_x < small_max_x
    assert max_y < small_max_y
    assert min_x <= window.x() <= max_x
    assert min_y <= window.y() <= max_y
    assert window.target is None
    window.close()


def test_screen_geometry_change_refreshes_roaming_edges(monkeypatch: object) -> None:
    screen = FakeScreen(QRect(0, 0, 1000, 700))
    monkeypatch.setattr(runtime, "application_screens", lambda: [screen])
    window = make_window(
        monkeypatch,
        PetConfig(movement="roam", animation="auto", x=0, y=0),
    )
    _min_x, old_max_x, _min_y, old_max_y = window.roaming_position_limits()
    window.move(old_max_x, old_max_y)
    window.target = QPoint(old_max_x, old_max_y)

    screen._geometry = QRect(0, 0, 640, 480)
    screen._available = screen._geometry
    window.screen_geometry_changed()

    min_x, max_x, min_y, max_y = window.roaming_position_limits()
    assert max_x < old_max_x
    assert max_y < old_max_y
    assert min_x <= window.x() <= max_x
    assert min_y <= window.y() <= max_y
    assert window.target is None
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


def test_anchor_from_roaming_syncs_stationary_frame_before_positioning(
    monkeypatch: object,
) -> None:
    window = make_window(
        monkeypatch,
        PetConfig(movement="roam", animation="auto", x=100, y=100),
    )
    window.target = QPoint(500, 100)
    window.active_animation = "walk-right"
    window.frame = 0
    window.render_frame()
    window.handle({"action": "anchor", "value": "top-left"})
    visible = window.scaled_content_rect().translated(window.pos())
    assert window.active_animation == "idle"
    assert visible.left() == window.work_area().left()
    assert visible.top() == window.work_area().top()
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


def test_tray_and_right_click_share_complete_menu(monkeypatch: object) -> None:
    window = make_window(monkeypatch)
    owner = MenuOwner(window)
    menu = runtime.PetApplication.create_menu(owner)  # type: ignore[arg-type]
    owner.menu = menu
    window.context_menu = menu
    monkeypatch.setattr(QSystemTrayIcon, "show", lambda _tray: None)
    tray = runtime.PetApplication.create_tray(owner)  # type: ignore[arg-type]
    assert tray.contextMenu() is menu
    labels = {action.text() for action in menu.actions()}
    assert {"Roam", "Stay", "Mode", "Size", "Transparency", "Productivity"} <= labels
    assert window.context_menu is tray.contextMenu()
    tray.hide()
    tray.deleteLater()
    window.close()


def test_screen_switch_and_corner_anchor_use_selected_monitor(monkeypatch: object) -> None:
    screens = [
        FakeScreen(QRect(0, 0, 800, 600)),
        FakeScreen(QRect(800, -100, 1000, 700), QRect(800, -80, 1000, 660)),
    ]
    monkeypatch.setattr(runtime, "application_screens", lambda: screens)
    window = make_window(
        monkeypatch,
        PetConfig(screen=1, bounds="full-screen", movement="stay"),
    )
    assert window.work_area() == QRect(800, -100, 1000, 700)
    window.apply_anchor("bottom-right")
    visible = window.scaled_content_rect().translated(window.pos())
    assert visible.right() == 1799
    assert visible.bottom() == 599
    window.handle({"action": "screen", "value": "next"})
    assert window.config.screen == 0
    assert window.work_area() == QRect(0, 0, 800, 600)
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
