"""
Airspace Monitor - main loop.
Runs for RUN_SECONDS (default 540), then saves state and exits.
GitHub Actions starts it again every 10 minutes.
"""
import json
import os
import time
from datetime import datetime, timedelta, timezone

import config as C
import detectors as D
import notify as N
import sources as S

STATE_FILE = "state.json"
RUN_SECONDS = int(os.environ.get("RUN_SECONDS", "540"))
TRACK_KEEP_SEC = 900
RIYADH = timezone(timedelta(hours=3))


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_state(st):
    with open(STATE_FILE, "w") as f:
        json.dump(st, f)


def cooled_down(st, kind, key, now):
    alerts = st.setdefault("alerts", {})
    k = f"{kind}:{key}"
    if now - alerts.get(k, 0) < C.ALERT_COOLDOWN_SEC[kind]:
        return False
    alerts[k] = now
    return True


def now_local_str():
    return datetime.now(RIYADH).strftime("%d %b %Y %H:%M") + " KSA"


def map_link(hexid):
    return f"https://globe.airplanes.live/?icao={hexid}"


def ac_label(ac):
    cs = (ac.get("flight") or "").strip() or "UNKNOWN"
    parts = [cs]
    if ac.get("t"):
        parts.append(ac["t"])
    if ac.get("r"):
        parts.append(ac["r"])
    return " | ".join(parts)


# ---------------------------------------------------------------------------
# NOTAMs
# ---------------------------------------------------------------------------
def check_notams(st, now, first_run):
    seen = st.setdefault("notams_seen", {})
    locations = list(C.FIRS) + list(C.AIRPORTS)
    new_alerts, active, fetched_any = [], [], False

    for loc in locations:
        items = S.fetch_notams(loc)
        if items is None:
            continue
        fetched_any = True
        for n in items:
            text = n.get("icaoMessage") or n.get("traditionalMessage") or ""
            num = n.get("notamNumber") or ""
            fac = n.get("facilityDesignator") or n.get("icaoId") or loc
            nid = f"{fac}-{num}"
            if not num or str(n.get("cancelledOrExpired")).lower() == "true":
                continue
            cat = D.classify_notam(text)
            if not cat or not C.NOTAM_CATEGORIES.get(cat):
                continue
            entry = (loc, cat, nid, text)
            active.append(entry)
            if nid not in seen:
                seen[nid] = now
                if not first_run:
                    new_alerts.append(entry)

    # forget very old ids (30 days)
    for k in [k for k, v in seen.items() if now - v > 30 * 86400]:
        del seen[k]

    for loc, cat, nid, text in new_alerts:
        place = C.FIRS.get(loc) or C.AIRPORTS.get(loc, (loc,))[0]
        icon = "🟢" if cat.startswith("REOPENED") else "🔴"
        N.send(
            f"{icon} <b>NEW NOTAM - {N.esc(cat)}</b>\n"
            f"📍 {N.esc(loc)} - {N.esc(place)}\n"
            f"🆔 {N.esc(nid)}\n\n"
            f"<code>{N.esc(text[:1500])}</code>\n\n"
            f"🕒 {now_local_str()}"
        )

    if first_run and fetched_any:
        lines = [
            "✅ <b>Airspace Monitor started</b>",
            f"Watching {len(C.FIRS)} FIRs and {len(C.AIRPORTS)} airports.",
            f"Currently active relevant NOTAMs: <b>{len(active)}</b>",
            "",
        ]
        by_cat = {}
        for loc, cat, nid, text in active:
            by_cat.setdefault(cat, []).append(f"• {loc} {nid}")
        for cat, rows in by_cat.items():
            lines.append(f"<b>{N.esc(cat)}</b> ({len(rows)})")
            lines.extend(N.esc(r) for r in rows[:25])
            if len(rows) > 25:
                lines.append(f"• ...and {len(rows) - 25} more")
            lines.append("")
        lines.append("From now on you will only receive NEW items.")
        N.send("\n".join(lines))

    return fetched_any


# ---------------------------------------------------------------------------
# Live traffic
# ---------------------------------------------------------------------------
def update_tracks(st, now, ac_list):
    tracks = st.setdefault("tracks", {})
    for ac in ac_list:
        hexid = ac.get("hex")
        lat, lon = ac.get("lat"), ac.get("lon")
        if not hexid or lat is None or lon is None:
            continue
        pt = [now, lat, lon, ac.get("alt_baro"), ac.get("gs"), (ac.get("flight") or "").strip()]
        tr = tracks.setdefault(hexid, [])
        if not tr or now - tr[-1][0] >= 10:
            tr.append(pt)
    for hexid in list(tracks):
        tracks[hexid] = [p for p in tracks[hexid] if now - p[0] <= TRACK_KEEP_SEC]
        if not tracks[hexid]:
            del tracks[hexid]


def sweep_airports(st, now):
    """Poll traffic around every airport. Returns dict hex -> aircraft."""
    seen, ok, counts, failed = {}, False, {}, []
    for icao, (_, lat, lon) in C.AIRPORTS.items():
        acs = S.aircraft_near(lat, lon, C.AIRPORT_RADIUS_NM)
        if acs is None:
            failed.append(icao)
            continue
        ok = True
        counts[icao] = len(acs)
        for ac in acs:
            if ac.get("hex"):
                seen[ac["hex"]] = ac
    update_tracks(st, now, seen.values())
    busiest = sorted(counts.items(), key=lambda x: -x[1])[:8]
    print(f"[SWEEP] {datetime.now(RIYADH):%H:%M:%S} aircraft={len(seen)} "
          f"top={busiest} failed={failed}", flush=True)
    return seen, ok


def check_holds(st, now, current):
    for hexid, pts in st.get("tracks", {}).items():
        if hexid not in current:
            continue
        h = D.detect_hold(pts, C.HOLD_WINDOW_SEC)
        if h:
            print(f"[HOLD] {hexid} {(current[hexid].get('flight') or '').strip()} {h}", flush=True)
        if not h or not cooled_down(st, "hold", hexid, now):
            continue
        ac = current[hexid]
        apt, d = D.nearest_airport(h["lat"], h["lon"], C.AIRPORTS)
        name = C.AIRPORTS[apt][0]
        N.send(
            f"🟠 <b>HOLDING DETECTED</b>\n"
            f"✈️ {N.esc(ac_label(ac))}\n"
            f"📍 {d:.0f} NM from {apt} ({N.esc(name)})\n"
            f"⬆️ ~FL{h['alt'] // 100:03d} ({h['alt']:,} ft)\n"
            f"⏱ Pattern for {h['minutes']} min\n\n"
            f"{map_link(hexid)}\n\n"
            f"🕒 {now_local_str()}"
        )


def check_diversions(st, now, current):
    """Alert only when a flight is clearly ARRIVING at an airport that is not
    on its published route. If we see a flight DEPART from an airport that is
    not its published origin, its route data is stale: ignore it for 24 h."""
    prefixes = tuple(p.upper() for p in C.DIVERSION_CALLSIGN_PREFIXES)
    bad = st.setdefault("bad_routes", {})
    for k in [k for k, v in bad.items() if now - v > 86400]:
        del bad[k]
    tracks = st.get("tracks", {})

    for hexid, ac in current.items():
        cs = (ac.get("flight") or "").strip().upper()
        if not cs.startswith(prefixes) or ac.get("lat") is None:
            continue
        alt = ac.get("alt_baro")
        if isinstance(alt, (int, float)) and alt > 6000:
            continue
        route = S.route_for(cs)
        if not route or cs in bad:
            continue
        phase = D.flight_phase(tracks.get(hexid, [])[:-1], alt)
        apt, dist = D.nearest_airport(ac["lat"], ac["lon"], C.AIRPORTS)

        if phase == "climb" and dist <= 20 and route[0] and apt != route[0]:
            bad[cs] = now
            print(f"[ROUTE] {cs}: departed {apt}, database says {route[0]}; route ignored 24h")
            continue
        if phase != "descent":
            continue

        div_apt = D.check_diversion(cs, ac["lat"], ac["lon"], alt, route, C.AIRPORTS)
        if div_apt and cooled_down(st, "diversion", f"{hexid}:{div_apt}", now):
            N.send(
                f"🟣 <b>POSSIBLE DIVERSION</b>\n"
                f"✈️ {N.esc(ac_label(ac))}\n"
                f"🛫 Planned: {route[0] or '?'} → {route[1] or '?'}\n"
                f"🛬 Now landing at: {div_apt} ({N.esc(C.AIRPORTS[div_apt][0])})\n"
                f"ℹ️ Route data comes from a public schedule database; please confirm.\n\n"
                f"{map_link(hexid)}\n\n"
                f"🕒 {now_local_str()}"
            )


def check_emergencies(st, now):
    la0, la1, lo0, lo1 = C.REGION_BBOX
    for code, label in C.EMERGENCY_SQUAWKS.items():
        acs = S.aircraft_by_squawk(code) or []
        for ac in acs:
            lat, lon = ac.get("lat"), ac.get("lon")
            if lat is None or lon is None:
                continue
            if not (la0 <= lat <= la1 and lo0 <= lon <= lo1):
                continue
            if not cooled_down(st, "emergency", f"{ac.get('hex')}:{code}", now):
                continue
            apt, d = D.nearest_airport(lat, lon, C.AIRPORTS)
            alt = ac.get("alt_baro")
            alt_s = f"{alt:,} ft" if isinstance(alt, (int, float)) else str(alt)
            N.send(
                f"🚨 <b>SQUAWK {label}</b>\n"
                f"✈️ {N.esc(ac_label(ac))}\n"
                f"📍 {d:.0f} NM from {apt} ({N.esc(C.AIRPORTS[apt][0])})\n"
                f"⬆️ {N.esc(alt_s)}\n\n"
                f"{map_link(ac.get('hex'))}\n\n"
                f"🕒 {now_local_str()}"
            )


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
def source_warning(st, now, name, ok):
    key = f"down:{name}"
    if ok:
        if st.get(key):
            N.send(f"✅ Data source back online: {name}")
            st.pop(key, None)
        return
    if not st.get(key):
        st[key] = now
        N.send(f"⚠️ Data source not responding: {name}. Alerts of this type may be missed.")


def heartbeat(st):
    local = datetime.now(RIYADH)
    today = local.strftime("%Y-%m-%d")
    if local.hour == C.HEARTBEAT_HOUR_LOCAL and st.get("heartbeat") != today:
        st["heartbeat"] = today
        N.send(
            f"💚 <b>Daily check</b> - Airspace Monitor is running.\n"
            f"Aircraft tracked right now: {len(st.get('tracks', {}))}\n"
            f"🕒 {now_local_str()}"
        )


# ---------------------------------------------------------------------------
def main():
    start = time.time()
    st = load_state()
    # NOTAM baseline is taken on the first SUCCESSFUL fetch, so a source
    # outage at start-up never causes a flood of "new" alerts later.
    first_run = not st.get("notams_seeded")

    ok = check_notams(st, int(time.time()), first_run)
    source_warning(st, int(time.time()), "NOTAMs", ok)
    if ok:
        st["notams_seeded"] = True
    st["initialized"] = True
    save_state(st)

    sweep_no = 0
    while time.time() - start < RUN_SECONDS - 45:
        t0 = time.time()
        now = int(t0)
        current, ok = sweep_airports(st, now)
        source_warning(st, now, "Live traffic", ok)
        if ok:
            check_holds(st, now, current)
            check_diversions(st, now, current)
        if sweep_no % 2 == 0:
            check_emergencies(st, now)
        heartbeat(st)
        save_state(st)
        sweep_no += 1
        elapsed = time.time() - t0
        if elapsed < C.SWEEP_INTERVAL_SEC:
            time.sleep(C.SWEEP_INTERVAL_SEC - elapsed)

    save_state(st)
    print(f"Run finished: {sweep_no} sweeps, {len(st.get('tracks', {}))} tracks.")


if __name__ == "__main__":
    main()
