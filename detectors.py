"""Pure detection logic (no network). Unit-tested in test_detectors.py."""
import math
import re

EARTH_NM = 3440.065


def dist_nm(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_NM * math.asin(math.sqrt(a))


def bearing(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    x = math.sin(dl) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def nearest_airport(lat, lon, airports):
    best, best_d = None, 1e9
    for icao, (_, alat, alon) in airports.items():
        d = dist_nm(lat, lon, alat, alon)
        if d < best_d:
            best, best_d = icao, d
    return best, best_d


# ---------------------------------------------------------------------------
# Holding pattern detection
# track point = [t, lat, lon, alt_ft, gs_kt, callsign]
# ---------------------------------------------------------------------------
def detect_hold(points, min_window_sec=360):
    """Return dict with hold info, or None.

    A hold is flagged when, over at least `min_window_sec`:
      * the aircraft is airborne (alt > 2500 ft) and fast (gs > 120 kt)
      * altitude stays roughly level (spread <= 1200 ft)
      * it turns through >= 300 degrees in total
      * it makes little net progress (net distance < 35% of path flown)
      * it stays inside a small area (<= 12 NM from its centre)
    """
    pts = [p for p in points if isinstance(p[3], (int, float))]
    if len(pts) < 6:
        return None
    t_end = pts[-1][0]
    window = [p for p in pts if t_end - p[0] <= min_window_sec * 1.6]
    if len(window) < 6 or window[-1][0] - window[0][0] < min_window_sec:
        return None

    alts = [p[3] for p in window]
    if min(alts) < 2500 or max(alts) - min(alts) > 1200:
        return None
    if min((p[4] or 0) for p in window) < 120:
        return None

    path = 0.0
    turn = 0.0
    prev_brg = None
    for a, b in zip(window, window[1:]):
        seg = dist_nm(a[1], a[2], b[1], b[2])
        path += seg
        if seg < 0.3:
            continue
        brg = bearing(a[1], a[2], b[1], b[2])
        if prev_brg is not None:
            d = (brg - prev_brg + 540) % 360 - 180
            turn += abs(d)
        prev_brg = brg
    if path < 5:
        return None
    net = dist_nm(window[0][1], window[0][2], window[-1][1], window[-1][2])

    clat = sum(p[1] for p in window) / len(window)
    clon = sum(p[2] for p in window) / len(window)
    spread = max(dist_nm(clat, clon, p[1], p[2]) for p in window)

    if turn >= 300 and net < 0.35 * path and spread <= 12:
        return {
            "lat": clat,
            "lon": clon,
            "alt": int(sum(alts) / len(alts)),
            "minutes": round((window[-1][0] - window[0][0]) / 60),
            "turn": int(turn),
        }
    return None


# ---------------------------------------------------------------------------
# NOTAM classification
# ---------------------------------------------------------------------------
Q_RE = re.compile(r"Q\)\s*([A-Z]{4})\s*/\s*Q([A-Z]{2})([A-Z]{2})")

AIRSPACE_SUBJECTS = {"AF", "AE", "AT", "AC", "AX", "AL", "AA", "AU", "AZ"}


def classify_notam(text):
    """Return a category string from config.NOTAM_CATEGORIES, or None."""
    if not text:
        return None
    up = text.upper()
    m = Q_RE.search(up)
    subj, cond = (m.group(2), m.group(3)) if m else (None, None)

    if subj:
        if cond == "AK" and (subj in AIRSPACE_SUBJECTS or subj in {"FA", "AR", "MR", "MX"}):
            return "REOPENED / RESUMED"
        if subj in {"GA", "GW"}:
            return "GNSS / GPS INTERFERENCE"
        if cond == "LC":
            if subj in AIRSPACE_SUBJECTS:
                return "FIR / AIRSPACE CLOSED"
            if subj == "FA":
                return "AERODROME CLOSED"
            if subj == "AR":
                return "ATS ROUTE CLOSED"
            if subj in {"MR", "MX"}:
                return "RUNWAY CLOSED"
        if subj[0] == "R" and cond in {"CA", "CR", "CH", "LT"}:
            return "RESTRICTED / DANGER AREA ACTIVE"

    # Fallback on free text when the Q-line is missing or generic
    body = up.split("E)", 1)[-1] if "E)" in up else up
    if re.search(r"\b(GNSS|GPS)\b.*\b(INTERFERENCE|JAMMING|SPOOFING|UNRELIABLE|OUTAGE)", body):
        return "GNSS / GPS INTERFERENCE"
    if re.search(r"\b(AIRSPACE|FIR)\b.*\b(CLSD|CLOSED)\b", body):
        return "FIR / AIRSPACE CLOSED"
    if re.search(r"\bAD\b.*\b(CLSD|CLOSED)\b", body) and "RWY" not in body:
        return "AERODROME CLOSED"
    return None


# ---------------------------------------------------------------------------
# Diversion check
# ---------------------------------------------------------------------------
def check_diversion(callsign, lat, lon, alt, route, airports, max_dist_nm=15, max_alt=4000):
    """route = (origin_icao, dest_icao). Returns airport ICAO if diverting there."""
    if not route or not route[1]:
        return None
    if isinstance(alt, (int, float)) and alt > max_alt:
        return None
    apt, d = nearest_airport(lat, lon, airports)
    if apt and d <= max_dist_nm and apt not in route:
        return apt
    return None


# ---------------------------------------------------------------------------
# Flight phase from recent track: "climb", "descent" or None
# ---------------------------------------------------------------------------
def flight_phase(points, current_alt=None):
    alts = [p[3] for p in points if isinstance(p[3], (int, float))]
    if current_alt == "ground":
        # on ground: arrival only if we saw it airborne before
        return "descent" if alts and max(alts) >= 2000 else None
    if isinstance(current_alt, (int, float)):
        alts = alts + [current_alt]
    if len(alts) < 2:
        return None
    if alts[-1] - min(alts) >= 800 and alts[-1] >= alts[0]:
        return "climb"
    if max(alts) - alts[-1] >= 1500 and alts[-1] <= alts[0]:
        return "descent"
    return None
