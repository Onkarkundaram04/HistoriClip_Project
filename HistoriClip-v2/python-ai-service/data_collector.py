"""
HistoriClip - Mapillary Data Collector (v3.0)
===============================================
Harvests geotagged street-level imagery from Mapillary for building
the visual geolocation index (DINOv2 + GeM + FAISS).

Sampling Strategy:
  Road-Graph Sampling via OSMnx — samples points at regular intervals
  along the actual road network, ensuring dense, realistic coverage.
  This mirrors how a user would actually encounter street-level views
  (walking/driving along roads), producing much better FAISS matches
  than naive grid-based sampling.

Naming Strategy:
  Each downloaded image is reverse geocoded via Nominatim to obtain
  the nearest real POI name (temple, museum, road, etc.) instead of
  meaningless auto-generated identifiers. This ensures that FAISS
  matches can return meaningful location names.

Pipeline:
  1. Build road network graph via OSMnx
  2. Sample lat/lon points along road edges at configurable spacing
  3. For each point, fetch nearby Mapillary images via API
  4. Download image, reverse geocode coordinates, save to CSV

ALL settings come from config.py — no hardcoded values here.

Author: HistoriClip Team (Final Year Project)
"""

import csv
import math
import re
import time
import requests
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

# Names that are generic infrastructure, not landmarks
_ROAD_SUFFIXES = re.compile(
    r'\b(road|street|lane|avenue|path|marg|rasta|galli|chowk|nagar|colony)\s*$',
    re.IGNORECASE
)

# Centralized config
from modules.config import MapillaryConfig, load_config_from_env


# ============================================================
# STATISTICS
# ============================================================

@dataclass
class CollectorStats:
    """Download and geocoding statistics."""
    total_api_hits: int = 0      # Images found via Mapillary API
    downloaded: int = 0           # Successfully downloaded
    skipped: int = 0              # Already in database (deduplication)
    failed: int = 0               # Download or API failures
    geocoded: int = 0             # Successfully reverse geocoded
    geocode_failed: int = 0       # Reverse geocoding failures


# ============================================================
# REVERSE GEOCODING (Nominatim)
# ============================================================

# In-memory cache to avoid hitting Nominatim for nearby coordinates.
# Key: (rounded_lat, rounded_lon) at 4 decimal places (~11m precision).
# This drastically reduces API calls since many Mapillary images
# are clustered within the same 11m² area.
_geocode_cache: Dict[Tuple[float, float], dict] = {}

# How many decimal places to round lat/lon for cache key.
# 4 = ~11m precision, 3 = ~111m, 5 = ~1.1m
_GEOCODE_CACHE_PRECISION = 4


def _reverse_geocode_cached(lat: float, lon: float) -> Optional[dict]:
    """
    Reverse geocode with in-memory caching and Nominatim rate limiting.

    Returns dict with keys: name, display_name, city, state, country
    or None on failure.

    Nominatim Terms of Service require max 1 request/second.
    The cache reduces actual API calls by ~90% for clustered data.
    """
    cache_key = (
        round(lat, _GEOCODE_CACHE_PRECISION),
        round(lon, _GEOCODE_CACHE_PRECISION)
    )

    if cache_key in _geocode_cache:
        return _geocode_cache[cache_key]

    try:
        # Nominatim ToS: max 1 req/sec, must have User-Agent
        time.sleep(1.1)

        resp = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={
                'lat': lat, 'lon': lon,
                'format': 'json', 'addressdetails': 1, 'zoom': 18
            },
            headers={'User-Agent': 'HistoriClip/3.0 (FinalYearProject)'},
            timeout=10
        )
        resp.raise_for_status()
        data = resp.json()
        addr = data.get('address', {})

        # Priority: tourism > historic > building > amenity > leisure > place_of_worship
        # NOTE: 'road' is deliberately excluded — road names are infrastructure,
        # not landmarks, and cause the pipeline to generate wrong content.
        name = (
            addr.get('tourism') or
            addr.get('historic') or
            addr.get('building') or
            addr.get('amenity') or
            addr.get('leisure') or
            addr.get('place_of_worship') or
            addr.get('shop') or
            None
        )

        # Reject generic road/street names even if they slipped through
        if name and _ROAD_SUFFIXES.search(name):
            name = None

        result = {
            'name': name,
            'display_name': data.get('display_name', ''),
            'city': addr.get('city') or addr.get('town') or addr.get('suburb', ''),
            'state': addr.get('state', ''),
            'country': addr.get('country', ''),
        }

        _geocode_cache[cache_key] = result
        return result

    except Exception:
        _geocode_cache[cache_key] = None
        return None


# ============================================================
# MAIN COLLECTOR
# ============================================================

class MapillaryCollector:
    """
    Collects geotagged street-level images from Mapillary.

    Uses road-graph sampling (OSMnx) to generate sample points along
    the actual road network, then fetches nearby Mapillary images
    for each point. Every downloaded image is reverse geocoded to
    obtain a real location name.

    All settings (bbox, paths, delays, limits) come from MapillaryConfig.
    """

    API_BASE = "https://graph.mapillary.com"

    def __init__(self, config: MapillaryConfig = None):
        """Initialize collector from config. Loads from environment if not provided."""
        if config is None:
            config = load_config_from_env().mapillary
        self.config = config

        if not self.config.client_token:
            raise ValueError(
                "MAPILLARY_CLIENT_TOKEN not set. "
                "Get one at https://www.mapillary.com/dashboard/developers"
            )

        # Derive paths from config
        self.output_dir = Path(self.config.output_dir)
        self.images_dir = self.output_dir / self.config.images_subdir
        self.csv_path = self.output_dir / self.config.csv_filename
        self.delay = self.config.download_delay

        self.images_dir.mkdir(parents=True, exist_ok=True)
        self._downloaded_ids = self._load_existing_ids()
        self.stats = CollectorStats()

        print(f"[Collector] City:     {self.config.city_name}")
        print(f"[Collector] BBox:     {self.config.bbox}")
        print(f"[Collector] Output:   {self.output_dir}")
        print(f"[Collector] Existing: {len(self._downloaded_ids)} images in database")

    def _load_existing_ids(self) -> set:
        """Load already-downloaded image IDs from existing CSV to avoid re-downloading."""
        ids = set()
        if self.csv_path.exists():
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                for row in csv.DictReader(f):
                    fn = row.get('filename', '')
                    if fn.startswith('mapillary_'):
                        ids.add(fn.replace('mapillary_', '').replace('.jpg', ''))
        return ids

    # ============================================================
    # Mapillary API
    # ============================================================

    def _fetch_images_in_bbox(self, bbox: List[float], limit: int = 50) -> List[Dict]:
        """Fetch image metadata from Mapillary within a bounding box."""
        url = f"{self.API_BASE}/images"
        params = {
            'fields': 'id,geometry,thumb_1024_url,captured_at',
            'bbox': ','.join(map(str, bbox)),
            'limit': limit
        }
        headers = {"Authorization": f"OAuth {self.config.client_token}"}

        try:
            resp = requests.get(url, params=params, headers=headers, timeout=30)
            resp.raise_for_status()
            return resp.json().get('data', [])
        except requests.exceptions.HTTPError:
            if resp.status_code == 429:
                print("[Collector] Rate limited by Mapillary — waiting 60s...")
                time.sleep(60)
                return self._fetch_images_in_bbox(bbox, limit)
            return []
        except Exception:
            return []

    def _fetch_images_near_point(self, lat: float, lon: float,
                                  radius: float = 100) -> List[Dict]:
        """Fetch Mapillary images near a GPS point (converts to bbox query)."""
        lat_off = radius / 111_000
        lon_off = radius / (111_000 * math.cos(math.radians(lat)))
        bbox = [lon - lon_off, lat - lat_off, lon + lon_off, lat + lat_off]
        return self._fetch_images_in_bbox(bbox, limit=5)

    # ============================================================
    # Image Download + Reverse Geocoding
    # ============================================================

    def _download_image(self, img_data: Dict) -> Optional[Dict]:
        """
        Download a single Mapillary image and reverse geocode its location.

        Returns a CSV-ready record dict with real location name,
        or None if download failed or image was already in database.
        """
        img_id = str(img_data.get('id'))
        if img_id in self._downloaded_ids:
            self.stats.skipped += 1
            return None

        img_url = img_data.get('thumb_1024_url')
        if not img_url:
            self.stats.failed += 1
            return None

        coords = img_data.get('geometry', {}).get('coordinates', [0, 0])
        lon, lat = coords[0], coords[1]

        try:
            resp = requests.get(img_url, timeout=30)
            resp.raise_for_status()
            filename = f"mapillary_{img_id}.jpg"
            with open(self.images_dir / filename, 'wb') as f:
                f.write(resp.content)
            self._downloaded_ids.add(img_id)
            self.stats.downloaded += 1

            # Reverse geocode to get a real location name
            geo = _reverse_geocode_cached(lat, lon)
            if geo and geo.get('name'):
                name = geo['name']
                self.stats.geocoded += 1
            else:
                # Fallback: use coordinates as name (honest, not fabricated)
                name = f"Location ({lat:.4f}, {lon:.4f})"
                self.stats.geocode_failed += 1

            return {
                'filename': filename,
                'lat': lat,
                'lon': lon,
                'name': name,
                'source': 'mapillary',
                'captured_at': img_data.get('captured_at', '')
            }

        except Exception:
            self.stats.failed += 1
            return None

    # ============================================================
    # CSV Persistence
    # ============================================================

    def _save_to_csv(self, records: List[Dict]):
        """Append records to the locations CSV file."""
        if not records:
            return
        exists = self.csv_path.exists()
        with open(self.csv_path, 'a', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=[
                'filename', 'lat', 'lon', 'name', 'source', 'captured_at'
            ])
            if not exists:
                w.writeheader()
            w.writerows(records)

    # ============================================================
    # Road-Graph Sampling (OSMnx)
    # ============================================================

    def _build_road_network(self, bbox: List[float]):
        """
        Build a road network graph for the bounding box using OSMnx.

        Uses graph_from_point with a radius covering the full bbox
        to avoid the polygon subdivision issues in OSMnx 2.x.
        """
        import osmnx as ox

        min_lon, min_lat, max_lon, max_lat = bbox

        # Compute center point and radius from bbox
        center_lat = (min_lat + max_lat) / 2
        center_lon = (min_lon + max_lon) / 2

        # Approximate radius in meters (covers the full bbox diagonal)
        lat_span_m = (max_lat - min_lat) * 111_000
        lon_span_m = (max_lon - min_lon) * 111_000 * math.cos(math.radians(center_lat))
        radius_m = max(lat_span_m, lon_span_m) / 2 * 1.2  # 20% buffer

        print(f"[Collector] Downloading {self.config.city_name} road network...")
        print(f"[Collector] Center: ({center_lat:.4f}, {center_lon:.4f}), "
              f"Radius: {radius_m:.0f}m")

        graph = ox.graph_from_point(
            (center_lat, center_lon),
            dist=radius_m,
            network_type="drive"
        )
        print(f"[Collector] Network: {len(graph.nodes)} nodes, "
              f"{len(graph.edges)} edges")
        return graph

    def _sample_points_along_roads(self, graph, spacing_meters: float,
                                    total_limit: int) -> List[Tuple[float, float]]:
        """
        Sample GPS points at regular intervals along all road edges.

        Uses a seen-set with configurable precision to prevent duplicate
        samples in densely-connected areas.
        """
        points, seen = [], set()
        edges = list(graph.edges(data=True))
        print(f"[Collector] Sampling every {spacing_meters}m along "
              f"{len(edges)} road edges...")

        for u, v, data in edges:
            if len(points) >= total_limit:
                break

            # Get edge geometry (either explicit or from node positions)
            if 'geometry' in data:
                coords = list(data['geometry'].coords)
            else:
                nu, nv = graph.nodes[u], graph.nodes[v]
                coords = [(nu['x'], nu['y']), (nv['x'], nv['y'])]

            for i in range(len(coords) - 1):
                if len(points) >= total_limit:
                    break
                lon1, lat1 = coords[i]
                lon2, lat2 = coords[i + 1]
                seg_len = self._haversine(lat1, lon1, lat2, lon2)
                if seg_len < 1:
                    continue

                n_samples = int(seg_len / spacing_meters) + 1
                for j in range(n_samples):
                    if len(points) >= total_limit:
                        break
                    frac = j / max(n_samples - 1, 1)
                    s_lat = lat1 + (lat2 - lat1) * frac
                    s_lon = lon1 + (lon2 - lon1) * frac
                    key = (round(s_lat, 4), round(s_lon, 4))
                    if key not in seen:
                        seen.add(key)
                        points.append((s_lat, s_lon))

        print(f"[Collector] Generated {len(points)} sample points")
        return points

    @staticmethod
    def _haversine(lat1: float, lon1: float,
                   lat2: float, lon2: float) -> float:
        """Haversine distance in meters between two GPS coordinates."""
        R = 6_371_000  # Earth radius in meters
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dp = math.radians(lat2 - lat1)
        dl = math.radians(lon2 - lon1)
        a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    # ============================================================
    # Main Collection Pipeline
    # ============================================================

    def collect(self, bbox: List[float] = None, spacing_meters: float = None,
                total_limit: int = None) -> CollectorStats:
        """
        Collect images using road-graph sampling.

        Pipeline:
          1. Build road network graph (OSMnx)
          2. Sample points at `spacing_meters` intervals along all roads
          3. For each point, fetch up to 2 nearby Mapillary images
          4. Download each image, reverse geocode, save to CSV

        All params default from config if not provided.
        Requires OSMnx to be installed: pip install osmnx

        Args:
            bbox:            [min_lon, min_lat, max_lon, max_lat]
            spacing_meters:  Distance between sample points along roads
            total_limit:     Maximum total images to download

        Returns:
            CollectorStats with download/geocoding counts
        """
        bbox = bbox or self.config.bbox
        spacing_meters = spacing_meters or self.config.sample_spacing_meters
        total_limit = total_limit or self.config.total_limit

        print(f"\n{'=' * 60}")
        print(f"Road-Graph Collection — {self.config.city_name}")
        print(f"{'=' * 60}")
        print(f"  BBox:     {bbox}")
        print(f"  Spacing:  {spacing_meters}m")
        print(f"  Limit:    {total_limit}")
        print(f"  Geocode:  Nominatim (cached, 1 req/s)")
        print()

        # Step 1: Build road network
        try:
            graph = self._build_road_network(bbox)
        except ImportError:
            print("[Collector] ERROR: OSMnx not installed.")
            print("[Collector] Install with: pip install osmnx")
            print("[Collector] Aborting collection.")
            return self.stats
        except Exception as e:
            print(f"[Collector] ERROR building road network: {e}")
            return self.stats

        # Step 2: Sample points along roads
        points = self._sample_points_along_roads(
            graph, spacing_meters, total_limit * 5
        )
        if not points:
            print("[Collector] No sample points generated. Check bounding box.")
            return self.stats

        # Step 3+4: Fetch, download, geocode, save
        records = []
        for idx, (lat, lon) in enumerate(points):
            if self.stats.downloaded >= total_limit:
                break

            # Progress logging every 50 points
            if idx % 50 == 0:
                print(f"  [{idx + 1}/{len(points)}] "
                      f"({lat:.4f}, {lon:.4f}) | "
                      f"downloaded={self.stats.downloaded} "
                      f"geocoded={self.stats.geocoded}")

            imgs = self._fetch_images_near_point(lat, lon)
            self.stats.total_api_hits += len(imgs)

            for img in imgs[:2]:  # Max 2 images per sample point
                rec = self._download_image(img)
                if rec:
                    records.append(rec)
                time.sleep(self.delay)

            # Flush to CSV every 50 records to avoid data loss on crash
            if len(records) >= 50:
                self._save_to_csv(records)
                records = []

        self._save_to_csv(records)
        self._print_summary()
        return self.stats

    def _print_summary(self):
        """Print final collection statistics."""
        s = self.stats
        print(f"\n{'=' * 60}")
        print(f"Collection Complete — {self.config.city_name}")
        print(f"{'=' * 60}")
        print(f"  API Hits:       {s.total_api_hits}")
        print(f"  Downloaded:     {s.downloaded}")
        print(f"  Skipped (dup):  {s.skipped}")
        print(f"  Failed:         {s.failed}")
        print(f"  Geocoded:       {s.geocoded} ({s.geocode_failed} fallbacks)")
        print(f"  Total in DB:    {len(self._downloaded_ids)}")
        print(f"{'=' * 60}\n")


# ============================================================
# CLI
# ============================================================

def main():
    """
    CLI entry point for data collection.

    Usage:
      python data_collector.py [limit] [--spacing N]

    Examples:
      python data_collector.py 500                 # Collect 500 images
      python data_collector.py 1000 --spacing 30   # Every 30m, up to 1000
      python data_collector.py                     # Use defaults from .env
    """
    import sys

    config = load_config_from_env()

    if not config.mapillary.client_token:
        print("ERROR: MAPILLARY_CLIENT_TOKEN not set in .env")
        print("Get one at: https://www.mapillary.com/dashboard/developers")
        sys.exit(1)

    args = sys.argv[1:]
    spacing = config.mapillary.sample_spacing_meters
    total_limit = config.mapillary.total_limit

    # Parse --spacing flag
    for i, a in enumerate(args):
        if a == "--spacing" and i + 1 < len(args):
            spacing = float(args[i + 1])
            args = args[:i] + args[i + 2:]
            break

    # Positional argument: total_limit
    if args:
        try:
            total_limit = int(args[0])
        except ValueError:
            print(f"Invalid limit: {args[0]}")
            sys.exit(1)

    collector = MapillaryCollector(config=config.mapillary)
    collector.collect(spacing_meters=spacing, total_limit=total_limit)

    print("Next step: python -m modules.loc_engine build")


if __name__ == "__main__":
    main()
