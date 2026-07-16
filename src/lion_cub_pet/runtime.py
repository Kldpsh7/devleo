from __future__ import annotations

import json
import logging
import math
import random
import sys
import time
from ctypes import c_void_p
from importlib.resources import files
from pathlib import Path
from typing import Any

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer
from PySide6.QtGui import (
    QAction,
    QContextMenuEvent,
    QGuiApplication,
    QIcon,
    QMouseEvent,
    QMoveEvent,
    QPixmap,
    QResizeEvent,
)
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QLabel, QMenu, QSystemTrayIcon, QWidget

from lion_cub_pet.bubble import ThoughtBubble
from lion_cub_pet.config import PetConfig, load_config, log_path, save_config
from lion_cub_pet.dialogues import DialogueDeck
from lion_cub_pet.ipc import SERVER_NAME

CELL = QSize(192, 208)
DISPLAY_NAME = "Leo the Dev"
MIN_SCALE = 0.7
MAX_SCALE = 1.25
FRAME_COUNTS = {0: 6, 1: 8, 2: 8, 3: 4, 4: 5, 5: 8, 6: 6, 7: 6, 8: 6, 9: 8, 10: 8}
CUSTOM_FRAME_COUNTS = {"relax": 6, "focus": 6, "sleep": 6, "motivate": 4, "advice": 6}
CUSTOM_FALLBACKS = {
    "relax": "idle",
    "focus": "working",
    "sleep": "idle",
    "motivate": "wave",
    "advice": "waiting",
}
STATIONARY_ANIMATIONS = {
    "idle",
    "waiting",
    "working",
    "review",
    "relax",
    "focus",
    "sleep",
    "motivate",
    "advice",
}
ANIMATION_ROWS = {
    "idle": 0,
    "walk": 1,
    "walk-right": 1,
    "walk-left": 2,
    "wave": 3,
    "jump": 4,
    "failure": 5,
    "waiting": 6,
    "working": 7,
    "run": 7,
    "review": 8,
}


def asset_path(name: str) -> Path:
    return Path(str(files("lion_cub_pet.assets").joinpath(name)))


class PetWindow(QWidget):
    def __init__(self, config: PetConfig) -> None:
        super().__init__()
        self.config = config
        self.drag_offset: QPoint | None = None
        self.dragging = False
        self.drag_moved = False
        self.look_override: tuple[int, int] | None = None
        self.frame = 0
        self.row = 0
        self.active_animation = "idle"
        self.last_tick = time.monotonic()
        self.target: QPoint | None = None
        self.wait_until = 0.0
        self.context_menu: QMenu | None = None
        self.context_menu_open_count = 0
        self.press_position: QPoint | None = None
        self._content_rects: dict[tuple[str, int], QRect] = {}
        self.native_window_state: dict[str, Any] = {"applied": False}
        self.atlas = QPixmap(str(asset_path("spritesheet.webp")))
        self.concept = QPixmap(str(asset_path("byte-approved-concept.png")))
        self.mode_frames = self.load_mode_frames()
        self.dialogue_deck = DialogueDeck()
        self.last_spoken_at = 0.0
        self.temporary_animation: str | None = None
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if config.always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle(DISPLAY_NAME)
        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.bubble = ThoughtBubble(self)
        self.apply_size()
        self.setWindowOpacity(config.opacity)
        self.restore_position()
        self.animation_timer = QTimer(self, interval=110)
        self.animation_timer.timeout.connect(self.advance_frame)
        self.animation_timer.start()
        self.movement_timer = QTimer(self, interval=16)
        self.movement_timer.timeout.connect(self.move_tick)
        self.movement_timer.start()
        self.dialogue_timer = QTimer(self, interval=round(config.dialogue_interval * 1000))
        self.dialogue_timer.timeout.connect(self.speak_for_current_state)
        self.dialogue_timer.start()
        self.advice_timer = QTimer(self, singleShot=True)
        self.advice_timer.timeout.connect(self.trigger_advice)
        self.schedule_advice()
        self.render_frame()
        QTimer.singleShot(0, self.apply_platform_window_policy)

    def apply_size(self) -> None:
        self.config.scale = min(max(float(self.config.scale), MIN_SCALE), MAX_SCALE)
        size = QSize(
            round(CELL.width() * self.config.scale), round(CELL.height() * self.config.scale)
        )
        self.setFixedSize(size)
        self.label.setGeometry(QRect(QPoint(0, 0), size))
        self.update_label_geometry()
        if hasattr(self, "bubble"):
            self.position_bubble()

    def load_mode_frames(self) -> dict[str, list[QPixmap]]:
        loaded: dict[str, list[QPixmap]] = {}
        for mode, count in CUSTOM_FRAME_COUNTS.items():
            frames = [
                QPixmap(str(asset_path(f"modes/{mode}/{index:02}.png")))
                for index in range(count)
            ]
            if all(not frame.isNull() for frame in frames):
                loaded[mode] = frames
        return loaded

    def frame_count(self, animation: str) -> int:
        if animation.startswith("look-"):
            return 8
        if animation in CUSTOM_FRAME_COUNTS:
            return CUSTOM_FRAME_COUNTS[animation]
        return FRAME_COUNTS[ANIMATION_ROWS.get(animation, 0)]

    def source_pixmap(self, animation: str, frame: int) -> QPixmap:
        if animation.startswith("look-"):
            row = int(animation.removeprefix("look-"))
            return self.atlas.copy(
                (frame % 8) * CELL.width(),
                row * CELL.height(),
                CELL.width(),
                CELL.height(),
            )
        custom = self.mode_frames.get(animation)
        if custom:
            return custom[frame % len(custom)]
        fallback = CUSTOM_FALLBACKS.get(animation, animation)
        row = ANIMATION_ROWS.get(fallback, 0)
        return self.atlas.copy(
            (frame % FRAME_COUNTS[row]) * CELL.width(),
            row * CELL.height(),
            CELL.width(),
            CELL.height(),
        )

    def render_factor(self, animation: str | None = None) -> float:
        animation = animation or self.active_animation
        return (
            self.config.stationary_scale
            if animation in STATIONARY_ANIMATIONS or animation.startswith("look-")
            else 1.0
        )

    def work_area(self) -> QRect:
        screens = QGuiApplication.screens()
        index = min(max(self.config.screen, 0), len(screens) - 1)
        screen = screens[index]
        return (
            screen.availableGeometry() if self.config.bounds == "work-area" else screen.geometry()
        )

    def restore_position(self) -> None:
        if (
            self.config.anchor == "current"
            and self.config.x is not None
            and self.config.y is not None
        ):
            self.move(self.clamp(QPoint(self.config.x, self.config.y)))
        elif self.config.anchor != "none":
            self.apply_anchor(self.config.anchor)
        elif self.config.x is not None and self.config.y is not None:
            self.move(self.clamp(QPoint(self.config.x, self.config.y)))
        else:
            self.apply_anchor("bottom-right")

    def content_rect(self, animation: str | None = None, frame: int | None = None) -> QRect:
        animation = animation or self.active_animation
        frame = self.frame if frame is None else frame
        key = (animation, frame)
        if key in self._content_rects:
            return self._content_rects[key]
        crop = self.source_pixmap(animation, frame).toImage()
        left, top, right, bottom = CELL.width(), CELL.height(), -1, -1
        for y in range(crop.height()):
            for x in range(crop.width()):
                if crop.pixelColor(x, y).alpha() > 8:
                    left, top = min(left, x), min(top, y)
                    right, bottom = max(right, x), max(bottom, y)
        rect = (
            QRect(left, top, right - left + 1, bottom - top + 1)
            if right >= left and bottom >= top
            else QRect(QPoint(0, 0), CELL)
        )
        self._content_rects[key] = rect
        return rect

    def base_scaled_content_rect(self) -> QRect:
        rect = self.content_rect()
        factor = self.render_factor()
        target_width = round(self.width() * factor)
        target_height = round(self.height() * factor)
        offset_x = (self.width() - target_width) // 2
        offset_y = self.height() - target_height
        scale_x = target_width / CELL.width()
        scale_y = target_height / CELL.height()
        left = offset_x + round(rect.left() * scale_x)
        top = offset_y + round(rect.top() * scale_y)
        right = offset_x + round((rect.right() + 1) * scale_x) - 1
        bottom = offset_y + round((rect.bottom() + 1) * scale_y) - 1
        return QRect(left, top, right - left + 1, bottom - top + 1)

    def update_label_geometry(self) -> None:
        offset = QPoint(0, 0)
        if self.config.anchor in {"top-left", "top-right", "bottom-left", "bottom-right"}:
            content = self.base_scaled_content_rect()
            offset.setX(
                -content.left()
                if self.config.anchor.endswith("left")
                else self.width() - 1 - content.right()
            )
            offset.setY(
                -content.top()
                if self.config.anchor.startswith("top")
                else self.height() - 1 - content.bottom()
            )
        self.label.setGeometry(QRect(offset, self.size()))

    def scaled_content_rect(self) -> QRect:
        return self.base_scaled_content_rect().translated(self.label.pos())

    def position_limits(self) -> tuple[int, int, int, int]:
        area = self.work_area()
        content = self.scaled_content_rect()
        return (
            area.left() - content.left(),
            area.right() - content.right(),
            area.top() - content.top(),
            area.bottom() - content.bottom(),
        )

    def clamp(self, point: QPoint) -> QPoint:
        min_x, max_x, min_y, max_y = self.position_limits()
        return QPoint(
            min(max(point.x(), min_x), max_x),
            min(max(point.y(), min_y), max_y),
        )

    def anchor_position(self, anchor: str) -> QPoint:
        min_x, max_x, min_y, max_y = self.position_limits()
        positions = {
            "top-left": QPoint(min_x, min_y),
            "top-right": QPoint(max_x, min_y),
            "bottom-left": QPoint(min_x, max_y),
            "bottom-right": QPoint(max_x, max_y),
        }
        return positions[anchor]

    def apply_anchor(self, anchor: str) -> None:
        if anchor in {"top-left", "top-right", "bottom-left", "bottom-right"}:
            self.target = None
            self.config.anchor = anchor
            self.config.movement = "stay"
            self.update_label_geometry()
            self.move(self.anchor_position(anchor))
            self.persist_position()

    def persist_position(self) -> None:
        self.config.x, self.config.y = self.x(), self.y()
        save_config(self.config)

    def current_animation(self) -> str:
        if self.temporary_animation is not None:
            return self.temporary_animation
        if self.config.mode != "normal":
            return self.config.mode
        if self.config.animation != "auto":
            return self.config.animation
        if self.config.movement == "roam" and self.target is not None:
            return "walk-right" if self.target.x() >= self.x() else "walk-left"
        return "idle"

    def advance_frame(self) -> None:
        if self.config.paused:
            return
        if self.look_override is not None:
            self.row, self.frame = self.look_override
            self.active_animation = f"look-{self.row}"
            self.render_frame()
            return
        animation = self.current_animation()
        if animation != self.active_animation:
            self.active_animation = animation
            self.frame = 0
            self.on_animation_changed(animation)
        else:
            self.frame = (self.frame + 1) % self.frame_count(animation)
        self.row = ANIMATION_ROWS.get(CUSTOM_FALLBACKS.get(animation, animation), -1)
        self.render_frame()
        if self.config.anchor in {"top-left", "top-right", "bottom-left", "bottom-right"}:
            self.move(self.anchor_position(self.config.anchor))

    def render_frame(self) -> None:
        source = self.source_pixmap(self.active_animation, self.frame)
        if not source.isNull():
            factor = self.render_factor()
            target = QSize(round(self.width() * factor), round(self.height() * factor))
            pixmap = source.scaled(
                target,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        else:
            pixmap = self.concept.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        self.label.setPixmap(pixmap)
        self.update_label_geometry()
        self.position_bubble()

    def on_animation_changed(self, animation: str) -> None:
        category = CUSTOM_FALLBACKS.get(animation, animation)
        if animation in CUSTOM_FRAME_COUNTS:
            category = animation
        talking_states = {
            "working",
            "waiting",
            "review",
            "failure",
            "relax",
            "focus",
            "sleep",
            "motivate",
        }
        if category in talking_states:
            self.speak(category)

    def dialogue_category(self) -> str:
        animation = self.current_animation()
        if animation in {"walk", "walk-right", "walk-left"}:
            return "departing"
        return CUSTOM_FALLBACKS.get(animation, animation)

    def speak(self, category: str, duration_ms: int = 4300, force: bool = False) -> bool:
        if not self.config.dialogues:
            return False
        if not force and time.monotonic() - self.last_spoken_at < 10.0:
            return False
        self.position_bubble()
        shown = self.bubble.show_message(self.dialogue_deck.next(category), duration_ms)
        if shown:
            self.last_spoken_at = time.monotonic()
        return shown

    def speak_for_current_state(self) -> None:
        if not self.config.paused:
            self.speak(self.dialogue_category())

    def schedule_advice(self) -> None:
        low = max(30.0, float(self.config.advice_min_interval))
        high = max(low, float(self.config.advice_max_interval))
        self.advice_timer.start(round(random.uniform(low, high) * 1000))

    def trigger_advice(self) -> None:
        if self.config.advice and self.config.mode not in {"sleep", "focus"}:
            self.temporary_animation = "advice"
            self.look_override = None
            self.target = None
            self.active_animation = "advice"
            self.frame = 0
            self.render_frame()
            self.speak("advice", 6000, force=True)
            QTimer.singleShot(6500, self.finish_advice)
        self.schedule_advice()

    def finish_advice(self) -> None:
        if self.temporary_animation == "advice":
            self.temporary_animation = None
            self.active_animation = self.current_animation()
            self.frame = 0
            self.render_frame()

    def position_bubble(self) -> None:
        if not hasattr(self, "bubble"):
            return
        pet_rect = QRect(self.mapToGlobal(QPoint(0, 0)), self.size())
        self.bubble.place_near(pet_rect, self.work_area())

    def moveEvent(self, event: QMoveEvent) -> None:  # noqa: N802
        super().moveEvent(event)
        self.position_bubble()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.position_bubble()

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:  # noqa: N802
        if self.context_menu is not None:
            if not self.context_menu.isVisible():
                self.show_context_menu(event.globalPos())
            event.accept()
            return
        super().contextMenuEvent(event)

    def show_context_menu(self, global_pos: QPoint) -> None:
        if self.context_menu is None:
            return
        self.context_menu_open_count += 1
        self.context_menu.popup(global_pos)

    def choose_target(self) -> None:
        min_x, max_x, min_y, max_y = self.position_limits()
        self.target = QPoint(
            random.randint(min_x, max_x),
            random.randint(min_y, max_y),
        )
        if random.random() < 0.55:
            self.speak("departing")

    def move_tick(self) -> None:
        now = time.monotonic()
        dt, self.last_tick = min(now - self.last_tick, 0.1), now
        if (
            self.config.paused
            or self.config.movement != "roam"
            or self.config.mode != "normal"
            or self.temporary_animation is not None
            or self.dragging
        ):
            return
        if self.target is None:
            if now >= self.wait_until:
                self.choose_target()
            return
        dx, dy = self.target.x() - self.x(), self.target.y() - self.y()
        distance = math.hypot(dx, dy)
        if distance < 4:
            self.move(self.target)
            self.target = None
            self.wait_until = now + self.config.idle_delay
            self.persist_position()
            return
        step = min(distance, self.config.speed * dt)
        self.move(
            self.clamp(
                QPoint(
                    round(self.x() + dx / distance * step), round(self.y() + dy / distance * step)
                )
            )
        )

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.RightButton and self.context_menu is not None:
            self.show_context_menu(event.globalPosition().toPoint())
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self.drag_moved = False
            self.target = None
            self.press_position = event.globalPosition().toPoint()
            self.drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self.dragging and self.drag_offset is not None:
            if self.press_position is not None:
                delta = event.globalPosition().toPoint() - self.press_position
                distance = delta.manhattanLength()
                self.drag_moved = self.drag_moved or distance >= 5
            if not self.drag_moved:
                return
            self.move(self.clamp(event.globalPosition().toPoint() - self.drag_offset))
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self.dragging = False
        if not self.drag_moved:
            self.speak("clicked", force=True)
            event.accept()
            return
        bottom_right = self.anchor_position("bottom-right")
        if (self.pos() - bottom_right).manhattanLength() <= self.config.snap_distance * 2:
            self.apply_anchor("bottom-right")
        else:
            self.config.anchor = "none"
            self.config.movement = "stay"
            self.update_label_geometry()
            self.move(self.clamp(self.pos()))
            self.persist_position()
        event.accept()

    def handle(self, command: dict[str, Any]) -> dict[str, Any]:
        action = str(command.get("action", "status"))
        value = command.get("value")
        if action == "show":
            self.config.visible = True
            self.show()
        elif action == "hide":
            self.config.visible = False
            self.hide()
        elif action == "toggle":
            self.config.visible = not self.isVisible()
            self.setVisible(self.config.visible)
        elif action in {"pause", "resume"}:
            self.config.paused = action == "pause"
        elif action in {"roam", "stay"}:
            self.config.movement = action
            self.config.mode = "normal"
            self.config.anchor = "none"
            self.update_label_geometry()
            self.target = None
        elif action == "mode":
            mode = str(value)
            if mode not in {"normal", *CUSTOM_FRAME_COUNTS} - {"advice"}:
                raise ValueError(f"unknown mode: {mode}")
            self.config.mode = mode
            self.temporary_animation = None
            self.look_override = None
            self.target = None
            self.active_animation = "idle" if mode == "normal" else mode
            self.frame = 0
            self.render_frame()
            if mode != "normal":
                self.speak(mode, force=True)
        elif action == "say":
            if not isinstance(value, str) or not value.strip():
                raise ValueError("say requires text")
            self.position_bubble()
            self.bubble.show_message(value.strip(), 5000)
        elif action == "advice-now":
            self.trigger_advice()
        elif action == "anchor":
            if value == "current":
                self.config.anchor = "current"
                self.config.movement = "stay"
                self.persist_position()
            else:
                self.apply_anchor(str(value))
        elif action == "unanchor":
            self.config.anchor = "none"
            self.update_label_geometry()
        elif action == "move":
            if not isinstance(value, list) or len(value) != 2:
                raise ValueError("move requires [x, y]")
            self.config.anchor = "none"
            self.config.movement = "stay"
            self.update_label_geometry()
            self.move(self.clamp(QPoint(int(value[0]), int(value[1]))))
        elif action == "screen":
            if value is None:
                raise ValueError("screen requires an index or next")
            screens = QGuiApplication.screens()
            self.config.screen = (
                (self.config.screen + 1) % len(screens) if value == "next" else int(value)
            )
            self.restore_position()
        elif action == "set":
            key = str(command["key"])
            if value is None:
                raise ValueError(f"{key} requires a value")
            setattr(self.config, key, value)
            if command["key"] == "scale":
                self.config.scale = min(max(float(value), MIN_SCALE), MAX_SCALE)
                self.apply_size()
                self.restore_position()
            elif command["key"] == "opacity":
                self.setWindowOpacity(float(value))
            elif command["key"] == "bounds":
                self.restore_position()
            elif command["key"] == "dialogues" and not bool(value):
                self.bubble.hide()
            elif command["key"] == "dialogue_interval":
                self.dialogue_timer.setInterval(round(max(8.0, float(value)) * 1000))
            elif command["key"] == "click_through":
                self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, bool(value))
            elif command["key"] == "always_on_top":
                self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, bool(value))
                self.show()
                QTimer.singleShot(0, self.apply_platform_window_policy)
            elif command["key"] == "laptop":
                self.config.animation = {
                    "auto": "auto",
                    "closed": "idle",
                    "half-open": "waiting",
                    "open": "working",
                }[str(value)]
        elif action == "play":
            self.config.mode = "normal"
            self.config.animation = str(value)
            self.look_override = None
            self.frame = 0
            ttl = command.get("ttl")
            if ttl:
                QTimer.singleShot(
                    int(ttl) * 1000,
                    lambda: self.handle({"action": "play", "value": "auto"}),
                )
        elif action == "look":
            if value is None:
                raise ValueError("look requires degrees")
            degree = float(value) % 360
            self.row = 9 if degree < 180 else 10
            self.frame = round((degree % 180) / 22.5) % 8
            self.look_override = (self.row, self.frame)
            self.active_animation = f"look-{self.row}"
            self.render_frame()
        elif action == "demo":
            self.look_override = None
            sequence = ["idle", "wave", "jump", "waiting", "working", "review", "failure", "auto"]
            for index, animation in enumerate(sequence):
                QTimer.singleShot(
                    index * 1800,
                    lambda name=animation: self.handle({"action": "play", "value": name}),
                )
        elif action == "quit":
            QTimer.singleShot(0, QApplication.quit)
        self.persist_position()
        content = self.scaled_content_rect()
        area = self.work_area()
        app = QApplication.instance()
        assert isinstance(app, QApplication)
        return {
            "ok": True,
            "action": action,
            "config": self.config.__dict__
            if hasattr(self.config, "__dict__")
            else {slot: getattr(self.config, slot) for slot in self.config.__slots__},
            "runtime": {
                "window": [self.x(), self.y(), self.width(), self.height()],
                "visible_content": [
                    self.x() + content.left(),
                    self.y() + content.top(),
                    content.width(),
                    content.height(),
                ],
                "screen_bounds": [area.x(), area.y(), area.width(), area.height()],
                "native_window": self.native_window_state,
                "animation": self.current_animation(),
                "row": self.row,
                "frame": self.frame,
                "application_icon": {
                    "qt": not app.windowIcon().isNull(),
                    "native": bool(app.property("nativeApplicationIconApplied")),
                },
                "mode_assets": sorted(self.mode_frames),
                "dialogue_visible": self.bubble.isVisible(),
                "dialogue_text": self.bubble.label.text() if self.bubble.isVisible() else None,
                "context_menu_open_count": self.context_menu_open_count,
            },
        }

    def apply_platform_window_policy(self) -> None:
        if sys.platform != "darwin":
            self.native_window_state = {"applied": True, "platform": sys.platform}
            return
        try:
            import AppKit  # type: ignore[import-not-found]
            import objc  # type: ignore[import-not-found]

            view = objc.objc_object(c_void_p=c_void_p(int(self.winId())))
            window = view.window()
            if window is None:
                raise RuntimeError("Qt native window is not available")
            level = AppKit.NSFloatingWindowLevel if self.config.always_on_top else 0
            behavior = (
                AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces
                | AppKit.NSWindowCollectionBehaviorFullScreenAuxiliary
            )
            window.setLevel_(level)
            window.setCollectionBehavior_(behavior)
            window.setHidesOnDeactivate_(False)
            self.native_window_state = {
                "applied": True,
                "platform": "darwin",
                "level": int(window.level()),
                "all_spaces": True,
                "full_screen_auxiliary": True,
            }
        except Exception as error:  # noqa: BLE001
            logging.exception("failed to apply native macOS window policy")
            self.native_window_state = {
                "applied": False,
                "platform": "darwin",
                "error": str(error),
            }


class PetApplication(QApplication):
    def __init__(self, argv: list[str]) -> None:
        super().__init__(argv)
        self.setQuitOnLastWindowClosed(False)
        self.setApplicationName(DISPLAY_NAME)
        self.setApplicationDisplayName(DISPLAY_NAME)
        self.icon_path = asset_path("byte-approved-concept.png")
        self.setWindowIcon(QIcon(str(self.icon_path)))
        self.setProperty("nativeApplicationIconApplied", self.apply_platform_application_icon())
        self.config = load_config()
        self.window = PetWindow(self.config)
        self.menu = self.create_menu()
        self.window.context_menu = self.menu
        self.server = QLocalServer(self)
        if not self.server.listen(SERVER_NAME):
            probe = QLocalSocket()
            probe.connectToServer(SERVER_NAME)
            if probe.waitForConnected(300):
                raise RuntimeError("lion cub pet is already running")
            QLocalServer.removeServer(SERVER_NAME)
            if not self.server.listen(SERVER_NAME):
                raise RuntimeError(self.server.errorString())
        self.server.newConnection.connect(self.accept_connection)
        self.tray = self.create_tray()
        if self.config.visible:
            self.window.show()
            QTimer.singleShot(0, self.window.apply_platform_window_policy)

    def apply_platform_application_icon(self) -> bool:
        if sys.platform != "darwin":
            return True
        try:
            import AppKit

            image = AppKit.NSImage.alloc().initWithContentsOfFile_(str(self.icon_path))
            if image is None:
                raise RuntimeError(f"could not load application icon: {self.icon_path}")
            AppKit.NSApplication.sharedApplication().setApplicationIconImage_(image)
            return True
        except Exception:  # noqa: BLE001
            logging.exception("failed to set native macOS application icon")
            return False

    def create_menu(self) -> QMenu:
        menu = QMenu(DISPLAY_NAME)

        def add_action(target: QMenu, label: str, action: str, value: Any = None) -> None:
            item = QAction(label, target)
            item.triggered.connect(
                lambda _checked=False, a=action, v=value: self.window.handle(
                    {"action": a, "value": v}
                )
            )
            target.addAction(item)

        for label, action, value in [
            ("Show", "show", None),
            ("Hide", "hide", None),
            ("Roam", "roam", None),
            ("Stay", "stay", None),
        ]:
            add_action(menu, label, action, value)

        mode_menu = menu.addMenu("Mode")
        for label, mode in [
            ("Normal", "normal"),
            ("Relax", "relax"),
            ("Focus", "focus"),
            ("Sleep", "sleep"),
            ("Motivate", "motivate"),
        ]:
            add_action(mode_menu, label, "mode", mode)

        size_menu = menu.addMenu("Size")
        for label, scale in [("Small", 0.75), ("Normal", 1.0), ("Large", 1.2)]:
            item = QAction(label, size_menu)
            item.triggered.connect(
                lambda _checked=False, value=scale: self.window.handle(
                    {"action": "set", "key": "scale", "value": value}
                )
            )
            size_menu.addAction(item)

        personality_menu = menu.addMenu("Personality")
        for label, key, enabled in [
            ("Dialogues on", "dialogues", True),
            ("Dialogues off", "dialogues", False),
            ("Advice reminders on", "advice", True),
            ("Advice reminders off", "advice", False),
        ]:
            item = QAction(label, personality_menu)
            item.triggered.connect(
                lambda _checked=False, k=key, v=enabled: self.window.handle(
                    {"action": "set", "key": k, "value": v}
                )
            )
            personality_menu.addAction(item)

        menu.addSeparator()
        add_action(menu, "Tell me something", "say", "I’m Leo. I turn coffee into code.")
        add_action(menu, "Give advice now", "advice-now")
        add_action(menu, "Anchor bottom-right", "anchor", "bottom-right")
        add_action(menu, "Pause", "pause")
        add_action(menu, "Resume", "resume")
        menu.addSeparator()
        add_action(menu, "Quit", "quit")
        return menu

    def create_tray(self) -> QSystemTrayIcon:
        tray = QSystemTrayIcon(QIcon(str(asset_path("byte-approved-concept.png"))), self)
        tray.setContextMenu(self.menu)
        tray.setToolTip(DISPLAY_NAME)
        tray.show()
        return tray

    def accept_connection(self) -> None:
        socket = self.server.nextPendingConnection()
        if socket is None or not socket.waitForReadyRead(1000):
            return
        try:
            command = json.loads(bytes(socket.readAll().data()).decode().strip())
            response = self.window.handle(command)
        except Exception as error:  # noqa: BLE001
            response = {"ok": False, "error": str(error)}
        socket.write((json.dumps(response) + "\n").encode())
        socket.flush()
        socket.waitForBytesWritten(1000)
        socket.disconnectFromServer()


def main() -> int:
    path = log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=path, level=logging.INFO)
    app = PetApplication(sys.argv)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
