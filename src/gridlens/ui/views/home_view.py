from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gridlens._resources import resource
from gridlens.ui.theme.colors import Colors
from gridlens.ui.views._base import PageView


class _HeroBanner(QWidget):
    """Full-width banner that paints a background photo (scaled to cover) under a
    dark gradient, with title / tagline / actions laid out on top. Falls back to
    a brand-coloured gradient when the photo asset is missing."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(300)
        # Accept either home_hero.png or home_hero.jpg — whichever the user drops in.
        self._pixmap = QPixmap()
        for ext in ("png", "jpg"):
            candidate = resource("ui", "assets", f"home_hero.{ext}")
            if candidate.exists():
                self._pixmap = QPixmap(str(candidate))
                break

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        rect = self.rect()

        if not self._pixmap.isNull():
            # Cover: scale keeping aspect ratio to fill, then centre-crop.
            scaled = self._pixmap.scaled(
                rect.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (scaled.width() - rect.width()) // 2
            y = (scaled.height() - rect.height()) // 2
            painter.drawPixmap(rect, scaled, scaled.rect().adjusted(x, y, -x, -y))
            # Dark gradient overlay so the text stays readable.
            overlay = QLinearGradient(0, 0, rect.width(), 0)
            overlay.setColorAt(0.0, QColor(6, 10, 20, 252))
            overlay.setColorAt(0.45, QColor(6, 10, 20, 195))
            overlay.setColorAt(0.8, QColor(6, 10, 20, 70))
            overlay.setColorAt(1.0, QColor(6, 10, 20, 30))
            painter.fillRect(rect, overlay)
        else:
            grad = QLinearGradient(0, 0, rect.width(), rect.height())
            grad.setColorAt(0.0, QColor(Colors.BG_PANEL))
            grad.setColorAt(1.0, QColor(Colors.BRAND))
            painter.fillRect(rect, grad)

        super().paintEvent(event)


class HomeView(PageView):
    page_key = "home"
    page_title = "Welcome to GridLens"
    breadcrumbs = ["Home"]

    openRequested = pyqtSignal()
    reloadExampleRequested = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # ---------------------------- hero banner --------------------------- #
        hero = _HeroBanner()
        hero.setMinimumHeight(460)
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(44, 32, 44, 32)
        hero_layout.setSpacing(12)
        hero_layout.addStretch(1)

        title = QLabel("GridLens")
        title.setFont(QFont("Segoe UI", 34, QFont.Weight.Bold))
        title.setStyleSheet("color: white; background: transparent;")
        hero_layout.addWidget(title)

        tagline = QLabel("Distribution Feeder Analyzer")
        tagline.setFont(QFont("Segoe UI", 15, QFont.Weight.DemiBold))
        tagline.setStyleSheet("color: #7db4ff; background: transparent;")
        hero_layout.addWidget(tagline)

        intro = QLabel(
            "Turn a fixed feeder topology and its live operating conditions into "
            "instant visibility of every bus voltage, with violations flagged "
            "automatically. Open a network file to begin, or load an example feeder."
        )
        intro.setWordWrap(True)
        intro.setMinimumWidth(560)
        intro.setMaximumWidth(640)
        intro.setStyleSheet(
            "color: #ffffff; background: transparent; font-size: 11.5pt;"
        )
        hero_layout.addWidget(intro)

        hero_layout.addSpacing(8)
        actions = QHBoxLayout()
        actions.setSpacing(10)
        open_btn = QPushButton("Open Network File…")
        open_btn.setObjectName("PrimaryButton")
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.clicked.connect(self.openRequested)
        examples_btn = QPushButton("Load Example Feeder")
        examples_btn.setObjectName("SecondaryButton")
        examples_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        examples_btn.clicked.connect(self.reloadExampleRequested)
        actions.addWidget(open_btn)
        actions.addWidget(examples_btn)
        actions.addStretch(1)
        hero_layout.addLayout(actions)
        hero_layout.addStretch(1)

        layout.addWidget(hero)

        # ----------------------------- feature row -------------------------- #
        features = QHBoxLayout()
        features.setContentsMargins(24, 24, 24, 24)
        features.setSpacing(16)
        for icon, name, desc in (
            ("⚡", "VA Power-Flow Solver",
             "Power-summation backward-forward sweep for radial feeders, up to 10 buses."),
            ("◫", "Single-Line Diagram",
             "Distinct symbols per equipment type, with live voltage-violation tinting."),
            ("✎", "On-the-Fly Editing",
             "Adjust loads, generators and capacitors; the network re-solves instantly."),
        ):
            features.addWidget(self._feature_card(icon, name, desc), 1)
        layout.addLayout(features)
        layout.addStretch(1)

        self.set_content(body)

    def _feature_card(self, icon: str, name: str, desc: str) -> QWidget:
        card = QWidget()
        card.setObjectName("FeatureCard")
        card.setStyleSheet(
            f"""
            #FeatureCard {{
                background-color: {Colors.BG_PANEL};
                border: 1px solid {Colors.BORDER};
                border-radius: 8px;
            }}
            """
        )
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 16, 16, 16)
        cl.setSpacing(6)

        head = QLabel(f"{icon}  {name}")
        head.setStyleSheet(
            f"color: {Colors.TEXT}; font-weight: bold; font-size: 11pt; border: none;"
        )
        body = QLabel(desc)
        body.setWordWrap(True)
        body.setStyleSheet(f"color: {Colors.TEXT_MUTED}; border: none;")
        cl.addWidget(head)
        cl.addWidget(body)
        cl.addStretch(1)
        return card
