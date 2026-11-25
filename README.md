# Self-Hosted SMS Gateway (FastAPI + MongoDB + React Dashboard + Flutter App)

A production-ready SMS Gateway that queues SMS messages in MongoDB and dispatches them in real-time over WebSocket to your Android phone gateway app.

## Network & Access Endpoints (Unified Port 8072)

Both the **Frontend Dashboard** and the **Backend REST & WebSocket APIs** run continuously 24/7 on a single unified port: **`8072`** via IIS and Windows Services.

- **Admin Web Dashboard (LAN)**: [http://192.168.1.91:8072](http://192.168.1.91:8072)
- **Admin Web Dashboard (Public IP)**: [http://115.244.240.22:8072](http://115.244.240.22:8072)
- **Local Dashboard**: [http://localhost:8072](http://localhost:8072)
- **Backend API Docs (Swagger UI)**: [http://192.168.1.91:8072/docs](http://192.168.1.91:8072/docs)
- **Mobile App WebSocket Bridge (Public IP)**: `ws://115.244.240.22:8072/ws/device?token=rbpssk-sms-gateway-secret-2026`

---

## 24/7 Production Continuous Service

The stack runs continuously in the background with zero terminal windows needed:
1. **Windows Service (`SmsGatewayBackend`)**:
   - Manages FastAPI Uvicorn process with auto-restart on system boot.
   - Logs rotating output to `logs/service-stdout.log`.
2. **IIS Site (`SMS-Gateway-Backend` on Port 8072)**:
   - Serves the compiled React Vite SPA dashboard.
   - Reverse-proxies all `/api/*`, `/docs`, `/openapi.json`, and `/ws/*` (WebSockets) seamlessly to the FastAPI backend.

---

## Android App Setup (Public IP)

Open the **SMS Gateway** Android app:
1. Tap the **Settings** icon.
2. Set **Server URL** to:
   ```text
   ws://115.244.240.22:8072/ws/device
   ```
3. Set **Device Secret Token** to:
   ```text
   rbpssk-sms-gateway-secret-2026
   ```
4. Tap **Save Settings** and ensure the Gateway switch is active.
