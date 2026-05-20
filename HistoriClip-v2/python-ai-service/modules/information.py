"""
HistoriClip - Information Module (v3.0)
========================================
Narration script generation pipeline:

  1. Validate landmark name (reject garbage/unidentified)
  2. Query Wikidata for UNESCO World Heritage status
  3. Build context-aware Gemini prompt with Wikidata facts
  4. Generate narration script + scene segmentation via Gemini
  5. Return complete information package

Three classes:
  WikidataClient        — UNESCO verification (SPARQL + REST API)
  ScriptGenerator       — Gemini prompt building + script generation
  InformationGenerator  — Public API (used by app.py)

Author: HistoriClip Team (Final Year Project)
"""

import logging
import json
import re
from typing import Optional, Dict, Any

import google.generativeai as genai

from .config import LocationEngineConfig, load_config_from_env

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# WikidataClient — UNESCO Verification
# ─────────────────────────────────────────────────────────────

class WikidataClient:
    """Queries Wikidata for UNESCO World Heritage status. All queries are live, zero hardcoded data."""

    def __init__(self, config: LocationEngineConfig):
        self._info_cfg = config.information
        self._endpoint = self._info_cfg.wikidata_endpoint
        self._timeout = self._info_cfg.wikidata_timeout
        self._user_agent = self._info_cfg.wikidata_user_agent

    # ── Public API ───────────────────────────────────────────

    def query_unesco_status(self, landmark_name: str) -> Dict[str, Any]:
        """
        Query Wikidata for UNESCO status using 4 strategies in order:
          1. Exact SPARQL label match
          2. Fuzzy search (original name)
          3. Fuzzy search with UNESCO suffix
          4. Coordinate-based SPARQL (5km radius)
        """
        logger.info(f"[Information] Querying Wikidata for: {landmark_name}")

        # Strategy 1: Exact label match
        result = self._sparql_unesco_query(landmark_name)
        if result and result.get('wikidata_id'):
            logger.info(f"[Information] Wikidata match found: {result.get('wikidata_id')}")
            if result.get('unesco_verified'):
                return result
            logger.info("[Information] Exact match is not UNESCO, trying fuzzy search...")
            non_unesco_fallback = result
        else:
            non_unesco_fallback = None

        # Strategy 2: Fuzzy search
        logger.info("[Information] Trying fuzzy search...")
        result = self._fuzzy_search_unesco(landmark_name)
        if result and result.get('wikidata_id'):
            if result.get('unesco_verified') or not non_unesco_fallback:
                logger.info(f"[Information] Fuzzy match found: {result.get('wikidata_id')}")
                if result.get('unesco_verified'):
                    return result
                if not non_unesco_fallback:
                    non_unesco_fallback = result

        # Strategy 3: Enhanced fuzzy search with UNESCO suffix
        logger.info("[Information] Trying enhanced fuzzy search with UNESCO suffix...")
        for suffix in ["World Heritage Site", "UNESCO"]:
            enhanced_name = f"{landmark_name} {suffix}"
            result = self._fuzzy_search_unesco(enhanced_name)
            if result and result.get('unesco_verified'):
                logger.info(f"[Information] ✅ Enhanced fuzzy search found UNESCO via: '{enhanced_name}'")
                result['wikidata_label'] = landmark_name
                return result

        # Strategy 4: Coordinate-based SPARQL (ultimate fallback)
        coords = None
        if non_unesco_fallback and non_unesco_fallback.get('coordinates'):
            coords = non_unesco_fallback['coordinates']

        if coords:
            logger.info(f"[Information] Trying coordinate-based UNESCO search near "
                        f"({coords['lat']:.4f}, {coords['lon']:.4f})...")
            result = self._search_nearby_unesco(coords['lat'], coords['lon'], landmark_name)
            if result and result.get('unesco_verified'):
                return result

        if non_unesco_fallback:
            logger.info(f"[Information] Using exact match fallback: {non_unesco_fallback.get('wikidata_id')}")
            return non_unesco_fallback

        logger.info(f"[Information] No Wikidata match for '{landmark_name}'")
        return self._empty_result()

    # ── Strategy 1: SPARQL Exact Match ───────────────────────

    def _sparql_unesco_query(self, landmark_name: str) -> Optional[Dict[str, Any]]:
        """SPARQL query for exact label match. Checks P1435, P8362, P625, P571, P1448."""
        try:
            from SPARQLWrapper import SPARQLWrapper, JSON

            safe_name = landmark_name.replace('"', '\\"').replace("\\", "\\\\")

            sparql_query = f"""
            SELECT ?item ?itemLabel ?itemDescription
                   ?heritageLabel ?unescoId ?inscriptionYear
                   ?coords ?officialName
            WHERE {{
                ?item rdfs:label "{safe_name}"@en .
                OPTIONAL {{ ?item wdt:P1435 ?heritage . }}
                OPTIONAL {{ ?item wdt:P8362 ?unescoId . }}
                OPTIONAL {{
                    ?item wdt:P571 ?inception .
                    BIND(YEAR(?inception) AS ?inscriptionYear)
                }}
                OPTIONAL {{ ?item wdt:P625 ?coords . }}
                OPTIONAL {{ ?item wdt:P1448 ?officialName . }}
                SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
            }}
            LIMIT 5
            """

            sparql = SPARQLWrapper(self._endpoint)
            sparql.setQuery(sparql_query)
            sparql.setReturnFormat(JSON)
            sparql.setTimeout(self._timeout)
            sparql.addCustomHttpHeader("User-Agent", self._user_agent)

            results = sparql.query().convert()
            bindings = results.get("results", {}).get("bindings", [])

            if not bindings:
                return None
            return self._parse_sparql_results(bindings)

        except Exception as e:
            logger.error(f"[Information] SPARQL query error: {e}")
            return None

    # ── Strategy 2: Fuzzy Search via Wikidata API ────────────

    def _fuzzy_search_unesco(self, landmark_name: str) -> Optional[Dict[str, Any]]:
        """Search Wikidata by fuzzy name match, then verify UNESCO status via REST API."""
        try:
            import requests

            params = {
                "action": "wbsearchentities",
                "search": landmark_name,
                "language": "en",
                "format": "json",
                "limit": 10,
                "type": "item"
            }
            headers = {"User-Agent": self._user_agent}

            resp = requests.get("https://www.wikidata.org/w/api.php",
                                params=params, headers=headers, timeout=self._timeout)
            resp.raise_for_status()
            search_results = resp.json().get("search", [])

            if not search_results:
                return None

            candidate_ids = [c.get("id") for c in search_results]
            logger.info(f"[Information] Fuzzy search candidates: {candidate_ids}")

            for candidate in search_results:
                qid = candidate.get("id")
                if not qid:
                    continue
                logger.info(f"[Information] Checking candidate {qid}: "
                            f"{candidate.get('label', '?')} - {candidate.get('description', '?')}")
                result = self._check_entity_unesco_rest(qid)
                if result:
                    return result

            best = search_results[0]
            return self._build_non_unesco_result(best)

        except Exception as e:
            logger.error(f"[Information] Fuzzy search error: {e}")
            return None

    # ── Entity-Level UNESCO Check (SPARQL) ───────────────────

    def _check_entity_unesco(self, qid: str) -> Optional[Dict[str, Any]]:
        """Check a specific QID for UNESCO status via SPARQL. Returns result if UNESCO, else None."""
        try:
            from SPARQLWrapper import SPARQLWrapper, JSON

            sparql_query = f"""
            SELECT ?itemLabel ?itemDescription
                   ?heritageLabel ?unescoId ?inscriptionYear
                   ?coords ?officialName
            WHERE {{
                BIND(wd:{qid} AS ?item)
                OPTIONAL {{ ?item wdt:P1435 ?heritage . }}
                OPTIONAL {{ ?item wdt:P8362 ?unescoId . }}
                OPTIONAL {{
                    ?item wdt:P571 ?inception .
                    BIND(YEAR(?inception) AS ?inscriptionYear)
                }}
                OPTIONAL {{ ?item wdt:P625 ?coords . }}
                OPTIONAL {{ ?item wdt:P1448 ?officialName . }}
                SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
            }}
            LIMIT 5
            """

            sparql = SPARQLWrapper(self._endpoint)
            sparql.setQuery(sparql_query)
            sparql.setReturnFormat(JSON)
            sparql.setTimeout(self._timeout)
            sparql.addCustomHttpHeader("User-Agent", self._user_agent)

            results = sparql.query().convert()
            bindings = results.get("results", {}).get("bindings", [])

            if not bindings:
                return None

            parsed = self._parse_sparql_results(bindings, forced_qid=qid)
            if parsed.get('unesco_verified'):
                return parsed
            return None

        except Exception as e:
            logger.error(f"[Information] SPARQL check error for {qid}: {e}")
            logger.info(f"[Information] Trying fast REST API fallback for {qid}...")
            return self._check_entity_unesco_rest(qid)

    # ── Entity-Level UNESCO Check (REST API — 7 Methods) ─────

    def _check_entity_unesco_rest(self, qid: str, _visited: set = None) -> Optional[Dict[str, Any]]:
        """
        Comprehensive UNESCO detection via REST API with 6 methods:
          1. P8362 (UNESCO ID)  2. P1435 (heritage labels)
          3. P31 (instance of WHS)  4. Description keywords
          5. P361 (part of)  6. P276 (location) — recursive with visited guard
        """
        if _visited is None:
            _visited = set()
        if qid in _visited:
            return None
        _visited.add(qid)

        try:
            import requests

            url = f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
            resp = requests.get(url, headers={"User-Agent": self._user_agent}, timeout=15)
            resp.raise_for_status()

            entity_data = resp.json().get("entities", {}).get(qid, {})
            claims = entity_data.get("claims", {})
            labels = entity_data.get("labels", {})
            descriptions = entity_data.get("descriptions", {})

            heritage_types = []

            # Method 1: P8362 (UNESCO World Heritage Site ID)
            has_unesco_id = "P8362" in claims
            if has_unesco_id:
                logger.info(f"[Information] {qid} has P8362 (UNESCO World Heritage Site ID)")

            # Method 2: P1435 (heritage designation) — fetch labels dynamically
            has_heritage = False
            if "P1435" in claims:
                heritage_qids = []
                for claim in claims["P1435"]:
                    hq = claim.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id", "")
                    if hq:
                        heritage_qids.append(hq)

                if heritage_qids:
                    heritage_labels = self._fetch_entity_labels(heritage_qids)
                    for hq, label in heritage_labels.items():
                        label_lower = label.lower()
                        logger.info(f"[Information] {qid} P1435 → {hq} = '{label}'")
                        if any(kw in label_lower for kw in
                               ["world heritage", "unesco", "patrimoine mondial",
                                "patrimonio de la humanidad", "welterbe"]):
                            has_heritage = True
                            heritage_types.append(label)

            # Method 3: P31 (instance of) — check for WHS classes
            has_instance_of = False
            whs_classes = {"Q9259", "Q43501", "Q386426", "Q54916622"}
            if "P31" in claims:
                for claim in claims["P31"]:
                    instance_qid = claim.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id", "")
                    if instance_qid in whs_classes:
                        has_instance_of = True
                        heritage_types.append("World Heritage Site")
                        logger.info(f"[Information] {qid} P31 → {instance_qid} (instance of WHS)")
                        break

            # Method 4: Description/label keyword detection
            has_desc_match = False
            desc_text = descriptions.get("en", {}).get("value", "").lower()
            label_text = labels.get("en", {}).get("value", "").lower()
            for kw in ["world heritage", "unesco", "patrimoine mondial", "patrimonio de la humanidad"]:
                if kw in desc_text or kw in label_text:
                    has_desc_match = True
                    heritage_types.append("World Heritage Site")
                    logger.info(f"[Information] {qid} UNESCO detected via keyword: '{kw}'")
                    break

            # If any direct method matched, build result
            if has_unesco_id or has_heritage or has_instance_of or has_desc_match:
                return self._build_unesco_result(qid, claims, labels, descriptions, heritage_types)

            # Method 5: P361 (part of) — check parent entities
            parent_result = self._check_parent_properties(qid, claims, labels, "P361", "part of", _visited)
            if parent_result:
                return parent_result

            # Method 6: P276 (location) — check location entities
            parent_result = self._check_parent_properties(qid, claims, labels, "P276", "location", _visited)
            if parent_result:
                return parent_result

            logger.info(f"[Information] {qid} is NOT a UNESCO site")
            return None

        except Exception as e:
            logger.error(f"[Information] REST API error for {qid}: {e}")
            return None

    def _check_parent_properties(self, child_qid: str, child_claims: dict,
                                  child_labels: dict, prop: str, prop_name: str,
                                  _visited: set) -> Optional[Dict[str, Any]]:
        """Recursively check if entities linked via P361/P276 are UNESCO sites."""
        if prop not in child_claims:
            return None

        parent_qids = []
        for claim in child_claims[prop]:
            parent_qid = claim.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id", "")
            if parent_qid and parent_qid not in _visited:
                parent_qids.append(parent_qid)

        if not parent_qids:
            return None

        logger.info(f"[Information] {child_qid} has {prop} ({prop_name}): {parent_qids[:5]}")
        for parent_qid in parent_qids[:5]:
            parent_result = self._check_entity_unesco_rest(parent_qid, _visited)
            if parent_result and parent_result.get('unesco_verified'):
                logger.info(f"[Information] ✅ {child_qid} is {prop_name.upper()} UNESCO site "
                            f"{parent_qid} ({parent_result.get('wikidata_label', '?')})")
                child_label = child_labels.get("en", {}).get("value")
                if child_label:
                    parent_result['wikidata_label'] = child_label
                parent_result['wikidata_id'] = child_qid
                parent_result['parent_unesco_site'] = parent_result.get('description', parent_qid)
                return parent_result

        return None

    # ── Strategy 4: Coordinate-Based SPARQL Search ───────────

    def _search_nearby_unesco(self, lat: float, lon: float,
                               landmark_name: str) -> Optional[Dict[str, Any]]:
        """Find UNESCO sites within 5km of given coordinates via SPARQL geo-query."""
        try:
            from SPARQLWrapper import SPARQLWrapper, JSON

            sparql_query = f"""
            SELECT ?site ?siteLabel ?siteDescription ?unescoId ?coords
            WHERE {{
                SERVICE wikibase:around {{
                    ?site wdt:P625 ?coords .
                    bd:serviceParam wikibase:center "Point({lon} {lat})"^^geo:wktLiteral .
                    bd:serviceParam wikibase:radius "5" .
                }}
                {{ ?site wdt:P31/wdt:P279* wd:Q9259 . }}
                UNION
                {{ ?site wdt:P8362 ?unescoId . }}
                SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
            }}
            LIMIT 5
            """

            sparql = SPARQLWrapper(self._endpoint)
            sparql.setQuery(sparql_query)
            sparql.setReturnFormat(JSON)
            sparql.setTimeout(self._timeout)
            sparql.addCustomHttpHeader("User-Agent", self._user_agent)

            results = sparql.query().convert()
            bindings = results.get("results", {}).get("bindings", [])

            if not bindings:
                logger.info("[Information] No UNESCO sites found nearby via coordinates.")
                return None

            best = bindings[0]
            site_uri = best.get("site", {}).get("value", "")
            site_qid = site_uri.split("/")[-1] if "/" in site_uri else None
            site_label = best.get("siteLabel", {}).get("value", "Unknown")
            site_desc = best.get("siteDescription", {}).get("value", "")

            logger.info(f"[Information] ✅ Found nearby UNESCO site: {site_label} ({site_qid})")

            result = self._empty_result()
            result['unesco_verified'] = True
            result['wikidata_id'] = site_qid
            result['wikidata_label'] = landmark_name
            result['description'] = site_desc
            result['heritage_types'] = ["World Heritage Site"]
            result['parent_unesco_site'] = site_label
            result['coordinates'] = {'lat': lat, 'lon': lon}

            unesco_id = best.get("unescoId", {}).get("value")
            if unesco_id:
                result['inscription_year'] = None

            return result

        except Exception as e:
            logger.error(f"[Information] Coordinate-based UNESCO search error: {e}")
            return None

    # ── Result Builders & Helpers ─────────────────────────────

    def _build_unesco_result(self, qid: str, claims: dict, labels: dict,
                             descriptions: dict, heritage_types: list) -> Dict[str, Any]:
        """Build a UNESCO-verified result dict from REST API entity data."""
        result = self._empty_result()
        result['wikidata_id'] = qid
        result['unesco_verified'] = True
        result['heritage_types'] = heritage_types

        if "en" in labels:
            result['wikidata_label'] = labels["en"]["value"]
        if "en" in descriptions:
            result['description'] = descriptions["en"]["value"]

        if "P625" in claims:
            try:
                coord_val = claims["P625"][0]["mainsnak"]["datavalue"]["value"]
                result['coordinates'] = {
                    'lat': coord_val.get("latitude"),
                    'lon': coord_val.get("longitude")
                }
            except (KeyError, IndexError):
                pass

        if "P571" in claims:
            try:
                time_val = claims["P571"][0]["mainsnak"]["datavalue"]["value"]["time"]
                result['inscription_year'] = time_val.split("-")[0].replace("+", "")
            except (KeyError, IndexError):
                pass

        logger.info(f"[Information] ✅ UNESCO verified via REST API for {qid}")
        return result

    @staticmethod
    def _build_non_unesco_result(search_entry: dict) -> Dict[str, Any]:
        """Build a result from Wikidata search API entry (non-UNESCO fallback)."""
        result = WikidataClient._empty_result()
        result['wikidata_id'] = search_entry.get('id')
        result['wikidata_label'] = search_entry.get('label')
        result['description'] = search_entry.get('description')
        return result

    def _fetch_entity_labels(self, qids: list) -> Dict[str, str]:
        """Batch-fetch English labels for a list of Wikidata QIDs via wbgetentities API."""
        try:
            import requests

            resp = requests.get(
                "https://www.wikidata.org/w/api.php",
                params={
                    "action": "wbgetentities", "ids": "|".join(qids),
                    "props": "labels", "languages": "en", "format": "json"
                },
                headers={"User-Agent": self._user_agent}, timeout=10
            )
            resp.raise_for_status()
            entities = resp.json().get("entities", {})

            return {
                qid: entities.get(qid, {}).get("labels", {}).get("en", {}).get("value", qid)
                for qid in qids
            }

        except Exception as e:
            logger.error(f"[Information] Failed to fetch entity labels: {e}")
            return {q: q for q in qids}

    def _parse_sparql_results(self, bindings: list, forced_qid: str = None) -> Dict[str, Any]:
        """Parse SPARQL bindings into a structured result dict. Determines UNESCO status dynamically."""
        result = self._empty_result()
        heritage_types = set()

        for row in bindings:
            if forced_qid:
                result['wikidata_id'] = forced_qid
            elif 'item' in row:
                uri = row['item']['value']
                result['wikidata_id'] = uri.split('/')[-1] if '/' in uri else uri

            if 'itemLabel' in row:
                result['wikidata_label'] = row['itemLabel']['value']
            if 'itemDescription' in row:
                result['description'] = row['itemDescription']['value']
            if 'heritageLabel' in row:
                heritage_types.add(row['heritageLabel']['value'])

            if 'inscriptionYear' in row and not result['inscription_year']:
                try:
                    result['inscription_year'] = str(int(float(row['inscriptionYear']['value'])))
                except (ValueError, TypeError):
                    pass

            if 'coords' in row and not result['coordinates']:
                parsed = self._parse_wkt_point(row['coords']['value'])
                if parsed:
                    result['coordinates'] = parsed

            if 'officialName' in row and not result['official_name']:
                result['official_name'] = row['officialName']['value']

        result['heritage_types'] = list(heritage_types)

        # UNESCO detection: P8362 ID check
        for row in bindings:
            if 'unescoId' in row and row['unescoId']:
                result['unesco_verified'] = True
                logger.info(f"[Information] UNESCO verified via WHS ID: {row['unescoId']['value']}")
                break

        # UNESCO detection: heritage label keyword check
        if not result['unesco_verified']:
            for ht in heritage_types:
                if any(kw in ht.lower() for kw in
                       ['world heritage', 'patrimoine mondial', 'patrimonio de la humanidad',
                        'welterbe', 'unesco']):
                    result['unesco_verified'] = True
                    logger.info(f"[Information] UNESCO verified via heritage label: {ht}")
                    break

        return result

    @staticmethod
    def _parse_wkt_point(wkt_string: str) -> Optional[Dict[str, float]]:
        """Parse WKT 'Point(lon lat)' into {lat, lon} dict."""
        try:
            match = re.search(r'Point\(([-\d.]+)\s+([-\d.]+)\)', wkt_string)
            if match:
                return {'lat': float(match.group(2)), 'lon': float(match.group(1))}
        except Exception:
            pass
        return None

    @staticmethod
    def _empty_result() -> Dict[str, Any]:
        """Blank result template."""
        return {
            'unesco_verified': False, 'official_name': None,
            'inscription_year': None, 'coordinates': None,
            'wikidata_id': None, 'wikidata_label': None,
            'description': None, 'heritage_types': []
        }


# ─────────────────────────────────────────────────────────────
# ScriptGenerator — Gemini-Powered Narration
# ─────────────────────────────────────────────────────────────

class ScriptGenerator:
    """Generates narration scripts and scene segmentation via Google Gemini."""

    def __init__(self, config: LocationEngineConfig):
        self._config = config
        self._info_cfg = config.information
        self._visual_cfg = config.visual
        self._gemini_model = None
        self._setup_gemini()

    def _setup_gemini(self):
        """Initialize Gemini with API key from config."""
        api_key = self._visual_cfg.gemini_api_key
        if not api_key:
            logger.warning("[Information] GEMINI_API_KEY not set.")
            return
        genai.configure(api_key=api_key)
        self._gemini_model = genai.GenerativeModel(self._visual_cfg.gemini_model)
        logger.info(f"[Information] Gemini configured: {self._visual_cfg.gemini_model}")

    # ── Script Generation ────────────────────────────────────

    def generate_script(self, landmark_name: str, wikidata_info: Dict[str, Any],
                        duration_seconds: int) -> Optional[str]:
        """Generate a narration script via Gemini. Returns script text or None."""
        if not self._gemini_model:
            logger.error("[Information] Gemini model not initialized.")
            return None

        target_words = self._compute_word_count(duration_seconds)
        prompt = self._build_prompt(landmark_name, wikidata_info, target_words, duration_seconds)

        try:
            logger.info(f"[Information] Generating script for '{landmark_name}' "
                        f"(~{target_words} words, {duration_seconds}s)...")
            response = self._gemini_model.generate_content(prompt)
            script = self._clean_script(response.text.strip())
            logger.info(f"[Information] Script generated: {len(script.split())} words")
            return script
        except Exception as e:
            logger.error(f"[Information] Gemini generation failed: {e}")
            return None

    def _compute_word_count(self, duration_seconds: int) -> int:
        """Convert duration to target word count using configured WPM."""
        return max(int((duration_seconds / 60.0) * self._info_cfg.words_per_minute), 50)

    # ── Prompt Building ──────────────────────────────────────

    def _build_prompt(self, landmark_name: str, wikidata_info: Dict[str, Any],
                      target_words: int, duration_seconds: int) -> str:
        """Build Gemini prompt with Wikidata context. UNESCO sites get enriched prompts."""
        unesco_verified = wikidata_info.get('unesco_verified', False)

        preamble = (
            f"You are a world-class documentary narrator and historian. "
            f"Write a narration script for a short documentary about "
            f"'{landmark_name}'.\n\n"
            f"STRICT REQUIREMENTS:\n"
            f"- The script must be approximately {target_words} words "
            f"(for a {duration_seconds}-second narration).\n"
            f"- Write ONLY the narration text — no stage directions, "
            f"no timestamps, no scene descriptions, no markdown.\n"
            f"- The tone should be engaging, informative, and cinematic.\n"
            f"- Include verified historical facts.\n"
            f"- Structure: Hook → Historical Context → Key Details → "
            f"Cultural Significance → Closing.\n"
        )

        context_section = self._build_context_section(landmark_name, wikidata_info)

        if unesco_verified:
            unesco_instructions = (
                f"\nUNESCO HERITAGE CONTEXT (MUST be referenced in the script):\n"
                f"- This is a UNESCO World Heritage Site. Mention this designation.\n"
            )
            if wikidata_info.get('inscription_year'):
                unesco_instructions += f"- UNESCO inscription year: {wikidata_info['inscription_year']}.\n"
            if wikidata_info.get('official_name'):
                unesco_instructions += f"- Official UNESCO name: '{wikidata_info['official_name']}'.\n"
            if wikidata_info.get('heritage_types'):
                unesco_instructions += f"- Heritage designations: {', '.join(wikidata_info['heritage_types'])}\n"
        else:
            unesco_instructions = (
                f"\nNOTE: This landmark is not a UNESCO World Heritage Site. "
                f"Focus on historical and cultural significance without false UNESCO claims.\n"
            )

        return preamble + context_section + unesco_instructions

    def _build_context_section(self, landmark_name: str, wikidata_info: Dict[str, Any]) -> str:
        """Build the Wikidata facts section of the prompt."""
        lines = ["\nVERIFIED FACTS FROM WIKIDATA:\n"]

        label = wikidata_info.get('wikidata_label')
        if label and label != landmark_name:
            lines.append(f"- Wikidata name: {label}")
        if wikidata_info.get('description'):
            lines.append(f"- Description: {wikidata_info['description']}")
        if wikidata_info.get('coordinates'):
            c = wikidata_info['coordinates']
            lines.append(f"- Location: {c['lat']:.4f}°N, {c['lon']:.4f}°E")
        if wikidata_info.get('official_name'):
            lines.append(f"- Official name: {wikidata_info['official_name']}")
        if wikidata_info.get('inscription_year'):
            lines.append(f"- Year of origin/inscription: {wikidata_info['inscription_year']}")

        if len(lines) == 1:
            lines.append(f"- No detailed Wikidata entry found for '{landmark_name}'. "
                         f"Use your knowledge to provide accurate historical facts.")

        return "\n".join(lines) + "\n"

    @staticmethod
    def _clean_script(raw_text: str) -> str:
        """Strip markdown artifacts from Gemini output."""
        text = raw_text.strip()
        if text.startswith("```"):
            text = re.sub(r'^```\w*\n?', '', text)
            text = re.sub(r'\n?```$', '', text)
        text = re.sub(r'^#{1,6}\s+.*$', '', text, flags=re.MULTILINE)
        text = text.replace("**", "").replace("__", "")
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    # ── Scene Segmentation ───────────────────────────────────

    def generate_scenes(self, landmark_name: str, script: str,
                        duration_seconds: int) -> Dict[str, Any]:
        """Split script into visual scenes and generate SDXL image prompts via Gemini."""
        if not self._gemini_model:
            return {'scenes': [], 'prompts': []}

        num_scenes = max(3, int(duration_seconds / 10))

        prompt = (
            f"You are a documentary director. Break this narration script for '{landmark_name}' "
            f"into exactly {num_scenes} distinct visual scenes.\n\n"
            f"SCRIPT:\n{script}\n\n"
            f"REQUIREMENTS:\n"
            f"1. Split the script text into {num_scenes} segments. Every word must be included exactly once, in order.\n"
            f"2. For each segment, write a highly detailed, photorealistic 8k SDXL image prompt.\n"
            f"3. Prompts must be diverse: Aerial view, Close-up details, Wide shot, Interior, etc.\n"
            f"4. OUTPUT FORMAT: A strictly valid JSON list of objects:\n"
            f"[{{\"segment_text\": \"...\", \"image_prompt\": \"...\"}}, ...]\n"
            f"5. NO markdown formatting, NO extra text. Just the raw JSON list."
        )

        try:
            logger.info(f"[Information] Generating {num_scenes} scenes via Gemini...")
            response = self._gemini_model.generate_content(prompt)
            text = response.text.strip()

            if text.startswith("```"):
                text = re.sub(r'^```\w*\n?', '', text)
                text = re.sub(r'\n?```$', '', text)

            scenes = json.loads(text)

            prompts, valid_scenes = [], []
            if isinstance(scenes, list):
                for s in scenes:
                    raw_prompt = s.get('image_prompt', '')
                    if raw_prompt:
                        full_prompt = f"{raw_prompt}, photorealistic, 8k, cinematic lighting, detailed texture"
                        valid_scenes.append({
                            'segment_text': s.get('segment_text', ''),
                            'image_prompt': full_prompt
                        })
                        prompts.append(full_prompt)

            logger.info(f"[Information] Generated {len(valid_scenes)} scenes.")
            if not valid_scenes:
                raise ValueError("No valid scenes found in Gemini response")

            return {'scenes': valid_scenes, 'prompts': prompts}

        except Exception as e:
            logger.error(f"[Information] Scene generation failed: {e}")
            fallback = [f"Cinematic shot of {landmark_name}, photorealistic, 8k"
                        for _ in range(num_scenes)]
            return {'scenes': [], 'prompts': fallback}


# ─────────────────────────────────────────────────────────────
# InformationGenerator — Public API (used by app.py)
# ─────────────────────────────────────────────────────────────

_GARBAGE_LANDMARK_RE = re.compile(
    r"^street\s*point|^unknown$|^unnamed|^\d+$|^mapillary|^unidentified|^location\s*\(",
    re.IGNORECASE
)


class InformationGenerator:
    """
    Public API. Orchestrates: validate → Wikidata → Gemini → return package.

    Usage:
        gen = InformationGenerator()
        result = gen.generate("Taj Mahal", user_duration=60)
    """

    def __init__(self, config: LocationEngineConfig = None):
        """Load config from environment if not provided."""
        self._config = config if config is not None else load_config_from_env()
        self._wikidata = WikidataClient(self._config)
        self._script_gen = ScriptGenerator(self._config)
        logger.info("[Information] InformationGenerator ready.")

    def generate(self, vision_result: Any, user_duration: int = None) -> Dict[str, Any]:
        """
        Generate a complete information package for a landmark.
        Accepts either a dict (from vision.py) or a string (landmark name directly).
        """
        # Step 1: Extract and validate landmark name
        landmark_name = self._extract_landmark_name(vision_result)

        if not landmark_name:
            logger.error("[Information] No landmark_name found in input.")
            return self._error_result("No landmark name provided.")

        # Step 1b: Reject unidentified locations (identified=False from vision.py)
        if isinstance(vision_result, dict) and vision_result.get('identified') is False:
            logger.warning(f"[Information] Rejecting unidentified location: '{landmark_name}'")
            return self._error_result(
                "Location could not be identified. Cannot generate a factual script "
                "without a verified landmark name.",
                landmark_name=landmark_name, unidentified=True
            )

        # Step 1c: Reject garbage/auto-generated names
        if _GARBAGE_LANDMARK_RE.search(landmark_name):
            logger.warning(f"[Information] Rejecting garbage landmark name: '{landmark_name}'")
            return self._error_result(
                f"Invalid landmark name: '{landmark_name}'. "
                f"This appears to be an auto-generated identifier, not a real place.",
                landmark_name=landmark_name, unidentified=True
            )

        logger.info(f"[Information] ═══ Processing: {landmark_name} ═══")

        # Step 2: Query Wikidata for UNESCO status
        wikidata_info = self._wikidata.query_unesco_status(landmark_name)
        unesco_verified = wikidata_info.get('unesco_verified', False)

        if unesco_verified:
            logger.info("[Information] ✓ UNESCO World Heritage Site VERIFIED")
            if wikidata_info.get('inscription_year'):
                logger.info(f"[Information]   Year: {wikidata_info['inscription_year']}")
            if wikidata_info.get('official_name'):
                logger.info(f"[Information]   Official: {wikidata_info['official_name']}")
        else:
            logger.info("[Information] ✗ Not a UNESCO World Heritage Site")

        # Step 3: Generate script via Gemini
        duration = user_duration or self._config.information.default_duration_seconds

        script = self._script_gen.generate_script(landmark_name, wikidata_info, duration)
        if not script:
            logger.error("[Information] Script generation failed.")
            return self._error_result(
                "Script generation failed.",
                landmark_name=landmark_name,
                wikidata_info=wikidata_info,
                unesco_verified=unesco_verified
            )

        # Step 4: Segment into visual scenes + image prompts
        logger.info("[Information] Segmenting script into scenes...")
        scene_data = self._script_gen.generate_scenes(landmark_name, script, duration)

        word_count = len(script.split())

        # Step 5: Return complete package
        result = {
            'script': script,
            'landmark_name': landmark_name,
            'unesco_verified': unesco_verified,
            'wikidata_info': wikidata_info,
            'duration_seconds': duration,
            'word_count': word_count,
            'scenes': scene_data.get('scenes', []),
            'prompts': scene_data.get('prompts', []),
            'is_unesco': unesco_verified,
            'unesco_year': wikidata_info.get('inscription_year'),
        }

        logger.info(f"[Information] ═══ Complete: {word_count} words, UNESCO={unesco_verified} ═══")
        return result

    # ── Helpers ───────────────────────────────────────────────

    @staticmethod
    def _extract_landmark_name(vision_result: Any) -> Optional[str]:
        """Extract landmark name from dict (vision.py) or string (app.py direct call)."""
        if isinstance(vision_result, str):
            return vision_result.strip() if vision_result.strip() else None
        if isinstance(vision_result, dict):
            for key in ('landmark_name', 'landmark', 'name'):
                val = vision_result.get(key)
                if val and isinstance(val, str) and val.strip():
                    return val.strip()
        return None

    @staticmethod
    def _error_result(message: str, landmark_name: str = None,
                      wikidata_info: Dict = None, unesco_verified: bool = False,
                      unidentified: bool = False) -> Dict[str, Any]:
        """Build a standardized error response."""
        return {
            'script': None, 'landmark_name': landmark_name,
            'unesco_verified': unesco_verified, 'wikidata_info': wikidata_info,
            'duration_seconds': 0, 'word_count': 0,
            'is_unesco': unesco_verified,
            'unesco_year': wikidata_info.get('inscription_year') if wikidata_info else None,
            'error': message, 'unidentified': unidentified,
            'scenes': [], 'prompts': []
        }


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    print("=" * 60)
    print("HistoriClip - Information Module v3.0")
    print("Wikidata UNESCO + Gemini Script Generation")
    print("=" * 60)

    if len(sys.argv) < 2:
        print("\nUsage: python -m modules.information <landmark_name> [duration_seconds]")
        print("\nExamples:")
        print('  python -m modules.information "Taj Mahal"')
        print('  python -m modules.information "Eiffel Tower" 90')
        sys.exit(0)

    landmark = sys.argv[1]
    duration = int(sys.argv[2]) if len(sys.argv) >= 3 else None

    gen = InformationGenerator()
    result = gen.generate(landmark, user_duration=duration)

    print(f"\n{'─' * 60}")
    print(f"Landmark:  {result.get('landmark_name')}")
    print(f"UNESCO:    {result.get('unesco_verified')}")
    print(f"Year:      {result.get('unesco_year', 'N/A')}")
    print(f"Words:     {result.get('word_count')}")
    print(f"Duration:  {result.get('duration_seconds')}s")
    print(f"{'─' * 60}")

    if result.get('wikidata_info'):
        print("\nWikidata Info:")
        for k, v in result['wikidata_info'].items():
            print(f"  {k}: {v}")

    if result.get('script'):
        print(f"\n{'─' * 60}")
        print("SCRIPT:")
        print(f"{'─' * 60}")
        print(result['script'])
    elif result.get('error'):
        print(f"\nERROR: {result['error']}")
