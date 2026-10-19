# -*- coding: utf-8 -*-
"""VPN-ядро для grom: подписки, серверы, пинг, sing-box.

Вместе с grom встроен sing-box (тот же движок, что у современных
VPN-клиентов, включая happ). Модуль умеет:

* скачивать подписку и декодировать её (обычный текст или base64);
* разбирать ссылки vless:// vmess:// trojan:// ss:// hysteria2:// tuic://;
* делать TCP-пинг серверов;
* собирать конфиг sing-box и управлять системным прокси Windows.
"""

import base64
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

CREATE_NO_WINDOW = 0x08000000
DEFAULT_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) "
              "Gecko/20100101 Firefox/128.0 grom")
SCHEMES = ("vless", "vmess", "trojan", "ss", "hysteria2", "hy2", "tuic")

# ----------------------------------------------------- флаги стран по имени
# Код: двухбуквенный ключ (в т.ч. как ЗАГЛАВНЫЕ коды в именах серверов),
# Слово: названия стран и городов, встречаются в именах подписок.
FLAGS = {
    "us": "🇺🇸", "usa": "🇺🇸", "america": "🇺🇸", "united states": "🇺🇸",
    "new york": "🇺🇸", "los angeles": "🇺🇸", "seattle": "🇺🇸",
    "de": "🇩🇪", "germany": "🇩🇪", "frankfurt": "🇩🇪", "berlin": "🇩🇪",
    "nl": "🇳🇱", "netherlands": "🇳🇱", "amsterdam": "🇳🇱",
    "fi": "🇫🇮", "finland": "🇫🇮", "helsinki": "🇫🇮",
    "se": "🇸🇪", "sweden": "🇸🇪", "stockholm": "🇸🇪",
    "no": "🇳🇴", "norway": "🇳🇴", "oslo": "🇳🇴",
    "dk": "🇩🇰", "denmark": "🇩🇰", "copenhagen": "🇩🇰",
    "is": "🇮🇸", "iceland": "🇮🇸", "reykjavik": "🇮🇸",
    "tr": "🇹🇷", "turkey": "🇹🇷", "turkiye": "🇹🇷", "istanbul": "🇹🇷",
    "ru": "🇷🇺", "russia": "🇷🇺", "moscow": "🇷🇺", "москва": "🇷🇺",
    "fr": "🇫🇷", "france": "🇫🇷", "paris": "🇫🇷",
    "gb": "🇬🇧", "uk": "🇬🇧", "united kingdom": "🇬🇧", "england": "🇬🇧",
    "london": "🇬🇧",
    "jp": "🇯🇵", "japan": "🇯🇵", "tokyo": "🇯🇵", "осака": "🇯🇵",
    "sg": "🇸🇬", "singapore": "🇸🇬",
    "hk": "🇭🇰", "hong kong": "🇭🇰",
    "kr": "🇰🇷", "korea": "🇰🇷", "seoul": "🇰🇷",
    "tw": "🇹🇼", "taiwan": "🇹🇼",
    "ca": "🇨🇦", "canada": "🇨🇦", "toronto": "🇨🇦",
    "mx": "🇲🇽", "mexico": "🇲🇽",
    "br": "🇧🇷", "brazil": "🇧🇷",
    "ar": "🇦🇷", "argentina": "🇦🇷",
    "cl": "🇨🇱", "chile": "🇨🇱",
    "co": "🇨🇴", "colombia": "🇨🇴",
    "pe": "🇵🇪", "peru": "🇵🇪",
    "pl": "🇵🇱", "poland": "🇵🇱", "warsaw": "🇵🇱", "варшава": "🇵🇱",
    "at": "🇦🇹", "austria": "🇦🇹", "vienna": "🇦🇹",
    "ch": "🇨🇭", "switzerland": "🇨🇭", "zurich": "🇨🇭",
    "es": "🇪🇸", "spain": "🇪🇸", "madrid": "🇪🇸",
    "it": "🇮🇹", "italy": "🇮🇹", "milan": "🇮🇹", "rome": "🇮🇹",
    "be": "🇧🇪", "belgium": "🇧🇪", "brussels": "🇧🇪",
    "pt": "🇵🇹", "portugal": "🇵🇹", "lisbon": "🇵🇹",
    "ie": "🇮🇪", "ireland": "🇮🇪", "dublin": "🇮🇪",
    "cz": "🇨🇿", "czech": "🇨🇿", "czechia": "🇨🇿", "prague": "🇨🇿",
    "sk": "🇸🇰", "slovakia": "🇸🇰", "bratislava": "🇸🇰",
    "hu": "🇭🇺", "hungary": "🇭🇺", "budapest": "🇭🇺",
    "ro": "🇷🇴", "romania": "🇷🇴", "bucharest": "🇷🇴",
    "bg": "🇧🇬", "bulgaria": "🇧🇬", "sofia": "🇧🇬",
    "rs": "🇷🇸", "serbia": "🇷🇸", "belgrade": "🇷🇸",
    "hr": "🇭🇷", "croatia": "🇭🇷", "zagreb": "🇭🇷",
    "si": "🇸🇮", "slovenia": "🇸🇮", "ljubljana": "🇸🇮",
    "gr": "🇬🇷", "greece": "🇬🇷", "athens": "🇬🇷",
    "ua": "🇺🇦", "ukraine": "🇺🇦", "kyiv": "🇺🇦", "киев": "🇺🇦",
    "by": "🇧🇾", "belarus": "🇧🇾", "минск": "🇧🇾",
    "md": "🇲🇩", "moldova": "🇲🇩",
    "ee": "🇪🇪", "estonia": "🇪🇪", "tallinn": "🇪🇪",
    "lv": "🇱🇻", "latvia": "🇱🇻", "riga": "🇱🇻",
    "lt": "🇱🇹", "lithuania": "🇱🇹", "vilnius": "🇱🇹",
    "lu": "🇱🇺", "luxembourg": "🇱🇺",
    "kz": "🇰🇿", "kazakhstan": "🇰🇿", "алматы": "🇰🇿", "астана": "🇰🇿",
    "uz": "🇺🇿", "uzbekistan": "🇺🇿", "ташкент": "🇺🇿",
    "kg": "🇰🇬", "kyrgyzstan": "🇰🇬", "бишкек": "🇰🇬",
    "tj": "🇹🇯", "tajikistan": "🇹🇯",
    "ge": "🇬🇪", "georgia": "🇬🇪", "tbilisi": "🇬🇪", "тбилиси": "🇬🇪",
    "am": "🇦🇲", "armenia": "🇦🇲", "yerevan": "🇦🇲", "ереван": "🇦🇲",
    "az": "🇦🇿", "azerbaijan": "🇦🇿", "baku": "🇦🇿",
    "mn": "🇲🇳", "mongolia": "🇲🇳",
    "ae": "🇦🇪", "uae": "🇦🇪", "dubai": "🇦🇪", "emirates": "🇦🇪",
    "sa": "🇸🇦", "saudi": "🇸🇦", "riyadh": "🇸🇦",
    "qa": "🇶🇦", "qatar": "🇶🇦", "doha": "🇶🇦",
    "il": "🇮🇱", "israel": "🇮🇱", "tel aviv": "🇮🇱",
    "in": "🇮🇳", "india": "🇮🇳", "mumbai": "🇮🇳", "delhi": "🇮🇳",
    "pk": "🇵🇰", "pakistan": "🇵🇰",
    "bd": "🇧🇩", "bangladesh": "🇧🇩",
    "id": "🇮🇩", "indonesia": "🇮🇩", "jakarta": "🇮🇩",
    "my": "🇲🇾", "malaysia": "🇲🇾", "kuala lumpur": "🇲🇾",
    "th": "🇹🇭", "thailand": "🇹🇭", "bangkok": "🇹🇭",
    "vn": "🇻🇳", "vietnam": "🇻🇳", "hanoi": "🇻🇳", "ho chi minh": "🇻🇳",
    "ph": "🇵🇭", "philippines": "🇵🇭", "manila": "🇵🇭",
    "au": "🇦🇺", "australia": "🇦🇺", "sydney": "🇦🇺", "melbourne": "🇦🇺",
    "nz": "🇳🇿", "new zealand": "🇳🇿", "auckland": "🇳🇿",
    "za": "🇿🇦", "south africa": "🇿🇦", "johannesburg": "🇿🇦",
    "ng": "🇳🇬", "nigeria": "🇳🇬", "lagos": "🇳🇬",
    "eg": "🇪🇬", "egypt": "🇪🇬", "cairo": "🇪🇬",
    "ke": "🇰🇪", "kenya": "🇰🇪", "nairobi": "🇰🇪",
}
# ключи-коды (2 буквы) и ключи-слова (для разбиения по способу поиска)
_CODE_KEYS = {k for k in FLAGS if len(k) == 2 and k.isascii()}
_WORD_KEYS = sorted((k for k in FLAGS if len(k) > 2),
                    key=len, reverse=True)
# английские предлоги/союзы длиной 2 — не принимаем за код страны
_STOP2 = {"in", "on", "of", "at", "to", "by", "no", "is", "it", "be",
          "my", "me", "or", "as", "so", "up", "do", "if", "we", "he"}


def guess_flag(name):
    """Эмодзи-флаг по имени сервера (или пустая строка)."""
    name = (name or "").strip()
    if not name:
        return ""
    low = name.lower()
    norm = re.sub(r"[^0-9a-zа-яё]+", " ", low).strip()
    # 1) многосимвольные: "hong kong", "germany", "tokyo"...
    for key in _WORD_KEYS:
        if len(key) > 3:
            if key in norm:
                return FLAGS[key]
    # 2) короткие названия ("no", "uk", "tr"...) — только как целое слово
    words = set(norm.split())
    for key in _CODE_KEYS:
        if len(key) > 2 and key in words:
            return FLAGS[key]
    # 3) ДВУХБУКВЕННЫЕ КОДЫ: надёжнее всего ЗАГЛАВНЫЕ ("US-01", "DE Premium")
    for tok in re.split(r"[^0-9A-Za-zА-Яа-яЁё]+", name):
        if len(tok) == 2 and tok.isascii() and tok.isupper() \
                and tok.lower() in _CODE_KEYS:
            return FLAGS[tok.lower()]
    # 4) строчные коды, кроме английских слов
    for w in words:
        if len(w) == 2 and w not in _STOP2 and w in _CODE_KEYS:
            return FLAGS[w]
    return ""


def local_data_dir():
    return os.path.join(os.environ.get("LOCALAPPDATA",
                                       os.path.expanduser("~")), "grom")


VPN_DIR = os.path.join(local_data_dir(), "vpn")
CORE_BUNDLE = os.path.join(getattr(sys, "_MEIPASS",
                                   os.path.dirname(os.path.abspath(__file__))),
                           "vpnbin", "sing-box.exe")
CORE_PATH = os.path.join(VPN_DIR, "sing-box.exe")


def ensure_core(version):
    """Распаковать встроенное ядро sing-box в %LOCALAPPDATA%\\grom\\vpn.

    Возвращает путь к exe или None.
    """
    marker = os.path.join(VPN_DIR, "grom-version.txt")
    try:
        if os.path.isfile(CORE_PATH) and os.path.isfile(marker):
            with open(marker, encoding="utf-8") as f:
                if f.read().strip() == version:
                    return CORE_PATH
        os.makedirs(VPN_DIR, exist_ok=True)
        if os.path.isfile(CORE_BUNDLE):
            shutil.copy2(CORE_BUNDLE, CORE_PATH)
            with open(marker, "w", encoding="utf-8") as f:
                f.write(version)
            return CORE_PATH
    except OSError:
        pass
    return CORE_PATH if os.path.isfile(CORE_PATH) else None


# ------------------------------------------------------------------ подписки

def _b64(text):
    """Декодирует base64 (с пропущенным паддингом и urlsafe-вариантом)."""
    s = "".join(text.split())
    s += "=" * (-len(s) % 4)
    for fn in (base64.urlsafe_b64decode, base64.b64decode):
        try:
            return fn(s)
        except Exception:
            continue
    return None


def decode_subscription(text):
    """Подписка -> список ссылок. Понимает base64-блоки и обычный текст."""
    text = (text or "").strip()
    if not text:
        return []
    if "://" not in text:
        raw = _b64(text)
        if raw:
            try:
                text = raw.decode("utf-8", errors="replace")
            except Exception:
                return []
        else:
            return []
    links = []
    for part in text.replace("\r", "\n").replace("|", "\n").split("\n"):
        part = part.strip()
        low = part.lower()
        if any(low.startswith(s + "://") for s in SCHEMES):
            links.append(part)
    # убрать дубли, сохранив порядок
    seen = set()
    out = []
    for l in links:
        if l not in seen:
            seen.add(l)
            out.append(l)
    return out


def fetch_subscription(url, ua=DEFAULT_UA, timeout=20):
    """Скачивает подписку. Возвращает текст или бросает исключение."""
    req = urllib.request.Request(url, headers={
        "User-Agent": ua,
        "Accept": "*/*",
        "Accept-Encoding": "identity",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    for enc in ("utf-8", "cp1251"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


# ------------------------------------------------------------------- парсер

def _int(v, default=0):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def _transport(net, params):
    """Параметры транспорта (ws/grpc/...) для sing-box."""
    net = (net or "tcp").lower()
    if net == "ws":
        t = {"type": "ws", "path": params.get("path") or "/"}
        host = params.get("host")
        if host:
            t["headers"] = {"Host": host}
        return t
    if net == "grpc":
        return {"type": "grpc",
                "service_name": params.get("serviceName") or ""}
    if net in ("h2", "http"):
        t = {"type": "http", "path": params.get("path") or "/"}
        host = params.get("host")
        if host:
            t["headers"] = {"Host": host}
        return t
    if net == "httpupgrade":
        t = {"type": "httpupgrade", "path": params.get("path") or "/"}
        if params.get("host"):
            t["host"] = params["host"]
        return t
    return None


def _tls(params, server_name, force=False):
    """Блок tls для sing-box из query-параметров ссылки."""
    sec = (params.get("security") or ("tls" if force else "")).lower()
    if sec not in ("tls", "reality"):
        return None
    tls = {"enabled": True,
           "server_name": params.get("sni") or params.get("peer")
           or server_name}
    if str(params.get("allowInsecure") or params.get("insecure")) in ("1", "true"):
        tls["insecure"] = True
    fp = params.get("fp") or params.get("fingerprint")
    if fp:
        tls["utls"] = {"enabled": True, "fingerprint": fp}
    if sec == "reality" and params.get("pbk"):
        tls["reality"] = {"enabled": True, "public_key": params["pbk"],
                          "short_id": params.get("sid") or ""}
    return tls


def parse_link(link):
    """Разбирает ссылку сервера. Возвращает запись или None.

    Запись: {"type", "name", "host", "port", "link", "ob"} — ob это готовый
    outbound для sing-box (без тега).
    """
    link = (link or "").strip()
    try:
        scheme = link.split("://", 1)[0].lower()
    except IndexError:
        return None
    try:
        if scheme == "vmess":
            return _parse_vmess(link)
        u = urllib.parse.urlparse(link)
        host, port = u.hostname, u.port
        if not host or not port:
            return None
        name = urllib.parse.unquote(u.fragment or "") or f"{host}:{port}"
        params = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
        if scheme == "vless":
            ob = {"type": "vless", "server": host, "server_port": port,
                  "uuid": urllib.parse.unquote(u.username or ""),
                  "packet_encoding": "xudp"}
            flow = params.get("flow")
            if flow:
                ob["flow"] = flow
            net = (params.get("type") or "tcp").lower()
            t = _transport(net, params)
            if t:
                ob["transport"] = t
            tls = _tls(params, host)
            if tls:
                ob["tls"] = tls
            return {"type": "vless", "name": name, "host": host,
                    "port": port, "link": link, "ob": ob}
        if scheme == "trojan":
            ob = {"type": "trojan", "server": host, "server_port": port,
                  "password": urllib.parse.unquote(u.username or "")}
            net = (params.get("type") or "tcp").lower()
            t = _transport(net, params)
            if t:
                ob["transport"] = t
            tls = _tls(params, host, force=True)
            if tls:
                ob["tls"] = tls
            return {"type": "trojan", "name": name, "host": host,
                    "port": port, "link": link, "ob": ob}
        if scheme in ("hysteria2", "hy2"):
            ob = {"type": "hysteria2", "server": host, "server_port": port,
                  "password": urllib.parse.unquote(u.username or "")}
            tls = {"enabled": True,
                   "server_name": params.get("sni") or host}
            if str(params.get("insecure")) in ("1", "true"):
                tls["insecure"] = True
            ob["tls"] = tls
            if params.get("obfs"):
                ob["obfs"] = {"type": params["obfs"],
                              "password": params.get("obfs-password", "")}
            return {"type": "hysteria2", "name": name, "host": host,
                    "port": port, "link": link, "ob": ob}
        if scheme == "tuic":
            cred = urllib.parse.unquote(u.username or "")
            ob = {"type": "tuic", "server": host, "server_port": port,
                  "uuid": cred.split(":")[0],
                  "password": ":".join(cred.split(":")[1:]),
                  "congestion_control": params.get("congestion_control") or "bbr",
                  "udp_relay_mode": params.get("udp_relay_mode") or "native",
                  "heartbeat": "10s",
                  "tls": {"enabled": True,
                          "server_name": params.get("sni") or host,
                          "alpn": ["h3"]}}
            if str(params.get("allowInsecure") or params.get("insecure")) in ("1", "true"):
                ob["tls"]["insecure"] = True
            return {"type": "tuic", "name": name, "host": host,
                    "port": port, "link": link, "ob": ob}
        if scheme == "ss":
            return _parse_ss(link, name, host, port, u)
    except Exception:
        return None
    return None


def _parse_vmess(link):
    raw = _b64(link[len("vmess://"):])
    if not raw:
        return None
    d = json.loads(raw.decode("utf-8", errors="replace"))
    host, port = d.get("add"), _int(d.get("port"))
    if not host or not port:
        return None
    params = {"sni": d.get("sni") or d.get("host") or "",
              "type": d.get("net") or "tcp",
              "path": d.get("path") or "",
              "host": d.get("host") or "",
              "fp": d.get("fp") or ""}
    if d.get("tls"):
        params["security"] = "tls"
    ob = {"type": "vmess", "server": host, "server_port": port,
          "uuid": d.get("id") or "", "security": d.get("scy") or "auto",
          "alter_id": _int(d.get("aid"))}
    net = (d.get("net") or "tcp").lower()
    t = _transport(net, params)
    if t:
        ob["transport"] = t
    tls = _tls(params, host)
    if tls:
        ob["tls"] = tls
    name = d.get("ps") or f"{host}:{port}"
    return {"type": "vmess", "name": name, "host": host,
            "port": port, "link": link, "ob": ob}


def _parse_ss(link, name, host, port, u):
    body = link[len("ss://"):].split("#", 1)[0]
    if "@" in body:
        userinfo, rest = body.rsplit("@", 1)
        dec = _b64(userinfo)
        cred = (dec.decode("utf-8", errors="replace") if dec
                else urllib.parse.unquote(userinfo))
    else:
        dec = _b64(body)
        if not dec or "@" not in dec.decode("utf-8", errors="replace"):
            return None
        cred, rest = dec.decode("utf-8", errors="replace").rsplit("@", 1)
    if ":" not in cred:
        return None
    method, password = cred.split(":", 1)
    if "@" in rest:
        host_port = rest.rsplit("@", 1)[1]
        if ":" in host_port:
            host, port_s = host_port.rsplit(":", 1)
            port = _int(port_s, port)
    ob = {"type": "shadowsocks", "server": host, "server_port": port,
          "method": method, "password": password}
    return {"type": "ss", "name": name, "host": host, "port": port,
            "link": link, "ob": ob}


def parse_links(links):
    """Пакетный разбор; в список записей (нераспознанные пропускаются).

    К каждой записи добавляется «flag» — эмодзи-флаг по имени сервера.
    """
    out = []
    for l in links:
        rec = parse_link(l)
        if rec:
            rec["flag"] = guess_flag(rec["name"])
            out.append(rec)
    return out


# --------------------------------------------------------------------- пинг

def tcp_ping(host, port, timeout=2.5):
    """TCP-пинг: миллисекунды до сервера или None (таймаут/ошибка)."""
    t0 = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            pass
    except Exception:
        return None
    return round((time.perf_counter() - t0) * 1000)


def proxy_health(proxy_port, timeout=6):
    """Умная проверка туннеля: HTTP-запрос ЧЕРЕЗ прокси к generate_204.

    True — интернет через VPN реально работает.
    False — сервер принимает подключения (TCP-пинг живой), но трафик
    через него не проходит: sing-box отвечает 502 Bad Gateway, когда
    удалённый сервер мёртв (так бывает с «сдохшими» серверами подписок).
    """
    proxy = "http://127.0.0.1:%d" % proxy_port
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    for url in ("http://cp.cloudflare.com/generate_204",
                "http://www.gstatic.com/generate_204"):
        try:
            with opener.open(url, timeout=timeout) as r:
                if 200 <= r.status < 400:
                    return True
        except urllib.error.HTTPError as e:
            # ответ прокси-сервера получен: 5xx (например 502) = туннель мёртв
            if 200 <= e.code < 400:
                return True
        except Exception:
            pass
    return False


# ------------------------------------------------------------------ sing-box

def make_config(outbound, port, log_path=None):
    """Полный конфиг sing-box: прокси-инbound + выбранный сервер."""
    ob = dict(outbound)
    ob["tag"] = "proxy"
    cfg = {
        "log": {"level": "warn", "timestamp": True},
        "inbounds": [{"type": "mixed", "tag": "in", "listen": "127.0.0.1",
                      "listen_port": port}],
        "outbounds": [ob, {"type": "direct", "tag": "direct"}],
        "route": {"final": "proxy"},
    }
    if log_path:
        cfg["log"]["output"] = log_path
    return cfg


def find_free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def tail_file(path, lines=12):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return "".join(f.readlines()[-lines:])
    except OSError:
        return ""


# ----------------------------------------------------------- системный прокси

_INTERNET_SETTINGS = (r"Software\Microsoft\Windows\CurrentVersion"
                      r"\Internet Settings")


def save_proxy_state():
    """Читает текущие значения системного прокси."""
    import winreg
    state = {}
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _INTERNET_SETTINGS)
        for name in ("ProxyEnable", "ProxyServer", "AutoConfigURL"):
            try:
                state[name] = winreg.QueryValueEx(key, name)[0]
            except OSError:
                state[name] = None
        winreg.CloseKey(key)
    except OSError:
        pass
    return state


def _refresh_wininet():
    import ctypes
    opt = ctypes.windll.Wininet.InternetSetOptionW
    opt(0, 39, 0, 0)   # INTERNET_OPTION_SETTINGS_CHANGED
    opt(0, 37, 0, 0)   # INTERNET_OPTION_REFRESH


def set_system_proxy(enabled, server=None):
    """Включает/выключает системный прокси Windows."""
    import winreg
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _INTERNET_SETTINGS, 0,
                         winreg.KEY_SET_VALUE)
    try:
        winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD,
                          1 if enabled else 0)
        if enabled and server:
            winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, server)
        winreg.DeleteValue(key, "AutoConfigURL")
    except OSError:
        pass
    winreg.CloseKey(key)
    _refresh_wininet()


def restore_proxy_state(state):
    """Возвращает сохранённое состояние прокси."""
    import winreg
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _INTERNET_SETTINGS, 0,
                         winreg.KEY_SET_VALUE)
    try:
        winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD,
                          _int(state.get("ProxyEnable")))
        if state.get("ProxyServer"):
            winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ,
                              str(state["ProxyServer"]))
        else:
            try:
                winreg.DeleteValue(key, "ProxyServer")
            except OSError:
                pass
        if state.get("AutoConfigURL"):
            winreg.SetValueEx(key, "AutoConfigURL", 0, winreg.REG_SZ,
                              str(state["AutoConfigURL"]))
        else:
            try:
                winreg.DeleteValue(key, "AutoConfigURL")
            except OSError:
                pass
    except OSError:
        pass
    winreg.CloseKey(key)
    _refresh_wininet()


def launch_core(exe, config_path):
    """Запускает sing-box скрыто. Возвращает Popen или None."""
    return subprocess.Popen(
        [exe, "run", "-c", config_path],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=CREATE_NO_WINDOW)
