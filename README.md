# DarkTrace

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Node.js](https://img.shields.io/badge/node.js-18+-green.svg)](https://nodejs.org/)
[![React](https://img.shields.io/badge/react-latest-blue.svg)](https://reactjs.org/)
[![Flask](https://img.shields.io/badge/flask-latest-lightgrey.svg)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

---

## What is DarkTrace?

DarkTrace is a local honeypot monitoring platform built for controlled security research and lab environments. It combines a Flask/Socket.IO backend, a React dashboard, SQLite event storage, and optional integrations for Cowrie SSH honeypot ingestion, MongoDB authentication, and a fine-tuned language model for simulated shell responses.

> **Important:** Run DarkTrace only in environments where you have explicit permission to collect and analyze traffic. This tool is intended for lab use only.

---

## Features

- Live React security dashboard with attack counters, logs, analytics, and map views
- Flask REST API for summaries, logs, command statistics, clusters, timeline data, and attack IP locations
- Socket.IO event stream for real-time dashboard updates
- Browser-based terminal console for running local project commands through the backend
- Simulated Linux shell responses for attacker-style command interaction
- Risk scoring for commands and Cowrie events
- SQLite persistence for captured events
- Optional Cowrie Docker setup for SSH honeypot telemetry
- Optional Hugging Face causal language model for AI-assisted shell responses
- Optional MongoDB-backed register/login API

---

## Project Structure

```
.
├── backend/
│   ├── app.py               # Flask API, Socket.IO server, terminal handling
│   ├── cowrie_watcher.py    # Tails Cowrie JSON logs and forwards events
│   ├── train_model.py       # Fine-tunes the local response model
│   ├── import_dataset.py    # Imports CSV events into SQLite
│   ├── requirements.txt     # Python dependencies
│   └── models/              # Optional trained model files
├── frontend/
│   ├── src/                 # React dashboard source
│   └── package.json         # Frontend scripts and dependencies
├── docker/
│   ├── docker-compose.yml   # Cowrie + backend services
│   └── cowrie.cfg           # Cowrie configuration
├── scripts/
│   └── prepare_data.py      # Downloads Cowrie sample data for training
├── phase1/                  # Training/data artifacts
└── README.md
```

---

## Requirements

- Python 3.11 (recommended)
- Node.js and npm
- Docker Desktop *(only if using the Cowrie Docker workflow)*
- MongoDB *(only if enabling the register/login routes)*

---

## Getting Started

### 1. Install backend dependencies

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Configure the backend

Create a `.env` file inside `backend/`:

```env
SECRET_KEY=change-this-secret
SQLITE_DB=data/honeypot.db
MODEL_PATH=./models/honeypot_model
USE_AI_MODEL=false
MONGO_URI=
MONGO_DB=honey_hive
ENABLE_HOST_POWERSHELL=false
```

> **Warning:** Setting `ENABLE_HOST_POWERSHELL=true` allows the web terminal to execute host PowerShell commands through the backend. Only enable this in a fully trusted, isolated lab environment.

### 3. Start the backend

```powershell
cd backend
python app.py
```

The backend runs at:

```
http://localhost:5001
```

### 4. Install and start the frontend

Open a second terminal:

```powershell
cd frontend
npm install
npm start
```

The dashboard will be available at:

```
http://localhost:3000
```

---

## Optional: Cowrie SSH Honeypot (Docker)

If you want real SSH honeypot telemetry, use the provided Docker setup:

```powershell
cd docker
docker compose up -d
```

Once running, `cowrie_watcher.py` will tail Cowrie's JSON logs and forward events to the backend automatically.

---

## Optional: AI Shell Responses

DarkTrace supports a fine-tuned Hugging Face causal language model to generate realistic shell responses for attacker interactions.

**Step 1 — Prepare training data:**

```powershell
python scripts/prepare_data.py
```

**Step 2 — Fine-tune the model:**

```powershell
cd backend
python train_model.py
```

**Step 3 — Enable it in `.env`:**

```env
USE_AI_MODEL=true
MODEL_PATH=./models/honeypot_model
```

---

## Optional: MongoDB Authentication

To enable user registration and login:

1. Spin up a MongoDB instance (local or [MongoDB Atlas](https://www.mongodb.com/cloud/atlas)).
2. Set `MONGO_URI` in your `.env` file.
3. Restart the backend — the `/register` and `/login` routes will become active.

Without MongoDB, authentication routes are disabled and the app runs in open local mode.

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/summary` | Overall attack summary and counters |
| GET | `/api/logs` | Captured honeypot event logs |
| GET | `/api/commands` | Command statistics and frequency |
| GET | `/api/clusters` | Clustered attacker behavior |
| GET | `/api/timeline` | Attack timeline data |
| GET | `/api/locations` | Attack IP geolocation data |
| POST | `/api/register` | Register a new user (MongoDB required) |
| POST | `/api/login` | Log in a user (MongoDB required) |

Socket.IO events are streamed in real time to the dashboard as new honeypot events arrive.

---

## Risk Scoring

DarkTrace assigns a risk score to every captured command and Cowrie event based on factors like:

- Known malicious command patterns
- Privilege escalation attempts
- File system enumeration
- Network reconnaissance activity

Scores are visible in the dashboard and exportable via the logs API.

---

## Tech Stack

**Backend:** Python 3.11 · Flask · Flask-SocketIO · SQLite · Hugging Face Transformers · pymongo

**Frontend:** React · Socket.IO client · Leaflet (map views)

**Infrastructure:** Docker · Cowrie SSH Honeypot · MongoDB Atlas (optional)

---

## Security Notice

DarkTrace is designed for **lab and research use only**. Do not deploy it on production systems or public-facing networks. The simulated shell and terminal features can expose your host system if misconfigured. Always:

- Keep `ENABLE_HOST_POWERSHELL=false` unless you fully understand the risk
- Run inside an isolated VM or lab network
- Never expose port 5001 to the public internet

---

## Contributing

1. Fork the repo
2. Create a branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m "Add your feature"`
4. Push: `git push origin feature/your-feature`
5. Open a Pull Request

Please follow PEP 8 for Python and ESLint for React code.

---

## License

MIT License — free to use, modify, and distribute. Keep the original copyright notice intact.

---

## Contact

Maintainer: Rakesh
Email: sairakesh6309@gmail.com
GitHub: @rAkesh3241

---

*Built for security research. Use responsibly.*
