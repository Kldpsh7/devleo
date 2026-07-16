from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPaintEvent, QPen
from PySide6.QtWidgets import QLabel, QWidget


class ThoughtBubble(QWidget):
    def __init__(self, parent: QWidget) -> None:
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        super().__init__(parent, flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFixedSize(250, 104)
        self.label = QLabel(self)
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont("Avenir Next", 13)
        font.setWeight(QFont.Weight.DemiBold)
        self.label.setFont(font)
        self.label.setStyleSheet("color: #202020; background: transparent;")
        self.label.setGeometry(18, 12, 214, 62)
        self.hide_timer = QTimer(self, singleShot=True)
        self.hide_timer.timeout.connect(self.hide)

    def show_message(self, text: str, duration_ms: int = 4300) -> bool:
        if self.isVisible():
            return False
        self.label.setText(text)
        self.show()
        self.raise_()
        self.hide_timer.start(duration_ms)
        return True

    def place_near(self, pet: QRect, screen: QRect) -> None:
        x = pet.center().x() - self.width() // 2
        x = min(max(x, screen.left()), screen.right() - self.width() + 1)
        above = pet.top() - self.height() + 20
        y = above if above >= screen.top() else pet.bottom() - 20
        y = min(max(y, screen.top()), screen.bottom() - self.height() + 1)
        self.move(QPoint(x, y))

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#252525"), 3))
        painter.setBrush(QColor(255, 255, 255, 246))
        path = QPainterPath()
        path.addRoundedRect(3, 3, self.width() - 6, 78, 22, 22)
        painter.drawPath(path)
        painter.drawEllipse(48, 79, 18, 14)
        painter.drawEllipse(31, 92, 10, 8)
