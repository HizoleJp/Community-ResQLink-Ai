# ResQlink Python + Phone Integration

This is a Python FastAPI version of the ResQlink backend. It uses SQLite and exposes the same core hazard-report and SOS API used by the mobile-friendly interface.

## Run locally

Install Python 3.10+:

    python -m venv .venv
    pip install -r requirements.txt
    python app.py

    By default the API uses its local SQLite database. To use the supplied MySQL database instead:

    1. Install MySQL 8+ and import the schema once from the project folder. In PowerShell:

           cmd /c "mysql -u root -p < server\schema.sql"

       Or open `server/schema.sql` in MySQL Workbench and run it. The script includes sample records; import it only once.

    2. Copy `server/.env.example` to `server/.env` and set `DATABASE_URL` to your MySQL username, password, host, and `resqlink_db` database. Do not commit or share `server/.env`.

    3. Install the server requirements and start it from the `server` folder:

        .venv\Scripts\python -m pip install -r requirements.txt
        .venv\Scripts\python app.py

    When `DATABASE_URL` is configured, reports and SOS use `disaster_reports` and `sos_alerts`; agencies and shelters are read from `emergency_agencies` and `shelters`. Without it, the existing SQLite implementation remains active.

On Windows, activate with:
    .venv\Scripts\activate

On Android/Pydroid, you can also install the requirements and run the FastAPI server.

## Connect your phone over Wi-Fi

Find your computer's local IP, for example 192.168.1.20.

Start the server with:
    python app.py

From the phone, open:
    http://192.168.1.20:8001/docs

The computer and phone must be on the same network.

## Permanent phone access

For a real deployment, host this FastAPI server on an HTTPS server. Then point the ResQlink mobile web/PWA or native client to that API URL.

Keeping the existing mobile web interface as a PWA is the simplest phone integration. A native Android client can later be built with Kivy or BeeWare and call these same endpoints.

## API

GET  /api/health
GET  /api/hazards
POST /api/hazards
POST /api/reports
GET  /api/agencies?type=hospital&lat=14.45&lng=120.97
GET  /api/shelters?lat=14.45&lng=120.97
GET  /api/sos/status
POST /api/sos
DELETE /api/sos
GET  /api/admin/overview
PUT  /api/admin/hazards/{id}/verify
DELETE /api/admin/hazards/{id}
POST /api/admin/sos/clear

## Administrator security

Set ADMIN_TOKEN to a strong secret before using administrator endpoints. Do not put a real token inside a public mobile application. For production, use HTTPS, real account authentication, and an administrator role/allowlist.
