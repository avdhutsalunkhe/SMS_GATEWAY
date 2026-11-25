# Self-Hosted SMS Gateway Backend (FastAPI + MongoDB PyMongo AsyncMongoClient)

A 100% free, production-ready SMS Gateway backend that queues SMS messages in MongoDB and dispatches them over a real-time WebSocket connection to your Android phone.

## Project Structure

```text
.
├── main.py            # FastAPI app, REST endpoints, WebSocket device bridge, asyncio worker
├── database.py        # Settings, PyMongo AsyncMongoClient connection, indexes, Project 1 auto-seed
├── models.py          # Pydantic v2 request/response schemas and +91 / E.164 phone validation
├── .env.example       # Environment configuration template
├── requirements.txt   # Python dependencies
└── tests/             # Automated API, worker, and WebSocket tests
```

## Setup & Run Locally

### 1. Create `.env`

```powershell
Copy-Item .env.example .env
```

Edit `.env` and set a strong `DEVICE_SECRET` (and your `MONGODB_URI` — local MongoDB or free MongoDB Atlas).

### 2. Create Virtual Environment & Install Dependencies

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

*(On Linux/macOS: `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`)*

### 3. Start MongoDB (if running locally)

Using Docker:

```powershell
docker run -d --name sms-mongo -p 27017:27017 -v sms_mongo_data:/data/db mongo:7
```

Or use a free MongoDB Atlas M0 cluster URI in `MONGODB_URI`.

### 4. Run the FastAPI Server

```powershell
uvicorn main:app --host 0.0.0.0 --port 8000
```

On first startup, if the `projects` collection is empty, `"Project 1"` is automatically seeded and its API key is printed in the server logs (and visible via `GET /api/v1/admin/projects`).

## Exposing Locally for Free (No Cloudflare)

Choose any of these free non-Cloudflare options to reach your gateway from your Android phone over mobile data or external networks:

### Option A: Tailscale Funnel (Free, Persistent HTTPS/WSS URL)

```powershell
tailscale funnel 8000
```

Your phone connects to `wss://<your-machine>.<tailnet>.ts.net/ws/device?token=YOUR_DEVICE_SECRET`.

### Option B: ngrok (Free Tier HTTPS/WSS URL)

```powershell
ngrok http 8000
```

Use the generated `https://...` URL (and `wss://...` for the WebSocket endpoint).

### Option C: Pinggy (Free Zero-Install SSH Tunnel)

```powershell
ssh -p 443 -R0:localhost:8000 a.pinggy.io
```

### Option D: Local Wi-Fi / LAN Only (Zero Tunnel Required)

If your Android phone and PC are on the same Wi-Fi, connect directly to your PC's LAN IP:
`ws://<YOUR_PC_LAN_IP>:8000/ws/device?token=YOUR_DEVICE_SECRET`
