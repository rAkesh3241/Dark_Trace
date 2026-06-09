"""
cowrie_watcher.py  –  Live Cowrie JSON log ingestor
Tails cowrie.json, parses every line, scores risk,
inserts into SQLite, and notifies Flask via REST so
the dashboard updates live via SocketIO.
"""

import os
import time
import json
import sqlite3
import hashlib
import datetime
import requests

from dotenv import load_dotenv
load_dotenv()

COWRIE_LOG    = os.getenv("COWRIE_LOG_PATH", "/cowrie_logs/cowrie.json")
DB_PATH       = os.getenv("SQLITE_DB",       "data/honeypot.db")
BACKEND_URL   = os.getenv("BACKEND_URL",     "http://localhost:5001")
POLL_INTERVAL = 0.5

print("=" * 60)
print("COWRIE LOG =", COWRIE_LOG)
print("DB PATH    =", os.path.abspath(DB_PATH))
print("BACKEND    =", BACKEND_URL)
print("=" * 60)

# ── Geo fallback ──────────────────────────────────────────────────────────────
FALLBACK_LOCATIONS = [
    {"lat": 51.5074, "lng": -0.1278,  "city": "London",    "country": "GB"},
    {"lat": 52.5200, "lng": 13.4050,  "city": "Berlin",    "country": "DE"},
    {"lat": 55.7558, "lng": 37.6173,  "city": "Moscow",    "country": "RU"},
    {"lat": 40.7128, "lng": -74.0060, "city": "New York",  "country": "US"},
    {"lat": 28.6139, "lng": 77.2090,  "city": "New Delhi", "country": "IN"},
    {"lat":  1.3521, "lng": 103.8198, "city": "Singapore", "country": "SG"},
    {"lat": 35.6762, "lng": 139.6503, "city": "Tokyo",     "country": "JP"},
    {"lat": 48.8566, "lng":   2.3522, "city": "Paris",     "country": "FR"},
    {"lat": 39.9042, "lng": 116.4074, "city": "Beijing",   "country": "CN"},
    {"lat": 37.5665, "lng": 126.9780, "city": "Seoul",     "country": "KR"},
]

def geo_lookup(ip):
    try:
        import geoip2.database
        r = geoip2.database.Reader("GeoLite2-City.mmdb").city(ip)
        return {
            "lat":     r.location.latitude  or 0,
            "lng":     r.location.longitude or 0,
            "city":    r.city.name or "",
            "country": r.country.iso_code or "",
        }
    except Exception:
        pass
    digest = hashlib.md5(ip.encode()).hexdigest()
    loc    = FALLBACK_LOCATIONS[int(digest, 16) % len(FALLBACK_LOCATIONS)]
    return {"lat": loc["lat"], "lng": loc["lng"], "city": loc["city"], "country": loc["country"]}


# ── Risk classifier ───────────────────────────────────────────────────────────
def classify_risk(command="", eventid="", message=""):
    text = f"{command} {eventid} {message}".lower()
    critical = [
        "rm -rf", "mkfs", "dd if=", "bash -i", "/dev/tcp", "nc -e",
        "chmod 777", "exec 5<>", "python3 -c 'import socket",
        "python -c 'import socket", "perl -e 'use Socket",
        "/bin/sh -i", "meterpreter", "reverse_tcp", "msfconsole",
        "msfvenom", "nc -lv", "socat", "chattr -i", "iptables -f",
    ]
    high = [
        "wget", "curl", "scp", "tftp", "python -c", "perl -e",
        "base64", "busybox", "xmrig", "stratum+tcp", "minerd",
        "ssh-keygen", "authorized_keys", "crontab -e",
        "chmod +x", "nmap", "masscan", "hydra", "medusa",
        "john", "hashcat", "sqlmap", "nikto", "gobuster",
        "linpeas", "linenum", "pspy", "bloodhound", "crackmapexec",
    ]
    medium = [
        "cat /etc/passwd", "cat /etc/shadow", "uname", "whoami", "id",
        "login.failed", "ps aux", "netstat", "ifconfig", "ip addr",
        "history", "env", "find / -perm", "sudo", "groups", "lastlog",
        "systemctl", "docker ps", "cat /proc", "ls /root",
    ]
    if any(x in text for x in critical): return 95
    if any(x in text for x in high):     return 75
    if any(x in text for x in medium):   return 45
    if "login.success" in text:          return 60
    if "login.failed"  in text:          return 40
    if "session.connect" in text:        return 25
    return 15


# ── DB helpers ────────────────────────────────────────────────────────────────
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT,
            ip          TEXT,
            command     TEXT,
            response    TEXT DEFAULT '',
            eventid     TEXT,
            src_port    TEXT DEFAULT '',
            dst_ip      TEXT DEFAULT '',
            dst_port    TEXT DEFAULT '',
            session     TEXT DEFAULT '',
            protocol    TEXT DEFAULT 'ssh',
            message     TEXT,
            username    TEXT DEFAULT '',
            password    TEXT DEFAULT '',
            duration    TEXT DEFAULT '',
            risk_score  INTEGER DEFAULT 0,
            country     TEXT DEFAULT '',
            city        TEXT DEFAULT '',
            lat         REAL  DEFAULT 0,
            lng         REAL  DEFAULT 0
        )
    """)
    conn.commit()


def insert_event(conn, ev, geo, risk):
    conn.execute("""
        INSERT INTO logs
            (timestamp, ip, command, response, eventid, src_port,
             session, protocol, message, username, password,
             risk_score, country, city, lat, lng)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        ev.get("timestamp", datetime.datetime.utcnow().isoformat() + "Z"),
        ev.get("src_ip",    ""),
        ev.get("input",     ev.get("username", "")),
        "",
        ev.get("eventid",  ""),
        str(ev.get("src_port", "")),
        ev.get("session",  ""),
        ev.get("protocol", "ssh"),
        ev.get("message",  ""),
        ev.get("username", ""),
        ev.get("password", ""),
        risk,
        geo["country"],
        geo["city"],
        geo["lat"],
        geo["lng"],
    ))
    conn.commit()


# ── Notify Flask backend ──────────────────────────────────────────────────────
def notify_backend(ev, geo, risk):
    try:
        payload = {
            "timestamp":  ev.get("timestamp", ""),
            "ip":         ev.get("src_ip",    ""),
            "command":    ev.get("input",     ev.get("username", "")),
            "eventid":    ev.get("eventid",   ""),
            "session":    ev.get("session",   ""),
            "username":   ev.get("username",  ""),
            "password":   ev.get("password",  ""),
            "message":    ev.get("message",   ""),
            "risk_score": risk,
            "city":       geo["city"],
            "country":    geo["country"],
            "lat":        geo["lat"],
            "lng":        geo["lng"],
        }
        requests.post(
            f"{BACKEND_URL}/api/internal/cowrie_event",
            json=payload,
            timeout=2,
        )
    except Exception:
        pass


# ── Relevant events ───────────────────────────────────────────────────────────
INTERESTING_EVENTS = {
    "cowrie.login.success",
    "cowrie.login.failed",
    "cowrie.command.input",
    "cowrie.command.success",
    "cowrie.command.failed",
    "cowrie.session.connect",
    "cowrie.session.closed",
    "cowrie.session.file_download",
    "cowrie.session.file_upload",
    "cowrie.direct-tcpip.request",
    "cowrie.direct-tcpip.data",
}


# ── Process a single line ─────────────────────────────────────────────────────
def process_line(line, conn):
    line = line.strip()
    if not line:
        return

    try:
        ev = json.loads(line)
    except json.JSONDecodeError:
        return

    eventid = ev.get("eventid", "")
    if eventid not in INTERESTING_EVENTS:
        return

    ip   = ev.get("src_ip", "127.0.0.1")
    risk = classify_risk(
        command = ev.get("input",   ""),
        eventid = eventid,
        message = ev.get("message", ""),
    )
    geo = geo_lookup(ip)

    try:
        insert_event(conn, ev, geo, risk)
    except Exception as e:
        print(f"[watcher] DB insert error: {e}")
        return

    notify_backend(ev, geo, risk)

    print(f"[watcher] {eventid:35s} | {ip:15s} | risk={risk:3d} | "
          f"{ev.get('input', ev.get('username', ''))[:60]}")


# ── Main tail loop ────────────────────────────────────────────────────────────
def tail_cowrie_log():
    print(f"[watcher] Waiting for Cowrie log: {COWRIE_LOG}")

    while not os.path.exists(COWRIE_LOG):
        time.sleep(2)

    print(f"[watcher] Log found. Importing existing logs then watching live...")

    conn = get_conn()
    ensure_table(conn)

    with open(COWRIE_LOG, "r", encoding="utf-8", errors="replace") as f:

        # Replay all existing lines first
        for line in f:
            process_line(line, conn)

        print(f"[watcher] Historical import done. Watching for new events...")

        # Then follow live
        while True:
            line = f.readline()
            if not line:
                time.sleep(POLL_INTERVAL)
                continue
            process_line(line, conn)


if __name__ == "__main__":
    tail_cowrie_log()