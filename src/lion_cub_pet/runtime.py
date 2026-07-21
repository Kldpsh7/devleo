from __future__ import annotations

import json
import logging
import math
import random
import sys
import time
from ctypes import c_void_p
from datetime import date, datetime, timedelta
from importlib import import_module
from importlib.resources import files
from pathlib import Path
from typing import Any

from PySide6.QtCore import QPoint, QPointF, QRect, QSize, Qt, QTimer
from PySide6.QtGui import (
    QAction,
    QContextMenuEvent,
    QCursor,
    QGuiApplication,
    QIcon,
    QMouseEvent,
    QMoveEvent,
    QPainter,
    QPixmap,
    QResizeEvent,
    QScreen,
)
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QLabel, QMenu, QSystemTrayIcon, QWidget

from lion_cub_pet.bubble import ThoughtBubble
from lion_cub_pet.config import PetConfig, load_config, log_path, save_config
from lion_cub_pet.dialogues import DialogueDeck, load_dialogue_pack
from lion_cub_pet.ipc import SERVER_NAME

CELL = QSize(192, 208)
DISPLAY_NAME = "Leo the Dev"
MIN_SCALE = 0.55
MAX_SCALE = 1.25
MIN_OPACITY = 0.25
MAX_OPACITY = 1.0
FRAME_COUNTS = {0: 6, 1: 8, 2: 8, 3: 4, 4: 5, 5: 8, 6: 6, 7: 6, 8: 6, 9: 8, 10: 8}
CUSTOM_FRAME_COUNTS = {"relax": 8, "focus": 8, "sleep": 8, "motivate": 8, "advice": 8}
# The approved v2 atlas remains authoritative for stationary states. Directional
# roaming uses isolated higher-frame-count sequences to avoid atlas-slot bleed.
SMOOTH_FRAME_COUNTS = {"walk-right": 16, "walk-left": 16}
FRAME_INTERVALS = {
    "idle": 230,
    "walk": 130,
    "walk-right": 85,
    "walk-left": 85,
    "wave": 180,
    "jump": 160,
    "failure": 190,
    "waiting": 230,
    "working": 180,
    "run": 180,
    "review": 220,
    "relax": 260,
    "focus": 210,
    "sleep": 360,
    "motivate": 240,
    "advice": 280,
}
DEFAULT_FRAME_INTERVAL = 135
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
ROAMING_ANIMATIONS = {"walk", "walk-right", "walk-left"}
MAX_ROAM_TILT_DEGREES = 8.0
ROAM_EDGE_MARGIN = 4
MIN_INWARD_TRAVEL = 48
MIN_ROAM_TRAVEL = 150
MIN_HORIZONTAL_TRAVEL_RATIO = 0.25
ROAM_TARGET_ATTEMPTS = 16
CURSOR_AVOIDANCE_RADIUS = 120
RUN_SPEED_MULTIPLIER = 1.55
RUN_FRAME_INTERVAL_FACTOR = 0.72
ROAM_EASING_DISTANCE = 120
MIN_ROAM_SPEED_FACTOR = 0.3
SHOWCASE_STEPS = (
    ("Idle", "animation", "idle"),
    ("Walk right", "animation", "walk-right"),
    ("Walk left", "animation", "walk-left"),
    ("Wave", "animation", "wave"),
    ("Jump", "animation", "jump"),
    ("Failure", "animation", "failure"),
    ("Waiting", "animation", "waiting"),
    ("Working", "animation", "working"),
    ("Active work", "animation", "run"),
    ("Review", "animation", "review"),
    ("Relax", "animation", "relax"),
    ("Focus", "animation", "focus"),
    ("Sleep", "animation", "sleep"),
    ("Motivate", "animation", "motivate"),
    ("Advice", "animation", "advice"),
    ("Gaze up", "look", "0"),
    ("Gaze right", "look", "90"),
    ("Gaze down", "look", "180"),
    ("Gaze left", "look", "270"),
)
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


def application_screens() -> list[QScreen]:
    return QGuiApplication.screens()


def cursor_position() -> QPoint:
    return QCursor.pos()


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
        self.movement_tilt_degrees = 0.0
        self.roaming_run = False
        self.roam_leg_start: QPointF | None = None
        self.roam_position: QPointF | None = None
        self.roam_speed_factor = 0.0
        self.last_cursor_replan_at = 0.0
        self.wait_until = 0.0
        self.context_menu: QMenu | None = None
        self.context_menu_open_count = 0
        self.press_position: QPoint | None = None
        self._content_rects: dict[tuple[str, int], QRect] = {}
        self.native_window_state: dict[str, Any] = {"applied": False}
        self.atlas = QPixmap(str(asset_path("spritesheet.webp")))
        self.concept = QPixmap(str(asset_path("leo-approved-concept.png")))
        self.mode_frames = self.load_mode_frames()
        self.animation_frames = self.load_animation_frames()
        try:
            self.dialogue_deck = DialogueDeck(load_dialogue_pack(config.dialogue_pack))
        except (OSError, ValueError, json.JSONDecodeError):
            logging.exception("failed to load dialogue pack; using built-in lines")
            self.dialogue_deck = DialogueDeck()
            self.config.dialogue_pack = None
        self.last_spoken_at = 0.0
        self.temporary_animation: str | None = None
        self.temporary_generation = 0
        self.mode_generation = 0
        self.showcase_generation = 0
        self.showcase_animation: str | None = None
        self.showcase_step_label: str | None = None
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if config.always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle(DISPLAY_NAME)
        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.debug_label = QLabel(self)
        self.debug_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.debug_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.debug_label.setStyleSheet(
            "background: rgba(0, 0, 0, 180); color: #8fffa0; padding: 3px; font: 9px monospace;"
        )
        self.debug_label.setWordWrap(False)
        self.debug_label.setVisible(False)
        self.bubble = ThoughtBubble(self)
        self.apply_size()
        self.config.opacity = min(max(float(config.opacity), MIN_OPACITY), MAX_OPACITY)
        self.setWindowOpacity(self.config.opacity)
        self.restore_position()
        self.animation_timer = QTimer(self, interval=self.animation_interval("idle"))
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
        self.pomodoro_timer = QTimer(self, singleShot=True)
        self.pomodoro_timer.timeout.connect(self.advance_pomodoro)
        self.rubber_duck_timer = QTimer(self, singleShot=True)
        self.rubber_duck_timer.timeout.connect(self.trigger_rubber_duck)
        if self.config.rubber_duck_enabled:
            self.schedule_rubber_duck()
        self.render_frame()
        if self.config.pomodoro_enabled:
            QTimer.singleShot(0, self.resume_pomodoro)
        QTimer.singleShot(0, self.apply_platform_window_policy)

    def apply_size(self) -> None:
        self.config.scale = min(max(float(self.config.scale), MIN_SCALE), MAX_SCALE)
        size = QSize(
            round(CELL.width() * self.config.scale), round(CELL.height() * self.config.scale)
        )
        self.setFixedSize(size)
        self.label.setGeometry(QRect(QPoint(0, 0), size))
        self.debug_label.setGeometry(2, 2, max(1, size.width() - 4), min(76, size.height() - 4))
        self.update_label_geometry()
        if hasattr(self, "bubble"):
            self.position_bubble()

    def load_mode_frames(self) -> dict[str, list[QPixmap]]:
        loaded: dict[str, list[QPixmap]] = {}
        for mode, count in CUSTOM_FRAME_COUNTS.items():
            frames = [
                QPixmap(str(asset_path(f"modes/{mode}/{index:02}.png"))) for index in range(count)
            ]
            if all(not frame.isNull() for frame in frames):
                loaded[mode] = frames
        return loaded

    def load_animation_frames(self) -> dict[str, list[QPixmap]]:
        loaded: dict[str, list[QPixmap]] = {}
        for animation, count in SMOOTH_FRAME_COUNTS.items():
            frames = [
                QPixmap(str(asset_path(f"animations/{animation}/{index:02}.png")))
                for index in range(count)
            ]
            if all(not frame.isNull() for frame in frames):
                loaded[animation] = frames
        return loaded

    def frame_count(self, animation: str) -> int:
        if animation.startswith("look-"):
            return 8
        if animation in self.animation_frames:
            return len(self.animation_frames[animation])
        if animation in CUSTOM_FRAME_COUNTS:
            return CUSTOM_FRAME_COUNTS[animation]
        return FRAME_COUNTS[ANIMATION_ROWS.get(animation, 0)]

    def animation_interval(self, animation: str | None = None) -> int:
        name = animation or self.active_animation
        if name.startswith("look-"):
            return 200
        interval = FRAME_INTERVALS.get(name, DEFAULT_FRAME_INTERVAL)
        if name in ROAMING_ANIMATIONS and self.roaming_run:
            return round(interval * RUN_FRAME_INTERVAL_FACTOR)
        return interval

    def source_pixmap(self, animation: str, frame: int) -> QPixmap:
        if animation.startswith("look-"):
            row = int(animation.removeprefix("look-"))
            return self.atlas.copy(
                (frame % 8) * CELL.width(),
                row * CELL.height(),
                CELL.width(),
                CELL.height(),
            )
        smooth = self.animation_frames.get(animation)
        if smooth:
            return smooth[frame % len(smooth)]
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
        screens = application_screens()
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

    def base_scaled_content_rect(
        self, animation: str | None = None, frame: int | None = None
    ) -> QRect:
        animation = animation or self.active_animation
        rect = self.content_rect(animation, frame)
        factor = self.render_factor(animation)
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

    def roaming_position_limits(self) -> tuple[int, int, int, int]:
        """Return a stable envelope that fits every directional roaming frame."""
        area = self.work_area()
        rects = [
            self.base_scaled_content_rect(animation, frame)
            for animation in ("walk-right", "walk-left")
            for frame in range(self.frame_count(animation))
        ]
        return (
            max(area.left() - rect.left() for rect in rects),
            min(area.right() - rect.right() for rect in rects),
            max(area.top() - rect.top() for rect in rects),
            min(area.bottom() - rect.bottom() for rect in rects),
        )

    @staticmethod
    def clamp_to_limits(point: QPoint, limits: tuple[int, int, int, int]) -> QPoint:
        min_x, max_x, min_y, max_y = limits
        return QPoint(
            min(max(point.x(), min_x), max_x),
            min(max(point.y(), min_y), max_y),
        )

    def clamp(self, point: QPoint) -> QPoint:
        min_x, max_x, min_y, max_y = self.position_limits()
        return QPoint(
            min(max(point.x(), min_x), max_x),
            min(max(point.y(), min_y), max_y),
        )

    def refresh_position_limits(self) -> None:
        """Reapply the active placement contract after geometry changes."""
        self.update_label_geometry()
        if self.config.anchor in {"top-left", "top-right", "bottom-left", "bottom-right"}:
            self.move(self.anchor_position(self.config.anchor))
        elif self.config.movement == "roam":
            limits = self.roaming_position_limits()
            self.move(self.clamp_to_limits(self.pos(), limits))
            self.reset_roam_motion()
            if self.target is not None and self.clamp_to_limits(self.target, limits) != self.target:
                self.target = None
                self.movement_tilt_degrees = 0.0
        else:
            self.move(self.clamp(self.pos()))
        self.position_bubble()
        self.update_movement_debug()

    def screen_geometry_changed(self, *_args: object) -> None:
        screens = application_screens()
        if not screens:
            return
        self.config.screen = min(max(self.config.screen, 0), len(screens) - 1)
        self.refresh_position_limits()
        self.persist_position()

    def reset_roam_motion(self) -> None:
        self.roam_position = QPointF(self.pos())
        self.roam_leg_start = QPointF(self.pos())
        self.roam_speed_factor = 0.0

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
            self.sync_current_animation()
            self.update_label_geometry()
            self.move(self.anchor_position(anchor))
            self.persist_position()

    def persist_position(self) -> None:
        self.config.x, self.config.y = self.x(), self.y()
        save_config(self.config)

    def current_animation(self) -> str:
        if self.showcase_animation is not None:
            return self.showcase_animation
        if self.temporary_animation is not None:
            return self.temporary_animation
        if self.config.mode != "normal":
            return self.config.mode
        if self.config.animation != "auto":
            return self.config.animation
        if self.config.movement == "roam" and self.target is not None:
            return "walk-right" if self.target.x() >= self.x() else "walk-left"
        return "idle"

    def sync_current_animation(self) -> None:
        if self.look_override is not None:
            self.row, self.frame = self.look_override
            animation = f"look-{self.row}"
        else:
            animation = self.current_animation()
            self.frame = 0
            self.row = ANIMATION_ROWS.get(CUSTOM_FALLBACKS.get(animation, animation), -1)
        self.active_animation = animation
        if hasattr(self, "animation_timer"):
            self.animation_timer.setInterval(self.animation_interval(animation))
        self.render_frame()

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
            self.animation_timer.setInterval(self.animation_interval(animation))
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
            if (
                self.active_animation in ROAMING_ANIMATIONS
                and abs(self.movement_tilt_degrees) > 0.05
            ):
                tilted = QPixmap(pixmap.size())
                tilted.fill(Qt.GlobalColor.transparent)
                painter = QPainter(tilted)
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                painter.translate(pixmap.width() / 2, pixmap.height() / 2)
                painter.rotate(self.movement_tilt_degrees)
                painter.translate(-pixmap.width() / 2, -pixmap.height() / 2)
                painter.drawPixmap(0, 0, pixmap)
                painter.end()
                pixmap = tilted
        else:
            pixmap = self.concept.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        self.label.setPixmap(pixmap)
        self.update_label_geometry()
        self.position_bubble()
        self.update_movement_debug()

    def movement_debug_state(self) -> dict[str, Any]:
        limits = list(self.roaming_position_limits()) if self.config.debug_movement else None
        target = self.target
        dx = target.x() - self.x() if target is not None else 0
        dy = target.y() - self.y() if target is not None else 0
        vertical = "up" if dy < 0 else "down" if dy > 0 else ""
        horizontal = "left" if dx < 0 else "right" if dx > 0 else ""
        direction = "-".join(part for part in (vertical, horizontal) if part) or "idle"
        return {
            "enabled": self.config.debug_movement,
            "bounds": limits,
            "target": [target.x(), target.y()] if target is not None else None,
            "vector": [dx, dy],
            "direction": direction,
            "tilt_degrees": round(self.movement_tilt_degrees, 2),
            "gait": "run" if self.roaming_run else "walk",
            "speed_factor": round(self.roam_speed_factor, 3),
            "cursor_avoidance": self.config.avoid_cursor,
        }

    def update_movement_debug(self) -> None:
        if not self.config.debug_movement:
            self.debug_label.hide()
            return
        state = self.movement_debug_state()
        bounds = state["bounds"]
        target = state["target"] or ["-", "-"]
        vector = state["vector"]
        self.debug_label.setText(
            f"B {bounds[0]},{bounds[2]}..{bounds[1]},{bounds[3]}\n"
            f"T {target[0]},{target[1]}  {state['direction']} {vector[0]},{vector[1]}\n"
            f"{state['gait']} x{state['speed_factor']:.2f}  tilt {state['tilt_degrees']:+.1f}°"
        )
        self.debug_label.show()
        self.debug_label.raise_()

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

    @staticmethod
    def clock_minutes(value: str) -> int:
        try:
            parsed = datetime.strptime(value, "%H:%M")
        except ValueError as error:
            raise ValueError(f"invalid time {value!r}; expected HH:MM") from error
        return parsed.hour * 60 + parsed.minute

    def quiet_hours_active(self) -> bool:
        if self.config.quiet_hours_enabled:
            return True
        if not self.config.quiet_schedule_enabled:
            return False
        start = self.clock_minutes(self.config.quiet_hours_start)
        end = self.clock_minutes(self.config.quiet_hours_end)
        now = datetime.now().hour * 60 + datetime.now().minute
        if start == end:
            return True
        return start <= now < end if start < end else now >= start or now < end

    def speak(self, category: str, duration_ms: int = 4300, force: bool = False) -> bool:
        if not self.config.dialogues or self.quiet_hours_active():
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

    def set_mode(self, mode: str, *, speak: bool = True) -> None:
        if mode not in {"normal", *CUSTOM_FRAME_COUNTS} - {"advice"}:
            raise ValueError(f"unknown mode: {mode}")
        self.config.mode = mode
        self.mode_generation += 1
        self.temporary_generation += 1
        self.temporary_animation = None
        self.look_override = None
        self.target = None
        self.active_animation = "idle" if mode == "normal" else mode
        self.animation_timer.setInterval(self.animation_interval(self.active_animation))
        self.frame = 0
        self.render_frame()
        if mode != "normal" and speak:
            self.speak(mode, force=True)
        if mode == "motivate":
            generation = self.mode_generation
            QTimer.singleShot(
                round(random.uniform(5.0, 8.0) * 1000),
                lambda: self.finish_motivate(generation),
            )

    def start_temporary_animation(
        self,
        animation: str,
        duration_ms: int,
        category: str | None = None,
    ) -> int:
        self.temporary_generation += 1
        generation = self.temporary_generation
        self.temporary_animation = animation
        self.look_override = None
        self.target = None
        self.active_animation = animation
        self.animation_timer.setInterval(self.animation_interval(animation))
        self.frame = 0
        self.render_frame()
        if category is not None:
            self.speak(category, min(duration_ms, 6000), force=True)
        QTimer.singleShot(duration_ms, lambda: self.finish_temporary_animation(generation))
        return generation

    def set_temporary_phase(self, generation: int, animation: str) -> None:
        if generation != self.temporary_generation or self.temporary_animation is None:
            return
        self.temporary_animation = animation
        self.active_animation = animation
        self.animation_timer.setInterval(self.animation_interval(animation))
        self.frame = 0
        self.render_frame()

    def finish_temporary_animation(self, generation: int) -> None:
        if generation != self.temporary_generation:
            return
        self.temporary_animation = None
        self.active_animation = self.current_animation()
        self.animation_timer.setInterval(self.animation_interval(self.active_animation))
        self.frame = 0
        self.render_frame()

    def trigger_advice(self) -> None:
        if self.config.advice and self.config.mode not in {"sleep", "focus"}:
            self.start_temporary_animation("advice", 6500, "advice")
        self.schedule_advice()

    def finish_advice(self) -> None:
        if self.temporary_animation == "advice":
            self.finish_temporary_animation(self.temporary_generation)

    def resume_pomodoro(self) -> None:
        phase = self.config.pomodoro_phase
        if phase not in {"focus", "break"}:
            phase = "focus"
            self.config.pomodoro_phase = phase
        self.set_mode("focus" if phase == "focus" else "relax", speak=False)
        self.speak(f"pomodoro_{phase}", force=True)
        minutes = (
            self.config.pomodoro_focus_minutes
            if phase == "focus"
            else self.config.pomodoro_break_minutes
        )
        self.pomodoro_timer.start(round(max(0.05, float(minutes)) * 60_000))

    def advance_pomodoro(self) -> None:
        if not self.config.pomodoro_enabled:
            return
        self.config.pomodoro_phase = "break" if self.config.pomodoro_phase == "focus" else "focus"
        self.resume_pomodoro()
        self.persist_position()

    def schedule_rubber_duck(self) -> None:
        low = max(60.0, float(self.config.rubber_duck_min_interval))
        high = max(low, float(self.config.rubber_duck_max_interval))
        self.rubber_duck_timer.start(round(random.uniform(low, high) * 1000))

    def trigger_rubber_duck(self, *, manual: bool = False) -> None:
        if (manual or self.config.rubber_duck_enabled) and self.config.mode not in {
            "sleep",
            "focus",
        }:
            self.start_temporary_animation("review", 6500, "rubber_duck")
        if self.config.rubber_duck_enabled:
            self.schedule_rubber_duck()

    def record_interaction(self, mood_delta: int) -> None:
        today = date.today()
        previous: date | None = None
        if self.config.last_interaction_date:
            try:
                previous = date.fromisoformat(self.config.last_interaction_date)
            except ValueError:
                previous = None
        if previous != today:
            self.config.interaction_streak = (
                self.config.interaction_streak + 1 if previous == today - timedelta(days=1) else 1
            )
            self.config.last_interaction_date = today.isoformat()
        self.config.mood = min(100, max(0, int(self.config.mood) + mood_delta))

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

    def pet_center_at(self, point: QPoint) -> QPoint:
        return point + QPoint(self.width() // 2, self.height() // 2)

    def distance_from_cursor(self, point: QPoint, cursor: QPoint) -> float:
        center = self.pet_center_at(point)
        return math.hypot(center.x() - cursor.x(), center.y() - cursor.y())

    def cursor_is_close(self) -> bool:
        if not self.config.avoid_cursor:
            return False
        radius = CURSOR_AVOIDANCE_RADIUS * self.config.scale
        return self.distance_from_cursor(self.pos(), cursor_position()) < radius

    def roam_easing_factor(self, remaining: float) -> float:
        if self.roam_leg_start is None or self.target is None:
            return MIN_ROAM_SPEED_FACTOR
        total = math.hypot(
            self.target.x() - self.roam_leg_start.x(),
            self.target.y() - self.roam_leg_start.y(),
        )
        if total <= 0:
            return MIN_ROAM_SPEED_FACTOR
        travelled = max(0.0, total - remaining)
        ramp_distance = min(ROAM_EASING_DISTANCE * self.config.scale, total / 2)
        if ramp_distance <= 0:
            return MIN_ROAM_SPEED_FACTOR
        progress = min(1.0, travelled / ramp_distance, remaining / ramp_distance)
        smooth = progress * progress * (3 - 2 * progress)
        return MIN_ROAM_SPEED_FACTOR + (1 - MIN_ROAM_SPEED_FACTOR) * smooth

    def choose_target(self) -> None:
        min_x, max_x, min_y, max_y = self.roaming_position_limits()

        def choose_axis(current: int, minimum: int, maximum: int) -> int:
            minimum_travel = min(round(MIN_INWARD_TRAVEL * self.config.scale), maximum - minimum)
            if current <= minimum + ROAM_EDGE_MARGIN:
                return random.randint(min(maximum, current + minimum_travel), maximum)
            if current >= maximum - ROAM_EDGE_MARGIN:
                return random.randint(minimum, max(minimum, current - minimum_travel))
            return random.randint(minimum, maximum)

        def points_inward(candidate: QPoint) -> bool:
            if self.x() <= min_x + ROAM_EDGE_MARGIN and candidate.x() <= self.x():
                return False
            if self.x() >= max_x - ROAM_EDGE_MARGIN and candidate.x() >= self.x():
                return False
            if self.y() <= min_y + ROAM_EDGE_MARGIN and candidate.y() <= self.y():
                return False
            return not (self.y() >= max_y - ROAM_EDGE_MARGIN and candidate.y() >= self.y())

        cursor = cursor_position() if self.config.avoid_cursor else None
        minimum_distance = MIN_ROAM_TRAVEL * self.config.scale
        cursor_radius = CURSOR_AVOIDANCE_RADIUS * self.config.scale
        candidates = [
            QPoint(
                choose_axis(self.x(), min_x, max_x),
                choose_axis(self.y(), min_y, max_y),
            )
            for _ in range(ROAM_TARGET_ATTEMPTS)
        ]

        def is_good(candidate: QPoint) -> bool:
            dx, dy = candidate.x() - self.x(), candidate.y() - self.y()
            distance = math.hypot(dx, dy)
            return (
                points_inward(candidate)
                and distance >= minimum_distance
                and abs(dx) / max(distance, 1.0) >= MIN_HORIZONTAL_TRAVEL_RATIO
                and (
                    cursor is None or self.distance_from_cursor(candidate, cursor) >= cursor_radius
                )
            )

        good = [candidate for candidate in candidates if is_good(candidate)]
        if good:
            self.target = (
                max(good, key=lambda point: self.distance_from_cursor(point, cursor))
                if cursor is not None
                else good[0]
            )
        else:
            corners = [
                QPoint(x, y)
                for x in (min_x, max_x)
                for y in (min_y, max_y)
                if points_inward(QPoint(x, y))
            ]
            fallback = corners or candidates

            def fallback_score(point: QPoint) -> float:
                dx, dy = point.x() - self.x(), point.y() - self.y()
                distance = math.hypot(dx, dy)
                horizontal = abs(dx) / max(distance, 1.0)
                cursor_clearance = (
                    self.distance_from_cursor(point, cursor) if cursor is not None else 0.0
                )
                return distance + minimum_distance * horizontal + cursor_clearance

            self.target = max(fallback, key=fallback_score)

        chance = min(max(int(self.config.run_chance), 0), 100) / 100
        self.roaming_run = random.random() < chance
        self.reset_roam_motion()
        if hasattr(self, "animation_timer"):
            self.animation_timer.setInterval(self.animation_interval(self.current_animation()))
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
            or self.showcase_animation is not None
            or self.look_override is not None
            or (
                self.config.animation != "auto"
                and self.current_animation() not in ROAMING_ANIMATIONS
            )
            or self.dragging
        ):
            return
        if self.target is None:
            self.movement_tilt_degrees = 0.0
            self.roaming_run = False
            self.roam_speed_factor = 0.0
            if now >= self.wait_until:
                self.choose_target()
            self.update_movement_debug()
            return
        roaming_limits = self.roaming_position_limits()
        if self.clamp_to_limits(self.target, roaming_limits) != self.target:
            self.choose_target()
            if self.target is None:
                return
        if now - self.last_cursor_replan_at >= 0.5 and self.cursor_is_close():
            self.choose_target()
            self.last_cursor_replan_at = now
            if self.target is None:
                return
        dx, dy = self.target.x() - self.x(), self.target.y() - self.y()
        distance = math.hypot(dx, dy)
        if distance < 4:
            self.move(self.target)
            self.target = None
            self.movement_tilt_degrees = 0.0
            self.roaming_run = False
            self.roam_speed_factor = 0.0
            self.roam_position = None
            self.roam_leg_start = None
            self.wait_until = now + self.config.idle_delay
            self.persist_position()
            self.update_movement_debug()
            return
        facing = 1.0 if dx >= 0 else -1.0
        self.movement_tilt_degrees = MAX_ROAM_TILT_DEGREES * dy / distance * facing
        self.roam_speed_factor = self.roam_easing_factor(distance)
        gait_multiplier = RUN_SPEED_MULTIPLIER if self.roaming_run else 1.0
        step = min(distance, self.config.speed * gait_multiplier * self.roam_speed_factor * dt)
        if self.roam_position is None:
            self.roam_position = QPointF(self.pos())
        next_position = QPointF(
            self.roam_position.x() + dx / distance * step,
            self.roam_position.y() + dy / distance * step,
        )
        rounded = QPoint(round(next_position.x()), round(next_position.y()))
        bounded = self.clamp_to_limits(rounded, roaming_limits)
        self.move(bounded)
        self.roam_position = next_position if bounded == rounded else QPointF(bounded)
        self.update_movement_debug()

    def start_showcase(self, seconds_per_state: float) -> None:
        interval_ms = round(min(max(seconds_per_state, 0.5), 10.0) * 1000)
        self.showcase_generation += 1
        generation = self.showcase_generation
        self.target = None
        self.apply_showcase_step(generation, SHOWCASE_STEPS[0])
        for index, step in enumerate(SHOWCASE_STEPS[1:], start=1):
            QTimer.singleShot(
                index * interval_ms,
                lambda item=step, token=generation: self.apply_showcase_step(token, item),
            )
        QTimer.singleShot(
            len(SHOWCASE_STEPS) * interval_ms,
            lambda token=generation: self.finish_showcase(token),
        )

    def apply_showcase_step(
        self,
        generation: int,
        step: tuple[str, str, str],
    ) -> None:
        if generation != self.showcase_generation:
            return
        label, kind, value = step
        self.showcase_step_label = label
        if kind == "look":
            degree = float(value) % 360
            self.showcase_animation = None
            self.row = 9 if degree < 180 else 10
            self.frame = round((degree % 180) / 22.5) % 8
            self.look_override = (self.row, self.frame)
            self.active_animation = f"look-{self.row}"
        else:
            self.look_override = None
            self.showcase_animation = value
            self.active_animation = value
            self.frame = 0
            self.row = ANIMATION_ROWS.get(CUSTOM_FALLBACKS.get(value, value), -1)
        self.animation_timer.setInterval(self.animation_interval(self.active_animation))
        self.render_frame()

    def finish_showcase(self, generation: int) -> None:
        if generation != self.showcase_generation:
            return
        self.showcase_generation += 1
        self.showcase_animation = None
        self.showcase_step_label = None
        self.look_override = None
        self.active_animation = self.current_animation()
        self.animation_timer.setInterval(self.animation_interval(self.active_animation))
        self.frame = 0
        self.render_frame()

    def cancel_showcase(self) -> None:
        if self.showcase_animation is None and self.showcase_step_label is None:
            return
        self.finish_showcase(self.showcase_generation)

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
            self.record_interaction(1)
            self.speak("clicked", force=True)
            self.persist_position()
            event.accept()
            return
        bottom_right = self.anchor_position("bottom-right")
        if (self.pos() - bottom_right).manhattanLength() <= self.config.snap_distance * 2:
            self.apply_anchor("bottom-right")
        else:
            self.config.anchor = "none"
            self.config.movement = "stay"
            self.sync_current_animation()
            self.update_label_geometry()
            self.move(self.clamp(self.pos()))
            self.persist_position()
        event.accept()

    def handle(self, command: dict[str, Any]) -> dict[str, Any]:
        action = str(command.get("action", "status"))
        value = command.get("value")
        if action not in {"status", "showcase", "demo"}:
            self.cancel_showcase()
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
            self.config.pomodoro_enabled = False
            self.pomodoro_timer.stop()
            self.config.movement = action
            if action == "roam":
                self.config.animation = "auto"
            self.set_mode("normal", speak=False)
            self.config.anchor = "none"
            self.update_label_geometry()
            self.target = None
        elif action == "mode":
            mode = str(value)
            self.config.pomodoro_enabled = False
            self.pomodoro_timer.stop()
            self.set_mode(mode)
        elif action == "say":
            if not isinstance(value, str) or not value.strip():
                raise ValueError("say requires text")
            if not self.quiet_hours_active():
                self.position_bubble()
                self.bubble.show_message(value.strip(), 5000)
        elif action == "advice-now":
            self.trigger_advice()
        elif action == "pomodoro":
            operation = str(value)
            if operation == "start":
                focus = command.get("focus")
                break_minutes = command.get("break_minutes")
                if focus is not None:
                    self.config.pomodoro_focus_minutes = max(0.05, float(focus))
                if break_minutes is not None:
                    self.config.pomodoro_break_minutes = max(0.05, float(break_minutes))
                self.config.pomodoro_enabled = True
                self.config.pomodoro_phase = "focus"
                self.resume_pomodoro()
            elif operation == "stop":
                self.config.pomodoro_enabled = False
                self.pomodoro_timer.stop()
                self.config.pomodoro_phase = "focus"
                self.set_mode("normal", speak=False)
            elif operation != "status":
                raise ValueError(f"unknown pomodoro operation: {operation}")
        elif action == "rubber-duck":
            operation = str(value)
            if operation == "on":
                self.config.rubber_duck_enabled = True
                self.schedule_rubber_duck()
            elif operation == "off":
                self.config.rubber_duck_enabled = False
                self.rubber_duck_timer.stop()
            elif operation == "ask":
                self.trigger_rubber_duck(manual=True)
            elif operation != "status":
                raise ValueError(f"unknown rubber-duck operation: {operation}")
        elif action == "victory":
            generation = self.start_temporary_animation("jump", 5200, "victory")
            QTimer.singleShot(1800, lambda: self.set_temporary_phase(generation, "wave"))
        elif action == "quiet-hours":
            operation = str(value)
            if operation == "on":
                self.config.quiet_hours_enabled = True
                self.bubble.hide()
            elif operation == "off":
                self.config.quiet_hours_enabled = False
            elif operation == "schedule":
                start = str(command.get("start"))
                end = str(command.get("end"))
                self.clock_minutes(start)
                self.clock_minutes(end)
                self.config.quiet_hours_start = start
                self.config.quiet_hours_end = end
                self.config.quiet_schedule_enabled = True
                if self.quiet_hours_active():
                    self.bubble.hide()
            elif operation == "unschedule":
                self.config.quiet_schedule_enabled = False
            elif operation != "status":
                raise ValueError(f"unknown quiet-hours operation: {operation}")
        elif action == "dialogue-pack":
            operation = str(value)
            if operation == "load":
                path = str(command.get("path", ""))
                dialogues = load_dialogue_pack(path)
                self.dialogue_deck = DialogueDeck(dialogues)
                self.config.dialogue_pack = str(Path(path).expanduser().resolve())
            elif operation == "clear":
                self.dialogue_deck = DialogueDeck()
                self.config.dialogue_pack = None
            elif operation != "status":
                raise ValueError(f"unknown dialogue-pack operation: {operation}")
        elif action == "treat":
            self.config.treats += 1
            self.record_interaction(8)
            self.start_temporary_animation("wave", 3600, "treat")
        elif action == "mood":
            pass
        elif action == "anchor":
            if value == "current":
                self.config.anchor = "current"
                self.config.movement = "stay"
                self.sync_current_animation()
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
            self.sync_current_animation()
            self.update_label_geometry()
            self.move(self.clamp(QPoint(int(value[0]), int(value[1]))))
        elif action == "screen":
            if value is None:
                raise ValueError("screen requires an index or next")
            screens = application_screens()
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
                self.refresh_position_limits()
            elif command["key"] == "opacity":
                self.config.opacity = min(max(float(value), MIN_OPACITY), MAX_OPACITY)
                self.setWindowOpacity(self.config.opacity)
            elif command["key"] == "bounds":
                self.refresh_position_limits()
            elif command["key"] == "run_chance":
                self.config.run_chance = min(max(int(value), 0), 100)
            elif command["key"] == "debug_movement":
                self.config.debug_movement = bool(value)
                self.update_movement_debug()
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
            self.config.pomodoro_enabled = False
            self.pomodoro_timer.stop()
            self.set_mode("normal", speak=False)
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
            self.start_showcase(1.8)
        elif action == "showcase":
            self.start_showcase(float(command.get("seconds_per_state", 1.2)))
        elif action == "quit":
            QTimer.singleShot(0, QApplication.quit)
        self.update_movement_debug()
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
                "animation": self.active_animation,
                "row": self.row,
                "frame": self.frame,
                "frame_interval_ms": self.animation_timer.interval(),
                "application_icon": {
                    "qt": not app.windowIcon().isNull(),
                    "native": bool(app.property("nativeApplicationIconApplied")),
                },
                "mode_assets": sorted(self.mode_frames),
                "smooth_animation_assets": sorted(self.animation_frames),
                "movement_debug": self.movement_debug_state(),
                "dialogue_visible": self.bubble.isVisible(),
                "dialogue_text": self.bubble.label.text() if self.bubble.isVisible() else None,
                "dialogue_window": [
                    self.bubble.x(),
                    self.bubble.y(),
                    self.bubble.width(),
                    self.bubble.height(),
                ],
                "dialogue_accepts_focus": not bool(
                    self.bubble.windowFlags() & Qt.WindowType.WindowDoesNotAcceptFocus
                ),
                "pomodoro": {
                    "enabled": self.config.pomodoro_enabled,
                    "phase": self.config.pomodoro_phase,
                    "remaining_seconds": max(0, self.pomodoro_timer.remainingTime()) // 1000,
                },
                "rubber_duck_enabled": self.config.rubber_duck_enabled,
                "quiet_hours_active": self.quiet_hours_active(),
                "dialogue_pack": self.config.dialogue_pack,
                "mood": self.config.mood,
                "treats": self.config.treats,
                "interaction_streak": self.config.interaction_streak,
                "context_menu_open_count": self.context_menu_open_count,
                "showcase": {
                    "active": self.showcase_step_label is not None,
                    "step": self.showcase_step_label,
                    "states": [label for label, _kind, _value in SHOWCASE_STEPS],
                },
            },
        }

    def finish_motivate(self, generation: int) -> None:
        if self.config.mode != "motivate" or generation != self.mode_generation:
            return
        self.config.mode = "normal"
        self.mode_generation += 1
        self.active_animation = "idle"
        self.animation_timer.setInterval(self.animation_interval("idle"))
        self.frame = 0
        self.render_frame()
        self.persist_position()

    def apply_platform_window_policy(self) -> None:
        if sys.platform != "darwin":
            self.native_window_state = {"applied": True, "platform": sys.platform}
            return
        qt_platform = QGuiApplication.platformName()
        if qt_platform != "cocoa":
            self.native_window_state = {
                "applied": False,
                "platform": "darwin",
                "qt_platform": qt_platform,
            }
            return
        try:
            appkit: Any = import_module("AppKit")
            objc: Any = import_module("objc")

            view = objc.objc_object(c_void_p=c_void_p(int(self.winId())))
            window = view.window()
            if window is None:
                raise RuntimeError("Qt native window is not available")
            level = appkit.NSFloatingWindowLevel if self.config.always_on_top else 0
            behavior = (
                appkit.NSWindowCollectionBehaviorCanJoinAllSpaces
                | appkit.NSWindowCollectionBehaviorFullScreenAuxiliary
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
        self.icon_path = asset_path("leo-approved-concept.png")
        self.setWindowIcon(QIcon(str(self.icon_path)))
        self.setProperty("nativeApplicationIconApplied", self.apply_platform_application_icon())
        self.config = load_config()
        self.window = PetWindow(self.config)
        self._observed_screens: set[int] = set()
        self.screenAdded.connect(self.register_screen_geometry)
        self.screenRemoved.connect(self.defer_screen_geometry_refresh)
        for screen in self.screens():
            self.register_screen_geometry(screen)
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

    def register_screen_geometry(self, screen: QScreen) -> None:
        identity = id(screen)
        if identity not in self._observed_screens:
            screen.geometryChanged.connect(self.window.screen_geometry_changed)
            screen.availableGeometryChanged.connect(self.window.screen_geometry_changed)
            self._observed_screens.add(identity)
        self.window.screen_geometry_changed()

    def defer_screen_geometry_refresh(self, screen: QScreen) -> None:
        self._observed_screens.discard(id(screen))
        QTimer.singleShot(0, self.window.screen_geometry_changed)

    def apply_platform_application_icon(self) -> bool:
        if sys.platform != "darwin":
            return True
        if QGuiApplication.platformName() != "cocoa":
            return False
        try:
            appkit: Any = import_module("AppKit")

            image = appkit.NSImage.alloc().initWithContentsOfFile_(str(self.icon_path))
            if image is None:
                raise RuntimeError(f"could not load application icon: {self.icon_path}")
            appkit.NSApplication.sharedApplication().setApplicationIconImage_(image)
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
        for label, scale in [("Tiny", 0.55), ("Small", 0.75), ("Normal", 1.0), ("Large", 1.2)]:
            item = QAction(label, size_menu)
            item.triggered.connect(
                lambda _checked=False, value=scale: self.window.handle(
                    {"action": "set", "key": "scale", "value": value}
                )
            )
            size_menu.addAction(item)

        transparency_menu = menu.addMenu("Transparency")
        for label, opacity in [
            ("Opaque", 1.0),
            ("Slight — 15%", 0.85),
            ("Medium — 35%", 0.65),
            ("Ghost — 60%", 0.4),
        ]:
            item = QAction(label, transparency_menu)
            item.triggered.connect(
                lambda _checked=False, value=opacity: self.window.handle(
                    {"action": "set", "key": "opacity", "value": value}
                )
            )
            transparency_menu.addAction(item)

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

        productivity_menu = menu.addMenu("Productivity")
        for label, action, value in [
            ("Start Pomodoro", "pomodoro", "start"),
            ("Stop Pomodoro", "pomodoro", "stop"),
            ("Ask Rubber Duck", "rubber-duck", "ask"),
            ("Rubber Duck prompts on", "rubber-duck", "on"),
            ("Rubber Duck prompts off", "rubber-duck", "off"),
            ("Celebrate victory", "victory", None),
            ("Quiet mode on", "quiet-hours", "on"),
            ("Quiet mode off", "quiet-hours", "off"),
        ]:
            add_action(productivity_menu, label, action, value)

        menu.addSeparator()
        add_action(menu, "Give Leo a treat", "treat")
        add_action(menu, "Tell me something", "say", "I’m Leo. I turn coffee into code.")
        add_action(menu, "Give advice now", "advice-now")
        add_action(menu, "Anchor bottom-right", "anchor", "bottom-right")
        add_action(menu, "Pause", "pause")
        add_action(menu, "Resume", "resume")
        menu.addSeparator()
        add_action(menu, "Quit", "quit")
        return menu

    def create_tray(self) -> QSystemTrayIcon:
        tray = QSystemTrayIcon(QIcon(str(asset_path("leo-approved-concept.png"))), self)
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
