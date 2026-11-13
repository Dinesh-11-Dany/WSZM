#!/usr/bin/env python3
"""
WSZM — Urban Safety & Navigation Desktop Suite
=============================================================
Serves the modern desktop frontend (desktop_ui.html) + Google Maps app
(bangalore_map.html) with a local REST API for multi-route 5-factor safety
scoring and statutory eCourts / NCRB CSV inspection.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import hmac
import http.server
import importlib.util
import json
import math
import re
import secrets
import shutil
import socket
import socketserver
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


ROOT_DIR = Path(__file__).resolve().parent
MAP_HTML = ROOT_DIR / "bangalore_map.html"
DESKTOP_UI_HTML = ROOT_DIR / "desktop_ui.html"
DATA_DIR = ROOT_DIR / "data"
SUMMARY_JSON = DATA_DIR / "bengaluru_crime_summary.json"
COURT_POLICE_JSON = DATA_DIR / "bengaluru_court_police_jurisdictions.json"
EXTRACTED_DIR = DATA_DIR / "extracted"
AUTH_SESSION_JSON = DATA_DIR / "user_session.json"
AUTH_ACCOUNTS_JSON = DATA_DIR / "auth_accounts.json"
AUTH_USERS_JSON = DATA_DIR / "auth_users.json"

NON_GOOGLE_DOMAINS = {
    "yahoo.com", "yahoo.co.in", "yahoo.in", "ymail.com",
    "outlook.com", "hotmail.com", "live.com", "msn.com",
    "rediffmail.com", "icloud.com", "me.com", "aol.com",
    "proton.me", "protonmail.com", "zohomail.com", "gmx.com",
}

AVATAR_COLORS = ["#2563eb", "#0f766e", "#4f46e5", "#0369a1", "#15803d", "#b45309"]

SAFETY_WEIGHTS = {
    "day": {"crime": 0.35, "police": 0.20, "lighting": 0.20, "crowd": 0.15, "isolation": 0.10},
    "night": {"crime": 0.30, "police": 0.12, "lighting": 0.28, "crowd": 0.20, "isolation": 0.10},
}

DEFAULT_PLACES = [
    {"name": "Mahatma Gandhi Road (MG Road)", "short": "MG Road", "region": "Central", "lat": 12.9756, "lng": 77.6066, "tier": 1, "type": "road", "safety": "safe"},
    {"name": "Majestic (Kempegowda Bus Station)", "short": "Majestic", "region": "Central", "lat": 12.9767, "lng": 77.5713, "tier": 1, "type": "transit", "safety": "moderate"},
    {"name": "Indiranagar", "short": "Indiranagar", "region": "East", "lat": 12.9784, "lng": 77.6408, "tier": 1, "type": "area", "safety": "safe"},
    {"name": "Koramangala", "short": "Koramangala", "region": "South", "lat": 12.9352, "lng": 77.6245, "tier": 1, "type": "area", "safety": "safe"},
    {"name": "Whitefield", "short": "Whitefield", "region": "East", "lat": 12.9698, "lng": 77.7500, "tier": 1, "type": "area", "safety": "moderate"},
    {"name": "Electronic City", "short": "Electronic City", "region": "South", "lat": 12.8452, "lng": 77.6602, "tier": 1, "type": "area", "safety": "caution"},
]

DEFAULT_POLICE = [
    {"name": "Cubbon Park PS", "lat": 12.9768, "lng": 77.5951},
    {"name": "Upparpet PS (Majestic)", "lat": 12.9776, "lng": 77.5735},
    {"name": "Indiranagar PS", "lat": 12.9781, "lng": 77.6416},
    {"name": "Koramangala PS", "lat": 12.9345, "lng": 77.6264},
]


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lng / 2) ** 2
    )
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1 - a)))


def min_max_norm(val: float, lo: float, hi: float) -> float:
    if hi <= lo:
        return 0.0
    return max(0.0, min(1.0, (val - lo) / (hi - lo)))


def risk_band_for_score(score: float) -> str:
    if score >= 75.0:
        return "Full Safety"
    if score >= 50.0:
        return "Medium Safe"
    return "Not Safe"


def _parse_js_string_field(obj_txt: str, key: str, default: str = "") -> str:
    m = re.search(rf"\b{key}\s*:\s*'([^']*)'", obj_txt)
    return m.group(1) if m else default


def _parse_js_float_field(obj_txt: str, key: str, default: float = 0.0) -> float:
    m = re.search(rf"\b{key}\s*:\s*([-+]?\d+(?:\.\d+)?)", obj_txt)
    return float(m.group(1)) if m else default


def load_places_and_police() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Read PLACES and BENGALURU_POLICE_STATIONS directly from bangalore_map.html."""
    if not MAP_HTML.exists():
        return DEFAULT_PLACES, DEFAULT_POLICE

    text = MAP_HTML.read_text(encoding="utf-8", errors="replace")
    places: List[Dict[str, Any]] = []
    stations: List[Dict[str, Any]] = []

    pm = re.search(r"const\s+PLACES\s*=\s*\[(.*?)\];", text, re.S)
    if pm:
        for obj in re.findall(r"\{[^{}]+\}", pm.group(1)):
            name = _parse_js_string_field(obj, "name")
            if not name:
                continue
            places.append({
                "name": name,
                "short": _parse_js_string_field(obj, "short", name),
                "region": _parse_js_string_field(obj, "region", "Bengaluru"),
                "lat": _parse_js_float_field(obj, "lat"),
                "lng": _parse_js_float_field(obj, "lng"),
                "tier": int(_parse_js_float_field(obj, "tier", 3)),
                "type": _parse_js_string_field(obj, "type", "area"),
                "safety": _parse_js_string_field(obj, "safety", "moderate"),
            })

    sm = re.search(r"const\s+BENGALURU_POLICE_STATIONS\s*=\s*\[(.*?)\];", text, re.S)
    if sm:
        for obj in re.findall(r"\{[^{}]+\}", sm.group(1)):
            name = _parse_js_string_field(obj, "name")
            if not name:
                continue
            stations.append({
                "name": name,
                "lat": _parse_js_float_field(obj, "lat"),
                "lng": _parse_js_float_field(obj, "lng"),
            })

    # Enrich and supplement with official Bengaluru District Court gazette jurisdictions
    if COURT_POLICE_JSON.exists():
        try:
            court_data = json.loads(COURT_POLICE_JSON.read_text(encoding="utf-8"))
            court_list = court_data.get("jurisdictions", [])
            norm_key = lambda s: re.sub(r"[^a-z0-9]", "", str(s or "").lower())
            lookup: Dict[str, Dict[str, Any]] = {}
            for cj in court_list:
                lookup[norm_key(cj.get("ps_name", ""))] = cj

            for st in stations:
                match = lookup.get(norm_key(st["name"]))
                if match:
                    st["court"] = match.get("court", "")
                    st["sub_division"] = match.get("sub_division", "")
                    st["division"] = match.get("division", "")
                    st["court_complex"] = match.get("court_complex", "")

            existing_keys = {norm_key(st["name"]) for st in stations}
            for cj in court_list:
                k = norm_key(cj.get("ps_name", ""))
                if k and k not in existing_keys:
                    stations.append({
                        "name": cj.get("ps_name", ""),
                        "lat": float(cj.get("lat", 12.9716)),
                        "lng": float(cj.get("lng", 77.5946)),
                        "court": cj.get("court", ""),
                        "sub_division": cj.get("sub_division", ""),
                        "division": cj.get("division", ""),
                        "court_complex": cj.get("court_complex", ""),
                    })
                    existing_keys.add(k)
        except Exception:
            pass

    return (places or DEFAULT_PLACES), (stations or DEFAULT_POLICE)


def compute_point_safety(
    lat: float,
    lng: float,
    places: List[Dict[str, Any]],
    stations: List[Dict[str, Any]],
    tod: str,
) -> Dict[str, Any]:
    is_night = tod == "night"
    w = SAFETY_WEIGHTS[tod]

    nearest_place = places[0]
    nearest_dist = float("inf")
    nearest_hub_dist = float("inf")
    nearby_hubs = 0.0

    for p in places:
        d = haversine_km(lat, lng, p["lat"], p["lng"])
        if d < nearest_dist:
            nearest_dist = d
            nearest_place = p
        is_hub = p["type"] in ("shop", "transit") or p["tier"] <= 2
        if is_hub and (not is_night or p["tier"] <= 2 or p["safety"] == "safe"):
            if d < nearest_hub_dist:
                nearest_hub_dist = d
            if d <= 1.4:
                nearby_hubs += 2.5 if p["tier"] == 1 else (1.6 if p["tier"] == 2 else 1.0)

    closest_ps = stations[0]
    police_dist_km = float("inf")
    for ps in stations:
        d = haversine_km(lat, lng, ps["lat"], ps["lng"])
        if d < police_dist_km:
            police_dist_km = d
            closest_ps = ps

    safety_tag = nearest_place["safety"]
    base_crime = 1.25 if safety_tag == "safe" else (2.45 if safety_tag == "moderate" else 3.55)
    if nearest_place["tier"] == 1 and safety_tag == "safe":
        base_crime -= 0.12
    if is_night and safety_tag != "safe":
        base_crime += 0.35
    crime_norm = min_max_norm(base_crime, 0.4, 4.5)

    police_dist_norm = min_max_norm(police_dist_km, 0.2, 5.5)

    lighting_raw = 0.82 if safety_tag == "safe" else (0.62 if safety_tag == "moderate" else 0.36)
    if nearest_place["tier"] >= 3 and nearest_place["type"] == "shop":
        lighting_raw = max(lighting_raw, 0.86)
    if is_night:
        lighting_raw -= 0.16 if safety_tag == "caution" else (0.09 if safety_tag == "moderate" else 0.04)
    lighting_norm = min_max_norm(lighting_raw, 0.15, 0.95)

    crowd_count = nearby_hubs * (0.58 if safety_tag == "safe" else 0.32) if is_night else nearby_hubs
    if safety_tag == "caution" and is_night:
        crowd_count *= 0.65
    crowd_norm = min_max_norm(crowd_count, 0.5, 16.0)

    iso_dist = nearest_hub_dist * 1.35 if is_night else nearest_hub_dist
    isolation_norm = min_max_norm(iso_dist, 0.08, 2.6)

    f_crime = 1.0 - crime_norm
    f_police = 1.0 - police_dist_norm
    f_lighting = lighting_norm
    f_crowd = crowd_norm
    f_iso = 1.0 - isolation_norm

    total01 = (
        w["crime"] * f_crime
        + w["police"] * f_police
        + w["lighting"] * f_lighting
        + w["crowd"] * f_crowd
        + w["isolation"] * f_iso
    )
    return {
        "score": round(total01 * 100.0, 1),
        "closest_ps": closest_ps,
        "police_dist_km": police_dist_km,
        "factors": [
            ("1 - crime", f_crime, w["crime"], w["crime"] * f_crime),
            ("1 - police distance", f_police, w["police"], w["police"] * f_police),
            ("Lighting", f_lighting, w["lighting"], w["lighting"] * f_lighting),
            ("Crowd / open shops", f_crowd, w["crowd"], w["crowd"] * f_crowd),
            ("1 - isolation", f_iso, w["isolation"], w["isolation"] * f_iso),
        ],
    }


def compute_route_safety(
    path: List[Tuple[float, float]],
    places: List[Dict[str, Any]],
    stations: List[Dict[str, Any]],
    tod: str,
) -> Dict[str, Any]:
    sample_n = min(20, max(4, len(path)))
    samples = []
    for i in range(sample_n):
        idx = min(len(path) - 1, round((i / max(1, sample_n - 1)) * (len(path) - 1)))
        lat, lng = path[idx]
        samples.append(compute_point_safety(lat, lng, places, stations, tod))

    avg_score = round(sum(s["score"] for s in samples) / len(samples), 1)
    min_seg = round(min(s["score"] for s in samples), 1)
    closest_ps_sample = min(samples, key=lambda s: s["police_dist_km"])

    sample_pts = [
        path[min(len(path) - 1, round((i / max(1, sample_n - 1)) * (len(path) - 1)))]
        for i in range(sample_n)
    ]
    station_dists = []
    for ps in stations:
        min_d = min(haversine_km(lat, lng, ps["lat"], ps["lng"]) for lat, lng in sample_pts)
        station_dists.append({
            "name": ps["name"],
            "lat": ps["lat"],
            "lng": ps["lng"],
            "court": ps.get("court", "Magistrate Court Bengaluru"),
            "division": ps.get("division", "Bengaluru City"),
            "sub_division": ps.get("sub_division", ""),
            "court_complex": ps.get("court_complex", "City Civil Court Complex"),
            "dist_km": round(min_d, 2),
        })
    station_dists.sort(key=lambda x: x["dist_km"])
    within_corridor = [s for s in station_dists if s["dist_km"] <= 2.5][:6]
    nearby_stations = within_corridor if len(within_corridor) >= 3 else station_dists[:4]

    agg_factors = []
    for fi in range(5):
        fname = samples[0]["factors"][fi][0]
        wt = samples[0]["factors"][fi][2]
        val = sum(s["factors"][fi][1] for s in samples) / len(samples)
        agg_factors.append({"name": fname, "val": val, "weight": wt, "contrib": val * wt})

    closest_ps_obj = closest_ps_sample["closest_ps"]
    return {
        "score": avg_score,
        "min_seg": min_seg,
        "band_label": risk_band_for_score(avg_score),
        "closest_ps": closest_ps_obj["name"],
        "closest_ps_court": closest_ps_obj.get("court", "Magistrate Court Bengaluru"),
        "closest_ps_division": closest_ps_obj.get("division", "Bengaluru City"),
        "closest_ps_km": closest_ps_sample["police_dist_km"],
        "nearby_stations": nearby_stations,
        "factors": agg_factors,
        "sample_count": len(samples),
        "tod": tod,
    }


def _http_get_json(url: str, timeout: float = 8.0) -> Optional[Dict[str, Any]]:
    req = urllib.request.Request(url, headers={"User-Agent": "WSZMDesktop/2.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None
    return None


def _routes_distinct(a_path: List[Tuple[float, float]], b_path: List[Tuple[float, float]]) -> bool:
    if not a_path or not b_path:
        return True
    mid = a_path[len(a_path) // 2]
    step = max(1, len(b_path) // 20)
    min_d = min(haversine_km(mid[0], mid[1], b_path[i][0], b_path[i][1]) for i in range(0, len(b_path), step))
    return min_d > 0.22


def fetch_all_routes(
    origin: Dict[str, Any],
    dest: Dict[str, Any],
    profile: str = "driving",
) -> List[Dict[str, Any]]:
    routes: List[Dict[str, Any]] = []

    def parse_osrm_rt(rt: Dict[str, Any], idx: int, fallback_label: str) -> Dict[str, Any]:
        coords = [(pt[1], pt[0]) for pt in rt["geometry"]["coordinates"]]
        mins = max(1, round(rt.get("duration", 0) / 60))
        dist_m = rt.get("distance", 0)
        names: List[str] = []
        for leg in rt.get("legs", []):
            for st in leg.get("steps", []):
                nm = st.get("name") or ""
                if nm and nm not in names:
                    names.append(nm)
                if len(names) >= 2:
                    break
        summary = " & ".join(names[:2]) if names else f"{fallback_label} {idx + 1}"
        return {
            "summary": summary,
            "duration_min": mins,
            "distance_km": dist_m / 1000.0,
            "distance_m": dist_m,
            "path": coords,
        }

    url = (
        f"https://router.project-osrm.org/route/v1/{profile}/"
        f"{origin['lng']},{origin['lat']};{dest['lng']},{dest['lat']}"
        "?overview=full&geometries=geojson&steps=true&alternatives=3"
    )
    data = _http_get_json(url)
    if data and data.get("routes"):
        for idx, rt in enumerate(data["routes"][:4]):
            parsed = parse_osrm_rt(rt, idx, "Bengaluru Route")
            if all(_routes_distinct(parsed["path"], ex["path"]) for ex in routes):
                routes.append(parsed)

    trip_km = haversine_km(origin["lat"], origin["lng"], dest["lat"], dest["lng"])
    if routes and len(routes) < 3 and trip_km > 0.85:
        mid_lat = (origin["lat"] + dest["lat"]) / 2.0
        mid_lng = (origin["lng"] + dest["lng"]) / 2.0
        cos_lat = math.cos(math.radians(mid_lat))
        d_lat_km = (dest["lat"] - origin["lat"]) * 111.0
        d_lng_km = (dest["lng"] - origin["lng"]) * 111.0 * cos_lat
        length = math.hypot(d_lat_km, d_lng_km) or 1.0
        offset_km = min(2.4, max(0.45, trip_km * 0.16))
        p_lat = (-d_lng_km / length) * offset_km / 111.0
        p_lng = (d_lat_km / length) * offset_km / (111.0 * cos_lat)
        base_m = routes[0]["distance_m"]

        for side_idx, sign in enumerate((1.0, -1.0)):
            if len(routes) >= 4:
                break
            v_lat = mid_lat + sign * p_lat
            v_lng = mid_lng + sign * p_lng
            via_url = (
                f"https://router.project-osrm.org/route/v1/{profile}/"
                f"{origin['lng']},{origin['lat']};{v_lng:.5f},{v_lat:.5f};{dest['lng']},{dest['lat']}"
                "?overview=full&geometries=geojson&steps=true"
            )
            vdata = _http_get_json(via_url)
            if vdata and vdata.get("routes"):
                cand = parse_osrm_rt(vdata["routes"][0], side_idx, "Alternate Corridor")
                if cand["distance_m"] <= max(base_m * 1.85, base_m + 3500):
                    if all(_routes_distinct(cand["path"], ex["path"]) for ex in routes):
                        routes.append(cand)

    if not routes:
        speed = 4.8 if profile == "foot" else (14.0 if profile == "bike" else 24.0)
        mins = max(2, round((trip_km * 1.25 / speed) * 60))
        routes.append({
            "summary": "Direct Corridor Estimate (offline)",
            "duration_min": mins,
            "distance_km": trip_km,
            "distance_m": trip_km * 1000.0,
            "path": [(origin["lat"], origin["lng"]), (dest["lat"], dest["lng"])],
        })

    return routes


def validate_google_email(raw_email: str) -> Tuple[bool, str]:
    email = (raw_email or "").strip().lower()
    if not email:
        return False, "Please enter your Google Email ID (e.g. name@gmail.com)."
    if not re.fullmatch(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", email):
        return False, "Please enter a valid Google Email ID format (e.g. name@gmail.com)."
    domain = email.split("@", 1)[1]
    if domain in NON_GOOGLE_DOMAINS:
        return False, f"'{domain}' is not a Google Email domain. Please use @gmail.com, @googlemail.com, or a Google Workspace email."
    return True, email


def build_google_profile(email: str, raw_name: str = "") -> Dict[str, Any]:
    local_part = email.split("@", 1)[0]
    cleaned_local = " ".join(part for part in re.split(r"[._\-+]+", local_part) if part and not part.isdigit())
    name = (raw_name or "").strip() or (cleaned_local.title() if cleaned_local else local_part.title())
    parts = [p for p in re.split(r"\s+", name) if p]
    if len(parts) >= 2:
        initials = (parts[0][0] + parts[1][0]).upper()
    elif parts:
        initials = parts[0][:2].upper()
    else:
        initials = email[:2].upper()
    color_idx = sum(ord(ch) for ch in email) % len(AVATAR_COLORS)
    return {
        "email": email,
        "name": name,
        "initials": initials,
        "color": AVATAR_COLORS[color_idx],
        "provider": "google",
        "logged_in_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def hash_password(password: str, salt_hex: Optional[str] = None) -> Tuple[str, str]:
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return salt.hex(), digest.hex()


def verify_password(password: str, salt_hex: str, expected_hash_hex: str) -> bool:
    if not salt_hex or not expected_hash_hex:
        return False
    _, computed = hash_password(password, salt_hex)
    return hmac.compare_digest(computed, expected_hash_hex)


class DesktopBackendState:
    def __init__(self) -> None:
        self.places, self.stations = load_places_and_police()
        self.place_map = {p["name"]: p for p in self.places}
        self.port = 8000
        self.shutdown_event = threading.Event()
        self.auth_lock = threading.Lock()
        self.current_user: Optional[Dict[str, Any]] = None
        self.recent_accounts: List[Dict[str, Any]] = []
        self.user_credentials: Dict[str, Dict[str, Any]] = {}
        self._load_auth_files()

    def _load_auth_files(self) -> None:
        if AUTH_USERS_JSON.exists():
            try:
                loaded_users = json.loads(AUTH_USERS_JSON.read_text(encoding="utf-8"))
                if isinstance(loaded_users, dict):
                    self.user_credentials = {
                        str(k).lower(): v for k, v in loaded_users.items() if isinstance(v, dict)
                    }
            except Exception:
                self.user_credentials = {}
        if AUTH_ACCOUNTS_JSON.exists():
            try:
                loaded = json.loads(AUTH_ACCOUNTS_JSON.read_text(encoding="utf-8"))
                if isinstance(loaded, list):
                    self.recent_accounts = [a for a in loaded if isinstance(a, dict) and a.get("email")][:6]
            except Exception:
                self.recent_accounts = []
        if AUTH_SESSION_JSON.exists():
            try:
                sess = json.loads(AUTH_SESSION_JSON.read_text(encoding="utf-8"))
                if isinstance(sess, dict) and sess.get("email") and sess.get("remember"):
                    self.current_user = sess
            except Exception:
                self.current_user = None

    def _save_recent_accounts(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        AUTH_ACCOUNTS_JSON.write_text(json.dumps(self.recent_accounts[:6], indent=2), encoding="utf-8")

    def _save_user_credentials(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        AUTH_USERS_JSON.write_text(json.dumps(self.user_credentials, indent=2), encoding="utf-8")

    def login_google_user(
        self,
        raw_email: str,
        raw_password: str,
        raw_name: str,
        remember: bool,
        mode: str = "login",
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        ok, res = validate_google_email(raw_email)
        if not ok:
            return False, res, None
        email = res
        password = raw_password or ""
        if not password:
            return False, "Please enter your email password.", None
        if len(password) < 6:
            return False, "Password must be at least 6 characters long.", None

        with self.auth_lock:
            cred = self.user_credentials.get(email)
            existing = next((a for a in self.recent_accounts if a.get("email") == email), None)

            if mode == "register":
                if cred is not None:
                    return False, "This Google Email ID is already registered. Switch to Sign In and enter its password.", None
                salt_hex, hash_hex = hash_password(password)
                chosen_name = (raw_name or "").strip() or (existing.get("name", "") if existing else "")
                profile = build_google_profile(email, chosen_name)
                self.user_credentials[email] = {
                    "email": email,
                    "name": profile["name"],
                    "salt": salt_hex,
                    "hash": hash_hex,
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                }
                self._save_user_credentials()
            else:
                if cred is None:
                    return False, "No password is set up for this Google Email ID yet. Switch to 'Create Account' to register it.", None
                if not verify_password(password, str(cred.get("salt", "")), str(cred.get("hash", ""))):
                    return False, "Incorrect password for this Google Email ID.", None
                chosen_name = (raw_name or "").strip() or str(cred.get("name", "")) or (existing.get("name", "") if existing else "")
                profile = build_google_profile(email, chosen_name)

            profile["remember"] = bool(remember)
            self.current_user = profile
            self.recent_accounts = [profile] + [a for a in self.recent_accounts if a.get("email") != email]
            self.recent_accounts = self.recent_accounts[:6]
            try:
                self._save_recent_accounts()
                if remember:
                    AUTH_SESSION_JSON.write_text(json.dumps(profile, indent=2), encoding="utf-8")
                elif AUTH_SESSION_JSON.exists():
                    AUTH_SESSION_JSON.unlink()
            except Exception:
                pass
            return True, "", profile

    def logout_user(self) -> None:
        with self.auth_lock:
            self.current_user = None
            try:
                if AUTH_SESSION_JSON.exists():
                    AUTH_SESSION_JSON.unlink()
            except Exception:
                pass

    def remove_saved_account(self, raw_email: str) -> None:
        email = (raw_email or "").strip().lower()
        with self.auth_lock:
            self.recent_accounts = [a for a in self.recent_accounts if a.get("email") != email]
            self.user_credentials.pop(email, None)
            try:
                self._save_recent_accounts()
                self._save_user_credentials()
            except Exception:
                pass
            if self.current_user and self.current_user.get("email") == email:
                self.current_user = None
                try:
                    if AUTH_SESSION_JSON.exists():
                        AUTH_SESSION_JSON.unlink()
                except Exception:
                    pass

    def resolve_place(self, query: str, coord: Any = None) -> Optional[Dict[str, Any]]:
        if isinstance(coord, dict) and isinstance(coord.get("lat"), (int, float)) and isinstance(coord.get("lng"), (int, float)):
            name = str(coord.get("name") or query or "Custom Bengaluru Location").strip()
            return {
                "name": name,
                "short": name.split(",")[0][:28],
                "region": "Bengaluru",
                "lat": float(coord["lat"]),
                "lng": float(coord["lng"]),
                "tier": 2,
                "type": "area",
                "safety": "moderate",
            }
        q = query.strip()
        if not q:
            return None
        if q in self.place_map:
            return self.place_map[q]
        ql = q.lower()
        for p in self.places:
            if p["name"].lower() == ql or p["short"].lower() == ql:
                return p
        for p in self.places:
            if ql in p["name"].lower() or ql in p["short"].lower():
                return p

        # Fallback: live Nominatim lookup scoped to Bengaluru if unknown landmark typed
        nom_url = (
            "https://nominatim.openstreetmap.org/search?format=json&limit=1&q="
            + urllib.parse.quote(f"{q}, Bengaluru, Karnataka, India")
        )
        try:
            req = urllib.request.Request(nom_url, headers={"User-Agent": "WSZMDesktop/2.0"})
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                if resp.status == 200:
                    arr = json.loads(resp.read().decode("utf-8"))
                    if arr:
                        return {
                            "name": q,
                            "short": q.split(",")[0][:28],
                            "region": "Bengaluru",
                            "lat": float(arr[0]["lat"]),
                            "lng": float(arr[0]["lon"]),
                            "tier": 2,
                            "type": "area",
                            "safety": "moderate",
                        }
        except Exception:
            pass
        return None


def find_app_browser() -> Optional[str]:
    candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    for exe in ("msedge", "chrome", "google-chrome"):
        found = shutil.which(exe)
        if found:
            return found
    return None


def launch_app_window(url: str) -> Optional[subprocess.Popen[bytes]]:
    browser = find_app_browser()
    if browser:
        profile_dir = Path(tempfile.gettempdir()) / "WSZM_DesktopProfile"
        profile_dir.mkdir(parents=True, exist_ok=True)
        return subprocess.Popen(
            [
                browser,
                f"--app={url}",
                "--window-size=1420,900",
                f"--user-data-dir={profile_dir}",
                "--no-first-run",
                "--no-default-browser-check",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    webbrowser.open(url)
    return None


def make_handler(state: DesktopBackendState) -> type[http.server.SimpleHTTPRequestHandler]:
    class DesktopRequestHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, directory=str(ROOT_DIR), **kwargs)

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            return

        def end_headers(self) -> None:
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            super().end_headers()

        def _send_json(self, status: int, payload: Dict[str, Any]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _read_json_body(self) -> Dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0") or "0")
            if length <= 0:
                return {}
            raw = self.rfile.read(length).decode("utf-8", errors="replace")
            return json.loads(raw) if raw.strip() else {}

        def do_GET(self) -> None:  # noqa: N802
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == "/":
                self.path = "/desktop_ui.html"
                super().do_GET()
                return

            if parsed.path == "/api/auth/session":
                with state.auth_lock:
                    self._send_json(200, {
                        "authenticated": state.current_user is not None,
                        "user": state.current_user,
                        "recent_accounts": state.recent_accounts,
                    })
                return

            if parsed.path == "/api/bootstrap":
                csv_files = sorted(p.name for p in EXTRACTED_DIR.glob("*.csv")) if EXTRACTED_DIR.exists() else []
                summary = {}
                if SUMMARY_JSON.exists():
                    try:
                        summary = json.loads(SUMMARY_JSON.read_text(encoding="utf-8"))
                    except Exception:
                        summary = {}
                court_summary = {}
                if COURT_POLICE_JSON.exists():
                    try:
                        cj = json.loads(COURT_POLICE_JSON.read_text(encoding="utf-8"))
                        court_summary = {
                            "source": cj.get("source", ""),
                            "notification_reference": cj.get("notification_reference", ""),
                            "total_stations": cj.get("total_stations", len(cj.get("jurisdictions", []))),
                        }
                    except Exception:
                        court_summary = {}
                self._send_json(200, {
                    "places": state.places,
                    "station_count": len(state.stations),
                    "weights": SAFETY_WEIGHTS,
                    "csv_files": csv_files,
                    "summary": summary,
                    "court_summary": court_summary,
                    "port": state.port,
                    "local_ip": get_local_ip(),
                })
                return

            if parsed.path == "/api/csv":
                qs = urllib.parse.parse_qs(parsed.query)
                name = (qs.get("name") or [""])[0]
                target = (EXTRACTED_DIR / Path(name).name).resolve()
                if not name or not target.exists() or target.parent != EXTRACTED_DIR.resolve():
                    self._send_json(404, {"error": "CSV file not found"})
                    return
                with target.open("r", encoding="utf-8", errors="replace", newline="") as f:
                    rows = list(csv.reader(f))
                headers = rows[0] if rows else []
                data_rows = rows[1:120] if len(rows) > 1 else []
                self._send_json(200, {
                    "name": target.name,
                    "headers": headers,
                    "rows": data_rows,
                    "total_rows": max(0, len(rows) - 1),
                })
                return

            super().do_GET()

        def do_POST(self) -> None:  # noqa: N802
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == "/api/auth/login":
                body = self._read_json_body()
                ok, err_msg, profile = state.login_google_user(
                    str(body.get("email", "")),
                    str(body.get("password", "")),
                    str(body.get("name", "")),
                    bool(body.get("remember", False)),
                    str(body.get("mode", "login")),
                )
                if not ok:
                    status = 401 if "Incorrect password" in err_msg else 400
                    self._send_json(status, {"error": err_msg})
                    return
                with state.auth_lock:
                    accounts = list(state.recent_accounts)
                self._send_json(200, {
                    "authenticated": True,
                    "user": profile,
                    "recent_accounts": accounts,
                })
                return

            if parsed.path == "/api/auth/logout":
                state.logout_user()
                with state.auth_lock:
                    accounts = list(state.recent_accounts)
                self._send_json(200, {
                    "authenticated": False,
                    "user": None,
                    "recent_accounts": accounts,
                })
                return

            if parsed.path == "/api/auth/remove-account":
                body = self._read_json_body()
                state.remove_saved_account(str(body.get("email", "")))
                with state.auth_lock:
                    accounts = list(state.recent_accounts)
                    user = state.current_user
                self._send_json(200, {
                    "authenticated": user is not None,
                    "user": user,
                    "recent_accounts": accounts,
                })
                return

            if parsed.path == "/api/analyze-routes":
                body = self._read_json_body()
                origin = state.resolve_place(str(body.get("origin", "")), body.get("origin_coord"))
                dest = state.resolve_place(str(body.get("dest", "")), body.get("dest_coord"))
                if not origin or not dest:
                    self._send_json(400, {"error": "Select valid Bengaluru Source and Destination names."})
                    return
                if origin["name"] == dest["name"] and haversine_km(origin["lat"], origin["lng"], dest["lat"], dest["lng"]) < 0.05:
                    self._send_json(400, {"error": "Source and Destination cannot be the same place."})
                    return

                tod_req = str(body.get("tod", "auto"))
                effective_tod = tod_req if tod_req in ("day", "night") else ("day" if 6 <= datetime.now().hour < 19 else "night")
                mode = str(body.get("mode", "driving"))
                profile = mode if mode in ("driving", "bike", "foot") else "driving"

                raw_routes = fetch_all_routes(origin, dest, profile=profile)
                enriched = []
                for rt in raw_routes:
                    safety = compute_route_safety(rt["path"], state.places, state.stations, effective_tod)
                    enriched.append({
                        "summary": rt["summary"],
                        "duration_min": rt["duration_min"],
                        "distance_km": rt["distance_km"],
                        "safety": safety,
                    })
                self._send_json(200, {
                    "origin": origin,
                    "dest": dest,
                    "effective_tod": effective_tod,
                    "routes": enriched,
                })
                return

            if parsed.path == "/api/open-external-map":
                launch_app_window(f"http://127.0.0.1:{state.port}/bangalore_map.html?v=compass_only")
                self._send_json(200, {"ok": True})
                return

            if parsed.path == "/api/shutdown":
                self._send_json(200, {"ok": True})
                threading.Thread(target=state.shutdown_event.set, daemon=True).start()
                return

            self._send_json(404, {"error": "Unknown API endpoint"})

    return DesktopRequestHandler


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def start_desktop_server(state: DesktopBackendState, preferred_port: int = 8050) -> socketserver.TCPServer:
    handler_cls = make_handler(state)
    socketserver.ThreadingMixIn.daemon_threads = True
    for port in range(preferred_port, preferred_port + 30):
        try:
            socketserver.TCPServer.allow_reuse_address = True
            srv = http.server.ThreadingHTTPServer(("0.0.0.0", port), handler_cls)
            state.port = port
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            return srv
        except OSError:
            continue
    raise RuntimeError("No free port available on 0.0.0.0")


def main() -> None:
    parser = argparse.ArgumentParser(description="WSZM Python Desktop Application")
    parser.add_argument("--port", type=int, default=8050, help="Preferred localhost port (default: 8050)")
    parser.add_argument("--no-launch", action="store_true", help="Start backend API server without opening window")
    args = parser.parse_args()

    state = DesktopBackendState()
    srv = start_desktop_server(state, preferred_port=args.port)
    local_ip = get_local_ip()
    url = f"http://127.0.0.1:{state.port}/desktop_ui.html"
    mobile_full_url = f"http://{local_ip}:{state.port}/"
    mobile_map_url = f"http://{local_ip}:{state.port}/bangalore_map.html?v=compass_only"
    print("=" * 66)
    print("WSZM Urban Safety & Navigation Suite is Running:")
    print(f"  • PC Desktop URL:              {url}")
    print(f"  • Android Full Suite (Wi-Fi):  {mobile_full_url}")
    print(f"  • Android Standalone Map:      {mobile_map_url}")
    print("=" * 66)

    if args.no_launch:
        try:
            while not state.shutdown_event.is_set():
                time.sleep(0.3)
        except KeyboardInterrupt:
            pass
        srv.shutdown()
        srv.server_close()
        return

    if importlib.util.find_spec("webview") is not None:
        import webview  # type: ignore

        webview.create_window("WSZM — Urban Safety & Navigation Suite", url, width=1420, height=900)
        webview.start()
        srv.shutdown()
        srv.server_close()
        return

    proc = launch_app_window(url)
    try:
        start_ts = time.time()
        while not state.shutdown_event.is_set():
            if proc is not None and proc.poll() is not None and (time.time() - start_ts) > 3.0:
                break
            time.sleep(0.35)
    except KeyboardInterrupt:
        pass
    finally:
        srv.shutdown()
        srv.server_close()


if __name__ == "__main__":
    main()
