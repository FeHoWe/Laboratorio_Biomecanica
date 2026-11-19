"""Painel de pose: sliders de ângulo articular, limitados pelos limites configurados."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget

from biomechanics.human_model.lower_limb import LowerLimbModel

LABELS = {"hip": "Quadril (flexão +)", "knee": "Joelho (flexão +)", "ankle": "Tornozelo (dorsiflexão +)"}


class PosePanel(QWidget):
    angle_changed = Signal(str, float)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.sliders: dict[str, QSlider] = {}
        self.value_labels: dict[str, QLabel] = {}
        self.hint = QLabel("Crie/selecione um modelo (menu Modelo) para ajustar a pose.")
        self.hint.setWordWrap(True)
        self.hint.setObjectName("subtitle")
        self.lay = QVBoxLayout(self)
        self.lay.addWidget(self.hint)
        self.reset_btn = QPushButton("Pose neutra (0°)")
        self.reset_btn.clicked.connect(self.reset)
        self.model: LowerLimbModel | None = None
        self.setEnabled(False)

    def set_model(self, model: LowerLimbModel | None) -> None:
        self.model = model
        for w in list(self.sliders.values()) + list(self.value_labels.values()):
            w.deleteLater()
        self.sliders.clear()
        self.value_labels.clear()
        while self.lay.count() > 1:
            item = self.lay.takeAt(1)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())
        self.setEnabled(model is not None)
        self.hint.setVisible(model is None)
        if model is None:
            return
        for j, jd in model.joints.items():
            row = QHBoxLayout()
            title = QLabel(f"{LABELS.get(j, j)}  [{jd.min_deg:g}°, {jd.max_deg:g}°]")
            sl = QSlider(Qt.Horizontal)
            sl.setRange(int(round(jd.min_deg)), int(round(jd.max_deg)))
            sl.setValue(int(round(model.angles_deg[j])))
            val = QLabel(f"{model.angles_deg[j]:.0f}°")
            sl.valueChanged.connect(lambda v, jn=j: self._changed(jn, v))
            self.sliders[j], self.value_labels[j] = sl, val
            self.lay.addWidget(title)
            row.addWidget(sl)
            row.addWidget(val)
            self.lay.addLayout(row)
        self.lay.addWidget(self.reset_btn)
        self.lay.addStretch(1)

    def _clear_layout(self, layout) -> None:
        while layout.count():
            it = layout.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

    def _changed(self, joint: str, value: int) -> None:
        self.value_labels[joint].setText(f"{value}°")
        self.angle_changed.emit(joint, float(value))

    def reset(self) -> None:
        for j, sl in self.sliders.items():
            lo, hi = sl.minimum(), sl.maximum()
            sl.setValue(min(max(0, lo), hi))
