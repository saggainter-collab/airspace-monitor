import math
import detectors as D
import config as C

NM_DEG = 1 / 60.0


def racetrack(lat0, lon0, t0=0, laps=2, step=30, gs=220, alt=14000):
    """Simulate a standard 1-min-leg racetrack hold, sampled every `step` s."""
    pts = []
    leg_nm = gs / 60.0
    r_nm = leg_nm / math.pi
    total = int(laps * 240)
    for t in range(0, total + 1, step):
        s = (t % 240)
        if s < 60:      # outbound leg north
            x, y = 0, s / 60 * leg_nm
        elif s < 120:   # turn
            a = (s - 60) / 60 * math.pi
            x, y = r_nm - r_nm * math.cos(a), leg_nm + r_nm * math.sin(a)
        elif s < 180:   # inbound leg south
            x, y = 2 * r_nm, leg_nm - (s - 120) / 60 * leg_nm
        else:           # turn
            a = (s - 180) / 60 * math.pi
            x, y = r_nm + r_nm * math.cos(a), -r_nm * math.sin(a)
        lat = lat0 + y * NM_DEG
        lon = lon0 + x * NM_DEG / math.cos(math.radians(lat0))
        pts.append([t0 + t, lat, lon, alt, gs, "KNE123"])
    return pts


def straight(lat0, lon0, step=30, gs=450, alt=36000, minutes=10):
    return [[t, lat0 + (gs / 3600 * t) * NM_DEG, lon0, alt, gs, "KNE1"]
            for t in range(0, minutes * 60 + 1, step)]


def test_hold_detected():
    h = D.detect_hold(racetrack(21.9, 39.3), 360)
    assert h is not None and h["minutes"] >= 6


def test_straight_not_hold():
    assert D.detect_hold(straight(21.0, 39.0), 360) is None


def test_descending_not_hold():
    pts = racetrack(21.9, 39.3)
    for i, p in enumerate(pts):
        p[3] = 14000 - i * 400
    assert D.detect_hold(pts, 360) is None


def test_short_pattern_not_hold():
    assert D.detect_hold(racetrack(21.9, 39.3, laps=1)[:8], 360) is None


def test_notam_classification():
    fir = "A1234/26 NOTAMN Q) OEJD/QAFLC/IV/NBO/E/000/999/2130N03910E999 A) OEJD E) JEDDAH FIR CLSD"
    ad = "Q) OEJD/QFALC/IV/NBO/A/000/999/ A) OEJN E) AD CLSD"
    rwy = "Q) OEJD/QMRLC/IV/NBO/A/000/999/ A) OEJN E) RWY 16L/34R CLSD DUE WIP"
    gps = "Q) OEJD/QGWAU/IV/BO/E/000/999/ E) GNSS SIGNAL UNRELIABLE"
    reopen = "Q) OEJD/QAFAK/IV/NBO/E/000/999/ E) JEDDAH FIR RESUMED NORMAL OPS"
    restr = "Q) OEJD/QRTCA/IV/BO/W/000/999/ E) TEMPO RESTRICTED AREA ACTIVATED"
    free = "E) DUE TO MIL ACTIVITY AIRSPACE CLOSED FOR ALL CIVIL ACFT"
    assert D.classify_notam(fir) == "FIR / AIRSPACE CLOSED"
    assert D.classify_notam(ad) == "AERODROME CLOSED"
    assert D.classify_notam(rwy) == "RUNWAY CLOSED"
    assert D.classify_notam(gps) == "GNSS / GPS INTERFERENCE"
    assert D.classify_notam(reopen) == "REOPENED / RESUMED"
    assert D.classify_notam(restr) == "RESTRICTED / DANGER AREA ACTIVE"
    assert D.classify_notam(free) == "FIR / AIRSPACE CLOSED"
    assert D.classify_notam("Q) OEJD/QOBCE/IV/M/A/000/999/ E) CRANE ERECTED") is None


def test_diversion():
    # KNE flight planned OERK->OEJN, now low near Madinah
    assert D.check_diversion("KNE123", 24.56, 39.71, 2000, ("OERK", "OEJN"), C.AIRPORTS) == "OEMA"
    # Landing at its planned destination: no alert
    assert D.check_diversion("KNE123", 21.68, 39.16, 1500, ("OERK", "OEJN"), C.AIRPORTS) is None
    # High altitude: no alert
    assert D.check_diversion("KNE123", 24.56, 39.71, 30000, ("OERK", "OEJN"), C.AIRPORTS) is None



def test_flight_phase():
    dep = [[0, 0, 0, 0, 150, ""], [30, 0, 0, 1500, 180, ""], [60, 0, 0, 3200, 200, ""]]
    arr = [[0, 0, 0, 9000, 250, ""], [30, 0, 0, 6000, 220, ""], [60, 0, 0, 3500, 180, ""]]
    assert D.flight_phase(dep[:-1], 3200) == "climb"
    assert D.flight_phase(arr[:-1], 3500) == "descent"
    assert D.flight_phase(arr, "ground") == "descent"
    assert D.flight_phase([], "ground") is None


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name)
