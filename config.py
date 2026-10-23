"""
Airspace Monitor - configuration.
Edit the lists below to change what is monitored. No code changes needed elsewhere.
"""

# ---------------------------------------------------------------------------
# 1) FIRs monitored for NOTAMs (airspace closures, restrictions, GNSS issues)
# ---------------------------------------------------------------------------
FIRS = {
    "OEJD": "Jeddah FIR (Saudi Arabia)",
    "OBBB": "Bahrain FIR",
    "OKAC": "Kuwait FIR",
    "OTDF": "Doha FIR",
    "OMAE": "Emirates FIR",
    "OOMM": "Muscat FIR",
    "OYSC": "Sanaa FIR",
    "OJAC": "Amman FIR",
    "ORBB": "Baghdad FIR",
    "OIIX": "Tehran FIR",
    "HECC": "Cairo FIR",
    "HSSS": "Khartoum FIR",
    "OSTT": "Damascus FIR",
    "OLBB": "Beirut FIR",
    "LLLL": "Tel Aviv FIR",
}

# ---------------------------------------------------------------------------
# 2) Airports: NOTAM checks + live traffic (holding / diversion detection)
#    ICAO: (name, latitude, longitude)
# ---------------------------------------------------------------------------
AIRPORTS = {
    # Saudi Arabia
    "OEJN": ("Jeddah", 21.6796, 39.1565),
    "OERK": ("Riyadh", 24.9576, 46.6988),
    "OEDF": ("Dammam", 26.4712, 49.7979),
    "OEMA": ("Madinah", 24.5534, 39.7051),
    "OEGS": ("Qassim", 26.3028, 43.7744),
    "OEAB": ("Abha", 18.2404, 42.6566),
    "OETF": ("Taif", 21.4834, 40.5443),
    "OEGN": ("Jazan", 16.9011, 42.5858),
    "OETB": ("Tabuk", 28.3654, 36.6189),
    "OEHL": ("Hail", 27.4379, 41.6863),
    "OENG": ("Najran", 17.6114, 44.4192),
    "OEYN": ("Yanbu", 24.1442, 38.0634),
    "OEAH": ("Al Ahsa", 25.2853, 49.4852),
    "OESK": ("Al Jouf", 29.7851, 40.1000),
    "OEBH": ("Bisha", 19.9844, 42.6209),
    "OESH": ("Sharurah", 17.4669, 47.1214),
    "OEGT": ("Gurayat", 31.4124, 37.2795),
    "OEAO": ("AlUla", 26.4833, 38.1169),
    "OEPA": ("Qaisumah", 28.3352, 46.1250),
    # Region
    "OMDB": ("Dubai", 25.2528, 55.3644),
    "OMAA": ("Abu Dhabi", 24.4330, 54.6511),
    "OMSJ": ("Sharjah", 25.3286, 55.5172),
    "OTHH": ("Doha", 25.2731, 51.6081),
    "OBBI": ("Bahrain", 26.2708, 50.6336),
    "OKKK": ("Kuwait", 29.2266, 47.9689),
    "OOMS": ("Muscat", 23.5933, 58.2844),
    "OJAI": ("Amman", 31.7226, 35.9932),
    "HECA": ("Cairo", 30.1219, 31.4056),
    "ORBI": ("Baghdad", 33.2625, 44.2346),
    "OIIE": ("Tehran IKA", 35.4161, 51.1522),
}

# Radius (NM) of the live-traffic circle polled around each airport
AIRPORT_RADIUS_NM = 40

# ---------------------------------------------------------------------------
# 3) Region box for emergency squawk alerts (lat_min, lat_max, lon_min, lon_max)
# ---------------------------------------------------------------------------
REGION_BBOX = (10.0, 38.0, 30.0, 62.0)

EMERGENCY_SQUAWKS = {
    "7500": "HIJACK (7500)",
    "7600": "RADIO FAILURE (7600)",
    "7700": "GENERAL EMERGENCY (7700)",
}

# ---------------------------------------------------------------------------
# 4) Diversion alerts: only for these callsign prefixes (ICAO airline codes)
#    KNE = flynas. Add more if needed, e.g. "SVA" (Saudia), "FAD" (flyadeal)
# ---------------------------------------------------------------------------
DIVERSION_CALLSIGN_PREFIXES = ["KNE"]

# ---------------------------------------------------------------------------
# 5) NOTAM categories to alert on (set False to mute a category)
# ---------------------------------------------------------------------------
NOTAM_CATEGORIES = {
    "FIR / AIRSPACE CLOSED": True,
    "AERODROME CLOSED": True,
    "ATS ROUTE CLOSED": True,
    "RESTRICTED / DANGER AREA ACTIVE": True,
    "GNSS / GPS INTERFERENCE": True,
    "REOPENED / RESUMED": True,
    "RUNWAY CLOSED": False,  # off by default: very frequent (maintenance)
}

# ---------------------------------------------------------------------------
# 6) Timing
# ---------------------------------------------------------------------------
SWEEP_INTERVAL_SEC = 30          # target time between live-traffic sweeps
HOLD_WINDOW_SEC = 360            # minimum time pattern must persist (6 min)
ALERT_COOLDOWN_SEC = {
    "hold": 3600,
    "emergency": 3600,
    "diversion": 6 * 3600,
}
HEARTBEAT_HOUR_LOCAL = 6         # daily "system alive" message (Riyadh time)
