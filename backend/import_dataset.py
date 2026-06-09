import csv
import os
import sqlite3

DATA_FILE = os.getenv("DATA_FILE", r"C:\Users\Sai RaKESH\Desktop\final_dataset.csv")
DB_PATH = os.getenv("SQLITE_DB", "honeypot.db")


def classify_risk(command="", eventid="", message=""):
    text = f"{command} {eventid} {message}".lower()

    if any(x in text for x in ["rm -rf", "wget", "curl", "bash -i", "nc -e", "chmod 777"]):
        return 80
    if "login.success" in text:
        return 60
    if "login.failed" in text:
        return 45
    if "session.connect" in text:
        return 30
    return 20


def setup_database(cur, conn):
    cur.execute("""
    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        ip TEXT,
        command TEXT,
        response TEXT,
        eventid TEXT,
        src_port TEXT,
        dst_ip TEXT,
        dst_port TEXT,
        session TEXT,
        protocol TEXT,
        message TEXT,
        username TEXT,
        password TEXT,
        duration TEXT,
        risk_score INTEGER DEFAULT 0
    )
    """)

    existing_columns = {
        row[1] for row in cur.execute("PRAGMA table_info(logs)").fetchall()
    }

    required_columns = {
        "eventid": "TEXT",
        "src_port": "TEXT",
        "dst_ip": "TEXT",
        "dst_port": "TEXT",
        "session": "TEXT",
        "protocol": "TEXT",
        "message": "TEXT",
        "username": "TEXT",
        "password": "TEXT",
        "duration": "TEXT",
        "risk_score": "INTEGER DEFAULT 0",
    }

    for column_name, column_type in required_columns.items():
        if column_name not in existing_columns:
            cur.execute(f"ALTER TABLE logs ADD COLUMN {column_name} {column_type}")

    cur.execute("CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs(timestamp)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_logs_ip ON logs(ip)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_logs_command ON logs(command)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_logs_eventid ON logs(eventid)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_logs_session ON logs(session)")

    conn.commit()


def main():
    if not os.path.exists(DATA_FILE):
        raise FileNotFoundError(f"Dataset not found: {DATA_FILE}")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    setup_database(cur, conn)

    inserted = 0

    with open(DATA_FILE, "r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            eventid = row.get("eventid", "")
            message = row.get("message", "")
            ip = row.get("src_ip", "")
            timestamp = row.get("timestamp", "")
            username = row.get("username", "")
            password = row.get("password", "")
            session = row.get("session", "")

            command = ""
            response = message
            risk_score = classify_risk(command=command, eventid=eventid, message=message)

            cur.execute("""
                INSERT INTO logs (
                    timestamp,
                    ip,
                    command,
                    response,
                    eventid,
                    src_port,
                    dst_ip,
                    dst_port,
                    session,
                    protocol,
                    message,
                    username,
                    password,
                    duration,
                    risk_score
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                timestamp,
                ip,
                command,
                response,
                eventid,
                row.get("src_port", ""),
                row.get("dst_ip", ""),
                row.get("dst_port", ""),
                session,
                row.get("protocol", ""),
                message,
                username,
                password,
                row.get("duration", ""),
                risk_score,
            ))

            inserted += 1

    conn.commit()
    conn.close()

    print(f"Imported {inserted} rows into {DB_PATH}")


if __name__ == "__main__":
    main()