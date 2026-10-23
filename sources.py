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


# ---------------------------------------------------------------------------
# NOTAMs - two free FAA sources (both include international ICAO locations).
# Source 1: FAA NOTAM Search (JSON). Source 2: FAA DINS (raw text), fallback.
# Every attempt is logged so problems are visible in the GitHub run log.
# ---------------------------------------------------------------------------
import html as _html
import re as _re

NOTAM_URL = "https://notams.aim.faa.gov/notamSearch/search"
DINS_URL = "https://www.notams.faa.gov/dinsQueryWeb/queryRetrievalMapAction.do"
BROWSER = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://notams.aim.faa.gov",
    "Referer": "https://notams.aim.faa.gov/notamSearch/nsapp.html",
}
_notam_source = {"ok": None}  # remembers which source worked this run


def _log(msg):
    print(f"[NOTAM] {msg}", flush=True)


def _fetch_search(location):
    out, offset = [], 0
    for _ in range(20):
        data = {
            "searchType": "0",
            "designatorsForLocation": location,
            "offset": str(offset),
            "notamsOnly": "false",
            "radius": "10",
            "sortColumns": "5 false",
            "sortDirection": "true",
        }
        try:
            r = requests.post(NOTAM_URL, data=data, headers=BROWSER, timeout=TIMEOUT)
        except requests.RequestException as e:
            _log(f"search {location}: network error {e}")
            return None
        if r.status_code != 200:
            _log(f"search {location}: HTTP {r.status_code} {r.text[:150]!r}")
            return None
        try:
            js = r.json()
        except ValueError:
            _log(f"search {location}: not JSON {r.text[:150]!r}")
            return None
        items = js.get("notamList") or []
        out.extend(items)
        total = int(js.get("totalNotamCount") or 0)
        offset += len(items)
        if not items or offset >= total:
            break
        time.sleep(0.5)
    return out


_PRE_RE = _re.compile(r"<PRE>(.*?)</PRE>", _re.S | _re.I)
_ID_RE = _re.compile(r"\b([A-Z]\d{4}/\d{2})\b")
_A_RE = _re.compile(r"A\)\s*([A-Z]{4})")


def _fetch_dins(location):
    params = {
        "reportType": "Raw",
        "retrieveLocId": location,
        "actionType": "notamRetrievalbyICAOs",
    }
    try:
        r = requests.get(DINS_URL, params=params, headers={"User-Agent": BROWSER["User-Agent"]},
                         timeout=TIMEOUT)
    except requests.RequestException as e:
        _log(f"dins {location}: network error {e}")
        return None
    if r.status_code != 200:
        _log(f"dins {location}: HTTP {r.status_code}")
        return None
    out = []
    for block in _PRE_RE.findall(r.text):
        text = _html.unescape(_re.sub(r"<[^>]+>", "", block)).strip()
        m = _ID_RE.search(text)
        if not m:
            continue
        a = _A_RE.search(text)
        out.append({
            "icaoMessage": text,
            "notamNumber": m.group(1),
            "facilityDesignator": a.group(1) if a else location,
        })
    if not out and "NOTAM" not in r.text.upper():
        _log(f"dins {location}: unexpected page {r.text[:150]!r}")
        return None
    return out


def fetch_notams(location):
    """Return list of NOTAM dicts for one ICAO location, or None if all sources fail."""
    order = [_fetch_search, _fetch_dins]
    if _notam_source["ok"] is _fetch_dins:
        order = [_fetch_dins, _fetch_search]
    for fn in order:
        items = fn(location)
        if items is not None:
            if _notam_source["ok"] is not fn:
                _log(f"using source: {fn.__name__} ({len(items)} items for {location})")
            _notam_source["ok"] = fn
            return items
    return None
