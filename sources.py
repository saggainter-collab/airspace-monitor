"""Network data sources (all free, no API key needed)."""
import time
import requests

UA = {"User-Agent": "personal-airspace-monitor/1.0 (non-commercial)"}
TIMEOUT = 20

# Live ADS-B traffic. Same API format on both; second one is a fallback.
ADSB_BASES = [
    "https://api.airplanes.live/v2",
    "https://api.adsb.lol/v2",
]

_last_adsb_call = 0.0


def _adsb_get(path):
    """Call the ADS-B API with ~1 request/second rate limit and fallback."""
    global _last_adsb_call
    for base in ADSB_BASES:
        wait = 1.1 - (time.time() - _last_adsb_call)
        if wait > 0:
            time.sleep(wait)
        _last_adsb_call = time.time()
        try:
            r = requests.get(f"{base}{path}", headers=UA, timeout=TIMEOUT)
            if r.status_code == 200:
                return r.json().get("ac") or []
        except (requests.RequestException, ValueError):
            pass
    return None  # all sources failed


def aircraft_near(lat, lon, radius_nm):
    return _adsb_get(f"/point/{lat:.4f}/{lon:.4f}/{int(min(radius_nm, 250))}")


def aircraft_by_squawk(code):
    return _adsb_get(f"/sqk/{code}")


# Flight route lookup (origin/destination by callsign), cached per run
_route_cache = {}


def route_for(callsign):
    cs = (callsign or "").strip().upper()
    if not cs:
        return None
    if cs in _route_cache:
        return _route_cache[cs]
    route = None
    try:
        r = requests.get(f"https://api.adsbdb.com/v0/callsign/{cs}", headers=UA, timeout=TIMEOUT)
        if r.status_code == 200:
            fr = (r.json().get("response") or {}).get("flightroute") or {}
            o = (fr.get("origin") or {}).get("icao_code")
            d = (fr.get("destination") or {}).get("icao_code")
            if o or d:
                route = (o, d)
    except (requests.RequestException, ValueError):
        pass
    _route_cache[cs] = route
    return route


# NOTAMs - FAA NOTAM Search (includes international NOTAMs by ICAO location)
NOTAM_URL = "https://notams.aim.faa.gov/notamSearch/search"


def fetch_notams(location):
    """Return list of NOTAM dicts for one ICAO location (FIR or aerodrome)."""
    out, offset = [], 0
    for _ in range(20):  # safety cap on pages
        data = {
            "searchType": "0",
            "designatorsForLocation": location,
            "offset": str(offset),
            "notamsOnly": "false",
        }
        try:
            r = requests.post(NOTAM_URL, data=data, headers=UA, timeout=TIMEOUT)
            if r.status_code != 200:
                break
            js = r.json()
        except (requests.RequestException, ValueError):
            break
        items = js.get("notamList") or []
        out.extend(items)
        total = int(js.get("totalNotamCount") or 0)
        offset += len(items)
        if not items or offset >= total:
            break
        time.sleep(0.5)
    return out
