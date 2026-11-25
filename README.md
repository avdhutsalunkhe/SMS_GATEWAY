# Self-Hosted SMS Gateway (FastAPI + MongoDB + React Dashboard + Flutter App)

A production-ready SMS Gateway that queues SMS messages in MongoDB and dispatches them in real-time over WebSocket to your Android phone gateway app.

## Network & Access Endpoints

- **Backend Port**: `8072`
- **Admin & Dashboard (LAN)**: `http://192.168.1.91:5173` (connecting to Backend at `http://192.168.1.91:8072`)
- **Backend API Docs (Swagger)**: `http://192.168.1.91:8072/docs` or `http://localhost:8072/docs`
- **Mobile App WebSocket (Public IP)**: `ws://115.244.240.22:8072/ws/device?token=rbpssk-sms-gateway-secret-2026`

---

## Project Structure

```text
.
├── main.py                     # FastAPI app, REST endpoints, WebSocket device bridge, asyncio worker
├── database.py                 # Settings, PyMongo AsyncMongoClient connection, indexes, Project auto-seed
├── models.py                   # Pydantic v2 schemas and +91 / E.164 phone validation
├── start_all.bat               # Starts both FastAPI (:8072) and React Dashboard (:5173) in separate windows
├── start_backend.bat           # Starts FastAPI backend on port 8072
├── start_frontend.bat          # Starts React Vite dashboard on port 5173
├── web_dashboard/              # React + Vite admin dashboard (CORS configured for LAN & local)
│   ├── .env                    # VITE_API_BASE_URL=http://192.168.1.91:8072
│   └── src/                    # UI components, logs table, test sender, API key manager
├── sms_gateway_app/            # Flutter Android gateway app
│   └── lib/services/           # WebSocket foreground service & background worker
└── tests/                      # Automated API, worker, and WebSocket tests
```

---

## Quick Start

### 1. Launch Everything (Windows)
Double-click `start_all.bat` or run:
```powershell
.\start_all.bat
```

### 2. Run Backend Separately
```powershell
.\.venv\Scripts\activate.ps1
$env:PYTHONPATH="."
python -m uvicorn main:app --host 0.0.0.0 --port 8072
```

### 3. Run Frontend Dashboard
```powershell
cd web_dashboard
npm run dev -- --host 0.0.0.0 --port 5173
```

---

## Android App Setup (Public IP)

Open the **SMS Gateway** Android app:
1. Tap the **Settings** icon.
2. Ensure **Server URL** is set to:
   ```text
   ws://115.244.240.22:8072/ws/device
   ```
3. Set **Device Secret Token** to:
   ```text
   rbpssk-sms-gateway-secret-2026
   ```
4. Tap **Save Settings** and ensure the Gateway switch is active.
