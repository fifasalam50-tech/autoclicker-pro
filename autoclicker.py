import ctypes
import math
import pathlib
import random
import sys
import tempfile
import time
from ctypes import wintypes

from PySide6.QtCore import (
    QAbstractNativeEventFilter,
    QPointF,
    QRectF,
    Qt,
    QTimer,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QIcon,
    QLinearGradient,
    QPainter,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

# ---------------------------------------------------------------------------
# Платформенная часть: клики мыши и глобальная горячая клавиша
# Windows использует нативные системные вызовы, Linux/macOS — библиотеку pynput
# ---------------------------------------------------------------------------

IS_WINDOWS = sys.platform == "win32"

HOTKEY_NAMES = ["F1", "F2", "F3", "F4", "F5", "F6",
                "F7", "F8", "F9", "F10", "F11", "F12"]

if IS_WINDOWS:
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004
    MOUSEEVENTF_RIGHTDOWN = 0x0008
    MOUSEEVENTF_RIGHTUP = 0x0010
    MOUSEEVENTF_MIDDLEDOWN = 0x0020
    MOUSEEVENTF_MIDDLEUP = 0x0040

    BUTTON_FLAGS = {
        "left": (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
        "right": (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
        "middle": (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP),
    }

    ULONG_PTR = wintypes.WPARAM

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = (
            ("dx", wintypes.LONG),
            ("dy", wintypes.LONG),
            ("mouseData", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ULONG_PTR),
        )

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = (
            ("wVk", wintypes.WORD),
            ("wScan", wintypes.WORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ULONG_PTR),
        )

    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = (
            ("uMsg", wintypes.DWORD),
            ("wParamL", wintypes.WORD),
            ("wParamH", wintypes.WORD),
        )

    class _INPUTUNION(ctypes.Union):
        _fields_ = (
            ("mi", MOUSEINPUT),
            ("ki", KEYBDINPUT),
            ("hi", HARDWAREINPUT),
        )

    class INPUT(ctypes.Structure):
        _fields_ = (
            ("type", wintypes.DWORD),
            ("u", _INPUTUNION),
        )

    user32 = ctypes.windll.user32
    WM_HOTKEY = 0x0312
    MOD_NOREPEAT = 0x4000
    HOTKEY_ID = 1

    VK_CODES = {
        "F1": 0x70, "F2": 0x71, "F3": 0x72, "F4": 0x73, "F5": 0x74, "F6": 0x75,
        "F7": 0x76, "F8": 0x77, "F9": 0x78, "F10": 0x79, "F11": 0x7A, "F12": 0x7B,
    }

    def _send_input(flags):
        inp = INPUT()
        inp.type = 0  # INPUT_MOUSE
        inp.u.mi = MOUSEINPUT()
        inp.u.mi.dx = 0
        inp.u.mi.dy = 0
        inp.u.mi.mouseData = 0
        inp.u.mi.dwFlags = flags
        inp.u.mi.time = 0
        inp.u.mi.dwExtraInfo = 0
        ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

    def ensure_message_queue():
        msg = wintypes.MSG()
        user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)

    def register_hotkey(vk):
        ensure_message_queue()
        user32.RegisterHotKey(None, HOTKEY_ID, MOD_NOREPEAT, vk)

    def unregister_hotkey():
        user32.UnregisterHotKey(None, HOTKEY_ID)

    class HotkeyFilter(QAbstractNativeEventFilter):
        def __init__(self, callback):
            super().__init__()
            self._callback = callback

        def nativeEventFilter(self, eventType, message):
            ptr = self._pointer(message)
            if ptr:
                msg = wintypes.MSG.from_address(ptr)
                if msg.message == WM_HOTKEY:
                    self._callback()
                    return True, 0
            return False, 0

        @staticmethod
        def _pointer(message):
            if isinstance(message, int):
                return message
            for attr in ("__int__", "__index__"):
                method = getattr(message, attr, None)
                if method is not None:
                    try:
                        return int(method())
                    except Exception:
                        pass
            return 0


class ClickController:
    """Клики мышью и глобальная горячая клавиша на любой ОС."""

    def __init__(self):
        self._last_trigger = 0.0
        self._callback = None
        self._listener = None
        self._mouse = None
        self._buttons = {}
        self._Key = None
        self._Listener = None
        self._pynput_ok = False

        if IS_WINDOWS:
            self.available = True
            return

        try:
            from pynput.keyboard import Key, Listener
            from pynput.mouse import Button, Controller
        except Exception:
            Key = Listener = Button = Controller = None
        self._Key = Key
        self._Listener = Listener
        self._pynput_ok = Key is not None
        if Controller is not None:
            self._mouse = Controller()
            self._buttons = {
                "left": Button.left,
                "right": Button.right,
                "middle": Button.middle,
            }
        self.available = self._pynput_ok and self._mouse is not None

    def click(self, button, times):
        if IS_WINDOWS:
            down, up = BUTTON_FLAGS[button]
            for _ in range(times):
                _send_input(down)
                _send_input(up)
                if times > 1:
                    time.sleep(0.015)
        else:
            btn = self._buttons[button]
            for _ in range(times):
                self._mouse.press(btn)
                self._mouse.release(btn)
                if times > 1:
                    time.sleep(0.015)

    def install_hotkey(self, name, callback):
        self._callback = callback
        if IS_WINDOWS:
            register_hotkey(VK_CODES[name])
        else:
            self._start_listener(name)

    def uninstall_hotkey(self):
        if IS_WINDOWS:
            try:
                unregister_hotkey()
            except Exception:
                pass
        else:
            self._stop_listener()

    def _start_listener(self, name):
        self._stop_listener()
        if not self._pynput_ok:
            return
        target = getattr(self._Key, f"f{int(name[1:])}")
        self._last_trigger = 0.0

        def on_press(key):
            if key != target:
                return
            now = time.monotonic()
            if now - self._last_trigger < 0.18:
                return
            self._last_trigger = now
            cb = self._callback
            if cb is not None:
                cb()

        self._listener = self._Listener(on_press=on_press)
        self._listener.daemon = True
        self._listener.start()

    def _stop_listener(self):
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None


# ---------------------------------------------------------------------------
# Неоновый интерфейс
# ---------------------------------------------------------------------------

def _make_svg(name, content):
    path = pathlib.Path(tempfile.gettempdir()) / name
    try:
        path.write_text(content, encoding="utf-8")
    except OSError:
        return ""
    return path.as_posix()


def build_stylesheet():
    arrow = _make_svg("oc_arrow.svg",
        '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 10 10">'
        '<path d="M2 3h6l-3 4.2z" fill="#8fa9e0"/></svg>')
    up = _make_svg("oc_up.svg",
        '<svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 8 8">'
        '<path d="M1 5.5 L4 2 L7 5.5 Z" fill="#8fa9e0"/></svg>')
    down = _make_svg("oc_down.svg",
        '<svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 8 8">'
        '<path d="M1 2.5 L4 6 L7 2.5 Z" fill="#8fa9e0"/></svg>')
    check = _make_svg("oc_check.svg",
        '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 12 12">'
        '<path d="M2 6.2 L4.8 8.6 L9.6 3" stroke="#ffffff" stroke-width="2" fill="none" '
        'stroke-linecap="round" stroke-linejoin="round"/></svg>')

    css = """
* { font-family: "Segoe UI", "Segoe UI Variable", sans-serif; }

QLabel { color: #eaf2ff; font-size: 13px; }

QLabel#title {
    font-size: 30px; font-weight: 800; color: #ffffff;
}
QLabel#subtitle { color: #9db4e0; font-size: 13px; }
QLabel#sectionTitle {
    font-size: 12px; font-weight: 700; color: #7fa8e8;
}
QLabel#fieldName { color: #c6d6f5; font-size: 13px; }
QLabel#hint { color: #7e8fb8; font-size: 12px; }
QLabel#counter { font-size: 42px; font-weight: 800; color: #ffffff; }
QLabel#counterCaption { color: #8fa3c9; font-size: 12px; }
QLabel#statusText { font-size: 14px; font-weight: 600; }
QLabel#version {
    color: #8fa3c9; font-size: 11px; background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.12); border-radius: 9px; padding: 4px 10px;
}

QFrame#panel {
    background: rgba(10, 20, 42, 0.55);
    border: 1px solid rgba(120, 170, 255, 0.14);
    border-radius: 18px;
}

QFrame#hline {
    background: rgba(255,255,255,0.10);
    border: none;
    max-height: 1px;
}

QComboBox {
    background: rgba(255,255,255,0.07);
    border: 1px solid rgba(140,180,255,0.20);
    border-radius: 10px;
    padding: 6px 28px 6px 12px;
    color: #eaf2ff; font-size: 13px;
    min-width: 110px;
}
QComboBox:hover { border-color: rgba(120,180,255,0.45); background: rgba(255,255,255,0.10); }
QComboBox:disabled { color: #5a6b8c; border-color: rgba(140,180,255,0.08); background: rgba(255,255,255,0.03); }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox::down-arrow {
    image: url(__ARROW__); width: 10px; height: 10px;
    subcontrol-origin: padding; subcontrol-position: right center;
}
QComboBox QAbstractItemView {
    background: #0e1830; color: #eaf2ff; border: 1px solid rgba(120,170,255,0.25);
    border-radius: 10px; selection-background-color: #2f6fd0; outline: none; padding: 4px;
}

QSpinBox {
    background: rgba(255,255,255,0.07);
    border: 1px solid rgba(140,180,255,0.20);
    border-radius: 10px;
    padding: 6px 26px 6px 10px;
    color: #eaf2ff; font-size: 13px; font-weight: 600;
}
QSpinBox:hover { border-color: rgba(120,180,255,0.45); }
QSpinBox:disabled { color: #5a6b8c; border-color: rgba(140,180,255,0.08); background: rgba(255,255,255,0.03); }
QSpinBox::up-button, QSpinBox::down-button { width: 18px; border: none; background: transparent; }
QSpinBox::up-arrow {
    image: url(__UP__); width: 8px; height: 8px;
    subcontrol-origin: padding; subcontrol-position: center;
}
QSpinBox::down-arrow {
    image: url(__DOWN__); width: 8px; height: 8px;
    subcontrol-origin: padding; subcontrol-position: center;
}

QCheckBox { color: #c6d6f5; font-size: 13px; spacing: 8px; }
QCheckBox::indicator { width: 18px; height: 18px; border-radius: 6px;
    border: 1px solid rgba(140,180,255,0.30); background: rgba(255,255,255,0.05); }
QCheckBox::indicator:hover { border-color: rgba(120,180,255,0.6); }
QCheckBox::indicator:checked {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #4a8cff, stop:1 #2a5bd0);
    border-color: #6aa8ff;
    image: url(__CHECK__);
}

QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #4a8cff, stop:1 #2656c4);
    color: white; border: none; border-radius: 12px;
    padding: 14px 16px; font-size: 15px; font-weight: 700;
}
QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #5d9cff, stop:1 #3366d8); }
QPushButton:pressed { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3a74e0, stop:1 #1f4ab0); }
QPushButton:disabled { background: #2a3550; color: #7a86a0; }
QPushButton#stopButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ff6b6b, stop:1 #d33a3a);
}
QPushButton#stopButton:hover { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ff8585, stop:1 #e04a4a); }
QPushButton#stopButton:pressed { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #e05555, stop:1 #bd2f2f); }
"""
    css = (css.replace("__ARROW__", arrow)
               .replace("__UP__", up)
               .replace("__DOWN__", down)
               .replace("__CHECK__", check))
    return css


class AnimatedBackground(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.phase = 0.0
        rnd = random.Random(42)
        self.particles = [
            (rnd.uniform(0, 1), rnd.uniform(0, 1), rnd.uniform(8, 38),
             rnd.uniform(0.4, 1.2), rnd.uniform(0.05, 0.25))
            for _ in range(26)
        ]
        self._timer = QTimer(self, interval=30)
        self._timer.timeout.connect(self._advance)
        self._timer.start()

    def _advance(self):
        self.phase += 0.015
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            return

        t = self.phase
        top = QColor(
            int(24 + 10 * math.sin(t * 0.7)),
            int(52 + 18 * math.sin(t * 0.9 + 1.2)),
            int(110 + 40 * math.sin(t * 1.1 + 2.4)),
        )
        mid = QColor(
            int(14 + 8 * math.sin(t * 0.8 + 0.5)),
            int(30 + 14 * math.sin(t * 1.0 + 1.8)),
            int(66 + 24 * math.sin(t * 1.2 + 3.0)),
        )
        bottom = QColor(5, 9, 22)

        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0.0, top)
        grad.setColorAt(0.55, mid)
        grad.setColorAt(1.0, bottom)
        p.fillRect(self.rect(), grad)

        sx = w * (0.5 + 0.45 * math.sin(t * 0.35))
        sy = h * (0.35 + 0.25 * math.sin(t * 0.55 + 1.0))
        glow = QRadialGradient(QPointF(sx, sy), max(w, h) * 0.9)
        glow.setColorAt(0.0, QColor(90, 170, 255, 46))
        glow.setColorAt(0.6, QColor(50, 110, 220, 16))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.fillRect(self.rect(), glow)

        v = QRadialGradient(QPointF(w * 0.5, h * 0.45), max(w, h) * 0.75)
        v.setColorAt(0.0, QColor(0, 0, 0, 0))
        v.setColorAt(1.0, QColor(0, 0, 0, 110))
        p.fillRect(self.rect(), v)

        for (px, py, size, speed, alpha) in self.particles:
            y = (py * h + t * speed * h * 0.15) % (h + 60) - 30
            x = px * w
            r = size
            a = int(alpha * 90 * (0.6 + 0.4 * math.sin(t * 1.5 + px * 20)))
            a = max(0, min(255, a))
            g = QRadialGradient(QPointF(x, y), r)
            g.setColorAt(0.0, QColor(140, 190, 255, a))
            g.setColorAt(1.0, QColor(140, 190, 255, 0))
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(g))
            p.drawEllipse(QPointF(x, y), r, r)


class StatusDot(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(18, 18)
        self.active = False
        self.phase = 0.0
        self._timer = QTimer(self, interval=30)
        self._timer.timeout.connect(self._advance)
        self._timer.start()

    def _advance(self):
        self.phase += 0.12
        self.update()

    def set_active(self, active):
        self.active = active
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = QPointF(9, 9)
        color = QColor(90, 255, 160) if self.active else QColor(150, 165, 195)
        pulse = 1.0 + (0.25 * math.sin(self.phase)) if self.active else 1.0
        glow_r = 14 * pulse
        g = QRadialGradient(c, glow_r)
        col = QColor(color)
        col.setAlpha(70)
        g.setColorAt(0.0, col)
        g.setColorAt(1.0, QColor(color.red(), color.green(), color.blue(), 0))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(g))
        p.drawEllipse(c, glow_r, glow_r)
        core = QColor(color) if not self.active else QColor(120, 255, 180)
        p.setBrush(QBrush(core))
        p.drawEllipse(c, 5.2, 5.2)
        p.setBrush(QBrush(QColor(255, 255, 255, 120)))
        p.drawEllipse(QPointF(7.2, 6.8), 2.0, 2.0)


class GlowButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self._glow = QGraphicsDropShadowEffect(self)
        self._glow.setBlurRadius(26)
        self._glow.setOffset(0, 0)
        self._glow.setColor(QColor(60, 140, 255, 200))
        self.setGraphicsEffect(self._glow)
        self.setCursor(Qt.PointingHandCursor)

    def set_glow_color(self, color):
        c = QColor(color)
        c.setAlpha(210)
        self._glow.setColor(c)


def make_app_icon():
    size = 256
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)

    rect = QRectF(0, 0, size, size)
    bg = QLinearGradient(0, 0, 0, size)
    bg.setColorAt(0.0, QColor(44, 96, 190))
    bg.setColorAt(1.0, QColor(7, 14, 38))
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(bg))
    p.drawRoundedRect(rect, 58, 58)

    glow = QRadialGradient(QPointF(size * 0.5, size * 0.38), size * 0.72)
    glow.setColorAt(0.0, QColor(120, 180, 255, 70))
    glow.setColorAt(1.0, QColor(120, 180, 255, 0))
    p.setBrush(QBrush(glow))
    p.drawRoundedRect(rect, 58, 58)

    body = QRectF(68, 56, 120, 148)
    bgrad = QLinearGradient(0, body.top(), 0, body.bottom())
    bgrad.setColorAt(0.0, QColor(120, 180, 255))
    bgrad.setColorAt(1.0, QColor(60, 110, 215))
    p.setBrush(QBrush(bgrad))
    p.drawRoundedRect(body, 42, 42)

    p.setBrush(QColor(10, 22, 50))
    p.drawRect(QRectF(126, 62, 4, 40))
    p.drawRect(QRectF(74, 96, 108, 4))

    p.end()
    return QIcon(pm)


# ---------------------------------------------------------------------------
# Главное окно
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.running = False
        self.clicks_done = 0

        self.setWindowTitle("Автокликер Pro")
        self.setWindowIcon(make_app_icon())
        self.setMinimumSize(720, 560)
        self.resize(740, 600)

        central = AnimatedBackground(self)
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(24, 18, 24, 18)
        root.setSpacing(16)

        root.addLayout(self._build_title())

        content = QHBoxLayout()
        content.setSpacing(16)
        content.addWidget(self._build_settings_panel(), 3)
        content.addWidget(self._build_control_panel(), 2)
        root.addLayout(content, 1)

        if IS_WINDOWS:
            tip = ("Клики выполняются там, где находится указатель мыши. "
                   "Горячая клавиша работает в любом окне.")
        elif sys.platform == "darwin":
            tip = ("Клики выполняются под курсором. Разрешите приложению доступ в "
                   "«Системные настройки → Приватность и безопасность → "
                   "Специальные возможности».")
        else:
            tip = ("Клики выполняются под курсором. Работает в сеансе X11 (Xorg); "
                   "под Wayland используйте протокол XWayland.")
        footer = QLabel(tip)
        footer.setObjectName("hint")
        footer.setWordWrap(True)
        footer.setAlignment(Qt.AlignCenter)
        root.addWidget(footer)

        self.controller = ClickController()
        self.click_timer = QTimer(self)
        self.click_timer.timeout.connect(self._tick)

        self._install_hotkey()
        self._refresh_state()
        if not self.controller.available:
            self.status_label.setText("Не удалось получить доступ к мыши и клавиатуре")
            self.status_label.setStyleSheet("color: #ffb36b;")

    # --- построение интерфейса -------------------------------------------

    def _build_title(self):
        box = QHBoxLayout()
        box.setSpacing(12)
        left = QVBoxLayout()
        left.setSpacing(2)
        title = QLabel("◆ Автокликер")
        title.setObjectName("title")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(36)
        shadow.setOffset(0, 0)
        shadow.setColor(QColor(80, 150, 255, 180))
        title.setGraphicsEffect(shadow)
        sub = QLabel("Профессиональный кликер с неоновым интерфейсом")
        sub.setObjectName("subtitle")
        left.addWidget(title)
        left.addWidget(sub)
        box.addLayout(left)
        box.addStretch(1)
        version = QLabel("v1.0")
        version.setObjectName("version")
        box.addWidget(version, 0, Qt.AlignTop)
        return box

    def _panel(self):
        panel = QFrame()
        panel.setObjectName("panel")
        return panel

    def _section_title(self, text):
        label = QLabel(text)
        label.setObjectName("sectionTitle")
        return label

    def _build_settings_panel(self):
        panel = self._panel()
        v = QVBoxLayout(panel)
        v.setContentsMargins(20, 18, 20, 18)
        v.setSpacing(14)
        v.addWidget(self._section_title("НАСТРОЙКИ КЛИКОВ"))

        # режим интервала
        mode_row = QHBoxLayout()
        mode_row.setSpacing(10)
        mode_lbl = QLabel("Интервал")
        mode_lbl.setObjectName("fieldName")
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Фиксированный", 0)
        self.mode_combo.addItem("Случайный", 1)
        mode_row.addWidget(mode_lbl)
        mode_row.addStretch(1)
        mode_row.addWidget(self.mode_combo)
        v.addLayout(mode_row)

        # фиксированный интервал
        self.fixed_spin = QSpinBox()
        self.fixed_spin.setRange(1, 60000)
        self.fixed_spin.setValue(100)
        self.fixed_spin.setSuffix(" мс")
        self.fixed_spin.setAlignment(Qt.AlignRight)
        fixed_lbl = QLabel("Задержка")
        fixed_lbl.setObjectName("fieldName")
        fixed_row = QHBoxLayout()
        fixed_row.setSpacing(10)
        fixed_row.addWidget(fixed_lbl)
        fixed_row.addStretch(1)
        fixed_row.addWidget(self.fixed_spin)
        v.addLayout(fixed_row)

        # случайный интервал
        self.rand_min_spin = QSpinBox()
        self.rand_min_spin.setRange(1, 60000)
        self.rand_min_spin.setValue(50)
        self.rand_min_spin.setSuffix(" мс")
        self.rand_min_spin.setAlignment(Qt.AlignRight)
        self.rand_max_spin = QSpinBox()
        self.rand_max_spin.setRange(1, 60000)
        self.rand_max_spin.setValue(250)
        self.rand_max_spin.setSuffix(" мс")
        self.rand_max_spin.setAlignment(Qt.AlignRight)
        rand_lbl = QLabel("Случайно от")
        rand_lbl.setObjectName("fieldName")
        rand_mid = QLabel("до")
        rand_mid.setObjectName("hint")
        self.rand_row = QHBoxLayout()
        self.rand_row.setSpacing(8)
        self.rand_row.addWidget(rand_lbl)
        self.rand_row.addStretch(1)
        self.rand_row.addWidget(self.rand_min_spin)
        self.rand_row.addWidget(rand_mid)
        self.rand_row.addWidget(self.rand_max_spin)
        v.addLayout(self.rand_row)

        v.addWidget(self._divider())

        # кнопка мыши
        btn_lbl = QLabel("Кнопка мыши")
        btn_lbl.setObjectName("fieldName")
        self.button_combo = QComboBox()
        self.button_combo.addItem("Левая", "left")
        self.button_combo.addItem("Правая", "right")
        self.button_combo.addItem("Средняя", "middle")
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addWidget(btn_lbl)
        btn_row.addStretch(1)
        btn_row.addWidget(self.button_combo)
        v.addLayout(btn_row)

        # тип клика
        type_lbl = QLabel("Тип клика")
        type_lbl.setObjectName("fieldName")
        self.type_combo = QComboBox()
        self.type_combo.addItem("Одиночный", 1)
        self.type_combo.addItem("Двойной", 2)
        self.type_combo.addItem("Тройной", 3)
        type_row = QHBoxLayout()
        type_row.setSpacing(10)
        type_row.addWidget(type_lbl)
        type_row.addStretch(1)
        type_row.addWidget(self.type_combo)
        v.addLayout(type_row)

        v.addWidget(self._divider())

        # лимит
        limit_lbl = QLabel("Лимит кликов")
        limit_lbl.setObjectName("fieldName")
        self.limit_check = QCheckBox("Бесконечно")
        self.limit_check.setChecked(True)
        self.limit_check.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(1, 1000000)
        self.limit_spin.setValue(100)
        self.limit_spin.setMinimumWidth(110)
        self.limit_spin.setAlignment(Qt.AlignRight)
        self.limit_spin.setEnabled(False)
        limit_row = QHBoxLayout()
        limit_row.setSpacing(10)
        limit_row.addWidget(limit_lbl)
        limit_row.addWidget(self.limit_check)
        limit_row.addStretch(1)
        limit_row.addWidget(self.limit_spin)
        v.addLayout(limit_row)
        v.addStretch(1)

        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self.limit_check.toggled.connect(lambda on: self.limit_spin.setEnabled(not on))
        self._on_mode_changed(0)
        return panel

    def _build_control_panel(self):
        panel = self._panel()
        v = QVBoxLayout(panel)
        v.setContentsMargins(20, 18, 20, 18)
        v.setSpacing(14)
        v.addWidget(self._section_title("УПРАВЛЕНИЕ"))

        status_row = QHBoxLayout()
        status_row.setSpacing(10)
        self.status_dot = StatusDot()
        self.status_label = QLabel("Готов к работе")
        self.status_label.setObjectName("statusText")
        status_row.addWidget(self.status_dot)
        status_row.addWidget(self.status_label)
        status_row.addStretch(1)
        v.addLayout(status_row)

        self.counter_label = QLabel("0")
        self.counter_label.setObjectName("counter")
        self.counter_label.setAlignment(Qt.AlignCenter)
        v.addWidget(self.counter_label)
        caption = QLabel("кликов выполнено")
        caption.setObjectName("counterCaption")
        caption.setAlignment(Qt.AlignCenter)
        v.addWidget(caption)

        v.addSpacing(4)
        v.addWidget(self._divider())

        hotkey_lbl = QLabel("Горячая клавиша")
        hotkey_lbl.setObjectName("fieldName")
        self.hotkey_combo = QComboBox()
        for key in HOTKEY_NAMES:
            self.hotkey_combo.addItem(key, key)
        self.hotkey_combo.setCurrentText("F6")
        hotkey_row = QHBoxLayout()
        hotkey_row.setSpacing(10)
        hotkey_row.addWidget(hotkey_lbl)
        hotkey_row.addStretch(1)
        hotkey_row.addWidget(self.hotkey_combo)
        v.addLayout(hotkey_row)

        hotkey_hint = QLabel("Нажмите клавишу, чтобы запустить или остановить клики")
        hotkey_hint.setObjectName("hint")
        hotkey_hint.setWordWrap(True)
        v.addWidget(hotkey_hint)

        v.addStretch(1)

        self.start_btn = GlowButton("▶ СТАРТ")
        self.start_btn.setMinimumHeight(54)
        self.start_btn.setCursor(Qt.PointingHandCursor)
        self.start_btn.clicked.connect(self.toggle)
        v.addWidget(self.start_btn)

        self.hotkey_combo.currentIndexChanged.connect(self._on_hotkey_changed)
        return panel

    def _divider(self):
        line = QFrame()
        line.setObjectName("hline")
        line.setFixedHeight(1)
        return line

    # --- логика -----------------------------------------------------------

    def _on_mode_changed(self, index):
        random_mode = index == 1
        self.fixed_spin.setEnabled(not random_mode)
        self.rand_min_spin.setEnabled(random_mode)
        self.rand_max_spin.setEnabled(random_mode)

    def _hotkey_pressed(self):
        QTimer.singleShot(0, self.toggle)

    def _on_hotkey_changed(self, index):
        self.controller.uninstall_hotkey()
        self.controller.install_hotkey(self.hotkey_combo.currentData(),
                                       self._hotkey_pressed)

    def _install_hotkey(self):
        if IS_WINDOWS:
            self._filter = HotkeyFilter(self._hotkey_pressed)
            QApplication.instance().installNativeEventFilter(self._filter)
        self.controller.install_hotkey(self.hotkey_combo.currentData(),
                                       self._hotkey_pressed)

    def _current_interval(self):
        if self.mode_combo.currentIndex() == 1:
            lo = self.rand_min_spin.value()
            hi = self.rand_max_spin.value()
            if hi < lo:
                lo, hi = hi, lo
            return random.randint(lo, hi)
        return self.fixed_spin.value()

    def toggle(self):
        if self.running:
            self.stop()
        else:
            self.start()

    def start(self):
        self.running = True
        self.clicks_done = 0
        self._update_counter()
        self.click_timer.start(self._current_interval())
        self._refresh_state()

    def stop(self):
        self.running = False
        self.click_timer.stop()
        self._refresh_state()

    def _tick(self):
        self.controller.click(self.button_combo.currentData(),
                              self.type_combo.currentData())
        self.clicks_done += self.type_combo.currentData()
        self._update_counter()

        if (not self.limit_check.isChecked()
                and self.clicks_done >= self.limit_spin.value()):
            self.stop()
            return
        if self.mode_combo.currentIndex() == 1:
            lo = self.rand_min_spin.value()
            hi = self.rand_max_spin.value()
            if hi < lo:
                lo, hi = hi, lo
            self.click_timer.setInterval(random.randint(lo, hi))

    def _update_counter(self):
        self.counter_label.setText(f"{self.clicks_done:,}")

    def _refresh_state(self):
        if self.running:
            self.start_btn.setText("■ СТОП")
            self.start_btn.setObjectName("stopButton")
            self.start_btn.set_glow_color(QColor(255, 90, 90))
            self.status_label.setText("Клики идут…")
            self.status_label.setStyleSheet("color: #8dffc0;")
            self.status_dot.set_active(True)
        else:
            self.start_btn.setText("▶ СТАРТ")
            self.start_btn.setObjectName("startButton")
            self.start_btn.set_glow_color(QColor(60, 140, 255))
            self.status_label.setText("Готов к работе")
            self.status_label.setStyleSheet("color: #9db4e0;")
            self.status_dot.set_active(False)
        self.start_btn.style().unpolish(self.start_btn)
        self.start_btn.style().polish(self.start_btn)
        self.start_btn.update()

    def closeEvent(self, event):
        self.stop()
        self.controller.uninstall_hotkey()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(build_stylesheet())
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
