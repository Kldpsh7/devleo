from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

import lion_cub_pet.runtime as runtime
from lion_cub_pet.config import PetConfig


def test_drop_in_bottom_right_snap_zone_anchors(monkeypatch: object) -> None:
    QApplication.instance() or QApplication([])
    monkeypatch.setattr(runtime, "save_config", lambda _config: None)  # type: ignore[attr-defined]
    window = runtime.PetWindow(PetConfig(movement="roam"))
    window.animation_timer.stop()
    window.movement_timer.stop()
    area = window.work_area()
    target = window.anchor_position("bottom-right")
    target_x, target_y = target.x(), target.y()
    window.move(target_x, target_y)
    event = QMouseEvent(
        QEvent.Type.MouseButtonRelease,
        QPointF(1, 1),
        QPointF(target_x + 1, target_y + 1),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    window.dragging = True
    window.mouseReleaseEvent(event)
    assert window.config.anchor == "bottom-right"
    assert window.config.movement == "stay"
    visible = window.scaled_content_rect().translated(window.pos())
    assert visible.right() == area.right()
    assert visible.bottom() == area.bottom()
    window.close()
