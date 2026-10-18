#!/usr/bin/env python3
"""
grom обходник — обёртка над winws (zapret) для Windows. v1.10

* Тёмный интерфейс, без консольных окон
* Новая VPN-страница (как в happ): подписка, список серверов, обновление,
  проверка пинга, подключение через встроенный sing-box + системный прокси
* Обновлённая иконка и дизайн (чипы меню, стеклянный логотип,
  градиентные акценты, кольцо-гロー у круглой кнопки)
* Разбор батников дистрибутива (zapret-win-bundle и стандартный формат)
* Идеально круглая кнопка запуска с плавными анимациями
* Анимации страниц, меню и статусов
* Вкладка «Тема»: цветовые темы, свой акцент, фон-картинка, скругление
* Вкладка «Игры»: загрузка CPU/GPU/ОЗУ в реальном времени (без FPS-монитора)
* Автозапуск обхода при открытии программы и при входе в Windows
* Внутри встроен дистрибутив zapret — работает и без папки zapret на ПК
* Всё в одном exe: pyinstaller --onefile --noconsole zapret_gui.py
"""

import ctypes
import json
import math
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
from ctypes import wintypes
from tkinter import colorchooser, filedialog, messagebox

import customtkinter as ctk
from PIL import Image, ImageOps

import vpn_core

APP_NAME = "grom обходник"
VERSION = "1.10"
AUTOSTART_TASK = "grom"
CONFIG_PATH = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")),
                           "grom", "config.json")
LEGACY_TASK = "ZapretGUI"
# правильный флаг: без него дочерние консольные процессы открывают окно
CREATE_NO_WINDOW = 0x08000000

# ------------------------------------------------------------------ оформление

BG = "#0A0C10"
SIDEBAR = "#0D0F15"
CARD = "#161B27"
CARD_HOVER = "#1D2432"
BTN_HOVER = "#242A36"   # ховер подчинённых кнопок (выводится из CARD_HOVER)
CONSOLE_BG = "#090B0F"
ACCENT = "#7C6CFF"
ACCENT_HOVER = "#6A59F2"
GREEN = "#2BD576"
RED = "#FF5D6C"
AMBER = "#FFB454"
TEXT = "#ECEDF3"
MUTED = "#788094"
BORDER = "#2A3145"
TINT_GREEN = "#12271D"
TINT_RED = "#2A151A"
TINT_AMBER = "#2A2113"
# активный пункт меню
ACTIVE_BG = "#181534"
ACTIVE_HOVER = "#1D1940"
ACTIVE_TEXT = "#A99DFF"
# приглушённые оттенки для пульсации
ACCENT_DIM = "#1A1740"
ACCENT_BRIGHT = "#221D50"
RED_DIM = "#3B2029"
GREEN_DIM = "#1F9A57"
AMBER_DIM = "#C98F3E"


def hex_to_rgb(c):
    c = str(c)
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))


def rgb_to_hex(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(round(v)))) for v in rgb)


def lerp_color(c1, c2, t):
    """Плавная интерполяция между двумя hex-цветами."""
    try:
        a, b = hex_to_rgb(c1), hex_to_rgb(c2)
    except Exception:
        return str(c2)
    return rgb_to_hex(a[i] + (b[i] - a[i]) * t for i in range(3))


def lighten(color, amt):
    r, g, b = hex_to_rgb(color)
    return rgb_to_hex((r + amt, g + amt, b + amt))


# текущий радиус скругления карточек (настраивается на странице «Тема»)
RADIUS = 16

# пресеты оформления: фон, карточки, рамка + акцент по умолчанию
THEME_PRESETS = {
    "violet": {"name": "Ночной фиолет",
               "bg": "#0A0C10", "sidebar": "#0D0F15", "card": "#161B27",
               "card_hover": "#1D2432", "console": "#090B0F", "border": "#2A3145",
               "accent": "#7C6CFF"},
    "ocean": {"name": "Океан",
              "bg": "#070C14", "sidebar": "#0A1120", "card": "#121C2C",
              "card_hover": "#1A2739", "console": "#050810", "border": "#24344A",
              "accent": "#38B6FF"},
    "malachite": {"name": "Малахит",
                  "bg": "#070D0A", "sidebar": "#0A120D", "card": "#12201A",
                  "card_hover": "#1A2C23", "console": "#050907", "border": "#24382D",
                  "accent": "#2BD576"},
    "magma": {"name": "Магма",
              "bg": "#120C08", "sidebar": "#160F0A", "card": "#221812",
              "card_hover": "#2C2018", "console": "#0E0906", "border": "#3C2C1E",
              "accent": "#FF8A3D"},
    "mono": {"name": "Монохром",
             "bg": "#0D0D0F", "sidebar": "#111114", "card": "#1A1A1E",
             "card_hover": "#232329", "console": "#0A0A0C", "border": "#2E2E36",
             "accent": "#E8E8F0"},
}

BG_DIR = os.path.join(os.path.dirname(CONFIG_PATH), "bg")


def apply_theme(preset: str, accent: str = None):
    """Ставит палитру темы в глобальные константы оформления."""
    global BG, SIDEBAR, CARD, CARD_HOVER, CONSOLE_BG, BORDER
    global ACCENT, ACCENT_HOVER, ACTIVE_BG, ACTIVE_HOVER, ACTIVE_TEXT
    global ACCENT_DIM, ACCENT_BRIGHT, BTN_HOVER
    t = THEME_PRESETS.get(preset) or THEME_PRESETS["violet"]
    BG = t["bg"]
    SIDEBAR = t["sidebar"]
    CARD = t["card"]
    CARD_HOVER = t["card_hover"]
    CONSOLE_BG = t["console"]
    BORDER = t["border"]
    ACCENT = accent or t["accent"]
    # производные оттенки акцента — автоматически под новый цвет
    ACCENT_HOVER = lerp_color(ACCENT, "#000000", 0.18)
    ACTIVE_TEXT = lerp_color(ACCENT, "#FFFFFF", 0.28)
    ACTIVE_BG = lerp_color(BG, ACCENT, 0.14)
    ACTIVE_HOVER = lerp_color(BG, ACCENT, 0.19)
    ACCENT_DIM = lerp_color(BG, ACCENT, 0.12)
    ACCENT_BRIGHT = lerp_color(BG, ACCENT, 0.22)
    BTN_HOVER = lerp_color(CARD_HOVER, "#FFFFFF", 0.10)


class CircleButton(tk.Frame):
    """Идеально круглая кнопка запуска/остановки.

    Рисуется на tk.Canvas в реальных пикселях — не зависит от масштаба DPI,
    поэтому всегда круглая. Имеет дыхание подсветки, эффект нажатия и
    плавную смену цвета при старте/остановке.
    """

    def __init__(self, master, command=None, size=118, ring=16):
        r_total = size + ring * 2
        super().__init__(master, width=r_total, height=r_total, bg=CARD,
                         bd=0, highlightthickness=0)
        self.pack_propagate(False)
        self.command = command
        self.running = False
        self._hover = False
        self._press = 0.0
        self._t = 0.0
        self.canvas = tk.Canvas(self, width=r_total, height=r_total, bg=CARD,
                                highlightthickness=0, bd=0, cursor="hand2")
        self.canvas.pack()
        self._glow = self.canvas.create_oval(
            0, 0, r_total - 1, r_total - 1, fill=ACCENT_DIM, outline="")
        # тонкое светящееся кольцо между подсветкой и кнопкой
        self._ring = self.canvas.create_oval(
            ring / 2, ring / 2, r_total - ring / 2 - 1, r_total - ring / 2 - 1,
            fill="", outline=lerp_color(ACCENT_DIM, ACCENT, 0.55), width=2)
        self._btn = self.canvas.create_oval(
            ring, ring, r_total - ring - 1, r_total - ring - 1,
            fill=ACCENT, outline="")
        self._glyph = self.canvas.create_text(
            r_total / 2, r_total / 2, text="▶", fill="#FFFFFF",
            font=("Segoe UI", 40, "bold"))
        self.canvas.bind("<Enter>", lambda e: self._set_hover(True))
        self.canvas.bind("<Leave>", lambda e: self._set_hover(False))
        self.canvas.bind("<Button-1>", self._on_click)
        self.after(45, self._tick)

    def _set_hover(self, v):
        self._hover = v
        try:
            self.canvas.config(cursor="hand2" if v else "")
        except tk.TclError:
            pass

    def set_running(self, running):
        self.running = bool(running)
        try:
            self.canvas.itemconfig(
                self._glyph, text="■" if self.running else "▶",
                font=("Segoe UI", 33 if self.running else 40, "bold"))
        except tk.TclError:
            pass

    def _on_click(self, _event):
        self._press = 1.0
        if self.command:
            self.command()

    def _tick(self):
        try:
            self._t += 0.11
            s = (math.sin(self._t) + 1) / 2
            self._press *= 0.80
            if self.running:
                glow = lerp_color(TINT_RED, RED_DIM, s)
                base = "#E04553" if self._hover else RED
            else:
                glow = lerp_color(ACCENT_DIM, ACCENT_BRIGHT, s)
                base = ACCENT_HOVER if self._hover else ACCENT
            self.canvas.itemconfig(self._glow, fill=glow)
            self.canvas.itemconfig(self._ring, outline=lerp_color(
                glow, lighten(base, self._press * 46), 0.55))
            self.canvas.itemconfig(self._btn, fill=lighten(base, self._press * 46))
        except tk.TclError:
            return
        self.after(45, self._tick)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ------------------------------------------------------------------ системное


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin():
    params = " ".join(f'"{a}"' for a in sys.argv if a != "--no-elevate")
    rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
    return rc > 32


def enable_dark_titlebar(hwnd):
    """Тёмный заголовок окна на Windows 10/11."""
    if not hwnd:
        return
    try:
        val = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            ctypes.c_void_p(hwnd), 20, ctypes.byref(val), ctypes.sizeof(val))
    except Exception:
        pass


def decode_console(raw: bytes) -> str:
    for enc in ("utf-8", "cp866", "cp1251"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def find_winws(zapret_dir: str):
    for rel in (os.path.join("bin", "winws.exe"),
                os.path.join("bin", "win64", "winws.exe"),
                os.path.join("bin", "win32", "winws.exe")):
        p = os.path.join(zapret_dir, rel)
        if os.path.isfile(p):
            return p
    for root, _dirs, files in os.walk(zapret_dir):
        for f in files:
            if f.lower() == "winws.exe":
                return os.path.join(root, f)
    return None


def detect_zapret_dir(cfg_dir: str = None):
    candidates = []
    if cfg_dir:
        candidates.append(cfg_dir)
    home = os.path.expanduser("~")
    for base in (os.path.join(home, "Desktop"), home,
                 os.path.join(home, "Documents"), os.path.join(home, "Downloads")):
        for name in ("запрет", "zapret"):
            candidates.append(os.path.join(base, name))
    for letter in "CDEFGH":
        for name in ("запрет", "zapret"):
            candidates.append(f"{letter}:\\{name}")
    for c in candidates:
        if os.path.isdir(c) and find_winws(c):
            return c
    return None

# ------------------------------------------------------------------ конфиг


def load_config():
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(cfg):
    try:
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

# ------------------------------------------------------------------ разбор батников


RE_CONTINUATION = re.compile(r"\s*\^\s*$")
RE_START = re.compile(r'^\s*start\s+"[^"]*"\s+(?:/min\s+)?"([^"]*winws\.exe)"\s*(.*)$', re.I)
RE_QUOTED_EXE = re.compile(r'^\s*"([^"]*winws\.exe)"\s*(.*)$', re.I)
RE_WINWS_LINE = re.compile(r"^\s*%winws%\s+(.+)$", re.I)
RE_WINWS_SET = re.compile(r"^\s*set\s+winws\d*=(.+winws\.exe.+)$", re.I)
RE_MENU = re.compile(r"^\s*echo\s+(\d{1,2})\s*-\s*(.+?)\s*$", re.I)


def game_filter_ports(zapret_dir: str):
    """Порты игрового фильтра — логика service.bat :game_switch_status."""
    flag = os.path.join(zapret_dir, "utils", "game_filter.enabled")
    mode = None
    try:
        with open(flag, encoding="utf-8", errors="replace") as f:
            mode = f.readline().strip()
    except OSError:
        pass
    if mode and mode.lower() == "all":
        return "1024-65535", "1024-65535"
    if mode and mode.lower() == "tcp":
        return "1024-65535", "12"
    if mode:
        return "12", "1024-65535"
    return "12", "12"


def resolve_vars(args: str, zapret_dir: str):
    gtcp, gudp = game_filter_ports(zapret_dir)
    bin_dir = os.path.join(zapret_dir, "bin") + "\\"
    lists_dir = os.path.join(zapret_dir, "lists") + "\\"
    subs = {
        "bin": bin_dir, "lists": lists_dir,
        "gamefiltertcp": gtcp, "gamefilterudp": gudp,
        "bin_path": bin_dir, "lists_path": lists_dir,
        "~dp0": zapret_dir + "\\",
    }

    def repl(m):
        return subs.get(m.group(1).lower(), m.group(0))

    return re.sub(r"%([^%]+)%", repl, args)


def parse_bat_file(path: str, zapret_dir: str):
    try:
        text = open(path, "rb").read().decode("utf-8", errors="replace")
    except OSError:
        return []

    logical, pending = [], ""
    for line in text.splitlines():
        pending = (pending + " " + line.strip()) if pending else line
        if RE_CONTINUATION.search(pending):
            pending = RE_CONTINUATION.sub("", pending)
            continue
        logical.append(pending)
        pending = ""
    if pending:
        logical.append(pending)

    strategies = []
    for line in logical:
        m = RE_START.match(line) or RE_QUOTED_EXE.match(line)
        if m and m.group(2).strip():
            strategies.append(("", resolve_vars(m.group(2).strip(), zapret_dir)))
    if strategies:
        return strategies

    menu, args_list = {}, []
    for line in logical:
        m = RE_MENU.match(line)
        if m:
            menu[int(m.group(1))] = m.group(2)
            continue
        m = RE_WINWS_LINE.match(line)
        if m:
            args_list.append(m.group(1).strip())
            continue
        m = RE_WINWS_SET.match(line)
        if m:
            val = m.group(1).strip()
            idx = val.lower().find("winws.exe")
            rest = val[idx + len("winws.exe"):].strip().strip('"')
            if rest:
                args_list.append(rest)
    for i, args in enumerate(args_list):
        strategies.append((menu.get(i, ""), resolve_vars(args, zapret_dir)))
    return strategies


SKIP_BATS = ("service.bat",)


def scan_strategies(zapret_dir: str):
    result = []
    try:
        bats = sorted(f for f in os.listdir(zapret_dir) if f.lower().endswith(".bat"))
    except OSError:
        bats = []
    for bat in bats:
        if bat.lower() in SKIP_BATS:
            continue
        strats = parse_bat_file(os.path.join(zapret_dir, bat), zapret_dir)
        stem = bat[:-4]
        for i, (menu_name, args) in enumerate(strats):
            name = menu_name or (stem if len(strats) == 1 else f"{stem} #{i + 1}")
            result.append((bat, name, args))
    return result

# --------------------------------------------- уборка артефактов сервисов (v1.2)

MARK_BEGIN = "# >>> Zapret GUI >>>"
MARK_END = "# <<< Zapret GUI <<<"


def remove_service_artifacts(zapret_dir: str):
    """Удалить ранее дописанные домены Telegram/Roblox из списков обхода."""
    if not zapret_dir:
        return
    lists_dir = os.path.join(zapret_dir, "lists")
    user_list = os.path.join(lists_dir, "list-general-user.txt")
    try:
        with open(user_list, encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
    except OSError:
        lines = []
    cleaned, skip, changed = [], False, False
    for ln in lines:
        if ln.strip() == MARK_BEGIN:
            skip, changed = True, True
            continue
        if ln.strip() == MARK_END:
            skip, changed = False, True
            continue
        if not skip:
            cleaned.append(ln)
    if changed:
        try:
            with open(user_list, "w", encoding="utf-8") as f:
                f.write("\n".join(cleaned).rstrip() + "\n")
        except OSError:
            pass
    ipset = os.path.join(lists_dir, "ipset-telegram.txt")
    try:
        if os.path.isfile(ipset):
            os.remove(ipset)
    except OSError:
        pass

# ------------------------------------------------------------------ автозапуск


def autostart_cmd():
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --autorun'
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    if os.path.isfile(pythonw):
        return f'"{pythonw}" "{os.path.abspath(__file__)}" --autorun'
    return f'"{sys.executable}" "{os.path.abspath(__file__)}" --autorun'


def autostart_state():
    rc = subprocess.run(["schtasks", "/Query", "/TN", AUTOSTART_TASK],
                        capture_output=True, creationflags=CREATE_NO_WINDOW)
    return rc.returncode == 0


def autostart_set(enabled: bool, cmd_line: str = None):
    if enabled:
        subprocess.run(
            ["schtasks", "/Create", "/F", "/TN", AUTOSTART_TASK,
             "/TR", cmd_line or autostart_cmd(), "/SC", "ONLOGON", "/RL", "HIGHEST"],
            capture_output=True, creationflags=CREATE_NO_WINDOW, check=True)
    else:
        subprocess.run(["schtasks", "/Delete", "/F", "/TN", AUTOSTART_TASK],
                       capture_output=True, creationflags=CREATE_NO_WINDOW)


def winws_already_running():
    rc = subprocess.run(["tasklist", "/FI", "IMAGENAME eq winws.exe"],
                        capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
    return "winws.exe" in (rc.stdout or "").lower()


def kill_foreign_winws():
    """Остановить чужие процессы winws (чтобы не было двух копий с пересечением фильтров)."""
    subprocess.run(["taskkill", "/IM", "winws.exe", "/F"],
                   capture_output=True, creationflags=CREATE_NO_WINDOW)


def cleanup_legacy():
    """Убрать артефакты старых версий (Zapret GUI): задачу планировщика."""
    subprocess.run(["schtasks", "/Delete", "/F", "/TN", LEGACY_TASK],
                   capture_output=True, creationflags=CREATE_NO_WINDOW)

# ------------------------------------------------------ встроенная копия zapret


def _local_data_dir():
    base = (os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
            or os.path.expanduser("~"))
    return os.path.join(base, "grom")


EMBEDDED_DIR = os.path.join(_local_data_dir(), "zapret")
BUNDLE_DIR = os.path.join(getattr(sys, "_MEIPASS",
                                  os.path.dirname(os.path.abspath(__file__))),
                          "zapret_bundle")
ICON_PATH = os.path.join(getattr(sys, "_MEIPASS",
                                 os.path.dirname(os.path.abspath(__file__))),
                         "grom_icon.ico")


def ensure_embedded_zapret():
    """Распаковать встроенную копию zapret в %LOCALAPPDATA%\\grom\\zapret.

    При обновлении версии grom копия распаковывается заново.
    Возвращает папку или None, если встроенной копии нет.
    """
    marker = os.path.join(EMBEDDED_DIR, "grom-version.txt")
    if find_winws(EMBEDDED_DIR) and os.path.isfile(marker):
        try:
            with open(marker, encoding="utf-8") as f:
                if f.read().strip() == VERSION:
                    return EMBEDDED_DIR
        except OSError:
            pass
    if not os.path.isdir(BUNDLE_DIR):
        return find_winws(EMBEDDED_DIR) and EMBEDDED_DIR
    shutil.rmtree(EMBEDDED_DIR, ignore_errors=True)
    try:
        shutil.copytree(BUNDLE_DIR, EMBEDDED_DIR)
        with open(marker, "w", encoding="utf-8") as f:
            f.write(VERSION)
    except OSError:
        pass
    return find_winws(EMBEDDED_DIR) and EMBEDDED_DIR


# ------------------------------------------------------------ счётчики железа


class _FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", wintypes.DWORD),
                ("dwHighDateTime", wintypes.DWORD)]


class _MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [("dwLength", wintypes.DWORD), ("dwMemoryLoad", wintypes.DWORD),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


def _ft2int(ft):
    return (ft.dwHighDateTime << 32) | ft.dwLowDateTime


def cpu_usage(prev):
    """Загрузка CPU в % и новое значение-счётчик для следующего вызова."""
    idle, kernel, user = _FILETIME(), _FILETIME(), _FILETIME()
    if not ctypes.windll.kernel32.GetSystemTimes(
            ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
        return None, prev
    cur = (_ft2int(idle), _ft2int(kernel) + _ft2int(user))
    if prev is None:
        return None, cur
    di = cur[0] - prev[0]
    dt = cur[1] - prev[1]
    if dt <= 0:
        return None, cur
    return max(0.0, min(100.0, 100.0 * (1.0 - di / dt))), cur


def ram_info():
    """(занято %, занято ГБ, всего ГБ)"""
    m = _MEMORYSTATUSEX()
    m.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
        return None
    total = m.ullTotalPhys / 1024 ** 3
    used = (m.ullTotalPhys - m.ullAvailPhys) / 1024 ** 3
    return m.dwMemoryLoad, used, total


def gpu_usage(pdh_state):
    """Суммарная загрузка GPU в % через PDH-счётчики. pdh_state — dict для
    переиспользования сессии; возвращает (значение или None, новое состояние)."""
    st = pdh_state or {}
    try:
        pdh = ctypes.WinDLL("pdh.dll")
        if "h" not in st:
            h = ctypes.c_void_p()
            if pdh.PdhOpenQueryW(None, 0, ctypes.byref(h)) != 0:
                return None, st
            st["h"] = h
            st["pdh"] = pdh
        pdh = st["pdh"]
        if "c" not in st:
            c = ctypes.c_void_p()
            if pdh.PdhAddEnglishCounterW(
                    st["h"], r"\GPU Engine(*)\Utilization Percentage",
                    0, ctypes.byref(c)) != 0:
                return None, st
            st["c"] = c
        pdh.PdhCollectQueryData(st["h"])
        time.sleep(0.25)
        pdh.PdhCollectQueryData(st["h"])

        size, count = ctypes.c_uint(0), ctypes.c_uint(0)
        buf = ctypes.c_void_p()
        PDH_FMT_DOUBLE, PDH_MORE_DATA = 0x200, 0x800007D2
        r = pdh.PdhGetFormattedCounterArrayW(
            st["c"], PDH_FMT_DOUBLE, ctypes.byref(size), ctypes.byref(count),
            ctypes.byref(buf), None)
        if (r & 0xFFFFFFFF) != PDH_MORE_DATA or size.value == 0:
            return None, st
        raw = ctypes.create_string_buffer(size.value)
        r = pdh.PdhGetFormattedCounterArrayW(
            st["c"], PDH_FMT_DOUBLE, ctypes.byref(size), ctypes.byref(count),
            ctypes.byref(raw), None)
        if r != 0 or count.value == 0:
            return None, st

        class FmtVal(ctypes.Structure):
            _fields_ = [("CStatus", wintypes.DWORD),
                        ("doubleValue", ctypes.c_double)]

        class FmtItem(ctypes.Structure):
            _fields_ = [("szName", wintypes.LPWSTR),
                        ("Value", FmtVal)]

        arr = ctypes.cast(raw, ctypes.POINTER(FmtItem))
        total = sum(arr[i].Value.doubleValue for i in range(count.value))
        return max(0.0, min(100.0, total)), st
    except Exception:
        return None, st

# ------------------------------------------------------------------ приложение


class App(ctk.CTk):
    def __init__(self, autorun: bool = False):
        super().__init__()
        self.proc = None
        self.strategies = []          # [{source, name, args}]
        self.selected = None
        self.autorun_mode = autorun
        self._pulse_t = 0.0
        self._shown_running = False
        self._current_page = None
        self.cfg = load_config()
        self.cfg.pop("services", None)
        self._radius_widgets = []
        self._init_theme()
        self._log_lines = []
        self._bg_label = None
        self._bg_photo = None
        self._bg_src = None
        self._bg_job = None

        self.title(f"{APP_NAME} · v{VERSION}")
        self.geometry("1020x720")
        self.minsize(940, 640)
        self.configure(fg_color=BG)
        try:
            if os.path.isfile(ICON_PATH):
                self.iconbitmap(ICON_PATH)
        except Exception:
            pass

        self.zapret_dir = detect_zapret_dir(self.cfg.get("zapret_dir"))
        if not self.zapret_dir:
            self.zapret_dir = ensure_embedded_zapret()
        self.winws_exe = find_winws(self.zapret_dir) if self.zapret_dir else None
        cleanup_legacy()
        remove_service_artifacts(self.zapret_dir)

        # состояние счётчиков железа
        self._cpu_prev = None
        self._pdh_state = {}
        self._hw = {"cpu": None, "gpu": None, "ram": None}
        self._hw_close = False

        # состояние VPN (подписка, серверы, подключение)
        vcfg = self.cfg.get("vpn") or {}
        self._vpn_sub_url = str(vcfg.get("sub_url") or "")
        self._vpn_sel_link = str(vcfg.get("selected_link") or "")
        self._vpn_servers = []        # записи parse_link
        self._vpn_pings = {}          # link -> мс или None
        self._vpn_rows = []           # (frame, dot, ping_label, rec)
        self._vpn_proc = None
        self._vpn_port = None
        self._vpn_proxy_state = None
        self._vpn_busy = False
        self._vpn_updated = None      # время последнего обновления

        self._build_sidebar()
        self._build_pages()
        self.show_page("home")

        self._reload_strategies()
        self._poll_process()
        self._animate_pulse()
        threading.Thread(target=self._hw_loop, daemon=True).start()
        self.after(1200, self._hw_update)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.after(150, self._apply_dark_titlebar)

        if not is_admin() and not autorun:
            self.after(400, self._ask_elevation)
        if autorun:
            self.after(900, self._autorun_start)
        elif self.cfg.get("autorun_bypass"):
            self.after(1500, self._auto_bypass_start)

    def _apply_dark_titlebar(self):
        try:
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            enable_dark_titlebar(hwnd)
        except Exception:
            pass

    # ---------------------------------------------------------------- сайдбар

    # ---- визуальные помощники

    @staticmethod
    def _load_icon_ctk(size):
        """Иконка grom как CTkImage нужного размера (или None)."""
        try:
            if os.path.isfile(ICON_PATH):
                src = Image.open(ICON_PATH).convert("RGBA").resize(
                    (size, size), Image.LANCZOS)
                return ctk.CTkImage(light_image=src, dark_image=src,
                                    size=(size, size))
        except Exception:
            pass
        return None

    @staticmethod
    def _grad_bar_image(w, h, color):
        """Неоновая линейка: яркая в центре, плавно гаснет к краям."""
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        r, g, b = hex_to_rgb(color)
        px = img.load()
        for x in range(w):
            s = math.sin(math.pi * x / max(1, w - 1))
            a = int(255 * (max(0.0, s) ** 1.3))
            for y in range(h):
                px[x, y] = (r, g, b, a)
        return ctk.CTkImage(light_image=img, dark_image=img, size=(w, h))

    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=244, fg_color=SIDEBAR, corner_radius=0)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        # тонкая линия-разделитель справа
        ctk.CTkFrame(self.sidebar, width=1, fg_color=BORDER).pack(
            side="right", fill="y")

        # ---- логотип
        logo = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        logo.pack(fill="x", padx=22, pady=(30, 0))
        badge = ctk.CTkFrame(logo, width=46, height=46, fg_color=CARD_HOVER,
                             corner_radius=14, border_width=1,
                             border_color=BORDER)
        badge.pack(side="left")
        badge.pack_propagate(False)
        self.logo_badge = badge
        self._logo_image = self._load_icon_ctk(34)
        if self._logo_image:
            self.logo_badge_glyph = ctk.CTkLabel(badge, image=self._logo_image, text="")
            self.logo_badge_glyph.pack(expand=True)
        else:
            self.logo_badge_glyph = ctk.CTkLabel(badge, text="⚡",
                                                 font=ctk.CTkFont(size=21),
                                                 text_color="#FFFFFF")
            self.logo_badge_glyph.pack(expand=True)
        names = ctk.CTkFrame(logo, fg_color="transparent")
        names.pack(side="left", padx=(12, 0))
        self.logo_name = ctk.CTkLabel(names, text="grom",
                                      font=ctk.CTkFont(size=22, weight="bold"),
                                      text_color=TEXT)
        self.logo_name.pack(anchor="w")
        self.logo_sub = ctk.CTkLabel(names, text=f"обходник · v{VERSION}",
                                     font=ctk.CTkFont(size=10),
                                     text_color=ACTIVE_TEXT)
        self.logo_sub.pack(anchor="w")

        # ---- разделитель и заголовок раздела
        ctk.CTkFrame(self.sidebar, height=1, fg_color=BORDER).pack(
            fill="x", padx=20, pady=(22, 16))
        self.menu_caption = ctk.CTkLabel(self.sidebar, text="М Е Н Ю", font=ctk.CTkFont(
            size=10, weight="bold"), text_color="#4A5165")
        self.menu_caption.pack(anchor="w", padx=28, pady=(0, 10))

        # ---- пункты навигации с индикатором активного раздела
        self.nav_buttons = {}
        self.nav_indicators = {}
        self.nav_chips = {}
        self.nav_chip_glyphs = {}
        for key, label, icon in (("home", "Главная", "⌂"),
                                 ("autostart", "Автозапуск", "↻"),
                                 ("vpn", "VPN", "◉"),
                                 ("games", "Игры", "⌘"),
                                 ("theme", "Тема", "◑"),
                                 ("about", "О программе", "ⓘ")):
            wrap = ctk.CTkFrame(self.sidebar, fg_color="transparent")
            wrap.pack(fill="x", padx=14, pady=3)
            ind = ctk.CTkFrame(wrap, width=4, height=24, corner_radius=2,
                               fg_color="transparent")
            ind.pack(side="left", padx=(5, 9))
            chip = ctk.CTkFrame(wrap, width=28, height=28, corner_radius=8,
                                fg_color="transparent")
            chip.pack(side="left", padx=(0, 9))
            chip.pack_propagate(False)
            glyph = ctk.CTkLabel(chip, text=icon, text_color=MUTED,
                                 font=ctk.CTkFont(size=13))
            glyph.pack(expand=True)
            b = ctk.CTkButton(wrap, text=label, anchor="w",
                              height=44, corner_radius=12,
                              fg_color="transparent", hover_color=CARD_HOVER,
                              text_color=MUTED, font=ctk.CTkFont(size=13),
                              command=lambda k=key: self.show_page(k))
            b.pack(fill="x", expand=True)
            self.nav_indicators[key] = ind
            self.nav_buttons[key] = b
            self.nav_chips[key] = chip
            self.nav_chip_glyphs[key] = glyph

        # ---- карточка статуса внизу
        bottom = ctk.CTkFrame(self.sidebar, fg_color=CARD, corner_radius=14,
                              border_width=1, border_color=BORDER)
        bottom.pack(side="bottom", fill="x", padx=16, pady=18)
        self.status_card = bottom
        row = ctk.CTkFrame(bottom, fg_color="transparent")
        row.pack(fill="x", padx=15, pady=(14, 0))
        self.side_status_dot = ctk.CTkLabel(row, text="●", text_color=MUTED,
                                            font=ctk.CTkFont(size=10))
        self.side_status_dot.pack(side="left")
        self.side_status_text = ctk.CTkLabel(row, text="winws не запущен",
                                             text_color=MUTED,
                                             font=ctk.CTkFont(size=12))
        self.side_status_text.pack(side="left", padx=(8, 0))
        ctk.CTkFrame(bottom, height=1, fg_color=BORDER).pack(
            fill="x", padx=15, pady=11)
        self.admin_label = ctk.CTkLabel(
            bottom,
            text="✓ права администратора" if is_admin() else "⚠ нужны права админа",
            text_color=GREEN if is_admin() else AMBER,
            font=ctk.CTkFont(size=11, weight="bold"))
        self.admin_label.pack(anchor="w", padx=15, pady=(0, 14))
        self.after(120, self._materialize_sidebar)

    def _materialize_sidebar(self):
        """Плавное «проявление» элементов сайдбара при старте."""
        seq = [(0, self.logo_badge, "fg_color", CARD_HOVER),
               (70, self.logo_name, "text_color", TEXT),
               (140, self.logo_sub, "text_color", ACTIVE_TEXT),
               (210, self.menu_caption, "text_color", "#4A5165")]
        for i, (key, b) in enumerate(self.nav_buttons.items()):
            active = key == self._current_page
            seq.append((280 + i * 70, b, "text_color",
                        ACTIVE_TEXT if active else MUTED))
            seq.append((280 + i * 70, self.nav_chips[key], "fg_color",
                        ACCENT if active else "transparent"))
            seq.append((280 + i * 70, self.nav_chip_glyphs[key], "text_color",
                        "#FFFFFF" if active else MUTED))
        seq.append((530, self.status_card, "fg_color", CARD))
        seq.append((560, self.side_status_text, "text_color", MUTED))
        seq.append((590, self.admin_label, "text_color",
                    GREEN if is_admin() else AMBER))
        for delay, w, prop, target in seq:
            self._fade_in(w, prop, target, delay)

    def _fade_in(self, widget, prop, target, delay=0, ms=430, steps=15):
        """Показывает элемент, плавно меняя цвет из «сливания с фоном»."""
        start = SIDEBAR

        def begin():
            def step(i=0):
                t = min(1, i / steps)
                e = 1 - (1 - t) ** 3
                try:
                    widget.configure(**{prop: lerp_color(start, target, e)})
                except tk.TclError:
                    return
                if t < 1:
                    self.after(max(1, ms // steps), step, i + 1)
            step()
        self.after(delay, begin)

    def _fade(self, widget, to, ms=340, steps=14):
        """Плавный переход свойств (цветов) у виджета."""
        frm = {}
        for p in to:
            try:
                v = str(widget.cget(p))
            except Exception:
                v = ""
            frm[p] = v if v.startswith("#") else to[p]

        def step(i=0):
            t = min(1, i / steps)
            e = 1 - (1 - t) ** 2
            for p, v in to.items():
                try:
                    widget.configure(**{p: lerp_color(frm[p], v, e)})
                except tk.TclError:
                    pass
            if t < 1:
                self.after(max(1, ms // steps), step, i + 1)
        step()

    # ---------------------------------------------------------------- страницы

    def _build_pages(self):
        self.pages = {}
        self.page_hosts = {}
        self.content = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self.content.pack(side="left", fill="both", expand=True)
        for key in ("home", "autostart", "vpn", "games", "theme", "about"):
            # прозрачный хост: через него работает слайд-анимация,
            # а снизу (если задан) видна картинка-фон
            self.page_hosts[key] = ctk.CTkFrame(self.content,
                                                fg_color="transparent",
                                                corner_radius=0)
            self.pages[key] = ctk.CTkFrame(self.page_hosts[key],
                                           fg_color="transparent",
                                           corner_radius=0)
            self.pages[key].pack(fill="both", expand=True, padx=30, pady=26)
        self._build_home()
        self._build_autostart()
        self._build_vpn()
        self._build_games()
        self._build_theme()
        self._build_about()
        self._apply_background()
        self.content.bind("<Configure>", self._on_content_resize)

    def show_page(self, key):
        if key == self._current_page:
            return
        self._current_page = key
        for k, page in self.pages.items():
            self.page_hosts[k].place_forget()
            btn = self.nav_buttons[k]
            ind = self.nav_indicators[k]
            chip = self.nav_chips[k]
            glyph = self.nav_chip_glyphs[k]
            if k == key:
                ind.configure(fg_color=ACCENT, height=6)
                self._anim_indicator(ind)
                btn.configure(fg_color=ACTIVE_BG, hover_color=ACTIVE_BG,
                              text_color=ACTIVE_TEXT,
                              font=ctk.CTkFont(size=13, weight="bold"))
                chip.configure(fg_color=ACCENT)
                glyph.configure(text_color="#FFFFFF")
            else:
                ind.configure(fg_color="transparent", height=24)
                btn.configure(fg_color="transparent", hover_color=CARD_HOVER,
                              text_color=MUTED, font=ctk.CTkFont(size=13))
                chip.configure(fg_color="transparent")
                glyph.configure(text_color=MUTED)
        host = self.page_hosts[key]
        host.place(relx=0, rely=0, relwidth=1, relheight=1, x=26)
        # мягкий выезд страницы справа
        start = 26
        steps = 13

        def slide(i=1):
            t = min(1, i / steps)
            e = 1 - (1 - t) ** 3
            try:
                host.place_configure(x=int(start * (1 - e)))
            except tk.TclError:
                return
            if t < 1:
                self.after(16, slide, i + 1)
        slide()

    def _anim_indicator(self, ind, steps=10):
        """Индикатор активного пункта меню плавно вырастает по высоте."""
        def step(i=1):
            t = min(1, i / steps)
            e = 1 - (1 - t) ** 2
            try:
                ind.configure(height=int(6 + 18 * e))
            except tk.TclError:
                return
            if t < 1:
                self.after(18, step, i + 1)
        step()

    # ---------------------------------------------------------------- главная

    def _build_home(self):
        p = self.pages["home"]
        head = ctk.CTkFrame(p, fg_color="transparent")
        head.pack(fill="x")
        ctk.CTkLabel(head, text="Главная", font=ctk.CTkFont(size=25, weight="bold"),
                     text_color=TEXT).pack(side="left")
        self.status_pill = ctk.CTkFrame(head, fg_color=TINT_AMBER, corner_radius=30,
                                        border_width=1, border_color="#3D3418")
        self.status_pill.pack(side="right")
        self.status_dot = ctk.CTkLabel(self.status_pill, text="●", text_color=AMBER,
                                       font=ctk.CTkFont(size=10))
        self.status_dot.pack(side="left", padx=(12, 4), pady=5)
        self.status_text = ctk.CTkLabel(self.status_pill, text="не запущен",
                                        text_color=AMBER,
                                        font=ctk.CTkFont(size=12, weight="bold"))
        self.status_text.pack(side="left", padx=(0, 12), pady=5)

        # ---- hero-карточка
        hero = ctk.CTkFrame(p, fg_color=CARD, corner_radius=RADIUS, border_width=1,
                            border_color=BORDER)
        hero.pack(fill="x", pady=(20, 0))
        ctk.CTkLabel(hero, image=self._grad_bar_image(220, 5, ACCENT),
                     text="").pack(pady=(14, 0))

        row1 = ctk.CTkFrame(hero, fg_color="transparent")
        row1.pack(fill="x", padx=24, pady=(16, 0))
        icon = ctk.CTkFrame(row1, width=52, height=52, fg_color="transparent")
        icon.pack(side="left")
        icon.pack_propagate(False)
        hero_icon = self._load_icon_ctk(52)
        if hero_icon:
            ctk.CTkLabel(icon, image=hero_icon, text="").pack(expand=True)
        else:
            icon.configure(fg_color=ACCENT, corner_radius=13)
            ctk.CTkLabel(icon, text="⚡", font=ctk.CTkFont(size=22),
                         text_color="#FFFFFF").pack(expand=True)
        meta = ctk.CTkFrame(row1, fg_color="transparent")
        meta.pack(side="left", padx=(14, 0))
        ctk.CTkLabel(meta, text="СТРАТЕГИЯ ОБХОДА", font=ctk.CTkFont(
            size=10, weight="bold"), text_color=MUTED).pack(anchor="w")
        self.hero_name = ctk.CTkLabel(meta, text="— не выбрана —",
                                      font=ctk.CTkFont(size=17, weight="bold"),
                                      text_color=TEXT, anchor="w")
        self.hero_name.pack(anchor="w")
        self.hero_source = ctk.CTkLabel(meta, text="", font=ctk.CTkFont(size=11),
                                        text_color=MUTED, anchor="w")
        self.hero_source.pack(anchor="w")
        self.btn_settings = ctk.CTkButton(
            row1, text="⚙", width=44, height=44, corner_radius=11,
            fg_color=CARD_HOVER, hover_color=BTN_HOVER, border_width=1,
            border_color=BORDER, text_color=TEXT, font=ctk.CTkFont(size=17),
            command=self._open_strategy_editor)
        self.btn_settings.pack(side="right")

        # ---- круглая кнопка запуска/остановки (настоящий круг на Canvas)
        ctrl = ctk.CTkFrame(hero, fg_color="transparent", height=196)
        ctrl.pack(fill="x", pady=(20, 0))
        ctrl.pack_propagate(False)
        self.power_btn = CircleButton(ctrl, command=self._toggle_power)
        self.power_btn.place(relx=0.5, y=88, anchor="center")
        self.power_caption = ctk.CTkLabel(
            ctrl, text="запустить обход", font=ctk.CTkFont(size=13, weight="bold"),
            text_color=MUTED)
        self.power_caption.place(relx=0.5, y=172, anchor="n")

        # ---- автозапуск обхода при открытии
        abrow = ctk.CTkFrame(hero, fg_color="transparent")
        abrow.pack(fill="x", pady=(4, 0))
        self.auto_bypass = ctk.CTkSwitch(
            abrow, text="запускать обход при открытии программы",
            font=ctk.CTkFont(size=12), text_color=MUTED, progress_color=ACCENT,
            button_color=ACCENT, button_hover_color=ACCENT_HOVER,
            command=self._toggle_auto_bypass)
        self.auto_bypass.pack(side="top")
        if self.cfg.get("autorun_bypass"):
            self.auto_bypass.select()
        ctk.CTkFrame(hero, height=16, fg_color="transparent").pack()

        # ---- папка
        dirbar = ctk.CTkFrame(p, fg_color="transparent")
        dirbar.pack(fill="x", pady=(14, 0))
        ctk.CTkLabel(dirbar, text="Папка zapret:", text_color=MUTED,
                     font=ctk.CTkFont(size=12)).pack(side="left")
        self.dir_entry = ctk.CTkEntry(dirbar, height=34, corner_radius=9,
                                      border_color=BORDER, fg_color=CARD,
                                      text_color=TEXT)
        self.dir_entry.pack(side="left", fill="x", expand=True, padx=10)
        if self.zapret_dir:
            self.dir_entry.insert(0, self.zapret_dir)
        ctk.CTkButton(dirbar, text="Обзор…", width=92, height=34, corner_radius=9,
                      fg_color=CARD_HOVER, hover_color=BTN_HOVER, border_width=1,
                      border_color=BORDER, text_color=TEXT,
                      command=self._choose_dir).pack(side="left")
        ctk.CTkButton(dirbar, text="Применить", width=104, height=34, corner_radius=9,
                      fg_color=ACCENT, hover_color=ACCENT_HOVER,
                      command=self._apply_dir).pack(side="left", padx=(6, 0))

        # ---- лог
        log_card = ctk.CTkFrame(p, fg_color=CARD, corner_radius=RADIUS, border_width=1,
                                border_color=BORDER)
        log_card.pack(fill="both", expand=True, pady=(14, 0))
        head2 = ctk.CTkFrame(log_card, fg_color="transparent")
        head2.pack(fill="x", padx=16, pady=(10, 0))
        for dot_color in (RED, AMBER, GREEN):
            ctk.CTkLabel(head2, text="●", text_color=dot_color,
                         font=ctk.CTkFont(size=9)).pack(side="left",
                                                        padx=(0, 6))
        ctk.CTkLabel(head2, text="ЛОГ WINWS", font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=MUTED).pack(side="left")
        ctk.CTkButton(head2, text="очистить", width=82, height=24, corner_radius=7,
                      fg_color="transparent", hover_color=CARD_HOVER, border_width=1,
                      border_color=BORDER, text_color=MUTED,
                      font=ctk.CTkFont(size=11),
                      command=self._clear_log).pack(side="right")
        self.log_box = ctk.CTkTextbox(log_card, fg_color=CONSOLE_BG, text_color="#9BD49B",
                                      font=ctk.CTkFont(family="Consolas", size=12),
                                      corner_radius=10, border_width=0)
        self.log_box.pack(fill="both", expand=True, padx=12, pady=(8, 12))
        self.log_box.configure(state="disabled")
        if not self._log_lines:
            self._log(f"{APP_NAME} v{VERSION}. Нажмите круглую кнопку, чтобы запустить обход.")

    # ---- редактор стратегии (вместо целой вкладки)

    def _open_strategy_editor(self):
        win = ctk.CTkToplevel(self)
        win.title("Настройка стратегии")
        win.geometry("760x460")
        win.configure(fg_color=BG)
        win.grab_set()
        win.after(100, lambda: enable_dark_titlebar(
            ctypes.windll.user32.GetParent(win.winfo_id())))
        try:
            if os.path.isfile(ICON_PATH):
                win.iconbitmap(ICON_PATH)
        except Exception:
            pass

        ctk.CTkLabel(win, text="Выбор стратегии", font=ctk.CTkFont(
            size=16, weight="bold"), text_color=TEXT).pack(anchor="w", padx=22,
                                                            pady=(18, 6))
        names = [s["name"] for s in self.strategies] or ["— нет стратегий —"]
        var = tk.StringVar(value=names[self.selected] if self.selected is not None
                           and self.strategies else names[0])
        menu = ctk.CTkOptionMenu(win, values=names, variable=var, height=36,
                                 corner_radius=10, fg_color=CARD_HOVER,
                                 button_color=ACCENT, button_hover_color=ACCENT_HOVER,
                                 dropdown_fg_color=CARD, dropdown_hover_color=CARD_HOVER,
                                 command=lambda _v: self._editor_select(names.index(_v)))
        menu.pack(fill="x", padx=22)

        ctk.CTkLabel(win, text="Аргументы winws (можно править)",
                     font=ctk.CTkFont(size=13), text_color=MUTED).pack(
            anchor="w", padx=22, pady=(14, 4))
        box = ctk.CTkTextbox(win, fg_color=CONSOLE_BG, text_color="#C8D0DC",
                             font=ctk.CTkFont(family="Consolas", size=11),
                             corner_radius=10)
        box.pack(fill="both", expand=True, padx=22)
        if self.selected is not None and self.strategies:
            box.insert("1.0", self.strategies[self.selected]["args"])

        def apply_edit():
            if self.selected is not None and self.strategies:
                self.strategies[self.selected]["args"] = box.get(
                    "1.0", "end").strip()
                self._log("Аргументы стратегии обновлены.")
            win.destroy()

        rowb = ctk.CTkFrame(win, fg_color="transparent")
        rowb.pack(fill="x", padx=22, pady=14)
        ctk.CTkButton(rowb, text="Применить", height=38, corner_radius=10,
                      fg_color=ACCENT, hover_color=ACCENT_HOVER,
                      command=apply_edit).pack(side="right")
        ctk.CTkButton(rowb, text="Отмена", height=38, corner_radius=10,
                      fg_color=CARD_HOVER, hover_color=BTN_HOVER,
                      border_width=1, border_color=BORDER, text_color=MUTED,
                      command=win.destroy).pack(side="right", padx=(0, 8))

    def _editor_select(self, idx):
        if 0 <= idx < len(self.strategies):
            self.select_strategy(idx)

    # ---------------------------------------------------------------- автозапуск

    def _build_autostart(self):
        p = self.pages["autostart"]
        ctk.CTkLabel(p, text="Автозапуск", font=ctk.CTkFont(size=25, weight="bold"),
                     text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(p, text="Обход вместе с входом в Windows — без лишних кликов",
                     font=ctk.CTkFont(size=13), text_color=MUTED).pack(
            anchor="w", pady=(4, 0))

        card = ctk.CTkFrame(p, fg_color=CARD, corner_radius=RADIUS, border_width=1,
                            border_color=BORDER)
        card.pack(fill="x", pady=(18, 0))
        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=22, pady=(18, 0))
        ib = ctk.CTkFrame(top, width=44, height=44, fg_color=ACTIVE_BG,
                          corner_radius=11)
        ib.pack(side="left")
        ib.pack_propagate(False)
        ctk.CTkLabel(ib, text="↻", font=ctk.CTkFont(size=20),
                     text_color=ACTIVE_TEXT).pack(expand=True)
        ctk.CTkLabel(top, text="Запуск при входе в систему",
                     font=ctk.CTkFont(size=17, weight="bold"),
                     text_color=TEXT).pack(side="left", padx=(13, 0))
        self.auto_switch = ctk.CTkSwitch(
            top, text="", width=40, progress_color=ACCENT,
            button_color=ACCENT, button_hover_color=ACCENT_HOVER,
            command=self._toggle_autostart)
        self.auto_switch.pack(side="right")
        if autostart_state():
            self.auto_switch.select()
        ctk.CTkLabel(card, text=(f"Создаётся задача планировщика Windows «{AUTOSTART_TASK}» — "
                                 "сохранённая стратегия запускается при входе\n"
                                 "в систему с правами администратора, без окон."),
                     text_color=MUTED, font=ctk.CTkFont(size=12), justify="left",
                     wraplength=720).pack(anchor="w", padx=22, pady=(12, 20))

        note = ctk.CTkFrame(p, fg_color=TINT_AMBER, corner_radius=14, border_width=1,
                            border_color="#3D3418")
        note.pack(fill="x", pady=(16, 0))
        ctk.CTkLabel(note, text=("ⓘ  На «Главной» есть отдельный переключатель «запускать обход "
                                 "при открытии программы» — он действует, только когда вы\n"
                                 "сами открываете grom. Оба переключателя независимы и дополняют "
                                 "друг друга."),
                     text_color=AMBER, font=ctk.CTkFont(size=12), justify="left",
                     wraplength=740).pack(anchor="w", padx=20, pady=14)

    def _toggle_autostart(self):
        try:
            enabled = self.auto_switch.get() == 1
            autostart_set(enabled)
            self._log(f"Автозапуск {'включён' if enabled else 'отключён'}.")
        except Exception as e:
            self.auto_switch.deselect()
            messagebox.showerror(APP_NAME, f"Ошибка автозапуска:\n{e}")

    # ---------------------------------------------------------------- игры

    def _build_games(self):
        p = self.pages["games"]
        ctk.CTkLabel(p, text="Игры", font=ctk.CTkFont(size=25, weight="bold"),
                     text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(p, text="Загрузка процессора, видеокарты и памяти "
                             "в реальном времени",
                     font=ctk.CTkFont(size=13), text_color=MUTED).pack(
            anchor="w", pady=(4, 0))

        # ---- загрузка железа
        card2 = ctk.CTkFrame(p, fg_color=CARD, corner_radius=RADIUS,
                             border_width=1, border_color=BORDER)
        card2.pack(fill="x", pady=(18, 0))
        ctk.CTkLabel(card2, text=" З А Г Р У З К А   П К ",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=MUTED).pack(anchor="w", padx=22, pady=(16, 10))
        self._hw_bars = {}
        for key, title in (("cpu", "процессор"), ("gpu", "видеокарта"),
                           ("ram", "память")):
            rw = ctk.CTkFrame(card2, fg_color="transparent")
            rw.pack(fill="x", padx=22, pady=(0, 6))
            ctk.CTkLabel(rw, text=title, width=90, anchor="w",
                         font=ctk.CTkFont(size=12), text_color=MUTED).pack(
                side="left")
            bar = ctk.CTkProgressBar(rw, height=14, progress_color=ACCENT,
                                     fg_color=BORDER)
            bar.pack(side="left", fill="x", expand=True, padx=10)
            bar.set(0)
            val = ctk.CTkLabel(rw, text="—", width=130, anchor="e",
                               font=ctk.CTkFont(size=12), text_color=TEXT)
            val.pack(side="left")
            self._hw_bars[key] = (bar, val)
        ctk.CTkFrame(card2, height=10, fg_color="transparent").pack()

    # ---- загрузка железа (фоновый поток + обновление виджетов)

    def _hw_loop(self):
        while not getattr(self, "_hw_close", False):
            cpu, self._cpu_prev = cpu_usage(self._cpu_prev)
            gpu, self._pdh_state = gpu_usage(self._pdh_state)
            ram = ram_info()
            self._hw = {"cpu": cpu, "gpu": gpu, "ram": ram}
            time.sleep(1.0)

    def _hw_update(self):
        try:
            hw = getattr(self, "_hw", {})
            cpu, gpu, ram = hw.get("cpu"), hw.get("gpu"), hw.get("ram")
            if cpu is not None:
                bar, val = self._hw_bars["cpu"]
                bar.set(cpu / 100.0)
                val.configure(text=f"{cpu:.0f}%")
            if gpu is not None:
                bar, val = self._hw_bars["gpu"]
                bar.set(gpu / 100.0)
                val.configure(text=f"{gpu:.0f}%")
            if ram is not None:
                pct, used, total = ram
                bar, val = self._hw_bars["ram"]
                bar.set(pct / 100.0)
                val.configure(text=f"{pct:.0f}% · {used:.1f}/{total:.0f} ГБ")
        except Exception:
            pass
        self.after(1000, self._hw_update)

    # ---------------------------------------------------------------- VPN

    def _build_vpn(self):
        p = self.pages["vpn"]
        head = ctk.CTkFrame(p, fg_color="transparent")
        head.pack(fill="x")
        ctk.CTkLabel(head, text="VPN", font=ctk.CTkFont(size=25, weight="bold"),
                     text_color=TEXT).pack(side="left")
        self.vpn_pill = ctk.CTkFrame(head, fg_color=CARD_HOVER, corner_radius=30,
                                     border_width=1, border_color=BORDER)
        self.vpn_pill.pack(side="right")
        self.vpn_status_dot = ctk.CTkLabel(self.vpn_pill, text="●",
                                           text_color=MUTED,
                                           font=ctk.CTkFont(size=10))
        self.vpn_status_dot.pack(side="left", padx=(12, 4), pady=5)
        self.vpn_status_text = ctk.CTkLabel(self.vpn_pill, text="не подключён",
                                            text_color=MUTED,
                                            font=ctk.CTkFont(size=12,
                                                             weight="bold"))
        self.vpn_status_text.pack(side="left", padx=(0, 12), pady=5)

        # ---- подписка
        card = ctk.CTkFrame(p, fg_color=CARD, corner_radius=RADIUS,
                            border_width=1, border_color=BORDER)
        card.pack(fill="x", pady=(18, 0))
        ctk.CTkLabel(card, text="П О Д П И С К А", font=ctk.CTkFont(
            size=10, weight="bold"), text_color=MUTED).pack(
            anchor="w", padx=22, pady=(16, 8))
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=22)
        self.vpn_sub_entry = ctk.CTkEntry(
            row, height=36, corner_radius=9, border_color=BORDER,
            fg_color=CONSOLE_BG, text_color=TEXT,
            placeholder_text="ссылка подписки (ключ от вашего VPN-сервиса)")
        self.vpn_sub_entry.pack(side="left", fill="x", expand=True)
        if self._vpn_sub_url:
            self.vpn_sub_entry.insert(0, self._vpn_sub_url)
        self.vpn_fetch_btn = ctk.CTkButton(
            row, text="обновить серверы", width=150, height=36, corner_radius=9,
            fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color=TEXT,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._vpn_fetch)
        self.vpn_fetch_btn.pack(side="left", padx=(10, 0))
        self.vpn_sub_hint = ctk.CTkLabel(card, font=ctk.CTkFont(size=11),
                                         text_color=MUTED, justify="left",
                                         anchor="w")
        self.vpn_sub_hint.pack(fill="x", padx=22, pady=(8, 16))
        self._vpn_update_hint()

        # ---- серверы
        card2 = ctk.CTkFrame(p, fg_color=CARD, corner_radius=RADIUS,
                             border_width=1, border_color=BORDER)
        card2.pack(fill="both", expand=True, pady=(14, 0))
        hrow = ctk.CTkFrame(card2, fg_color="transparent")
        hrow.pack(fill="x", padx=22, pady=(16, 6))
        ctk.CTkLabel(hrow, text="С Е Р В Е Р Ы", font=ctk.CTkFont(
            size=10, weight="bold"), text_color=MUTED).pack(side="left")
        self.vpn_ping_btn = ctk.CTkButton(
            hrow, text="проверить пинг", width=130, height=28, corner_radius=8,
            fg_color="transparent", hover_color=CARD_HOVER, border_width=1,
            border_color=BORDER, text_color=MUTED, font=ctk.CTkFont(size=11),
            command=self._vpn_ping_all)
        self.vpn_ping_btn.pack(side="right")
        self.vpn_count_label = ctk.CTkLabel(hrow, text="серверов: —",
                                            font=ctk.CTkFont(size=11),
                                            text_color=MUTED)
        self.vpn_count_label.pack(side="right", padx=(0, 12))
        self.vpn_list = ctk.CTkScrollableFrame(
            card2, fg_color="transparent", corner_radius=10)
        self.vpn_list.pack(fill="both", expand=True, padx=14, pady=(0, 8))

        # ---- подключение
        foot = ctk.CTkFrame(p, fg_color="transparent")
        foot.pack(fill="x", pady=(14, 0))
        self.vpn_sel_label = ctk.CTkLabel(foot, text="сервер не выбран",
                                          font=ctk.CTkFont(size=13),
                                          text_color=MUTED, anchor="w")
        self.vpn_sel_label.pack(side="left")
        self.vpn_btn = ctk.CTkButton(
            foot, text="подключить", width=190, height=42, corner_radius=11,
            fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color=TEXT,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._vpn_toggle)
        self.vpn_btn.pack(side="right")

        self._vpn_render_list()
        self._vpn_update_sel_label()

    # ---- обновление подписки

    def _vpn_update_hint(self):
        try:
            if self._vpn_updated and self._vpn_servers:
                t = self._vpn_updated.strftime("%H:%M")
                self.vpn_sub_hint.configure(
                    text=f"последнее обновление: {t} · серверов: "
                         f"{len(self._vpn_servers)}")
            elif self._vpn_sub_url:
                self.vpn_sub_hint.configure(
                    text="ссылка сохранена — нажмите «обновить серверы», "
                         "чтобы получить список")
            else:
                self.vpn_sub_hint.configure(
                    text="Вставьте ссылку подписки из вашего VPN-сервиса "
                         "(как в happ) и нажмите «обновить серверы».\n"
                         "Поддерживается vless, vmess, trojan, ss, "
                         "hysteria2 и tuic.")
        except Exception:
            pass

    def _vpn_fetch(self):
        if self._vpn_busy:
            return
        url = self.vpn_sub_entry.get().strip()
        if not url or "://" not in url:
            messagebox.showwarning(APP_NAME, "Вставьте ссылку подписки — "
                                             "она начинается с http:// или "
                                             "другой схемой.")
            return
        self._vpn_busy = True
        self.vpn_fetch_btn.configure(state="disabled", text="загрузка…")
        self._log("VPN: скачиваю подписку…")
        ua = str((self.cfg.get("vpn") or {}).get("ua") or "") or None
        threading.Thread(target=self._vpn_fetch_worker,
                         args=(url, ua), daemon=True).start()

    def _vpn_fetch_worker(self, url, ua):
        err = None
        servers = []
        try:
            text = vpn_core.fetch_subscription(url, ua=ua) if ua \
                else vpn_core.fetch_subscription(url)
            links = vpn_core.decode_subscription(text)
            servers = vpn_core.parse_links(links)
            if not links:
                err = "в подписке не найдено ни одной ссылки сервера"
            elif not servers:
                err = "ссылки есть, но разобрать их не удалось"
        except Exception as e:
            err = str(e) or type(e).__name__
        try:
            self.after(0, self._vpn_fetch_done, url, servers, err)
        except Exception:
            pass

    def _vpn_fetch_done(self, url, servers, err):
        self._vpn_busy = False
        try:
            self.vpn_fetch_btn.configure(state="normal", text="обновить серверы")
        except tk.TclError:
            return
        if err:
            self._log(f"VPN: не получилось — {err}")
            messagebox.showerror(APP_NAME, f"Не удалось получить серверы:\n{err}")
            return
        self._vpn_sub_url = url
        self._vpn_servers = servers
        self._vpn_pings = {}
        self._vpn_updated = time.localtime()
        self.cfg["vpn"] = dict(self.cfg.get("vpn") or {},
                               sub_url=url, selected_link=self._vpn_sel_link)
        save_config(self.cfg)
        # сохранённый выбор мог исчезнуть из подписки
        if self._vpn_sel_link not in {s["link"] for s in servers}:
            self._vpn_sel_link = ""
        self._vpn_render_list()
        self._vpn_update_sel_label()
        self._vpn_update_hint()
        self._log(f"VPN: подписка обновлена — серверов: {len(servers)}.")
        self._vpn_ping_all()

    # ---- список серверов

    def _vpn_render_list(self):
        for w in self.vpn_list.winfo_children():
            w.destroy()
        self._vpn_rows = []
        self.vpn_count_label.configure(
            text=f"серверов: {len(self._vpn_servers)}" if self._vpn_servers
            else "серверов: —")
        for i, rec in enumerate(self._vpn_servers):
            sel = rec["link"] == self._vpn_sel_link
            fr = ctk.CTkFrame(self.vpn_list, height=44, corner_radius=10,
                              fg_color=ACTIVE_BG if sel else "transparent",
                              border_width=1 if sel else 0,
                              border_color=ACCENT)
            fr.pack(fill="x", pady=2, padx=4)
            fr.pack_propagate(False)
            dot = ctk.CTkLabel(fr, text="●", font=ctk.CTkFont(size=9),
                               text_color=ACCENT if sel else MUTED)
            dot.pack(side="left", padx=(14, 8))
            name = rec["name"][:60]
            ctk.CTkLabel(fr, text=name, font=ctk.CTkFont(
                size=13, weight="bold" if sel else "normal"),
                text_color=TEXT if sel else "#C4C9D6", anchor="w").pack(
                side="left")
            ctk.CTkLabel(fr, text=rec["type"], font=ctk.CTkFont(size=10),
                         text_color=MUTED).pack(side="left", padx=(10, 0))
            ping = ctk.CTkLabel(fr, text="—", width=100, anchor="e",
                                font=ctk.CTkFont(size=12),
                                text_color=MUTED)
            ping.pack(side="right", padx=(0, 14))
            for w in (fr, dot, ping):
                w.bind("<Button-1>", lambda e, k=i: self._vpn_select(k))
            self._vpn_rows.append((fr, dot, ping, rec))
            if rec["link"] in self._vpn_pings:
                self._vpn_paint_ping(ping, self._vpn_pings[rec["link"]])

    def _vpn_select(self, idx):
        if not (0 <= idx < len(self._vpn_servers)):
            return
        self._vpn_sel_link = self._vpn_servers[idx]["link"]
        self.cfg["vpn"] = dict(self.cfg.get("vpn") or {},
                               sub_url=self._vpn_sub_url,
                               selected_link=self._vpn_sel_link)
        save_config(self.cfg)
        for i, (fr, dot, ping, rec) in enumerate(self._vpn_rows):
            sel = i == idx
            try:
                fr.configure(fg_color=ACTIVE_BG if sel else "transparent",
                             border_width=1 if sel else 0)
                dot.configure(text_color=ACCENT if sel else MUTED)
            except tk.TclError:
                pass
        self._vpn_update_sel_label()

    def _vpn_update_sel_label(self):
        rec = self._vpn_selected()
        text = (f"выбран: {rec['name'][:50]}  ({rec['host']}:{rec['port']})"
                if rec else "сервер не выбран")
        try:
            self.vpn_sel_label.configure(text=text)
        except tk.TclError:
            pass

    def _vpn_selected(self):
        for rec in self._vpn_servers:
            if rec["link"] == self._vpn_sel_link:
                return rec
        return None

    # ---- пинг

    def _vpn_ping_all(self):
        if self._vpn_busy or not self._vpn_servers:
            return
        self._vpn_busy = True
        self.vpn_ping_btn.configure(state="disabled", text="замер…")
        servers = list(self._vpn_servers)
        threading.Thread(target=self._vpn_ping_worker,
                         args=(servers,), daemon=True).start()

    def _vpn_ping_worker(self, servers):
        from concurrent.futures import ThreadPoolExecutor
        results = {}

        def one(rec):
            return rec["link"], vpn_core.tcp_ping(rec["host"], rec["port"])

        with ThreadPoolExecutor(max_workers=24) as pool:
            for link, ms in pool.map(one, servers):
                results[link] = ms
        try:
            self.after(0, self._vpn_ping_done, results)
        except Exception:
            pass

    def _vpn_ping_done(self, results):
        self._vpn_busy = False
        try:
            self.vpn_ping_btn.configure(state="normal", text="проверить пинг")
        except tk.TclError:
            return
        self._vpn_pings = results
        for fr, dot, ping, rec in self._vpn_rows:
            self._vpn_paint_ping(ping, results.get(rec["link"]))
        ok = sum(1 for v in results.values() if v is not None)
        self._log(f"VPN: пинг проверен — доступно {ok} из {len(results)}.")

    @staticmethod
    def _vpn_paint_ping(label, ms):
        try:
            if ms is None:
                label.configure(text="недоступен", text_color=RED)
            else:
                label.configure(
                    text=f"{ms:.0f} мс",
                    text_color=GREEN if ms <= 150 else (AMBER if ms <= 350
                                                        else RED))
        except tk.TclError:
            pass

    # ---- подключение

    def _vpn_toggle(self):
        if self._vpn_proc:
            self._vpn_disconnect()
        else:
            self._vpn_connect()

    def _vpn_connect(self):
        rec = self._vpn_selected()
        if not rec:
            messagebox.showwarning(APP_NAME, "Сначала выберите сервер "
                                             "в списке (клик по строке).")
            return
        exe = vpn_core.ensure_core(VERSION)
        if not exe:
            messagebox.showerror(APP_NAME, "Ядро VPN не найдено. Переустановите "
                                           "grom или скачайте заново.")
            return
        self._vpn_busy = True
        self.vpn_btn.configure(state="disabled", text="подключение…")
        self._log(f"VPN: подключаюсь к «{rec['name'][:40]}»…")
        threading.Thread(target=self._vpn_connect_worker,
                         args=(exe, rec), daemon=True).start()

    def _vpn_connect_worker(self, exe, rec):
        ok, err, port, proc = False, None, None, None
        try:
            os.makedirs(vpn_core.VPN_DIR, exist_ok=True)
            port = vpn_core.find_free_port()
            log_path = os.path.join(vpn_core.VPN_DIR, "sing-box.log")
            cfg_path = os.path.join(vpn_core.VPN_DIR, "config.json")
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(vpn_core.make_config(rec["ob"], port, log_path),
                          f, ensure_ascii=False, indent=2)
            proc = vpn_core.launch_core(exe, cfg_path)
            time.sleep(1.4)
            if proc.poll() is not None:
                proc = None
                err = vpn_core.tail_file(log_path) or "sing-box не запустился"
            else:
                ok = True
        except Exception as e:
            err = str(e) or type(e).__name__
        try:
            self.after(0, self._vpn_connect_done, ok, err, port, rec, proc)
        except Exception:
            pass

    def _vpn_connect_done(self, ok, err, port, rec, proc=None):
        self._vpn_busy = False
        try:
            self.vpn_btn.configure(state="normal")
        except tk.TclError:
            return
        if not ok:
            self.vpn_btn.configure(text="подключить")
            self._log(f"VPN: ошибка запуска — {err}")
            messagebox.showerror(APP_NAME,
                                 f"Сервер не запустился:\n{err}")
            return
        # поднять системный прокси
        try:
            self._vpn_proxy_state = vpn_core.save_proxy_state()
            vpn_core.set_system_proxy(True, f"127.0.0.1:{port}")
        except Exception as e:
            self._log(f"VPN: прокси не настроился ({e}) — туннель работает, "
                      f"но программы сами должны использовать "
                      f"127.0.0.1:{port}")
        self._vpn_proc = proc
        self._vpn_port = port
        self._vpn_apply_connected_ui()
        self._log(f"VPN: подключено к «{rec['name'][:40]}» "
                  f"({rec['host']}:{rec['port']}), прокси 127.0.0.1:{port}.")

    def _vpn_apply_connected_ui(self):
        try:
            self.vpn_btn.configure(text="отключить", fg_color=RED,
                                   hover_color="#E1495A", state="normal")
            self.vpn_status_dot.configure(text_color=GREEN)
            self.vpn_status_text.configure(text="подключён", text_color=GREEN)
            self.vpn_pill.configure(fg_color=TINT_GREEN,
                                    border_color=lerp_color(TINT_GREEN,
                                                            GREEN, 0.3))
        except tk.TclError:
            pass

    def _vpn_disconnect(self, silent=False):
        proc, self._vpn_proc = self._vpn_proc, None
        if proc:
            try:
                proc.kill()
            except Exception:
                pass
        if self._vpn_proxy_state is not None:
            try:
                vpn_core.restore_proxy_state(self._vpn_proxy_state)
            except Exception:
                pass
            self._vpn_proxy_state = None
        self._vpn_port = None
        try:
            self.vpn_btn.configure(text="подключить", fg_color=ACCENT,
                                   hover_color=ACCENT_HOVER, state="normal")
            self.vpn_status_dot.configure(text_color=MUTED)
            self.vpn_status_text.configure(text="не подключён",
                                           text_color=MUTED)
            self.vpn_pill.configure(fg_color=CARD_HOVER,
                                    border_color=BORDER)
        except (tk.TclError, AttributeError):
            pass
        if not silent and proc:
            self._log("VPN: отключено, системный прокси возвращён.")

    # ---------------------------------------------------------------- тема

    def _build_theme(self):
        p = self.pages["theme"]
        ctk.CTkLabel(p, text="Тема", font=ctk.CTkFont(size=25, weight="bold"),
                     text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(p, text="Цвет, фон и скругление — применяется сразу",
                     font=ctk.CTkFont(size=13), text_color=MUTED).pack(
            anchor="w", pady=(4, 0))

        th = self.cfg.get("theme") or {}
        preset = str(th.get("preset", "violet"))
        accent = th.get("accent")

        # ---- цветовая тема
        card = ctk.CTkFrame(p, fg_color=CARD, corner_radius=RADIUS, border_width=1,
                            border_color=BORDER)
        card.pack(fill="x", pady=(18, 0))
        ctk.CTkLabel(card, text="Ц В Е Т О В А Я   Т Е М А",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=MUTED).pack(anchor="w", padx=22, pady=(16, 8))
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=22, pady=(0, 18))
        for key, t in THEME_PRESETS.items():
            chip = ctk.CTkFrame(row, width=128, height=58, corner_radius=12,
                                fg_color=t["card"],
                                border_width=2 if key == preset else 1,
                                border_color=ACCENT if key == preset else BORDER)
            chip.pack(side="left", padx=(0, 10))
            chip.pack_propagate(False)
            ctk.CTkFrame(chip, width=26, height=26, corner_radius=13,
                         fg_color=t["accent"]).pack(padx=(12, 0), pady=(10, 0))
            ctk.CTkLabel(chip, text=t["name"], font=ctk.CTkFont(size=11, weight="bold"),
                         text_color=TEXT).pack(anchor="w", padx=12, pady=(4, 0))
            for w in (chip, *chip.winfo_children()):
                w.bind("<Button-1>", lambda e, k=key: self._set_preset(k))

        # ---- акцентный цвет
        card2 = ctk.CTkFrame(p, fg_color=CARD, corner_radius=RADIUS, border_width=1,
                             border_color=BORDER)
        card2.pack(fill="x", pady=(14, 0))
        ctk.CTkLabel(card2, text="А К Ц Е Н Т Н Ы Й   Ц В Е Т",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=MUTED).pack(anchor="w", padx=22, pady=(16, 8))
        sw_row = ctk.CTkFrame(card2, fg_color="transparent")
        sw_row.pack(fill="x", padx=22, pady=(0, 6))
        cur_accent = (accent or THEME_PRESETS[preset]["accent"]).upper()
        for c in ("#7C6CFF", "#38B6FF", "#2BD576", "#FFB454",
                  "#FF5D6C", "#FF6FCF", "#E8E8F0", "#56C2D9"):
            sw = ctk.CTkButton(sw_row, text="", width=38, height=38,
                               corner_radius=19, fg_color=c,
                               hover_color=lighten(c, 24),
                               border_width=2 if c.upper() == cur_accent else 0,
                               border_color=TEXT,
                               command=lambda col=c: self._set_accent(col))
            sw.pack(side="left", padx=(0, 10))
        ctk.CTkButton(sw_row, text="свой…", width=74, height=38, corner_radius=19,
                      fg_color=CARD_HOVER, hover_color=BTN_HOVER, border_width=1,
                      border_color=BORDER, text_color=TEXT,
                      font=ctk.CTkFont(size=12),
                      command=self._pick_custom_accent).pack(side="left")
        ctk.CTkLabel(card2, text="Выбор темы возвращает акцент к стандартному — "
                                 "свой цвет можно поставить после.",
                     font=ctk.CTkFont(size=11), text_color=MUTED).pack(
            anchor="w", padx=22, pady=(0, 16))

        # ---- фон и скругление
        card3 = ctk.CTkFrame(p, fg_color=CARD, corner_radius=RADIUS, border_width=1,
                             border_color=BORDER)
        card3.pack(fill="x", pady=(14, 0))
        ctk.CTkLabel(card3, text=" Ф О Н   И   У Г Л Ы ",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=MUTED).pack(anchor="w", padx=22, pady=(16, 8))

        bg_row = ctk.CTkFrame(card3, fg_color="transparent")
        bg_row.pack(fill="x", padx=22, pady=(0, 4))
        ctk.CTkButton(bg_row, text="выбрать картинку…", height=34, corner_radius=9,
                      fg_color=CARD_HOVER, hover_color=BTN_HOVER, border_width=1,
                      border_color=BORDER, text_color=TEXT,
                      font=ctk.CTkFont(size=12),
                      command=self._pick_bg_image).pack(side="left")
        ctk.CTkButton(bg_row, text="убрать фон", height=34, corner_radius=9,
                      fg_color="transparent", hover_color=CARD_HOVER,
                      border_width=1, border_color=BORDER, text_color=MUTED,
                      font=ctk.CTkFont(size=12),
                      command=self._remove_bg).pack(side="left", padx=(8, 0))
        self.bg_name_label = ctk.CTkLabel(
            bg_row, text=(os.path.basename(th.get("bg_image") or "") or "фон не задан"),
            font=ctk.CTkFont(size=11), text_color=MUTED)
        self.bg_name_label.pack(side="left", padx=(12, 0))

        dim_row = ctk.CTkFrame(card3, fg_color="transparent")
        dim_row.pack(fill="x", padx=22, pady=(6, 0))
        ctk.CTkLabel(dim_row, text="затемнение", font=ctk.CTkFont(size=12),
                     text_color=MUTED, width=90, anchor="w").pack(side="left")
        self.dim_slider = ctk.CTkSlider(
            dim_row, from_=20, to=88, number_of_steps=34, height=18,
            progress_color=ACCENT, button_color=ACCENT,
            button_hover_color=ACCENT_HOVER,
            command=self._on_dim_change)
        self.dim_slider.pack(side="left", fill="x", expand=True, padx=10)
        self.dim_slider.set(int(th.get("bg_dim", 60)))
        ctk.CTkLabel(dim_row, text="чем больше — тем темнее картинка",
                     font=ctk.CTkFont(size=11), text_color=MUTED).pack(side="left")

        rad_row = ctk.CTkFrame(card3, fg_color="transparent")
        rad_row.pack(fill="x", padx=22, pady=(10, 0))
        ctk.CTkLabel(rad_row, text="углы", font=ctk.CTkFont(size=12),
                     text_color=MUTED, width=90, anchor="w").pack(side="left")
        self.rad_slider = ctk.CTkSlider(
            rad_row, from_=0, to=24, number_of_steps=24, height=18,
            progress_color=ACCENT, button_color=ACCENT,
            button_hover_color=ACCENT_HOVER,
            command=self._on_radius_change)
        self.rad_slider.pack(side="left", fill="x", expand=True, padx=10)
        self.rad_slider.set(RADIUS)
        self.rad_value = ctk.CTkLabel(rad_row, text=f"{RADIUS} px",
                                      font=ctk.CTkFont(size=11), text_color=MUTED,
                                      width=44)
        self.rad_value.pack(side="left")
        ctk.CTkFrame(card3, height=14, fg_color="transparent").pack()

        # ---- сброс
        ctk.CTkButton(p, text="вернуть стандартное оформление", height=34,
                      corner_radius=9, fg_color="transparent",
                      hover_color=CARD_HOVER, border_width=1, border_color=BORDER,
                      text_color=MUTED, font=ctk.CTkFont(size=12),
                      command=self._reset_theme).pack(anchor="w", pady=(14, 0))

    # ---- действия темы

    def _theme_save(self):
        save_config(self.cfg)

    def _set_preset(self, key):
        th = self.cfg.get("theme") or {}
        th["preset"] = key
        th["accent"] = None          # акцент пресета; свой цвет ставится отдельно
        self.cfg["theme"] = th
        self._theme_save()
        self._log(f"Тема: «{THEME_PRESETS[key]['name']}».")
        self._rebuild_ui()

    def _set_accent(self, color):
        th = self.cfg.get("theme") or {}
        th["accent"] = color
        self.cfg["theme"] = th
        self._theme_save()
        self._log(f"Акцентный цвет: {color}.")
        self._rebuild_ui()

    def _pick_custom_accent(self):
        cur = ((self.cfg.get("theme") or {}).get("accent")
               or THEME_PRESETS[((self.cfg.get("theme") or {}).get("preset", "violet"))]["accent"])
        res = colorchooser.askcolor(color=cur, title="Свой акцентный цвет",
                                    parent=self)
        if res and res[1]:
            self._set_accent(res[1].upper())

    def _pick_bg_image(self):
        path = filedialog.askopenfilename(
            title="Картинка на фон",
            filetypes=[("Изображения", "*.png *.jpg *.jpeg *.bmp *.webp"),
                       ("Все файлы", "*.*")], parent=self)
        if not path:
            return
        try:
            os.makedirs(BG_DIR, exist_ok=True)
            ext = os.path.splitext(path)[1].lower() or ".png"
            dst = os.path.join(BG_DIR, "background" + ext)
            shutil.copy2(path, dst)
            Image.open(dst).verify()      # проверка, что файл — картинка
            th = self.cfg.get("theme") or {}
            th["bg_image"] = dst
            th.setdefault("bg_dim", 60)
            self.cfg["theme"] = th
            self._theme_save()
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Не удалось поставить картинку:\n{e}")
            return
        self._log("Фон: картинка установлена.")
        self._rebuild_ui()

    def _remove_bg(self):
        th = self.cfg.get("theme") or {}
        if not th.get("bg_image"):
            return
        th["bg_image"] = None
        self.cfg["theme"] = th
        self._theme_save()
        self._log("Фон: картинка убрана.")
        self._rebuild_ui()

    def _on_dim_change(self, v):
        th = self.cfg.get("theme") or {}
        th["bg_dim"] = int(float(v))
        self.cfg["theme"] = th
        self._theme_save()
        self._render_background()

    def _on_radius_change(self, v):
        global RADIUS
        old = RADIUS
        RADIUS = int(float(v))
        self.rad_value.configure(text=f"{RADIUS} px")
        th = self.cfg.get("theme") or {}
        th["radius"] = RADIUS
        self.cfg["theme"] = th
        self._theme_save()
        if RADIUS == old:
            return
        # перерисовать скругления карточек: меняем фреймы с прежним радиусом
        for w in self._walk_widgets():
            if not isinstance(w, ctk.CTkFrame):
                continue
            try:
                r = w.cget("corner_radius")
            except Exception:
                continue
            if r == old:
                try:
                    w.configure(corner_radius=RADIUS)
                except Exception:
                    pass

    def _reset_theme(self):
        self.cfg["theme"] = {}
        self._theme_save()
        self._log("Оформление сброшено к стандартному.")
        self._rebuild_ui()

    def _rebuild_ui(self):
        """Пересобрать интерфейс с новыми цветами (процесс winws не трогается)."""
        page = self._current_page or "home"
        self._init_theme()          # применить тему/акцент/углы из конфига
        self.configure(fg_color=BG)
        self._radius_widgets = []
        for w in self.winfo_children():
            w.destroy()
        self._bg_label = None
        self._bg_photo = None
        self._bg_src = None
        self._bg_job = None
        self._current_page = None
        self._build_sidebar()
        self._build_pages()
        self._apply_dark_titlebar()
        self.show_page(page)
        # вернуть лог и состояние
        if self._log_lines:
            self.log_box.configure(state="normal")
            self.log_box.insert("end", "\n".join(self._log_lines) + "\n")
            self.log_box.configure(state="disabled")
            self.log_box.see("end")
        if self.strategies:
            if 0 <= (self.selected or 0) < len(self.strategies):
                self.select_strategy(self.selected or 0)
        if self._vpn_proc:            # VPN остаётся подключённым при смене темы
            self._vpn_apply_connected_ui()
        self._shown_running = None   # существующий цикл опроса сам обновит статус

    def _walk_widgets(self):
        out = []
        stack = [self]
        while stack:
            w = stack.pop()
            out.append(w)
            try:
                stack.extend(w.winfo_children())
            except Exception:
                pass
        return out

    # ---- фон-картинка

    def _init_theme(self):
        """Применить сохранённую тему до построения виджетов."""
        global RADIUS
        th = self.cfg.get("theme") or {}
        apply_theme(str(th.get("preset", "violet")), th.get("accent"))
        try:
            RADIUS = max(0, min(24, int(th.get("radius", 16))))
        except Exception:
            RADIUS = 16

    def _apply_background(self):
        th = self.cfg.get("theme") or {}
        path = th.get("bg_image")
        if not path or not os.path.isfile(path):
            return
        try:
            self._bg_src = Image.open(path).convert("RGB")
        except Exception:
            return
        self._bg_label = ctk.CTkLabel(self.content, text="", fg_color="transparent")
        self._bg_label.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._bg_label.lower()
        self._render_background()

    def _render_background(self):
        if not self._bg_label or not self._bg_src:
            return
        try:
            w = max(self.content.winfo_width(), 200)
            h = max(self.content.winfo_height(), 200)
            dim = int((self.cfg.get("theme") or {}).get("bg_dim", 60))
            alpha = max(0.12, min(0.88, (100 - dim) / 100))
            fitted = ImageOps.fit(self._bg_src, (w, h), Image.LANCZOS)
            faded = Image.blend(Image.new("RGB", (w, h), BG), fitted, alpha)
            self._bg_photo = ctk.CTkImage(light_image=faded, dark_image=faded,
                                          size=(w, h))
            self._bg_label.configure(image=self._bg_photo)
        except Exception:
            pass

    def _on_content_resize(self, _event=None):
        if self._bg_job:
            try:
                self.after_cancel(self._bg_job)
            except Exception:
                pass
        self._bg_job = self.after(250, self._render_background)

    # ---------------------------------------------------------------- о программе

    def _build_about(self):
        p = self.pages["about"]
        ctk.CTkLabel(p, text="О программе", font=ctk.CTkFont(size=25, weight="bold"),
                     text_color=TEXT).pack(anchor="w")

        vbadge = ctk.CTkFrame(p, fg_color=ACTIVE_BG, corner_radius=20,
                              border_width=1,
                              border_color=lerp_color(ACTIVE_BG, ACCENT, 0.25))
        vbadge.pack(anchor="w", pady=(12, 0))
        ctk.CTkLabel(vbadge, text=f"⚡  {APP_NAME} v{VERSION}",
                     text_color=ACTIVE_TEXT, font=ctk.CTkFont(
                         size=13, weight="bold")).pack(padx=16, pady=6)

        card = ctk.CTkFrame(p, fg_color=CARD, corner_radius=RADIUS, border_width=1,
                            border_color=BORDER)
        card.pack(fill="x", pady=(14, 0))
        ctk.CTkLabel(card, text=("Графическая обёртка над winws из проекта zapret\n"
                                 "(github.com/bol-van/zapret).\n\n"
                                 "Программа читает стратегии из .bat-файлов и запускает winws.exe\n"
                                 "скрытно, без консольных окон, показывая лог.\n\n"
                                 "Если папки zapret на ПК нет — используется встроенная копия\n"
                                 "(распаковывается автоматически при первом запуске).\n\n"
                                 "Для работы нужны Windows 10/11 и права администратора —\n"
                                 "драйвер WinDivert перехватывает сетевой трафик."),
                     text_color=TEXT, font=ctk.CTkFont(size=13), justify="left",
                     wraplength=740).pack(anchor="w", padx=24, pady=20)

        ctk.CTkLabel(p, text="исходники: github.com/frogiiiiiiii1/grom",
                     text_color=MUTED, font=ctk.CTkFont(size=12)).pack(
            anchor="w", pady=(12, 0))

    # ---------------------------------------------------------------- логика

    def _log(self, text: str):
        line = text.rstrip()
        self._log_lines.append(line)
        if len(self._log_lines) > 400:
            self._log_lines.pop(0)
        self.log_box.configure(state="normal")
        self.log_box.insert("end", line + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _clear_log(self):
        self._log_lines.clear()
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    def _choose_dir(self):
        d = filedialog.askdirectory(title="Папка с zapret",
                                    initialdir=self.zapret_dir or os.path.expanduser("~"))
        if d:
            self.dir_entry.delete(0, "end")
            self.dir_entry.insert(0, d)
            self._apply_dir()

    def _apply_dir(self):
        d = self.dir_entry.get().strip()
        if not os.path.isdir(d) or not find_winws(d):
            messagebox.showerror(APP_NAME, "В этой папке не найден winws.exe.\n"
                                           "Укажите папку дистрибутива zapret.")
            return
        self.zapret_dir = d
        self.winws_exe = find_winws(d)
        self.cfg["zapret_dir"] = d
        save_config(self.cfg)
        self._reload_strategies()
        self._log(f"Папка zapret: {d}")

    def _reload_strategies(self):
        self.strategies = []
        if self.zapret_dir:
            for source, name, args in scan_strategies(self.zapret_dir):
                self.strategies.append({"source": source, "name": name, "args": args})
        if self.strategies:
            idx = self.cfg.get("sel_index", 0)
            if not (0 <= idx < len(self.strategies)):
                idx = 0
            self.select_strategy(idx)
        else:
            self.hero_name.configure(text="— стратегии не найдены —")
            self.hero_source.configure(text="укажите папку с zapret ниже")

    def select_strategy(self, idx):
        self.selected = idx
        s = self.strategies[idx]
        self.hero_name.configure(text=s["name"])
        self.hero_source.configure(text=f"{s['source']} · {len(self.strategies)} стратегий")
        self.cfg["sel_index"] = idx
        save_config(self.cfg)

    def _current_args(self):
        return self.strategies[self.selected]["args"] if (
                self.selected is not None and self.strategies) else ""

    def _toggle_power(self):
        if self.proc and self.proc.poll() is None:
            self._stop()
        else:
            self._start()

    def _toggle_auto_bypass(self):
        on = self.auto_bypass.get() == 1
        self.cfg["autorun_bypass"] = on
        save_config(self.cfg)
        self._log(f"Автозапуск обхода при открытии: {'включён' if on else 'выключен'}.")

    def _auto_bypass_start(self):
        """Автозапуск обхода при обычном (не через задачу) открытии grom."""
        if not self.cfg.get("autorun_bypass"):
            return
        if self.proc and self.proc.poll() is None:
            return
        if not is_admin() or not self.winws_exe or not self.strategies:
            return
        self._log("Автозапуск обхода (включена настройка «при открытии»)…")
        self._start()

    def _start(self):
        if self.proc and self.proc.poll() is None:
            return
        if not self.winws_exe:
            messagebox.showerror(APP_NAME, "winws.exe не найден. Укажите папку с zapret.")
            return
        if not is_admin():
            messagebox.showerror(APP_NAME, "Нужны права администратора.\n"
                                           "Перезапустите программу от имени администратора.")
            if relaunch_as_admin():
                self.destroy()
            return
        args = self._current_args()
        if not args:
            messagebox.showwarning(APP_NAME, "Нет аргументов — выберите стратегию (⚙).")
            return
        if winws_already_running():
            if messagebox.askyesno(
                    APP_NAME,
                    "Найден уже запущенный winws (служба или батник).\n"
                    "Его фильтры пересекаются с нашей копией и ломают обход.\n\n"
                    "Остановить чужой winws и запустить свою копию?"):
                kill_foreign_winws()
                time.sleep(1)
            else:
                return

        cmd_line = f'"{self.winws_exe}" {args}'
        self._log(f"> {cmd_line}")
        try:
            self.proc = subprocess.Popen(
                cmd_line, cwd=os.path.dirname(self.winws_exe),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                creationflags=CREATE_NO_WINDOW)
        except OSError as e:
            self._log(f"Ошибка запуска: {e}")
            messagebox.showerror(APP_NAME, f"Не удалось запустить winws:\n{e}")
            return
        threading.Thread(target=self._reader, daemon=True).start()
        if self.auto_switch.get() == 1:
            try:
                autostart_set(True)
                self._log("Задача автозапуска обновлена.")
            except Exception as e:
                self._log(f"Автозапуск не обновлён: {e}")

    def _autorun_start(self):
        if self.winws_exe and self.strategies:
            self._start()

    def _reader(self):
        proc = self.proc
        while proc and proc.poll() is None:
            raw = proc.stdout.readline()
            if not raw:
                break
            self.after(0, self._log, decode_console(raw))
        if proc:
            raw = proc.stdout.read()
            if raw:
                self.after(0, self._log, decode_console(raw))
            rc = proc.poll()
            self.after(0, self._log, f"--- winws завершён (код {rc}) ---")

    def _stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()
            self._log("Обход остановлен.")
        self.proc = None

    def _poll_process(self):
        running = bool(self.proc and self.proc.poll() is None)
        if running != self._shown_running:
            self._shown_running = running
            self.power_btn.set_running(running)
            if running:
                self.power_caption.configure(text="остановить обход")
                self._fade(self.power_caption, {"text_color": "#FF9AA5"})
                self.side_status_text.configure(text="обход работает",
                                                text_color=TEXT)
                self.status_text.configure(text="работает", text_color=GREEN)
                self._fade(self.status_pill, {"fg_color": TINT_GREEN,
                                              "border_color": "#1E4433"})
            else:
                self.power_caption.configure(text="запустить обход")
                self._fade(self.power_caption, {"text_color": MUTED})
                self.side_status_text.configure(text="winws не запущен",
                                                text_color=MUTED)
                self.status_text.configure(text="не запущен", text_color=AMBER)
                self._fade(self.status_pill, {"fg_color": TINT_AMBER,
                                              "border_color": "#3D3418"})
        self.after(120, self._poll_process)

    def _animate_pulse(self):
        """Плавная пульсация статусных точек (синус, без рывков)."""
        self._pulse_t += 0.085
        s = (math.sin(self._pulse_t) + 1) / 2
        running = bool(self.proc and self.proc.poll() is None)
        try:
            if running:
                self.side_status_dot.configure(
                    text_color=lerp_color(GREEN_DIM, GREEN, s))
                self.status_dot.configure(
                    text_color=lerp_color(RED, "#FF8A95", s))
            else:
                self.side_status_dot.configure(text_color=MUTED)
                self.status_dot.configure(
                    text_color=lerp_color(AMBER_DIM, AMBER, s))
        except tk.TclError:
            return
        self.after(60, self._animate_pulse)

    def _ask_elevation(self):
        if messagebox.askyesno(
                APP_NAME,
                "Для работы winws (драйвер WinDivert) нужны права администратора.\n"
                "Перезапустить программу от имени администратора?"):
            if relaunch_as_admin():
                self.destroy()

    def _on_close(self):
        self._hw_close = True
        self._vpn_disconnect(silent=True)
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
        save_config(self.cfg)
        self.destroy()


def main():
    if "--setup-embedded" in sys.argv:
        # скрытый тестовый режим: распаковать встроенную копию и выйти
        result = ensure_embedded_zapret()
        try:
            with open(os.path.join(os.environ.get("TEMP", "."), "grom-embedded.txt"),
                      "w", encoding="utf-8") as f:
                f.write(str(result))
        except OSError:
            pass
        return
    autorun = "--autorun" in sys.argv
    app = App(autorun=autorun)
    app.mainloop()


if __name__ == "__main__":
    main()
