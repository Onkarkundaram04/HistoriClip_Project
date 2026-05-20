"""
HistoriClip - Vision Module (v3.0)
====================================
4-Tier image analysis pipeline for visual geolocation.

  Tier 1:   Google Vision API     → Famous landmark detection
  Tier 2:   GPS EXIF + Nominatim  → Embedded coordinates + reverse geocode
  Tier 3:   DINOv2 + FAISS        → Visual place recognition (neighborhood GPS)
  Tier 3.5: Gemini VLM + GPS      → Geographic-constrained landmark identification

If no tier produces a real landmark name, the result returns
identified=False with landmark_name="Unidentified Location".
It NEVER fabricates names.

Author: HistoriClip Team (Final Year Project)
"""

import os
import re
import base64
import tempfile
import requests
from typing import Optional
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS


# ─────────────────────────────────────────────────────────────
# Constants & Garbage Name Detection
# ─────────────────────────────────────────────────────────────

UNIDENTIFIED = "Unidentified Location"

_GARBAGE_PATTERNS = [
    r"^street\s*point",
    r"^unknown$",
    r"^unnamed",
    r"^\d+$",
    r"^mapillary",
    r"^node\s*\d+",
    r"^way\s*\d+",
    r"^null$",
    r"^n/a$",
    r"^none$",
    r"^point\s*\d+",
]

_GARBAGE_RE = re.compile("|".join(_GARBAGE_PATTERNS), re.IGNORECASE)

# Names that are generic infrastructure, not landmarks
_ROAD_SUFFIXES = re.compile(
    r'\b(road|street|lane|avenue|path|marg|rasta|galli|chowk|nagar|colony)\s*$',
    re.IGNORECASE
)


# ─────────────────────────────────────────────────────────────
# TIER 1: Google Vision API — Landmark Detection
# ─────────────────────────────────────────────────────────────

def detect_landmark_google(image_path: str) -> Optional[dict]:
    """Call Google Vision REST API for landmark detection. Returns {name, confidence, lat, lon} or None."""
    api_key = os.getenv("GOOGLE_VISION_API_KEY")
    if not api_key:
        print("[Vision] GOOGLE_VISION_API_KEY not set. Skipping Tier 1.")
        return None

    try:
        with open(image_path, 'rb') as f:
            image_content = base64.b64encode(f.read()).decode('utf-8')

        url = f"https://vision.googleapis.com/v1/images:annotate?key={api_key}"
        payload = {
            "requests": [{
                "image": {"content": image_content},
                "features": [{"type": "LANDMARK_DETECTION", "maxResults": 5}]
            }]
        }

        response = requests.post(url, json=payload, timeout=15)
        response.raise_for_status()
        annotations = response.json().get("responses", [{}])[0]

        if "error" in annotations:
            print(f"[Vision] Tier 1 API ERROR: {annotations['error'].get('message', '?')}")
            return None

        landmarks = annotations.get("landmarkAnnotations", [])
        if not landmarks:
            print("[Vision] Tier 1: No landmarks found.")
            return None

        best = landmarks[0]
        score = best.get("score", 0.0)
        print(f"[Vision] Tier 1: '{best['description']}' (score={score})")

        lat, lon = None, None
        locs = best.get("locations", [])
        if locs:
            ll = locs[0].get("latLng", {})
            lat, lon = ll.get("latitude"), ll.get("longitude")

        return {'name': best['description'], 'confidence': score, 'lat': lat, 'lon': lon}

    except Exception as e:
        print(f"[Vision] Tier 1 error: {e}")
        return None


# ─────────────────────────────────────────────────────────────
# TIER 2: EXIF GPS Extraction
# ─────────────────────────────────────────────────────────────

def extract_gps_from_exif(image_path: str) -> Optional[dict]:
    """Read GPS lat/lon from image EXIF metadata. Returns {lat, lon} or None."""
    try:
        image = Image.open(image_path)
        exif = image._getexif()
        if not exif:
            return None

        gps_info = None
        for tag_id, val in exif.items():
            if TAGS.get(tag_id) == 'GPSInfo':
                gps_info = val
                break
        if not gps_info:
            return None

        gps = {GPSTAGS.get(k, k): v for k, v in gps_info.items()}

        lat = _dms_to_decimal(gps.get('GPSLatitude'))
        lon = _dms_to_decimal(gps.get('GPSLongitude'))
        if lat is None or lon is None:
            return None

        if gps.get('GPSLatitudeRef') == 'S':
            lat = -lat
        if gps.get('GPSLongitudeRef') == 'W':
            lon = -lon

        return {'lat': lat, 'lon': lon}
    except Exception:
        return None


def _dms_to_decimal(dms):
    """Convert degrees/minutes/seconds tuple to decimal degrees."""
    if not dms:
        return None
    try:
        return float(dms[0]) + float(dms[1]) / 60.0 + float(dms[2]) / 3600.0
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────
# TIER 2 + 3: Reverse Geocoding (Nominatim)
# ─────────────────────────────────────────────────────────────

def reverse_geocode(lat: float, lon: float) -> dict:
    """Convert GPS coordinates to a named location via OpenStreetMap Nominatim."""
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={'lat': lat, 'lon': lon, 'format': 'json', 'addressdetails': 1, 'zoom': 18},
            headers={'User-Agent': 'HistoriClip/3.0'},
            timeout=10
        )
        resp.raise_for_status()
        data = resp.json()
        addr = data.get('address', {})

        name = (
            addr.get('tourism') or addr.get('historic') or
            addr.get('building') or addr.get('amenity') or
            addr.get('leisure') or addr.get('place_of_worship') or
            addr.get('shop') or 'Unknown'
        )

        return {
            'display_name': data.get('display_name', 'Unknown'),
            'name': name,
            'city': addr.get('city') or addr.get('town') or addr.get('suburb', ''),
            'state': addr.get('state', ''),
            'country': addr.get('country', ''),
            'lat': lat, 'lon': lon
        }
    except Exception:
        return {
            'display_name': f"{lat:.4f}, {lon:.4f}", 'name': 'Unknown',
            'city': '', 'state': '', 'country': '', 'lat': lat, 'lon': lon
        }


def _haversine_quick(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in meters between two coordinates."""
    import math
    R = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _is_landmark_quality_name(name: str) -> bool:
    """
    Check if a name looks like a real landmark (not a shop code, bus stop, etc.).
    
    Filters out:
      - Too short (< 4 chars): "20-20", "ABC", etc.
      - Mostly digits: "402", "20-20", "B-44"
      - All uppercase short codes: "ATM", "HP"
    """
    if not name or len(name) < 4:
        return False
    # Reject if more than half the alphanumeric chars are digits
    alnum = [c for c in name if c.isalnum()]
    if not alnum:
        return False
    digit_ratio = sum(1 for c in alnum if c.isdigit()) / len(alnum)
    if digit_ratio > 0.5:
        return False
    return True


# POI type priority — higher = better landmark candidate
_POI_PRIORITY = {
    'place_of_worship': 10,  # Temples, churches, mosques
    'monument': 9,
    'memorial': 8,
    'museum': 8,
    'castle': 8,
    'fort': 8,
    'ruins': 7,
    'attraction': 7,
    'artwork': 6,
    'archaeological_site': 9,
    'heritage': 9,
}


def _find_landmark_in_area(gps_points: list, padding_km: float = 1.0) -> Optional[str]:
    """
    Find the most notable landmark within the area covered by multiple GPS points.
    
    Instead of querying per-point, this:
      1. Computes a bounding box around ALL GPS points + padding
      2. Runs ONE Nominatim search (fast, reliable)
      3. Falls back to ONE Overpass query if needed
    
    Args:
        gps_points: List of (lat, lon) tuples from FAISS top-K matches
        padding_km: Extra padding around the bounding box in km
    
    Returns:
        Best landmark name or None
    """
    if not gps_points:
        return None

    # Compute bounding box of all match points
    lats = [p[0] for p in gps_points]
    lons = [p[1] for p in gps_points]
    pad_deg = padding_km / 111.0  # ~1km ≈ 0.009 degrees

    min_lat = min(lats) - pad_deg
    max_lat = max(lats) + pad_deg
    min_lon = min(lons) - pad_deg
    max_lon = max(lons) + pad_deg

    center_lat = (min_lat + max_lat) / 2
    center_lon = (min_lon + max_lon) / 2

    print(f"[Vision] POI search area: ({min_lat:.4f},{min_lon:.4f}) to "
          f"({max_lat:.4f},{max_lon:.4f})")

    # ── Strategy 1: Nominatim search (FAST + RELIABLE) ──
    # Multiple targeted searches for specific POI types
    search_terms = [
        'temple',
        'mandir',
        'museum',
        'monument',
        'historic',
        'church',
        'mosque',
        'fort',
        'heritage',
    ]

    viewbox = f"{min_lon},{max_lat},{max_lon},{min_lat}"

    all_candidates = []

    for term in search_terms:
        try:
            resp = requests.get(
                "https://nominatim.openstreetmap.org/search",
                params={
                    'format': 'json', 'limit': 10,
                    'viewbox': viewbox, 'bounded': 1,
                    'addressdetails': 1,
                    'q': term
                },
                headers={'User-Agent': 'HistoriClip/3.0'},
                timeout=10
            )
            resp.raise_for_status()
            results = resp.json()

            for r in results:
                name = r.get('display_name', '').split(',')[0].strip()
                poi_type = r.get('type', '')
                poi_class = r.get('class', '')

                if not name or not _is_meaningful_name(name):
                    continue
                if _ROAD_SUFFIXES.search(name):
                    continue
                if not _is_landmark_quality_name(name):
                    continue

                # Score by POI type + importance
                type_score = _POI_PRIORITY.get(poi_type, 3)
                if poi_class == 'amenity' and poi_type == 'place_of_worship':
                    type_score = 10
                importance = float(r.get('importance', 0))

                # Distance penalty
                poi_lat = float(r.get('lat', center_lat))
                poi_lon = float(r.get('lon', center_lon))
                dist_km = _haversine_quick(center_lat, center_lon, poi_lat, poi_lon) / 1000.0
                distance_penalty = dist_km * 1.0  # Reduced penalty for distance

                final_score = type_score + (importance * 10) - distance_penalty
                all_candidates.append((final_score, name, dist_km, term))

        except Exception as e:
            print(f"[Vision] Nominatim search '{term}' failed: {e}")
            continue

    if all_candidates:
        all_candidates.sort(key=lambda x: -x[0])
        best_score, best_name, best_dist, best_term = all_candidates[0]
        print(f"[Vision] Nominatim found: {best_name} "
              f"(score={best_score:.1f}, dist={best_dist:.2f}km, via '{best_term}' search, "
              f"total={len(all_candidates)} candidates)")
        return best_name

    # ── Strategy 2: Overpass API (single bbox query, mirrors) ──
    # Compute radius from center to cover the entire bbox
    import math
    lat_span = (max_lat - min_lat) * 111_000
    lon_span = (max_lon - min_lon) * 111_000 * math.cos(math.radians(center_lat))
    radius_m = int(max(lat_span, lon_span) / 2) + 100  # +100m buffer

    query = f"""[out:json][timeout:10];
(node["amenity"="place_of_worship"](around:{radius_m},{center_lat},{center_lon});
 node["tourism"~"^(attraction|museum|monument|memorial|artwork)$"](around:{radius_m},{center_lat},{center_lon});
 node["historic"~"^(monument|memorial|fort|castle|ruins|archaeological_site|heritage|temple)$"](around:{radius_m},{center_lat},{center_lon});
 way["amenity"="place_of_worship"](around:{radius_m},{center_lat},{center_lon});
 way["tourism"~"^(attraction|museum|monument|memorial|artwork)$"](around:{radius_m},{center_lat},{center_lon});
 way["historic"~"^(monument|memorial|fort|castle|ruins|archaeological_site|heritage|temple)$"](around:{radius_m},{center_lat},{center_lon}););
out tags center 20;"""

    overpass_mirrors = [
        "https://overpass.kumi.systems/api/interpreter",
        "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
        "https://overpass-api.de/api/interpreter",
    ]

    all_overpass_candidates = []

    for mirror in overpass_mirrors:
        try:
            resp = requests.post(
                mirror, data={'data': query},
                headers={'User-Agent': 'HistoriClip/3.0'},
                timeout=12
            )
            resp.raise_for_status()
            elements = resp.json().get('elements', [])

            for el in elements:
                tags = el.get('tags', {})
                name = tags.get('name') or tags.get('name:en')
                if not name or not _is_meaningful_name(name):
                    continue
                if _ROAD_SUFFIXES.search(name):
                    continue
                if not _is_landmark_quality_name(name):
                    continue

                type_score = 0
                for tag_key in ('amenity', 'tourism', 'historic'):
                    tag_val = tags.get(tag_key, '')
                    type_score = max(type_score, _POI_PRIORITY.get(tag_val, 3))

                # Distance penalty — way elements use center sub-object
                center_obj = el.get('center', {})
                poi_lat = float(el.get('lat', center_obj.get('lat', center_lat)))
                poi_lon = float(el.get('lon', center_obj.get('lon', center_lon)))
                dist_km = _haversine_quick(center_lat, center_lon, poi_lat, poi_lon) / 1000.0
                distance_penalty = dist_km * 1.0

                final_score = type_score - distance_penalty
                all_overpass_candidates.append((final_score, name, dist_km))

            if all_overpass_candidates:
                all_overpass_candidates.sort(key=lambda x: -x[0])
                best_score, best_name, best_dist = all_overpass_candidates[0]
                print(f"[Vision] Overpass POI found: {best_name} "
                      f"(score={best_score:.1f}, dist={best_dist:.2f}km, "
                      f"total={len(all_overpass_candidates)}, via {mirror.split('/')[2]})")
                return best_name

            if resp.status_code == 200:
                break

        except Exception as e:
            print(f"[Vision] Overpass mirror {mirror.split('/')[2]} failed: {e}")
            continue

    return None


# ─────────────────────────────────────────────────────────────
# TIER 3.5: Gemini VLM — Geographic-Constrained Landmark ID
# ─────────────────────────────────────────────────────────────

def _identify_landmark_vlm(image_path: str, lat: float, lon: float,
                           city: str = "", state: str = "") -> Optional[str]:
    """
    Use Gemini VLM to identify the exact landmark in an image,
    constrained by approximate GPS coordinates from DINOv2+FAISS.

    This is the novel fusion: DINOv2 gives the neighborhood,
    Gemini VLM identifies the specific landmark within it.

    Args:
        image_path: Path to the query image
        lat: Approximate latitude from FAISS
        lon: Approximate longitude from FAISS
        city: City name from reverse geocode (if available)
        state: State/region from reverse geocode (if available)

    Returns:
        Landmark name string or None
    """
    try:
        import google.generativeai as genai
        from modules.config import load_config_from_env

        config = load_config_from_env()
        api_key = config.visual.gemini_api_key
        if not api_key:
            print("[Vision] Tier 3.5: No GEMINI_API_KEY configured, skipping VLM.")
            return None

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(config.visual.gemini_model)

        # Read image and prepare for Gemini
        with open(image_path, 'rb') as f:
            image_data = f.read()

        import PIL.Image as PILImage
        img = PILImage.open(image_path)

        # Build geographic context
        geo_context = f"GPS coordinates ({lat:.4f}, {lon:.4f})"
        if city:
            geo_context += f" in {city}"
        if state:
            geo_context += f", {state}"

        prompt = f"""You are an expert at identifying landmarks, monuments, temples, and historical buildings from photographs.

This photograph was taken near {geo_context}.

Your task:
1. Identify the EXACT name of the landmark, monument, temple, or historical building shown in this image.
2. Look for any visible text, signage, or architectural features that help identify it.
3. If you can read text on signs or boards in the image (in any language/script), use that to identify the landmark.
4. Return ONLY the official name of the landmark. Nothing else.
5. If you cannot identify a specific landmark, return exactly: UNIDENTIFIED

Respond with ONLY the landmark name, no explanations, no quotes, no punctuation except what is part of the name itself."""

        print(f"[Vision] Tier 3.5: Asking Gemini VLM with context: {geo_context}")

        response = model.generate_content([prompt, img])
        result = response.text.strip()

        # Validate the response
        if not result or result.upper() == 'UNIDENTIFIED' or len(result) < 3:
            print(f"[Vision] Tier 3.5: Gemini could not identify landmark.")
            return None

        # Clean up common artifacts
        result = result.strip('"\' \n')

        # Reject if it looks like a generic description, not a name
        generic_words = ['building', 'structure', 'temple', 'church', 'street', 'road', 'a ', 'the ']
        if result.lower() in generic_words or result.lower().startswith('a ') or result.lower().startswith('the '):
            print(f"[Vision] Tier 3.5: Gemini returned generic description '{result}', rejecting.")
            return None

        print(f"[Vision] Tier 3.5: Gemini VLM identified → {result}")
        return result

    except Exception as e:
        print(f"[Vision] Tier 3.5 error: {e}")
        return None


# ─────────────────────────────────────────────────────────────
# TIER 3: Location Engine (DINOv2 + FAISS) — Lazy Singleton
# ─────────────────────────────────────────────────────────────

_engine_instance = None


def _get_engine():
    """Lazy-load the LocationEngine singleton (heavy: loads DINOv2 model)."""
    global _engine_instance
    if _engine_instance is None:
        from .loc_engine import LocationEngine
        _engine_instance = LocationEngine()
    return _engine_instance


# ─────────────────────────────────────────────────────────────
# Name Validation Helpers
# ─────────────────────────────────────────────────────────────

def _is_meaningful_name(name: Optional[str]) -> bool:
    """Check if a name represents a real place (not garbage like 'Street Point 521653')."""
    if not name or not name.strip():
        return False
    name = name.strip()
    if len(name) < 2:
        return False
    return not _GARBAGE_RE.search(name)


def _resolve_landmark_name(location: Optional[dict]) -> str:
    """Extract the best landmark name from a Nominatim result, or return UNIDENTIFIED."""
    if not location:
        return UNIDENTIFIED

    name = location.get('name', '')
    if _is_meaningful_name(name):
        return name

    display = location.get('display_name', '')
    if display:
        first_part = display.split(',')[0].strip()
        if (_is_meaningful_name(first_part)
                and first_part.lower() != 'unknown'
                and not _ROAD_SUFFIXES.search(first_part)):
            return first_part

    return UNIDENTIFIED


# ─────────────────────────────────────────────────────────────
# Result Builder
# ─────────────────────────────────────────────────────────────

def _build_result(*, success, identified, method, landmark_name,
                  location=None, gps=None, confidence=0.0, message="", **extra):
    """Construct a standardized result dict. All tiers use this to ensure consistent schema."""
    result = {
        'success': success,
        'identified': identified,
        'method': method,
        'landmark_name': landmark_name,
        'location': location,
        'gps': gps,
        'confidence': confidence,
        'message': message,
    }
    result.update(extra)
    return result


# ─────────────────────────────────────────────────────────────
# Main Pipeline: 3-Tier Cascade
# ─────────────────────────────────────────────────────────────

def analyze_image(image_path: str) -> dict:
    """
    Run the 3-tier analysis cascade on an image.
    Tier 1 → Tier 2 → Tier 3 → Failure.
    Returns a result dict with identified=True only if a real landmark was found.
    """

    # ── TIER 1: Google Vision ────────────────────────────────
    print("[Vision] ── Tier 1: Google Vision landmark detection ──")
    landmark = detect_landmark_google(image_path)
    if landmark and _is_meaningful_name(landmark.get('name')):
        loc = reverse_geocode(landmark['lat'], landmark['lon']) if landmark.get('lat') else None
        name = landmark['name']
        print(f"[Vision] ✅ TIER 1 HIT: {name} (confidence={landmark.get('confidence', 0):.2f})")
        return _build_result(
            success=True, identified=True, method='tier1_landmark',
            landmark_name=name, location=loc,
            gps={'lat': landmark.get('lat'), 'lon': landmark.get('lon')},
            confidence=landmark.get('confidence', 0.9),
            message=f"Landmark identified: {name}"
        )

    # ── TIER 2: GPS EXIF + Reverse Geocode ───────────────────
    print("[Vision] ── Tier 2: EXIF GPS metadata ──")
    gps = extract_gps_from_exif(image_path)
    if gps:
        print(f"[Vision] Tier 2: EXIF GPS = ({gps['lat']:.6f}, {gps['lon']:.6f})")
        loc = reverse_geocode(gps['lat'], gps['lon'])
        name = _resolve_landmark_name(loc)
        identified = _is_meaningful_name(name) and name != UNIDENTIFIED

        # Fallback: search for nearby landmarks
        if not identified:
            poi_name = _find_landmark_in_area([(gps['lat'], gps['lon'])])
            if poi_name:
                name = poi_name
                identified = True
                if loc:
                    loc['name'] = poi_name

        label = "HIT" if identified else "GPS only, no landmark name"
        print(f"[Vision] {'✅' if identified else '⚠️'} TIER 2 {label}: {name}")

        return _build_result(
            success=True, identified=identified, method='tier2_gps',
            landmark_name=name, location=loc, gps=gps,
            confidence=0.7 if identified else 0.4,
            message=f"GPS located: {loc.get('display_name', '')}"
        )

    # ── TIER 3: DINOv2 + FAISS Visual Match ──────────────────
    print("[Vision] ── Tier 3: DINOv2 visual geolocation ──")
    try:
        engine = _get_engine()
        if not engine.load_index():
            print("[Vision] Tier 3: No FAISS index available.")
        else:
            search_result = engine.search(image_path)
            if search_result.get('success') and search_result.get('best_match'):
                best = search_result['best_match']
                similarity = best.get('similarity', 0)
                print(f"[Vision] Tier 3: FAISS match at "
                      f"({best.get('lat', 0):.4f}, {best.get('lon', 0):.4f}) "
                      f"sim={similarity:.3f}")

                # Derive name from reverse geocoding, NOT from FAISS metadata
                loc = reverse_geocode(best['lat'], best['lon']) if best.get('lat') else None
                if loc:
                    print(f"[Vision] Tier 3: Raw Geocode Display Name → {loc.get('display_name', 'None')}")
                    print(f"[Vision] Tier 3: Raw Geocode Name Field → {loc.get('name', 'None')}")
                    print(f"[Vision] Tier 3: Geocode City/Suburb → {loc.get('city', 'None')}")
                
                name = _resolve_landmark_name(loc)
                identified = _is_meaningful_name(name) and name != UNIDENTIFIED
                if loc and identified:
                    loc['name'] = name
                print(f"[Vision] Tier 3: Resolved Name (after filtering) → {name}")

                # ── TIER 3.5: Gemini VLM with geographic context ──
                # DINOv2 gave us the neighborhood. Now ask Gemini to identify
                # the exact landmark using the image + GPS context.
                vlm_name = None  # Initialize before conditional assignment
                if not identified:
                    city_name = loc.get('city', '') if loc else ''
                    state_name = loc.get('state', '') if loc else ''
                    vlm_name = _identify_landmark_vlm(
                        image_path, best['lat'], best['lon'],
                        city=city_name, state=state_name
                    )
                    if vlm_name:
                        name = vlm_name
                        identified = True
                        if loc:
                            loc['name'] = vlm_name
                        print(f"[Vision] ✅ TIER 3.5 VLM HIT: {vlm_name}")

                # Fallback: Area-wide POI search (Nominatim + Overpass)
                # Only if both reverse geocode AND VLM failed
                if not identified:
                    # Use ONLY consensus-consistent matches (within 500m of best)
                    consensus = search_result.get('gps_consensus', {})
                    consensus_lat = consensus.get('consensus_lat', best['lat'])
                    consensus_lon = consensus.get('consensus_lon', best['lon'])
                    all_matches = search_result.get('matches', [])
                    
                    gps_points = []
                    for m in all_matches:
                        if m.get('lat') and m.get('lon'):
                            dist = _haversine_quick(consensus_lat, consensus_lon, m['lat'], m['lon'])
                            if dist <= 500:  # 500m max from consensus
                                gps_points.append((m['lat'], m['lon']))
                    if not gps_points:
                        gps_points = [(best['lat'], best['lon'])]

                    print(f"[Vision] Tier 3: VLM failed, "
                          f"searching area with {len(gps_points)} consistent match points...")

                    poi_name = _find_landmark_in_area(gps_points, padding_km=1.0)
                    if poi_name:
                        name = poi_name
                        identified = True
                        if loc:
                            loc['name'] = poi_name

                # XAI visualizations: generate BOTH LightGlue matches AND attention map
                xai_matches_path, xai_attention_path = None, None
                try:
                    xai_matches_path = engine.visualize_matches(image_path, best.get('filename'))
                    print(f"[Vision] XAI: LightGlue visualization saved: {xai_matches_path}")
                except Exception as xai_err:
                    print(f"[Vision] XAI: LightGlue visualization failed: {xai_err}")
                try:
                    xai_attention_path = engine.visualize_attention(image_path)
                    print(f"[Vision] XAI: Attention map saved: {xai_attention_path}")
                except Exception as xai_err:
                    print(f"[Vision] XAI: Attention map failed: {xai_err}")

                # Build top-5 match data for frontend display
                raw_matches = search_result.get('matches', [])
                xai_top_matches = []
                for m in raw_matches[:5]:
                    match_entry = {
                        'rank': m.get('rank', 0),
                        'similarity': round(m.get('similarity', 0), 4),
                        'lat': m.get('lat'),
                        'lon': m.get('lon'),
                        'name': m.get('name', ''),
                        'filename': m.get('filename', ''),
                        'inliers': m.get('inliers', 0),
                        'verified': m.get('verified', False),
                    }
                    xai_top_matches.append(match_entry)

                # Determine which tier resolved the landmark
                xai_tier_used = 'tier3_faiss_vlm' if identified and vlm_name else \
                                'tier3_faiss_geocode' if identified else 'tier3_faiss_unresolved'

                label = f"HIT: {name}" if identified else f"GPS only (unidentified)"
                print(f"[Vision] {'✅' if identified else '⚠️'} TIER 3 {label}")

                return _build_result(
                    success=True, identified=identified, method='tier3_dinov2_gem',
                    landmark_name=name, location=loc,
                    gps={'lat': best.get('lat'), 'lon': best.get('lon')},
                    confidence=similarity,
                    message=f"Visual match: {name}" if identified
                            else "Coordinates found, landmark unidentified",
                    xai_matches_path=xai_matches_path,
                    xai_attention_path=xai_attention_path,
                    xai_top_matches=xai_top_matches,
                    xai_tier_used=xai_tier_used,
                    verification=search_result.get('verification'),
                    matches=raw_matches
                )
    except Exception as e:
        print(f"[Vision] Tier 3 error: {e}")

    # ── ALL TIERS FAILED ─────────────────────────────────────
    print("[Vision] ✗ All tiers failed.")
    return _build_result(
        success=False, identified=False, method=None,
        landmark_name=UNIDENTIFIED,
        message='All analysis tiers failed. Could not geolocate image.'
    )


# ─────────────────────────────────────────────────────────────
# Flask Wrapper
# ─────────────────────────────────────────────────────────────

class VisionAnalyzer:
    """Flask endpoint wrapper. Saves uploaded file to temp, runs analysis, cleans up."""

    def analyze(self, image_file) -> dict:
        """Analyze a Flask FileStorage image through the 3-tier pipeline."""
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                image_file.save(tmp.name)
                tmp_path = tmp.name
            return analyze_image(tmp_path)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m modules.vision <image>")
        sys.exit(1)
    if not os.path.exists(sys.argv[1]):
        print(f"Not found: {sys.argv[1]}")
        sys.exit(1)

    result = analyze_image(sys.argv[1])

    print(f"\n{'=' * 60}")
    print(f"  Identified:  {result.get('identified', False)}")
    print(f"  Landmark:    {result.get('landmark_name', 'N/A')}")
    print(f"  Method:      {result.get('method', 'N/A')}")
    print(f"  Confidence:  {result.get('confidence', 0):.3f}")
    print(f"  GPS:         {result.get('gps', 'N/A')}")
    loc = result.get('location')
    if loc:
        print(f"  Address:     {loc.get('display_name', 'N/A')}")
    print(f"  Message:     {result.get('message', '')}")
    print(f"{'=' * 60}")
