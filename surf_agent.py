import os
import time
import requests
from datetime import datetime, timedelta, timezone

print("Squiggly Wiggly surf agent started...")

# ============================================================
# 1. SETTINGS
# ============================================================

# Must match the topic subscribed to in your ntfy phone app.
NTFY_TOPIC = os.environ.get("NTFY_TOPIC") or "james-ct-surf-alerts-2026"
print("Topic source:", "GitHub secret" if os.environ.get("NTFY_TOPIC") else "local fallback")

SEND_TEST_MESSAGE = False   # True = also send a "connection check" ping each run

# True  = relaxed matching (ignores directions and tide) so you can test the pipeline.
# False = strict matching using every spot's own conditions. Use this for real alerts.
TEST_MODE = False

VERBOSE = True              # True = print forecast samples for every spot

LOOKAHEAD_DAYS = 3          # look at today + this many days ahead
MAX_NAMES_PER_LINE = 3      # spot names shown per notification line ("...and 4 more")
MAX_LINES_IN_MESSAGE = 3    # notification lines (one per time slot) before "plus N more"

# Monday-Friday you only get alerts for these spots (the ones you can reach before or
# after work). Saturday and Sunday alerts cover every spot. Names must match SURF_SPOTS.
WEEKDAY_SPOTS = ["Big Bay", "Bloubergstrand", "Glen Beach"]

# South Africa has no daylight saving, so a fixed UTC+2 offset is always correct.
TIMEZONE = timezone(timedelta(hours=2), "SAST")

# ---------------- Work schedule ----------------
# weekday numbers: Monday = 0 ... Sunday = 6. Weekends are free all day.
APPLY_WORK_HOURS = True
WORK_HOURS = {
    0: ("07:30", "16:30"),   # Monday
    1: ("07:30", "16:30"),   # Tuesday
    2: ("07:30", "16:30"),   # Wednesday
    3: ("07:30", "16:30"),   # Thursday
    4: ("08:00", "16:00"),   # Friday
}
# A surf must END at least this long before work starts, and START at least this
# long after work ends (travel, changing, etc.). Change to suit you.
TRAVEL_BUFFER_MIN = 30

# Surfing is allowed from this long before sunrise until sunset.
FIRST_LIGHT_BUFFER_MIN = 30

# If the forecast has no PEAK swell period for a spot, the (lower) MEAN period is used
# instead, multiplied by this rough factor so it is comparable. It is only an
# approximation - the script prints a warning whenever it has to be used.
MEAN_PERIOD_FALLBACK_FACTOR = 1.2

# How many spots to ask the weather service about in one request.
# Fewer, bigger requests are much kinder to the free service than one per spot.
SPOTS_PER_REQUEST = 8

# Relaxed TEST_MODE limits. NOT surf advice.
TEST_MIN_SWELL_M = 0.1
TEST_MAX_SWELL_M = 6.0
TEST_MIN_PERIOD_S = 4
TEST_MAX_WIND_KNOTS = 40

# ============================================================
# 2. SURF SPOTS
#
# swell directions / wind directions = where they come FROM.
# min/max_swell_m = the forecast model's swell height in metres (offshore, not wave-face).
# min_period_s = PEAK swell period, which is the number Windguru/Surfline show.
# tide_stages: any of "low", "mid", "high". None = any tide.
# tide_move: "rising" or "falling". None = either.
# Tide is estimated from a global model and is only approximate - sanity-check it
# against the official tide table before trusting it.
# Coordinates are approximate; the API snaps them to the nearest sea grid cell.
# ============================================================

SURF_SPOTS = {

    # -------- ATLANTIC COAST: CAPE TOWN --------

    "Big Bay": {
        "lat": -33.82, "lon": 18.45,
        "min_swell_m": 0.5, "max_swell_m": 2.0, "min_period_s": 8,
        "ideal_swell_dirs": ["SW", "WSW", "W"],
        "ideal_wind_dirs": ["E", "ESE", "ENE", "NE"],
        "max_wind_knots": 22,
        "tide_stages": None, "tide_move": None,
    },
    "Bloubergstrand": {
        "lat": -33.82, "lon": 18.46,
        "min_swell_m": 0.7, "max_swell_m": 2.5, "min_period_s": 9,
        "ideal_swell_dirs": ["SW", "WSW", "W"],
        "ideal_wind_dirs": ["NNE", "NE", "ENE", "E"],
        "max_wind_knots": 18,
        "tide_stages": None, "tide_move": None,
    },
    "Sunset Beach": {
        "lat": -33.86, "lon": 18.46,
        "min_swell_m": 0.7, "max_swell_m": 2.5, "min_period_s": 9,
        "ideal_swell_dirs": ["SW", "WSW", "W"],
        "ideal_wind_dirs": ["NE", "ENE", "E", "ESE"],
        "max_wind_knots": 18,
        "tide_stages": None, "tide_move": None,
    },
    "Haakgat": {
        "lat": -33.75, "lon": 18.43,
        "min_swell_m": 0.8, "max_swell_m": 2.5, "min_period_s": 10,
        "ideal_swell_dirs": ["SW", "WSW", "W"],
        "ideal_wind_dirs": ["E", "ENE"],
        "max_wind_knots": 18,
        "tide_stages": None, "tide_move": None,
    },
    "Melkbosstrand": {
        "lat": -33.72, "lon": 18.40,
        "min_swell_m": 0.6, "max_swell_m": 2.5, "min_period_s": 8,
        "ideal_swell_dirs": ["SW", "WSW", "W"],
        "ideal_wind_dirs": ["NNE", "NE", "ENE", "E"],
        "max_wind_knots": 18,
        "tide_stages": None, "tide_move": None,
    },
    "Milnerton": {
        "lat": -33.84, "lon": 18.46,
        "min_swell_m": 0.7, "max_swell_m": 2.4, "min_period_s": 9,
        "ideal_swell_dirs": ["SW", "WSW", "W"],
        "ideal_wind_dirs": ["E", "ESE", "SE"],
        "max_wind_knots": 18,
        "tide_stages": None, "tide_move": None,
    },
    "Glen Beach": {
        "lat": -33.94, "lon": 18.36,
        "min_swell_m": 0.6, "max_swell_m": 2.2, "min_period_s": 9,
        "ideal_swell_dirs": ["SW", "WSW", "W"],
        "ideal_wind_dirs": ["E", "ESE", "SE"],
        "max_wind_knots": 15,
        "tide_stages": None, "tide_move": None,
    },
    "Llandudno": {
        "lat": -34.00, "lon": 18.32,
        "min_swell_m": 0.8, "max_swell_m": 2.8, "min_period_s": 9,
        "ideal_swell_dirs": ["SW", "WSW", "W"],
        "ideal_wind_dirs": ["E", "ENE", "ESE"],
        "max_wind_knots": 18,
        "tide_stages": None, "tide_move": None,   # works on any tide; rising is usually better
    },
    "Dungeons (Hout Bay) - big wave, expert": {
        "lat": -34.05, "lon": 18.32,
        "min_swell_m": 3.0, "max_swell_m": 9.0, "min_period_s": 14,
        "ideal_swell_dirs": ["SW", "WSW", "SSW"],
        "ideal_wind_dirs": ["N", "NNE", "NNW"],
        "max_wind_knots": 15,
        "tide_stages": ["low", "mid"], "tide_move": None,
    },
    "Long Beach (Kommetjie)": {
        "lat": -34.13, "lon": 18.31,
        "min_swell_m": 0.7, "max_swell_m": 3.0, "min_period_s": 9,
        "ideal_swell_dirs": ["SW", "WSW", "W"],
        "ideal_wind_dirs": ["S", "SSE", "SSW"],
        "max_wind_knots": 18,
        "tide_stages": ["low", "mid"], "tide_move": None,   # too deep at high tide
    },
    "Sunsets (Kommetjie) - big, expert": {
        "lat": -34.1255, "lon": 18.334,
        "min_swell_m": 2.5, "max_swell_m": 5.0, "min_period_s": 12,
        "ideal_swell_dirs": ["SW", "WSW", "W", "WNW"],
        "ideal_wind_dirs": ["E", "ESE", "SE"],
        "max_wind_knots": 18,
        "tide_stages": ["low", "mid"], "tide_move": "rising",
    },
    "Noordhoek": {
        "lat": -34.11, "lon": 18.33,
        "min_swell_m": 0.7, "max_swell_m": 3.0, "min_period_s": 9,
        "ideal_swell_dirs": ["SW", "WSW", "W"],
        "ideal_wind_dirs": ["SE", "ESE", "E"],
        "max_wind_knots": 18,
        "tide_stages": ["low", "mid"], "tide_move": None,
    },
    "Dunes (Noordhoek) - expert": {
        "lat": -34.108, "lon": 18.351,
        "min_swell_m": 0.8, "max_swell_m": 2.5, "min_period_s": 10,
        "ideal_swell_dirs": ["SSW", "SW", "WSW", "W"],
        "ideal_wind_dirs": ["SE", "ESE", "SSE"],
        "max_wind_knots": 20,
        "tide_stages": None, "tide_move": None,   # any tide; rising is usually better
    },
    "The Hoek": {
        "lat": -34.08, "lon": 18.33,
        "min_swell_m": 0.7, "max_swell_m": 3.0, "min_period_s": 9,
        "ideal_swell_dirs": ["SW", "WSW", "W"],
        "ideal_wind_dirs": ["SE", "ESE", "E"],
        "max_wind_knots": 18,
        "tide_stages": None, "tide_move": None,
    },
    "Outer Kom": {
        "lat": -34.14, "lon": 18.30,
        "min_swell_m": 1.0, "max_swell_m": 4.0, "min_period_s": 10,
        "ideal_swell_dirs": ["W", "WSW", "SW"],
        "ideal_wind_dirs": ["NNE", "NE", "ENE"],
        "max_wind_knots": 18,
        "tide_stages": ["low", "mid"], "tide_move": "rising",
    },
    "Captains": {
        "lat": -34.15, "lon": 18.30,
        "min_swell_m": 1.0, "max_swell_m": 3.0, "min_period_s": 11,
        "ideal_swell_dirs": ["WSW", "W", "SW"],
        "ideal_wind_dirs": ["E", "ENE", "ESE"],
        "max_wind_knots": 20,
        "tide_stages": None, "tide_move": None,
    },
    "365s": {
        "lat": -34.15, "lon": 18.31,
        "min_swell_m": 1.0, "max_swell_m": 3.0, "min_period_s": 11,
        "ideal_swell_dirs": ["W", "WSW", "WNW"],
        "ideal_wind_dirs": ["N", "NNE", "NE", "ENE", "E"],
        "max_wind_knots": 20,
        "tide_stages": None, "tide_move": None,
    },
    "Crayfish Factory - heavy, expert": {
        "lat": -34.19, "lon": 18.34,
        "min_swell_m": 1.5, "max_swell_m": 4.0, "min_period_s": 12,
        "ideal_swell_dirs": ["SW", "WSW"],
        "ideal_wind_dirs": ["N", "NNE", "NE", "ENE", "NW"],
        "max_wind_knots": 18,
        "tide_stages": ["mid", "high"], "tide_move": None,
    },
    "Misty Cliffs": {
        "lat": -34.19, "lon": 18.35,
        "min_swell_m": 0.8, "max_swell_m": 3.0, "min_period_s": 9,
        "ideal_swell_dirs": ["SW", "WSW", "W"],
        "ideal_wind_dirs": ["ENE", "NE", "E"],
        "max_wind_knots": 18,
        "tide_stages": None, "tide_move": None,
    },
    "Scarborough Point": {
        "lat": -34.205, "lon": 18.36,
        "min_swell_m": 1.0, "max_swell_m": 3.0, "min_period_s": 11,
        "ideal_swell_dirs": ["SW", "WSW", "W"],
        "ideal_wind_dirs": ["ENE", "E", "ESE"],
        "max_wind_knots": 18,
        "tide_stages": ["mid", "high"], "tide_move": None,
    },
    "Scarborough Beach": {
        "lat": -34.20, "lon": 18.36,
        "min_swell_m": 0.7, "max_swell_m": 3.0, "min_period_s": 9,
        "ideal_swell_dirs": ["W", "WSW", "SW"],
        "ideal_wind_dirs": ["ENE", "NE", "E"],
        "max_wind_knots": 18,
        "tide_stages": None, "tide_move": None,
    },

    # -------- FALSE BAY --------

    "Muizenberg": {
        "lat": -34.10, "lon": 18.49,
        "min_swell_m": 0.4, "max_swell_m": 1.8, "min_period_s": 7,
        "ideal_swell_dirs": ["SE", "ESE", "S", "SW"],
        "ideal_wind_dirs": ["WNW", "NW", "W"],
        "max_wind_knots": 15,
        "tide_stages": ["low", "mid"], "tide_move": None,
    },
    "Fish Hoek": {
        "lat": -34.13, "lon": 18.46,
        "min_swell_m": 0.4, "max_swell_m": 1.8, "min_period_s": 7,
        "ideal_swell_dirs": ["SE", "ESE", "S"],
        "ideal_wind_dirs": ["WNW", "NW", "W"],
        "max_wind_knots": 15,
        "tide_stages": None, "tide_move": None,
    },
    "Kalk Bay Reef - heavy, expert": {
        "lat": -34.12, "lon": 18.47,
        "min_swell_m": 0.8, "max_swell_m": 3.0, "min_period_s": 10,
        "ideal_swell_dirs": ["SE", "ESE", "S"],
        "ideal_wind_dirs": ["WNW", "NW", "W"],
        "max_wind_knots": 15,
        "tide_stages": None, "tide_move": None,   # any tide; mid gives longer rides
    },
    "Danger Reef": {
        "lat": -34.13, "lon": 18.46,
        "min_swell_m": 0.8, "max_swell_m": 3.0, "min_period_s": 9,
        "ideal_swell_dirs": ["SE", "SSE", "S"],
        "ideal_wind_dirs": ["NW", "WNW", "NNW"],
        "max_wind_knots": 18,
        "tide_stages": None, "tide_move": None,
    },
    "Glencairn": {
        "lat": -34.17, "lon": 18.44,
        "min_swell_m": 0.8, "max_swell_m": 2.5, "min_period_s": 9,
        "ideal_swell_dirs": ["SE", "SSE", "S"],
        "ideal_wind_dirs": ["WNW", "NW", "W"],
        "max_wind_knots": 18,
        "tide_stages": None, "tide_move": None,
    },
    "Black Rocks (Cape Point) - expert": {
        "lat": -34.31, "lon": 18.462,
        "min_swell_m": 2.0, "max_swell_m": 5.0, "min_period_s": 12,
        "ideal_swell_dirs": ["S", "SSE", "SE", "SW"],
        "ideal_wind_dirs": ["W", "WNW", "NW", "WSW"],
        "max_wind_knots": 18,
        "tide_stages": ["mid", "high"], "tide_move": "rising",
    },
    "Strand (Pipe)": {
        "lat": -34.12, "lon": 18.85,
        "min_swell_m": 0.7, "max_swell_m": 2.5, "min_period_s": 9,
        "ideal_swell_dirs": ["SW", "SSW", "S"],
        "ideal_wind_dirs": ["E", "ENE", "ESE"],
        "max_wind_knots": 18,
        "tide_stages": None, "tide_move": None,
    },

    # -------- WEST COAST --------

    "Yzerfontein": {
        "lat": -33.33, "lon": 18.16,
        "min_swell_m": 0.7, "max_swell_m": 3.0, "min_period_s": 9,
        "ideal_swell_dirs": ["WSW", "SW", "W"],
        "ideal_wind_dirs": ["E", "ENE", "ESE"],
        "max_wind_knots": 18,
        "tide_stages": None, "tide_move": None,
    },
    "Elands Bay": {
        "lat": -32.314, "lon": 18.331,
        "min_swell_m": 1.0, "max_swell_m": 3.5, "min_period_s": 10,
        "ideal_swell_dirs": ["W", "WSW", "NW", "SW"],
        "ideal_wind_dirs": ["SE", "S", "SSE"],
        "max_wind_knots": 18,
        "tide_stages": None, "tide_move": None,   # works on low, mid and high
    },
    "Lamberts Bay": {
        "lat": -32.10, "lon": 18.28,
        "min_swell_m": 0.5, "max_swell_m": 2.2, "min_period_s": 8,
        "ideal_swell_dirs": ["NW", "W", "WSW", "SW"],
        "ideal_wind_dirs": ["S", "SE", "SSE"],
        "max_wind_knots": 18,
        "tide_stages": ["low", "mid"], "tide_move": None,
    },
    "Doring Bay": {
        "lat": -31.80, "lon": 18.21,
        "min_swell_m": 0.7, "max_swell_m": 3.0, "min_period_s": 9,
        "ideal_swell_dirs": ["WSW", "SW", "W"],
        "ideal_wind_dirs": ["ESE", "E", "SE"],
        "max_wind_knots": 18,
        "tide_stages": None, "tide_move": None,
    },
    "Strandfontein (West Coast)": {
        "lat": -31.79, "lon": 18.22,
        "min_swell_m": 0.6, "max_swell_m": 2.8, "min_period_s": 9,
        "ideal_swell_dirs": ["SW", "WSW", "W"],
        "ideal_wind_dirs": ["E", "ESE", "ENE"],
        "max_wind_knots": 18,
        "tide_stages": None, "tide_move": None,
    },
}

# ============================================================
# 3. HELPERS
# ============================================================

COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
           "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]


def degrees_to_compass(deg):
    if deg is None:
        return None
    return COMPASS[round((deg % 360) / 22.5) % 16]


def to_minutes(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def send_phone_notification(message, title="Surf Alert"):
    response = requests.post(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=message.encode("utf-8"),
        headers={"Title": title},
        timeout=15,
    )
    response.raise_for_status()
    print(f"Notification sent successfully: {title}")


def get_daylight():
    """Sunrise/sunset per date (Cape Town is close enough for the whole Western Cape)."""
    response = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": -33.92, "longitude": 18.42,
            "daily": "sunrise,sunset",
            "timezone": "Africa/Johannesburg",
            "forecast_days": 8,
        },
        timeout=20,
    )
    response.raise_for_status()
    d = response.json()["daily"]
    out = {}
    for day, rise, sett in zip(d["time"], d["sunrise"], d["sunset"]):
        out[datetime.fromisoformat(day).date()] = (
            datetime.fromisoformat(rise).replace(tzinfo=TIMEZONE),
            datetime.fromisoformat(sett).replace(tzinfo=TIMEZONE),
        )
    return out


def slot_is_surfable(t, daylight):
    """True if the hour starting at t is in daylight AND outside your work hours."""
    sun = daylight.get(t.date())
    if sun:
        sunrise, sunset = sun
        if t < sunrise - timedelta(minutes=FIRST_LIGHT_BUFFER_MIN):
            return False
        if t + timedelta(hours=1) > sunset:
            return False
    elif not (6 <= t.hour <= 18):
        return False

    if APPLY_WORK_HOURS:
        work = WORK_HOURS.get(t.weekday())
        if work:
            work_start, work_end = to_minutes(work[0]), to_minutes(work[1])
            start = t.hour * 60 + t.minute
            end = start + 60
            before_work = end + TRAVEL_BUFFER_MIN <= work_start
            after_work = start >= work_end + TRAVEL_BUFFER_MIN
            if not (before_work or after_work):
                return False
    return True


def tide_states(levels):
    """
    From hourly sea level, work out for each hour: ("low"/"mid"/"high", "rising"/"falling").
    'low/mid/high' is relative to the lowest and highest tide within +/-13 hours.
    """
    states = []
    n = len(levels)
    for i in range(n):
        if levels[i] is None:
            states.append(None)
            continue
        window = [v for v in levels[max(0, i - 13):i + 14] if v is not None]
        low, high = min(window), max(window)
        if high - low < 0.05:
            states.append(None)
            continue
        fraction = (levels[i] - low) / (high - low)
        stage = "low" if fraction < 0.33 else "mid" if fraction < 0.67 else "high"
        before = levels[i - 1] if i > 0 else None
        after = levels[i + 1] if i < n - 1 else None
        if before is not None and after is not None:
            move = "rising" if after > before else "falling"
        elif after is not None:
            move = "rising" if after > levels[i] else "falling"
        elif before is not None:
            move = "rising" if levels[i] > before else "falling"
        else:
            move = None
        states.append((stage, move))
    return states


FALLBACK_SPOTS = []   # filled in when peak period is missing for a spot

MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
WIND_URL = "https://api.open-meteo.com/v1/forecast"


def fetch_json(url, params, attempts=3, timeout=40):
    """GET with retries, so one slow reply doesn't ruin the whole run."""
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            response = requests.get(url, params=params, timeout=timeout)
            if response.status_code != 200:
                raise RuntimeError(f"HTTP {response.status_code}: {response.text[:200]}")
            return response.json()
        except Exception as error:
            last_error = error
            print(f"    attempt {attempt}/{attempts} failed: {error}")
            if attempt < attempts:
                time.sleep(4 * attempt)
    raise last_error


def build_hours(marine, wind):
    """Turn one spot's raw marine + wind data into a clean list of hourly dicts."""
    wind_index = {t: i for i, t in enumerate(wind["time"])}
    tides = tide_states(marine.get("sea_level_height_msl") or [None] * len(marine["time"]))
    mean_periods = marine.get("swell_wave_period") or [None] * len(marine["time"])

    hours = []
    nulls = {"swell": 0, "period": 0, "wind": 0}
    used_fallback = 0

    for i, stamp in enumerate(marine["time"]):
        j = wind_index.get(stamp)
        if j is None:
            continue
        swell = marine["swell_wave_height"][i]
        period = marine["swell_wave_peak_period"][i]
        if period is None and mean_periods[i] is not None:
            period = mean_periods[i] * MEAN_PERIOD_FALLBACK_FACTOR
            used_fallback += 1
        wind_speed = wind["wind_speed_10m"][j]

        if swell is None:
            nulls["swell"] += 1
        if period is None:
            nulls["period"] += 1
        if wind_speed is None:
            nulls["wind"] += 1
        if swell is None or period is None or wind_speed is None:
            continue

        tide = tides[i]
        hours.append({
            "time": datetime.fromisoformat(stamp).replace(tzinfo=TIMEZONE),
            "swell_m": swell,
            "period_s": period,
            "swell_dir": degrees_to_compass(marine["swell_wave_direction"][i]),
            "wind_kn": wind_speed,
            "wind_dir": degrees_to_compass(wind["wind_direction_10m"][j]),
            "tide_stage": tide[0] if tide else None,
            "tide_move": tide[1] if tide else None,
        })

    if not hours:
        raise ValueError(f"no usable rows (missing values: {nulls})")
    if used_fallback:
        FALLBACK_SPOTS.append(used_fallback)
    return hours


def get_all_forecasts():
    """Fetch every spot's forecast in a few batched requests. Returns {spot name: hours}."""
    names = list(SURF_SPOTS)
    results = {}

    for start in range(0, len(names), SPOTS_PER_REQUEST):
        chunk = names[start:start + SPOTS_PER_REQUEST]
        lats = ",".join(str(SURF_SPOTS[n]["lat"]) for n in chunk)
        lons = ",".join(str(SURF_SPOTS[n]["lon"]) for n in chunk)
        print(f"Fetching forecasts for spots {start + 1}-{start + len(chunk)} of {len(names)}...")

        try:
            marine = fetch_json(MARINE_URL, {
                "latitude": lats, "longitude": lons,
                "hourly": ("swell_wave_height,swell_wave_peak_period,swell_wave_period,"
                           "swell_wave_direction,sea_level_height_msl"),
                "timezone": "Africa/Johannesburg",
                "forecast_days": 7,
                "cell_selection": "sea",
            })
            wind = fetch_json(WIND_URL, {
                "latitude": lats, "longitude": lons,
                "hourly": "wind_speed_10m,wind_direction_10m",
                "wind_speed_unit": "kn",
                "timezone": "Africa/Johannesburg",
                "forecast_days": 7,
            })
        except Exception as error:
            print(f"  Could not fetch this batch: {error}")
            continue

        # One location returns an object; several return a list.
        if isinstance(marine, dict):
            marine = [marine]
        if isinstance(wind, dict):
            wind = [wind]

        for name, m, w in zip(chunk, marine, wind):
            try:
                results[name] = build_hours(m["hourly"], w["hourly"])
            except Exception as error:
                print(f"  {name}: {error}")

        time.sleep(1)

    print(f"Got forecast data for {len(results)} of {len(names)} spots.")
    if FALLBACK_SPOTS:
        print(f"NOTE: peak swell period was missing for {len(FALLBACK_SPOTS)} spot(s); "
              f"used mean period x {MEAN_PERIOD_FALLBACK_FACTOR} instead (approximate).")
    return results


def tide_ok(hour, spot):
    stages, move = spot.get("tide_stages"), spot.get("tide_move")
    if not stages and not move:
        return True
    if hour["tide_stage"] is None:
        return True                      # tide unknown: don't block the alert
    if stages and hour["tide_stage"] not in stages:
        return False
    if move and hour["tide_move"] != move:
        return False
    return True


def is_good(hour, spot):
    if TEST_MODE:
        return (TEST_MIN_SWELL_M <= hour["swell_m"] <= TEST_MAX_SWELL_M
                and hour["period_s"] >= TEST_MIN_PERIOD_S
                and hour["wind_kn"] <= TEST_MAX_WIND_KNOTS)

    return (spot["min_swell_m"] <= hour["swell_m"] <= spot["max_swell_m"]
            and hour["period_s"] >= spot["min_period_s"]
            and hour["swell_dir"] in spot["ideal_swell_dirs"]
            and hour["wind_dir"] in spot["ideal_wind_dirs"]
            and hour["wind_kn"] <= spot["max_wind_knots"]
            and tide_ok(hour, spot))


def tide_text(hour):
    if hour["tide_stage"] is None:
        return ""
    return f" | {hour['tide_stage']} tide {hour['tide_move'] or ''}".rstrip()


def day_label(t, now):
    diff = (t.date() - now.date()).days
    if diff == 0:
        return "Today"
    if diff == 1:
        return "Tomorrow"
    return t.strftime("%a %d %b")


def format_forecast(hour):
    return (f"{hour['time']:%a %d %b %H:%M} | swell {hour['swell_m']:.1f}m "
            f"{hour['period_s']:.0f}s from {hour['swell_dir'] or '?'} | "
            f"wind {hour['wind_kn']:.0f}kn {hour['wind_dir'] or '?'}{tide_text(hour)}")


# ============================================================
# 4. MAIN LOGIC
# ============================================================

def hour_words(t):
    h = t.hour % 12 or 12
    return f"{h}{'am' if t.hour < 12 else 'pm'}"


def when_words(t, now):
    """e.g. 'tomorrow morning at 6am', 'Saturday morning at 7am', 'this evening at 5pm'."""
    diff = (t.date() - now.date()).days
    part = "morning" if t.hour < 12 else "afternoon" if t.hour < 17 else "evening"
    if diff == 0:
        day = "this"
    elif diff == 1:
        day = "tomorrow"
    else:
        day = t.strftime("%A")
    return f"{day} {part} at {hour_words(t)}"


def names_words(names):
    shown = names[:MAX_NAMES_PER_LINE]
    extra = len(names) - len(shown)
    if extra > 0:
        return ", ".join(shown) + f" and {extra} more"
    if len(shown) == 1:
        return shown[0]
    return ", ".join(shown[:-1]) + " and " + shown[-1]


def build_message(matches, now):
    """Short, friendly lines grouped by time slot."""
    groups = {}
    for name, hour in matches:
        groups.setdefault(hour["time"], []).append(name)

    lines = []
    for t in sorted(groups):
        names = groups[t]
        verb = "looks" if len(names) == 1 else "look"
        lines.append(f"{names_words(names)} {verb} good {when_words(t, now)}.")

    if len(lines) > MAX_LINES_IN_MESSAGE:
        hidden = len(lines) - MAX_LINES_IN_MESSAGE
        lines = lines[:MAX_LINES_IN_MESSAGE] + [f"Plus {hidden} more time slot(s) coming up."]
    return "\n".join(lines)


def is_allowed_spot_day(spot_name, t):
    """Weekdays: only your short list of nearby spots. Weekends: every spot."""
    if t.weekday() < 5:
        return spot_name in WEEKDAY_SPOTS
    return True


def check_all_spots():
    now = datetime.now(TIMEZONE)
    last_day = (now + timedelta(days=LOOKAHEAD_DAYS)).date()

    try:
        daylight = get_daylight()
    except Exception as error:
        print(f"Could not get sunrise/sunset ({error}); using 06:00-19:00 instead.")
        daylight = {}

    forecasts = get_all_forecasts()
    matches = []
    failed = 0

    for spot_name, spot in SURF_SPOTS.items():
        print(f"\nChecking {spot_name}...")
        hours = forecasts.get(spot_name)
        if not hours:
            print("  No forecast data for this spot.")
            failed += 1
            continue

        if VERBOSE:
            upcoming = [h for h in hours if h["time"] >= now]
            for h in upcoming[:12:4]:
                print(f"    {format_forecast(h)}")

        found = None
        for h in hours:
            t = h["time"]
            if t < now or t.date() > last_day:
                continue
            if not slot_is_surfable(t, daylight):
                continue
            if not is_allowed_spot_day(spot_name, t):
                continue
            if is_good(h, spot):
                found = h
                break

        if found:
            matches.append((spot_name, found))
            print(f"  MATCH: {format_forecast(found)}")
        else:
            print("  No matching window.")

    matches.sort(key=lambda m: m[1]["time"])
    total = len(SURF_SPOTS)
    mode = "TEST MODE (relaxed, not surf advice)" if TEST_MODE else "strict"

    if failed == total:
        message = ("Couldn't get any forecast data today - the weather service didn't "
                   "respond. I'll try again tomorrow morning.")
        title = "Squiggly Wiggly - Forecast Unavailable"
    elif matches:
        message = build_message(matches, now)
        title = "Squiggly Wiggly"
    else:
        message = (f"Nothing looks good in the next {LOOKAHEAD_DAYS} days. "
                   f"I'll check again tomorrow morning.")
        title = "Squiggly Wiggly"

    if TEST_MODE and failed != total:
        message = "[TEST MODE - relaxed, not surf advice]\n" + message

    if 0 < failed < total:
        message += f"\n({failed} spot(s) could not be checked.)"

    print("\n" + message)
    try:
        send_phone_notification(message, title)
    except Exception as error:
        print(f"Could not send notification: {error}")
        raise SystemExit(1)   # makes the GitHub run show a red cross

    print("\nFinished checking all spots.")
    if failed == total:
        raise SystemExit(1)   # no data at all: also show a red cross


if __name__ == "__main__":
    if SEND_TEST_MESSAGE:
        try:
            send_phone_notification("Connection check: your surf agent is working!",
                                    "Surf Alert Test")
        except Exception as error:
            print(f"Test notification failed: {error}")

    check_all_spots()