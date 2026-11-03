import requests

# Replace with your computer's actual LAN IP for phone testing, e.g. http://192.168.1.20:8001
# For Android emulator, use http://10.0.2.2:8001
# For local testing on the same machine, use http://127.0.0.1:8001
API_BASE = 'http://192.168.254.149:8001'

def hazards():
    r = requests.get(f"{API_BASE}/api/hazards", timeout=10)
    r.raise_for_status()
    return r.json()["items"]


def report(type_, description, lat, lng):
    r = requests.post(
        f"{API_BASE}/api/hazards",
        json={"type": type_, "description": description, "lat": lat, "lng": lng},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def sos(lat, lng, label="Current phone location"):
    r = requests.post(
        f"{API_BASE}/api/sos",
        json={"lat": lat, "lng": lng, "label": label},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def stop_sos():
    r = requests.delete(f"{API_BASE}/api/sos", timeout=10)
    r.raise_for_status()
    return r.json()
