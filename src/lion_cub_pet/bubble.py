from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPaintEvent, QPen, QPolygonF
from PySide6.QtWidgets import QLabel, QWidget


class ThoughtBubble(QWidget):
    def __init__(self, parent: QWidget) -> None:
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        super().__init__(parent, flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFixedSize(160, 58)
        self.label = QLabel(self)
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        font = QFont("Avenir Next", 12)
        font.setWeight(QFont.Weight.DemiBold)
        self.label.setFont(font)
        self.label.setStyleSheet("color: #202020; background: transparent;")
        self.label.setGeometry(12, 7, 136, 38)
        self.hide_timer = QTimer(self, singleShot=True)
        self.hide_timer.timeout.connect(self.hide)

    def fit_message(self, text: str) -> None:
        metrics = self.label.fontMetrics()
        natural_width = metrics.horizontalAdvance(text) + 30
        width = min(max(natural_width, 116), 228)
        text_rect = metrics.boundingRect(
            QRect(0, 0, width - 24, 300),
            Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignCenter,
            text,
        )
        height = min(max(text_rect.height() + 23, 48), 92)
        self.setFixedSize(width, height)
        self.label.setGeometry(12, 6, width - 24, height - 17)

    def show_message(self, text: str, duration_ms: int = 4300) -> bool:
        if self.isVisible():
            return False
        self.label.setText(text)
        self.fit_message(text)
        self.show()
        self.hide_timer.start(duration_ms)
        return True

    def place_near(self, pet: QRect, screen: QRect) -> None:
        x = pet.center().x() - self.width() // 2
        x = min(max(x, screen.left()), screen.right() - self.width() + 1)
        above = pet.top() - self.height() + 9
        y = above if above >= screen.top() else pet.bottom() - 9
        y = min(max(y, screen.top()), screen.bottom() - self.height() + 1)
        self.move(QPoint(x, y))

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#252525"), 3))
        painter.setBrush(QColor(255, 255, 255, 246))
        path = QPainterPath()
        body_height = self.height() - 11
        path.addRoundedRect(3, 3, self.width() - 6, body_height - 3, 17, 17)
        painter.drawPath(path)
        tail_x = min(max(self.width() // 4, 24), self.width() - 36)
        painter.drawPolygon(
            QPolygonF(
                [
                    QPoint(tail_x, body_height - 2),
                    QPoint(tail_x + 19, body_height - 2),
                    QPoint(tail_x + 9, self.height() - 2),
                ]
            )
        )
