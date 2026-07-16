from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QContextMenuEvent, QMouseEvent
from PySide6.QtWidgets import QApplication, QMenu

import lion_cub_pet.runtime as runtime
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
    return window


def test_stationary_art_is_fifteen_percent_smaller(monkeypatch: object) -> None:
    window = make_window(monkeypatch)
    assert window.render_factor("idle") == 0.85
    assert window.render_factor("working") == 0.85
    assert window.render_factor("walk-left") == 1.0
    window.close()


def test_size_is_clamped_to_safe_range(monkeypatch: object) -> None:
    window = make_window(monkeypatch)
    window.handle({"action": "set", "key": "scale", "value": 8.0})
    assert window.config.scale == runtime.MAX_SCALE
    window.handle({"action": "set", "key": "scale", "value": 0.1})
    assert window.config.scale == runtime.MIN_SCALE
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
