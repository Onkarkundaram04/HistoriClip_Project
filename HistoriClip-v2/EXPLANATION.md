# HistoriClip — The Definitive Technical Architecture Manual (v3.0)

> **Purpose:** This document is the single source of truth for understanding every system, module, function, and data-flow in HistoriClip. It is written so that even after years away from this codebase, you can read it and completely reconstruct the project logic without touching the code. Every diagram, description, and code annotation here has been verified against the actual source files.

---

## Table of Contents

1. [What Is HistoriClip?](#1-what-is-historyclip)
2. [System Architecture Overview](#2-system-architecture-overview)
3. [The Grand Request Lifecycle](#3-the-grand-request-lifecycle)
4. [Python AI Service — The Brain](#4-python-ai-service--the-brain)
   - 4.1 [app.py — Flask Entry Point & Orchestrator](#41-apppy--flask-entry-point--orchestrator)
   - 4.2 [vision.py — The 4-Tier Location Pipeline](#42-visionpy--the-4-tier-location-pipeline)
   - 4.3 [loc_engine.py — DINOv2 + FAISS + LightGlue](#43-loc_enginepy--dinov2--faiss--lightglue)
   - 4.4 [information.py — Wikidata + Gemini Script Engine](#44-informationpy--wikidata--gemini-script-engine)
   - 4.5 [visual.py — SDXL Lightning Image Generator](#45-visualpy--sdxl-lightning-image-generator)
   - 4.6 [audio.py — Edge-TTS Narration Generator](#46-audiopy--edge-tts-narration-generator)
   - 4.7 [editor.py — FFmpeg Video Assembler](#47-editorpy--ffmpeg-video-assembler)
5. [Node.js Backend — The State Manager](#5-nodejs-backend--the-state-manager)
   - 5.1 [server.js — Express App Bootstrap](#51-serverjs--express-app-bootstrap)
   - 5.2 [Authentication Flow](#52-authentication-flow)
   - 5.3 [analyzeController.js — Generation Orchestrator](#53-analyzecontrollerjs--generation-orchestrator)
   - 5.4 [Database Models & Schema](#54-database-models--schema)
6. [React Frontend — The User Interface](#6-react-frontend--the-user-interface)
7. [Data Flow: End-to-End with Payloads](#7-data-flow-end-to-end-with-payloads)
8. [XAI — Explainable AI System](#8-xai--explainable-ai-system)
9. [Configuration System](#9-configuration-system)

---

## 1. What Is HistoriClip?

HistoriClip is a **full-stack AI documentary generator**. A user uploads a **photo of a historical monument or landmark**. The system:

1. **Identifies** the location using a 4-tier AI cascade (Google Vision → GPS → DINOv2/FAISS → Gemini VLM).
2. **Verifies** whether it is a UNESCO World Heritage Site using live Wikidata SPARQL queries.
3. **Generates** a cinematic narration script via Google Gemini, tailored to the exact landmark and its UNESCO status.
4. **Synthesizes** voice narration using Microsoft Azure Edge Neural TTS.
5. **Creates** AI-generated images via Stable Diffusion XL Lightning (8-step).
6. **Assembles** the final `.mp4` documentary video with Ken Burns zoom, crossfade transitions, and synchronized audio via FFmpeg.
7. **Provides Explainable AI (XAI)** proof — visual keypoint matching between the user's photo and the reference database using LightGlue geometry, and a DINOv2 attention heatmap.

---

## 2. System Architecture Overview

The project is split into **three independent services** that communicate over HTTP:

```
┌────────────────────────────────────────────────────────────────────────┐
│                         USER'S BROWSER                                 │
│                  React 19 (Vite, port 5173 dev)                        │
│   Pages: Home, Login, Signup, Dashboard, History, VideoDetail          │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │  HTTP REST (JSON + FormData)
                                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│                     NODE.JS BACKEND (Express.js)                       │
│                           Port: 5000                                   │
│  • JWT Auth           • MySQL (via mysql2/promise)                     │
│  • multer file save   • Video/Image/User models                        │
│  • Static /uploads    • Progress tracking via DB                       │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │  HTTP POST multipart/form-data
                                     │  X-AI-Service-Secret header
                                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   PYTHON AI SERVICE (Flask)                             │
│                           Port: 5001                                   │
│  • vision.py     → 4-tier landmark identification                      │
│  • loc_engine.py → DINOv2 + FAISS + LightGlue                         │
│  • information.py→ Wikidata SPARQL + Gemini script                     │
│  • visual.py     → SDXL Lightning image generation                     │
│  • audio.py      → Edge-TTS narration synthesis                        │
│  • editor.py     → FFmpeg video assembly                               │
└────────────────────────────────────────────────────────────────────────┘
```

![System Architecture Overview](diagrams/01_system_architecture.png)

---

## 3. The Grand Request Lifecycle

This is the **exact sequence** of events when a user uploads a photo and clicks "Generate":

![Grand Request Lifecycle — Sequence Diagram](diagrams/02_request_lifecycle.png)

### Critical Architecture Facts

| Fact | Correct Detail |
|---|---|
| **Non-blocking generation** | Node.js returns `200 OK` immediately. Video generation runs in a background `.catch()` promise — never awaited. |
| **Frontend polling** | React polls `GET /api/videos/:id` every ~3 seconds, checking the `status` field (`processing` → `completed` / `failed`). |
| **Progress reporting** | Python POSTs `{video_id, step}` to `http://localhost:5000/api/analyze/progress` after completing each pipeline step. This is **not** SSE streaming — it is plain HTTP callbacks. |
| **Authentication header** | The shared secret between Node.js and Python uses the header name `X-AI-Service-Secret`. |
| **File storage** | All generated files are saved into `backend/uploads/` subdirectories (not in `python-ai-service/`). |
| **URL building** | `host_url()` in `app.py` converts absolute disk paths → `http://localhost:5000/uploads/...` URLs for the frontend. |

---

## 4. Python AI Service — The Brain

### 4.1 `app.py` — Flask Entry Point & Orchestrator

**File:** `python-ai-service/app.py`

This file is the Flask microservice entry point. It does **not** contain AI logic — it wires together all the AI modules and provides the HTTP API surface.

![app.py Boot Sequence](diagrams/03_app_boot_sequence.png)

#### Why `KMP_DUPLICATE_LIB_OK = "TRUE"` Must Be Line 17

PyTorch and FAISS both link to OpenMP via different runtime libraries. On Windows, loading both causes a fatal "OMP: Error #15" crash. Setting this environment variable **before any C++ library is imported** tells the runtime to ignore duplicate OpenMP instances. Without this line, the service crashes the moment `import faiss` executes.

#### Lazy Loading Singletons — The VRAM Strategy

All AI models start as `None` globals:

```python
vision_analyzer = None   # VisionAnalyzer() — wraps DINOv2, Google API calls
info_generator   = None   # InformationGenerator() — Wikidata + Gemini
image_generator  = None   # ImageGenerator() — SDXL Lightning pipeline
audio_generator  = None   # AudioGenerator() — Edge-TTS
video_editor     = None   # VideoEditor() — FFmpeg wrapper
```

Each has a getter that initializes on first call:

```python
def get_image_generator():
    global image_generator
    if image_generator is None:
        image_generator = ImageGenerator()  # Loads 4GB SDXL model into VRAM — once only
    return image_generator
```

**Why?** Loading all models immediately on boot would require ~20 GB of combined GPU+RAM. With lazy loading, only the modules needed for the current request are loaded. On a 6 GB GPU, models are loaded one at a time and the generations are sequential.

#### `require_service_auth` Decorator — Security Gate

Every AI endpoint is decorated with this:

```python
@require_service_auth
def generate_video():
    ...
```

The decorator:
1. Reads `X-AI-Service-Secret` from the incoming request header (or `?secret=` query param as fallback).
2. Compares it against the `AI_SERVICE_SECRET` environment variable.
3. If they don't match → returns `{"error": "Unauthorized"}` with HTTP 401.
4. If `AI_SERVICE_SECRET` is empty/not set → prints `[WARNING] ... endpoints are OPEN!` and allows through (development convenience only).

> **Security rationale:** The Python Flask service has no firewall of its own. Any process on `localhost:5001` can call it. The shared secret ensures that only the authorized Node.js backend can trigger AI generation — not a rogue browser tab or attacker who discovers the port.

#### `/generate` — The Full Pipeline Endpoint

![/generate Endpoint Pipeline](diagrams/04_generate_endpoint.png)

#### `host_url(path)` — Disk Path to HTTP URL Converter

After generation, files live at disk paths like:
`C:\...\backend\uploads\generated_videos\video_abc.mp4`

The React frontend needs HTTP URLs. `host_url()` converts them:

1. Gets the absolute path of `backend/uploads`.
2. Computes `os.path.relpath(abs_file_path, backend_uploads)` → `generated_videos\video_abc.mp4`.
3. Replaces backslashes: `generated_videos/video_abc.mp4`.
4. Prefixes: `http://localhost:5000/uploads/generated_videos/video_abc.mp4`.

---

### 4.2 `vision.py` — The 4-Tier Location Pipeline

**File:** `python-ai-service/modules/vision.py`

This module answers: **"Which landmark is in this photo?"**

It tries up to 4 different techniques in order. The moment one succeeds, it returns a standardized result dict. If all fail, it returns `identified=False`. **It never fabricates a name.**

![4-Tier Vision Pipeline](diagrams/05_4tier_vision_pipeline.png)

After Tier 3 runs (regardless of `identified` outcome), it always:
- Generates the **LightGlue XAI visualization** (3-panel keypoint match image).
- Generates the **DINOv2 attention heatmap** (fallback XAI).
- Builds the **top-5 FAISS match list** for the frontend table.

---

#### Every Function in Detail

---

**`detect_landmark_google(image_path)` — Tier 1**

**What it does:** Queries Google's Cloud Vision API for landmark recognition in the photo.

**Step-by-step:**
1. Reads `GOOGLE_VISION_API_KEY` env var. If missing → logs a warning, returns `None` immediately (skips entire tier).
2. Opens the image file from disk in binary mode, encodes it to Base64 string.
3. Builds a JSON REST payload with feature type `LANDMARK_DETECTION` and `maxResults: 5`.
4. POSTs to `https://vision.googleapis.com/v1/images:annotate?key=API_KEY` with a 15-second timeout.
5. Parses the response: takes `responses[0].landmarkAnnotations[0]` (Google's top result).
6. Extracts `description` (the landmark name), `score` (Google's confidence, 0.0–1.0), and GPS from `locations[0].latLng`.

**Returns:** `{'name': 'Taj Mahal', 'confidence': 0.97, 'lat': 27.175, 'lon': 78.042}` or `None` on error/no detection.

> Note: The function does NOT apply any confidence threshold. It trusts Google's ranking — if Google returns a result, the pipeline uses it (after the `_is_meaningful_name` filter step in `analyze_image`).

---

**`extract_gps_from_exif(image_path)` — Tier 2**

**What it does:** Reads precise GPS coordinates that camera apps embed in JPEG/TIFF metadata (EXIF).

**Step-by-step:**
1. Opens image with PIL (`Image.open()`), calls `image._getexif()` to get raw tag dict.
2. If `_getexif()` returns `None` (PNG files, stripped JPEGs) → returns `None`.
3. Iterates EXIF tag IDs, looking for the tag where `TAGS.get(tag_id) == 'GPSInfo'`.
4. Decodes the GPS sub-IFD using `GPSTAGS.get(k, k)` for human-readable key names.
5. Calls `_dms_to_decimal()` on `GPSLatitude` and `GPSLongitude`.
6. Applies direction sign: if `GPSLatitudeRef == 'S'` → negate lat; if `GPSLongitudeRef == 'W'` → negate lon.

**Returns:** `{'lat': 18.5204, 'lon': 73.8567}` or `None`.

---

**`_dms_to_decimal(dms)` — GPS Coordinate Converter**

GPS in EXIF is encoded as Degrees/Minutes/Seconds, stored as rational number tuples. For example, `18°31'13.4"N` is stored as `((18,1), (31,1), (134,10))`.

The conversion formula:

$$\text{decimal\_degrees} = D + \frac{M}{60} + \frac{S}{3600}$$

Implementation:
```python
float(dms[0]) + float(dms[1]) / 60.0 + float(dms[2]) / 3600.0
```

The `float()` calls handle both integer and rational number (fraction tuple) formats.

---

**`reverse_geocode(lat, lon)` — Coordinates to Place Name**

**What it does:** Converts GPS coordinates into a structured location description via OpenStreetMap's Nominatim API.

**Step-by-step:**
1. Calls `https://nominatim.openstreetmap.org/reverse` with params: `lat`, `lon`, `format=json`, `addressdetails=1`, `zoom=18` (building-level detail).
2. **Must** set `User-Agent: HistoriClip/3.0` — Nominatim's Terms of Service require a descriptive User-Agent; requests without it may be rate-limited.
3. Extracts the `name` field from the address by checking fields in this priority order:
   `tourism` → `historic` → `building` → `amenity` → `leisure` → `place_of_worship` → `shop`
4. Also extracts `city`, `state`, `country` for context.

**Returns:**
```python
{
    'display_name': 'Shaniwar Wada, Kasba Peth, Pune, Maharashtra 411011, India',
    'name': 'Shaniwar Wada',
    'city': 'Pune',
    'state': 'Maharashtra',
    'country': 'India',
    'lat': 18.5193, 'lon': 73.8553
}
```

---

**`_haversine_quick(lat1, lon1, lat2, lon2)` — Earth-Curved Distance**

The [Haversine formula](https://en.wikipedia.org/wiki/Haversine_formula) calculates Great-Circle distance (in meters) between two GPS coordinates, accounting for Earth's spherical curvature:

$$a = \sin^2\!\left(\frac{\Delta\phi}{2}\right) + \cos\phi_1 \cdot \cos\phi_2 \cdot \sin^2\!\left(\frac{\Delta\lambda}{2}\right)$$
$$d = 2R \cdot \arctan2\!\left(\sqrt{a},\, \sqrt{1-a}\right)$$

Where $R = 6{,}371{,}000\,\text{m}$ (Earth's mean radius).

Used in:
- `_find_landmark_in_area()` — distance scoring for POI candidates.
- `_compute_gps_consensus()` in `loc_engine.py` — filtering outlier FAISS matches.
- `analyze_image()` — filtering consistent GPS points for area search.

---

**`_is_meaningful_name(name)` and `_is_landmark_quality_name(name)` — Name Validators**

Two guards against garbage data:

`_is_meaningful_name`: Checks against `_GARBAGE_RE` regex patterns — rejects strings matching: `"street point"`, `"unknown"`, `"unnamed"`, pure digits, `"mapillary"`, `"node 12345"`, `"way 12345"`, `"null"`, `"n/a"`.

`_is_landmark_quality_name`: Additional numeric-ratio check:
- Minimum 4 characters.
- Ratio of digit chars to total alphanumerics must be ≤ 50%. (Rejects `"B-44"`, `"402"`, `"20-20"` — these are OSM database IDs that accidentally leak through.)
- At least one non-digit alphanumeric character.

`_ROAD_SUFFIXES` regex: Rejects generic infrastructure (e.g., `"Shivaji Road"`, `"Gandhi Marg"`, `"Peth Lane"`) — these are street-level names, not landmarks.

---

**`_find_landmark_in_area(gps_points, padding_km=1.0)` — POI Area Search**

**When called:** When `reverse_geocode()` returns a generic result (a road name, generic building, or "Unknown").

**Strategy 1 — Nominatim bbox search (fast, ~1 second):**
1. Computes bounding box from all GPS points plus `padding_km ÷ 111` degrees padding per km.
2. Searches for 9 POI types one by one: `'temple', 'mandir', 'museum', 'monument', 'historic', 'church', 'mosque', 'fort', 'heritage'`.
3. For each result, computes: `final_score = type_score + (importance × 10) - (distance_km × 1.0)`.
4. `type_score` from `_POI_PRIORITY` dict: `place_of_worship=10`, `monument=9`, `archaeological_site=9`, `memorial=8`, `museum=8`, `ruins=7`, etc.
5. Returns the highest-scoring valid candidate name.

**Strategy 2 — Overpass API (fallback, ~3-12 seconds):**

If Nominatim finds nothing culturally significant, sends a single Overpass QL query covering the entire bounding box. Queries for nodes/ways tagged with:
- `amenity=place_of_worship`
- `tourism~attraction|museum|monument|memorial|artwork`
- `historic~monument|memorial|fort|castle|ruins|archaeological_site|heritage|temple`

Tries 3 mirror servers in sequence: `overpass.kumi.systems` → `maps.mail.ru` → `overpass-api.de`.

From results, scores by `_POI_PRIORITY` (similar to Strategy 1). Returns the best name found.

---

**`_identify_landmark_vlm(image_path, lat, lon, city, state)` — Tier 3.5: The Novel Fusion**

**What it does:** This is the key innovation of HistoriClip's vision pipeline. DINOv2+FAISS gave us the approximate GPS neighborhood. Now Gemini VLM looks at the actual photo AND the geographic context together to identify the specific landmark.

**Step-by-step:**
1. Loads `google.generativeai` with the `GEMINI_API_KEY`.
2. Opens the image as a PIL image object.
3. Builds a geographic context string: e.g., `"GPS coordinates (18.5193, 73.8553) in Pune, Maharashtra"`.
4. Crafts a detailed prompt:
   - "Identify the EXACT name of the landmark/monument/temple shown."
   - "Look for visible text, signage, or architectural features."
   - "If you can read signs in any language/script, use that."
   - "Return ONLY the official name. If uncertain, return exactly: UNIDENTIFIED"
5. Sends both the text prompt AND the PIL image to Gemini's multimodal API.
6. Validates the response: rejects if it says `UNIDENTIFIED`, is less than 3 chars, or starts with `"a "` / `"the "` (generic descriptions).

**Returns:** Landmark name string (e.g., `"Shaniwar Wada"`) or `None`.

> **Why this matters:** DINOv2 might match to the correct city block but not know the temple name. Gemini's vision ability combined with the location context ("near Pune") dramatically narrows down possibilities. A Pune temple and a similar-looking Delhi temple might confuse DINOv2 alone, but Gemini with location context will correctly identify both.

---

**`_build_result(**kwargs)` — Standardized Result Schema**

All tiers funnel results through this single constructor to guarantee a consistent dict schema:

| Field | Type | Description |
|---|---|---|
| `success` | bool | `True` if any GPS was found, even without a landmark name |
| `identified` | bool | `True` only if a real, culturally meaningful landmark name was verified |
| `method` | str | `'tier1_landmark'`, `'tier2_gps'`, or `'tier3_dinov2_gem'` |
| `landmark_name` | str | The identified name, or `"Unidentified Location"` |
| `location` | dict | Full Nominatim address dict |
| `gps` | dict | `{'lat': float, 'lon': float}` |
| `confidence` | float | 0.0–1.0; Google's score / 0.7 (GPS) / FAISS cosine similarity |
| `xai_matches_path` | str or None | Local disk path to LightGlue 3-panel image (Tier 3 only) |
| `xai_attention_path` | str or None | Local disk path to attention heatmap (Tier 3 only) |
| `xai_top_matches` | list or None | Top-5 FAISS matches with similarity, GPS, LightGlue inliers |
| `xai_tier_used` | str | Specific which Tier 3 sub-method resolved the name |

---

**`VisionAnalyzer.analyze(image_file)` — Flask Bridge Wrapper**

The `VisionAnalyzer` class exists purely to bridge Flask's `FileStorage` objects to file-path-based functions.

When Flask receives a file upload, `request.files['image']` is a `FileStorage` object in memory — not a disk path. The `analyze_image()` function in this module requires a disk path.

The bridge:
1. Creates a **named temporary file** using `tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)`.
2. Saves the `FileStorage` object to the temp file path.
3. Calls `analyze_image(tmp_path)`.
4. In the `finally` block (always runs, even on exception), deletes the temp file with `os.unlink(tmp_path)`.

---

### 4.3 `loc_engine.py` — DINOv2 + FAISS + LightGlue

**File:** `python-ai-service/modules/loc_engine.py`

This is the heaviest AI module. The `LocationEngine` class provides **visual place recognition** — it identifies locations by mathematically comparing a query photo against a database of thousands of geotagged reference images.

![DINOv2 + FAISS + LightGlue — Offline Build & Online Search](diagrams/06_dinov2_faiss_lightglue.png)

#### The Core Algorithm: Why DINOv2?

**DINOv2 (Meta AI, 2023)** is a Vision Transformer (ViT-Base) trained using DINO + iBOT self-supervised objectives on 142 million curated images. It produces dense patch representations — one 768-dimensional vector per 14×14 pixel region of the input image.

Unlike CNNs trained for classification, DINOv2's features have exceptional **place recognition** properties demonstrated in the **AnyLoc (ICRA 2024)** paper — meaning photos of the same building from different angles, times of day, or weather conditions produce mathematically close vectors in the 768-dimensional feature space.

#### GeM Pooling — Amplifying Distinctive Features

DINOv2 produces `~256 patch tokens` (for 224×224 input). Simply averaging them (mean pooling) dilutes the discriminative signal — sky, trees, and people get equal weight as the unique architecture.

**Generalized Mean (GeM) Pooling** (Radenović et al., TPAMI 2019):

$$\text{GeM}(\mathbf{X}, p) = \left(\frac{1}{N} \sum_{i=1}^{N} x_i^p \right)^{1/p}$$

With $p = 3.0$ (the AnyLoc default):
- Patch activations are raised to the **3rd power** before averaging.
- High-activation patches (distinctive architectural features: arches, columns, carvings) get mathematically amplified exponentially.
- Low-activation patches (sky, background, vegetation) become negligible.
- After the inverse power application, the result is a single 768-dim vector that heavily represents the unique visual signature of the structure.

```python
@staticmethod
def gem_pool(features: 'torch.Tensor', power: float = 3.0) -> 'torch.Tensor':
    # features shape: [batch=1, num_patches, 768]
    features = features.clamp(min=1e-6)   # Numerical stability (no log(0))
    return features.pow(power).mean(dim=1).pow(1.0 / power)
    # → shape: [batch=1, 768]
```

#### FAISS Index — `IndexFlatIP` (Cosine Similarity)

```python
self._index = faiss.IndexFlatIP(self._feature_dim)  # IP = Inner Product
```

After L2-normalizing all vectors to unit length ($\|\mathbf{v}\| = 1$), the Inner Product equals Cosine Similarity:

$$\text{cosine\_similarity}(\mathbf{a}, \mathbf{b}) = \mathbf{a} \cdot \mathbf{b} \quad \text{when } \|\mathbf{a}\| = \|\mathbf{b}\| = 1$$

`IndexFlatIP` performs **exact** brute-force search (no approximation). For the dataset sizes typical of this project (hundreds to thousands of reference images), exact search is fast enough and always returns the true best matches.

> ⚠️ **Correction from earlier documentation:** The FAISS index uses `IndexFlatIP` (Inner Product / cosine similarity), **NOT** `IndexFlatL2` (Euclidean distance). After L2 normalization, these are mathematically equivalent in ranking but cosine similarity has a natural 0–1 scale for the threshold comparison.

---

**`_load_model()`**

Lazy-loads `facebook/dinov2-base` from HuggingFace Hub. Checks for CUDA, loads with `.eval()` mode (disables dropout and batch normalization training behavior). After loading, records `self._feature_dim = model.config.hidden_size` (768 for dinov2-base).

**`extract_features(image_path)`**

For a single query image:
1. PIL.open → RGB convert.
2. `AutoImageProcessor` resizes and normalizes pixels.
3. Forward pass inside `torch.no_grad()`.
4. `outputs.last_hidden_state[:, 1:, :]` — skips the first token (CLS token, used for classification) and uses only the **spatial patch tokens**.
5. `gem_pool()` → 768-dim.
6. `features / np.linalg.norm(features)` → L2-normalize to unit vector.

**`extract_features_batch(image_paths)`**

Same as above but processes `batch_size` images at once (configured in `config.dinov2.batch_size`). Prints progress: `10/500 images (2%)`. Combines all batch results and normalizes the entire matrix in one operation: `features / np.linalg.norm(features, axis=1, keepdims=True)`.

---

**`build_index()`**

One-time operation, called from the CLI (`python -m modules.loc_engine build`):
1. Reads `locations.csv` (columns: `filename, lat, lon, name, source`).
2. Verifies each image file exists.
3. Calls `extract_features_batch()` on all images.
4. Adds all feature vectors to `faiss.IndexFlatIP`.
5. Saves: `faiss.write_index(self._index, index_file_path)` and metadata JSON.

**`load_index()`**

Loads the pre-built index from disk:
1. `faiss.read_index(idx_path)` → loads the binary FAISS index.
2. `json.load(meta_path)` → loads the metadata list (filename, lat, lon, name).
3. Calls `_load_model()` to ensure DINOv2 is ready for query extraction.
4. Returns `True` on success, `False` if files don't exist.

---

**`search(query_image_path)`**

The core search operation:
1. If index not loaded → tries `load_index()`.
2. Extracts query vector: `extract_features(query_image_path)`.
3. `self._index.search(query_vector.reshape(1,-1), k=5)` → returns `(scores, indices)`, arrays of shape `(1, 5)`.
4. Builds `matches` list from top-k results.
5. Checks if top match's `similarity ≥ min_confidence` (configured threshold, default 0.3).
6. Calls `_compute_gps_consensus()`.
7. Runs LightGlue verification loop over top-5 matches.
8. Returns the complete result dict.

---

**`_compute_gps_consensus(matches, max_spread_meters=500.0)`**

The top-5 FAISS matches can include false positives — visually similar buildings in other cities. This function filters them:

1. Takes the top FAISS match (`matches[0]`) as the anchor point.
2. Computes Haversine distance from anchor to each other match.
3. **Discards** any match further than 500 meters from the anchor.
4. Computes `numpy.median` of remaining latitudes and longitudes.

**Why median over mean?**

$$\text{Example:}$$
- Match 1: Pune (18.5193, 73.8553) 
- Match 2: Pune (18.5195, 73.8551)
- Match 3: Pune (18.5191, 73.8549)
- Match 4: Mumbai (19.0760, 72.8777) ← outlier, >500m away, discarded
- Match 5: Pune (18.5194, 73.8552)

Median lat = 18.5194, Median lon = 73.8552 → firmly in Pune.

If using mean and the outlier wasn't filtered: result would be in the Arabian Sea between Pune and Mumbai.

---

**`_verify_with_lightglue(query_path, match_filename)`**

Runs geometric verification between the query photo and a reference photo:

1. **`_load_lightglue()`** — Lazy-loads `DISK.from_pretrained("depth")` (feature extractor) and `LightGlueMatcher("disk")` from the `kornia.feature` module.
2. Both images are resized to fit within `config.dinov2.lightglue_max_size` (default: 1024px).
3. Images are padded to a multiple of 16 pixels (DISK architecture requirement).
4. `DISK` extracts keypoints + descriptors for each image.
5. `LightGlueMatcher` matches descriptors between the two images.
6. Counts valid match pairs (`num_matches`).
7. `verified = num_matches >= config.dinov2.min_matches_verified` (default: 15).

The LightGlue verification loop in `search()` runs this for all top-5 matches and **promotes whichever match has the most inliers**, even if it was ranked #3 or #4 by FAISS similarity. This is a critical correction mechanism: FAISS ranks by global appearance, but LightGlue counts locally-verified geometric correspondences.

```python
# If a non-#1 match has the most inliers, override the best match GPS
if best_ver_idx > 0 and best_ver.get('verified', False):
    promoted = matches[best_ver_idx]
    best['lat'] = promoted['lat']
    best['lon'] = promoted['lon']
```

---

**`visualize_matches(query_image_path, match_filename)` — 3-Panel XAI Image**

Generates the visual "proof" of the match shown in the VideoDetail page:

```
Panel 1        Panel 2          Panel 3 (Combined)
┌──────────┐  ┌──────────┐    ┌─────────────────────────┐
│          │  │          │    │          ┊               │
│  User's  │  │ Database │    │  User ───╋──────► Ref   │
│  photo   │  │  match   │    │  img   ──╋──────► img   │
│          │  │          │    │        ──╋──────►        │
└──────────┘  └──────────┘    └─────────────────────────┘
"Your Photo"  "Database Match"   "Keypoint Matches (N verified)"
```

Each green line in Panel 3 connects a detected keypoint in the user's photo to the geometrically corresponding keypoint in the database reference photo (e.g., a specific corner of an arch, a decorative element, an edge).

Saved as a 150 DPI JPEG at `query_image_path_matches.jpg`.

---

**`visualize_attention(image_path)` — Fallback XAI Heatmap**

If LightGlue / kornia is unavailable, falls back to showing where DINOv2 "looked":

1. Forward pass with `output_attentions=True`.
2. `outputs.attentions[-1]` → last transformer layer's attention tensor, shape `[1, num_heads, 1+n_patches, 1+n_patches]`.
3. `.mean(dim=1)` → average across all attention heads.
4. `att[0, 0, 1:]` → CLS token's attention weights to all spatial patches (shape: `[n_patches]`).
5. `reshape(n, n)` → square patch grid.
6. Normalize to [0, 1] for visualization.
7. Resize to original image dimensions and overlay with `cmap='hot'`.

```
Panel 1: Original    Panel 2: Attention Map    Panel 3: Overlay
┌──────────┐         ┌──────────┐              ┌──────────┐
│  temple  │         │ ⬛⬛🔥🔥⬛│              │ original │
│  with    │         │ ⬛🔥🔥🔥⬛│              │ + fire   │
│  arches  │         │ ⬛⬛🔥⬛⬛│              │  overlay │
└──────────┘         └──────────┘              └──────────┘
```

The hottest (brightest) regions are the pixels DINOv2 weighted most heavily when computing the landmark's visual fingerprint.

---

### 4.4 `information.py` — Wikidata + Gemini Script Engine

**File:** `python-ai-service/modules/information.py`

Three classes work in sequence:

![information.py Class Flow](diagrams/07_information_classes.png)

---

#### `WikidataClient` — UNESCO Verification

**4-Strategy Cascade:**

![WikidataClient 4-Strategy UNESCO Cascade](diagrams/08_wikidata_cascade.png)

---

**`_sparql_unesco_query(landmark_name)` — Strategy 1**

Sends a SPARQL query to `https://query.wikidata.org/sparql` via `SPARQLWrapper`:

```sparql
SELECT ?item ?heritageLabel ?unescoId ?inscriptionYear ?coords ?officialName
WHERE {
    ?item rdfs:label "Taj Mahal"@en .          -- exact English label match
    OPTIONAL { ?item wdt:P1435 ?heritage . }    -- P1435 = heritage designation
    OPTIONAL { ?item wdt:P8362 ?unescoId . }    -- P8362 = UNESCO WHS ID (e.g., "252")
    OPTIONAL { ?item wdt:P571 ?inception . }    -- P571  = year of inscription
    OPTIONAL { ?item wdt:P625 ?coords . }       -- P625  = geographic coordinates (WKT)
    OPTIONAL { ?item wdt:P1448 ?officialName . } -- P1448 = official name
    SERVICE wikibase:label { bd:serviceParam wikibase:language "en" . }
}
LIMIT 5
```

**Wikidata Properties Used:**

| Property | Meaning | Example |
|---|---|---|
| P1435 | Heritage designation | Q9259 = "World Heritage Site" |
| P8362 | UNESCO World Heritage Site ID | "252" (Taj Mahal's ID) |
| P625 | Geographic coordinates | `Point(78.0421 27.1750)` (WKT format) |
| P571 | Inception date | 1983-01-01T00:00:00Z |
| P1448 | Official name | "Taj Mahal" |
| P31 | Instance of | Q9259 (World Heritage Site class) |
| P361 | Part of | (parent entity) |
| P276 | Location | (containing region entity) |

UNESCO status is confirmed if any binding has: `unescoId` present OR `heritageLabel` contains "World Heritage" / "UNESCO" / "patrimoine mondial".

---

**`_check_entity_unesco_rest(qid, _visited)` — 6-Method Deep UNESCO Check**

When fuzzy search returns candidate QIDs, this performs exhaustive UNESCO detection via the REST API (`https://www.wikidata.org/wiki/Special:EntityData/{qid}.json`):

| Method | What It Checks |
|---|---|
| 1 | Has P8362 (UNESCO WHS ID) directly |
| 2 | P1435 labels contain "world heritage", "UNESCO", "patrimoine mondial", "welterbe" |
| 3 | P31 (instance of) includes known WHS class QIDs: Q9259, Q43501, Q386426, Q54916622 |
| 4 | English description or label text contains "world heritage" or "UNESCO" |
| 5 (recursive) | P361 (part of) entity is a UNESCO site |
| 6 (recursive) | P276 (location) entity is a UNESCO site |

**The Recursive Methods (5 & 6) — `_check_parent_properties()`:**

```
Example: "Shaniwar Wada's Hazari Karanja Gate" (QID X)
  → P361 (part of): "Shaniwar Wada" (QID Y)
    → P361 (part of): "Historic City of Pune" (QID Z — hypothetical UNESCO site)
      → Has P8362: YES → UNESCO confirmed ✅
      → Inherit: gate's documentary says it IS in a UNESCO complex
```

A `_visited: set` prevents infinite recursion in circular Wikidata graphs (e.g., Entity A "part of" Entity B "part of" Entity A). Maximum recursion depth: first 5 parents checked.

---

**`_fetch_entity_labels(qids)` — Batch Label Fetcher**

Method 2 of `_check_entity_unesco_rest` needs to know the English label of heritage QIDs (like Q9259 = "World Heritage Site"). Instead of making one API call per QID, this batches them:

```
GET https://www.wikidata.org/w/api.php
  ?action=wbgetentities
  &ids=Q9259|Q92206|Q123456
  &props=labels
  &languages=en
```

Returns: `{"Q9259": "World Heritage Site", "Q92206": "...", ...}`.

---

**`_search_nearby_unesco(lat, lon, landmark_name)` — Strategy 4: Geographic SPARQL**

When the landmark name itself isn't in Wikidata (obscure local landmark), searches for UNESCO sites near the FAISS-estimated GPS:

```sparql
SERVICE wikibase:around {
    ?site wdt:P625 ?coords .
    bd:serviceParam wikibase:center "Point(73.8553 18.5193)"^^geo:wktLiteral .
    bd:serviceParam wikibase:radius "5" .    -- 5 km radius
}
{ ?site wdt:P31/wdt:P279* wd:Q9259 . }      -- instance of World Heritage Site (or subclass)
UNION
{ ?site wdt:P8362 ?unescoId . }             -- OR has direct UNESCO ID
```

If a UNESCO site is found within 5 km, the landmark is considered to be within a UNESCO-designated area.

---

**`ScriptGenerator.generate_script(landmark_name, wikidata_info, duration_seconds)`**

Builds the Gemini prompt with:

```python
target_words = max(int((duration_seconds / 60.0) * words_per_minute), 50)
```

Where `words_per_minute` comes from `config.information.words_per_minute` (default: 130 WPM).

| Duration | Target Words |
|---|---|
| 30 seconds | max(65, 50) = 65 words |
| 60 seconds | max(130, 50) = 130 words |
| 90 seconds | max(195, 50) = 195 words |

The prompt structure includes:
- Word count requirement
- Documentary narrator persona
- Verified Wikidata facts (coordinates, description, official name, founding year)
- If UNESCO: **MUST** mention the designation and inscription year.
- If NOT UNESCO: **MUST NOT** falsely claim UNESCO status.
- Structure: `Hook → Historical Context → Key Details → Cultural Significance → Closing`
- No markdown, no stage directions, no timestamps in the raw script output.

`_clean_script()` post-processes the Gemini response to strip any accidental Markdown artifacts (code fences, `##` headers, `**bold**`, etc.).

---

**`ScriptGenerator.generate_scenes(landmark_name, script, duration_seconds)`**

Number of scenes: `max(3, int(duration_seconds / 10))`.

| Duration | Scenes |
|---|---|
| 30 seconds | max(3, 3) = 3 scenes |
| 60 seconds | max(3, 6) = 6 scenes |
| 90 seconds | max(3, 9) = 9 scenes |

Sends the entire finished narration script back to Gemini, asking it to:
1. Split the script into exactly N sequential segments (every word in order, no omissions).
2. Write an SDXL image prompt for each segment.
3. Prompts must be cinematically diverse: aerial views, close-up details, wide establishing shots, interior shots.

Output is forced to be a raw JSON list:
```json
[
  {"segment_text": "Rising above the banks...", "image_prompt": "Aerial cinematic shot of ..."},
  {"segment_text": "Built in 1732...", "image_prompt": "Close-up architectural detail of ..."}
]
```

After JSON parsing, each prompt is suffix-enhanced: `, photorealistic, 8k, cinematic lighting, detailed texture`.

The `fallback` list (returned on JSON parse failure) is `N` copies of `"Cinematic shot of {landmark_name}, photorealistic, 8k"`.

---

### 4.5 `visual.py` — SDXL Lightning Image Generator

**File:** `python-ai-service/modules/visual.py`

![SDXL Lightning Image Generation Pipeline](diagrams/09_sdxl_pipeline.png)

#### Why SDXL Lightning (8 Steps)?

Standard SDXL requires **50 denoising timesteps** per image. At 1024×576 resolution on a 6GB GPU, that takes ~3-5 minutes per image.

**ByteDance SDXL Lightning** is a **distilled** model — trained using adversarial distillation so the 8-step output matches the 50-step full model's quality. Result: **under 30 seconds** per image.

**Critical constraint:** The Lightning model **requires** `EulerDiscreteScheduler` with `timestep_spacing="trailing"`. Standard Euler or DDIM schedulers with default timestep spacing produce blurry, distorted outputs because the Lightning distillation was specifically trained with trailing spacing. The trailing spacing samples timesteps from the high-noise end of the diffusion chain.

#### TinyVAE — The 6GB VRAM Enabler

| Component | Standard SDXL | With TinyVAE |
|---|---|---|
| VAE size | ~2 GB | 10 MB |
| VAE VRAM | ~2 GB | ~300 MB |
| Quality | Reference | Near-identical |

`madebyollin/taesdxl` is a tiny encoder-decoder trained to approximate the full SDXL VAE's latent-to-pixel decoding. The approximation introduces slight smoothing but is barely perceptible in generated images.

#### CPU Offloading Strategy

`pipe.enable_model_cpu_offload()` uses PyTorch's sequential CPU offloading:
- **VRAM holds:** Only the model component currently being computed (e.g., UNet for step N).
- **RAM holds:** Text encoders (CLIP), VAE, and the UNet weights not currently active.
- Components are shuttled GPU ↔ RAM automatically at each diffusion step.

Without offloading: ~12 GB VRAM required.  
With offloading: ~4-6 GB VRAM required.

#### xformers — Attention Memory Optimization

Standard PyTorch Multi-Head Self-Attention in the UNet:
- Computes the full attention matrix: $O(n^2)$ memory where $n$ = number of latent pixels.
- For 1024×576: $n = 128 \times 72 = 9216$ patches. Matrix: $9216^2 = 84.9M$ elements.

xformers' Memory-Efficient Attention (based on FlashAttention):
- Computes attention in chunks: $O(n)$ peak memory.
- No accuracy loss — exact same mathematical result.
- 30-50% reduction in VRAM usage during attention operations.

---

### 4.6 `audio.py` — Edge-TTS Narration Generator

**File:** `python-ai-service/modules/audio.py`

![Edge-TTS Audio Generation Pipeline](diagrams/10_audio_tts_pipeline.png)

#### Why Script Preprocessing Is Essential

Without preprocessing, the TTS engine would literally vocalise:

> *"hash hash hash Historical Context\nasterisk asterisk Built in 1732 asterisk asterisk\nbracket Wikipedia bracket open paren URL close paren..."*

The preprocessing ensures only the intended spoken word content reaches the TTS engine.

Key transformations:

| Input (from Gemini) | Output (to TTS) |
|---|---|
| `## Historical Context` | `Historical Context` |
| `**Built in 1732**` | `Built in 1732` |
| `[UNESCO Site](url)` | `UNESCO Site` |
| `B.C.` | `B C` (prevents "B period C period") |
| `e.g.` | `for example` |
| `— ` (em dash) | `, ` (natural pause) |
| `\n\n` (paragraph break) | `. ` (sentence boundary pause) |

#### The Async-to-Sync Bridge Problem

`edge-tts` is designed for `async for` usage:

```python
async def main():
    communicate = edge_tts.Communicate(text="Hello", voice="...")
    async for chunk in communicate.stream():
        ...
asyncio.run(main())
```

Flask's WSGI server runs in synchronous threads — you cannot `await` in a route handler.

The bridge handles three cases:
1. **Normal Flask (no event loop):** Just `asyncio.run(_synth())` — creates a new event loop.
2. **Jupyter Notebook context (event loop running):** `nest_asyncio.apply()` patches the existing loop to allow nested `run_until_complete()`.
3. **No nest_asyncio in Jupyter:** Spawns a `ThreadPoolExecutor` thread where a fresh `asyncio.run()` is safe (the thread has no running loop).

#### SRT Subtitle Generation

`edge_tts.SubMaker` captures timing events from the TTS stream. As the TTS generates audio, it emits `WordBoundary` events with precise start-time for each word. `get_srt()` converts these into standard SRT format:

```srt
1
00:00:00,000 --> 00:00:02,450
Rising above the banks of the Mutha

2
00:00:02,450 --> 00:00:05,920
stands the eternal Shaniwar Wada.
```

These `.srt` files are stored alongside the `.mp3` in `backend/uploads/generated_audio/`.

---

### 4.7 `editor.py` — FFmpeg Video Assembler

**File:** `python-ai-service/modules/editor.py`

![FFmpeg Video Assembly Pipeline](diagrams/11_ffmpeg_editor.png)

#### Duration Mathematics

**Given:** 3 images, 30-second audio, 1-second crossfade transitions.

$$\text{slide\_dur} = \max\!\left(\frac{30 + (3-1) \times 1.0}{3},\; 1.0 + 0.1\right) = \max(10.67,\;1.1) = 10.67\,\text{s}$$

Total visual duration: $3 \times 10.67 - 2 \times 1.0 = 30.01\,\text{s} \approx 30\,\text{s audio}$ ✓

The formula ensures that when the crossfades overlap adjacent images, the total playback time still matches the audio duration exactly.

#### Ken Burns Zoom — `zoompan` Filter

```
zoompan=z='min(zoom+0.0015,1.5)':d=267:s=1024x576
```

- `zoom` starts at 1.0 (no zoom) for the first frame.
- Each frame: zoom increases by `0.0015`.
- Cap at `1.5` (50% zoom-in maximum, prevents excessive pixelation).
- `d=267`: duration in video frames. For 10.67 seconds × 25 fps: $\lfloor10.67 \times 25\rfloor = 267$.
- `s=1024x576`: output resolution (1024×576 is 16:9 HD).

The `zoompan` filter creates the "Ken Burns effect" — the slow, cinematic zoom into the center of the image that makes static photos feel like moving documentary footage.

#### Crossfade Chain Construction

For 3 images with 1.0s transitions:

```
Offset for image 2: 1 × (10.67 - 1.0) = 9.67s
Offset for image 3: 2 × (10.67 - 1.0) = 18.34s

filter_complex:
  [0:v] ... zoompan ... [v0]
  [1:v] ... zoompan ... [v1]
  [2:v] ... zoompan ... [v2]
  [v0][v1] xfade=transition=fade:duration=1.0:offset=9.67 [f1]
  [f1][v2] xfade=transition=fade:duration=1.0:offset=18.34 [f2]
```

The `xfade` filter blends `curr` and `next` streams during the overlap period. The `transition=fade` gradually changes opacity. Other available transitions: `wipeleft`, `wiperight`, `circleopen`, `distance`, `slidedown`, etc. (configured via `config.editor.transition_type`).

#### `_detect_nvenc()` — GPU Hardware Encoder Detection

```python
result = subprocess.run([self._ffmpeg, "-encoders"], capture_output=True, text=True)
found = "h264_nvenc" in result.stdout
```

`ffmpeg -encoders` lists all available video encoders. `h264_nvenc` is NVIDIA's dedicated video encoding chip (NVENC) — present on all RTX and most GTX 1000+ series GPUs.

| Encoder | Speed (30s video) | Quality |
|---|---|---|
| `h264_nvenc` (NVIDIA GPU) | ~2-3 seconds | Excellent |
| `libx264` (CPU) | 30-120 seconds | Excellent |

#### `_get_audio_duration()` — Why Parse stderr?

FFmpeg intentionally refuses to run without an output file. Running `ffmpeg -i audio.mp3` **fails** — but before failing, FFmpeg prints the file's metadata to `stderr`:

```
Input #0, mp3, from 'audio.mp3':
  Duration: 00:00:31.24, start: 0.000000, bitrate: 256 kb/s
```

The function intercepts `result.stderr` and regex-matches `Duration: (\d{2}):(\d{2}):(\d{2}\.\d+)` to extract the duration in `HH:MM:SS.ms` format, then converts to total seconds:

$$\text{duration} = H \times 3600 + M \times 60 + S = 0 \times 3600 + 0 \times 60 + 31.24 = 31.24\,\text{s}$$

---

## 5. Node.js Backend — The State Manager

### 5.1 `server.js` — Express App Bootstrap

**File:** `backend/src/server.js`

![server.js Express Bootstrap](diagrams/12_server_bootstrap.png)

#### Key Security Decisions

**`crossOriginResourcePolicy: 'cross-origin'`:** Without this override, helmet's default `same-origin` policy blocks the React frontend (port 5173) from loading video/audio URLs from port 5000. Setting `cross-origin` allows any origin to load the static uploaded files.

**`contentSecurityPolicy: false`:** In development, the React dev server (Vite) uses inline scripts and eval. A strict CSP would break it. In a production deployment via nginx, CSP would be set at the nginx level.

**CORS rules:** Three tiers of allowed origins:
1. Explicitly configured in `CORS_ORIGIN` env var (comma-separated list).
2. Any `http(s)://localhost:PORT` or `127.0.0.1:PORT` regex.
3. Private network ranges: `192.168.x.x`, `10.x.x.x`, `172.16-31.x.x` (for local network access from phones/tablets on the same Wi-Fi).

---

### 5.2 Authentication Flow

![Authentication Flow — Sequence Diagram](diagrams/13_auth_flow.png)

**bcrypt (10 rounds):** `bcrypt.hash("password", 10)` applies 10 rounds of the Blowfish-based one-way hash. The salt is embedded in the resulting hash string (e.g., `$2b$10$...`). Even with the database leaked, cracking a single bcrypt-10 hash takes hundreds of years on consumer hardware.

**JWT Structure:** The token has three Base64URL-encoded parts:
1. **Header:** `{"alg": "HS256", "typ": "JWT"}`
2. **Payload:** `{"userId": 5, "email": "user@example.com", "iat": 1709..., "exp": 1710...}`
3. **Signature:** `HMAC-SHA256(header.payload, JWT_SECRET)`

The middleware decodes the payload and verifies the signature on every protected request. The `exp` field enforces the 7-day expiry.

---

### 5.3 `analyzeController.js` — Generation Orchestrator

**File:** `backend/src/controllers/analyzeController.js`

#### `generate(req, res)` — Non-Blocking Handler

The fundamental insight: Video generation can take 5-40 minutes. HTTP connections have maximum timeout limits. The solution:

```javascript
// 1. DB record created immediately
const videoRecord = await Video.create({ status: 'processing' });
videoId = videoRecord.id;

// 2. Background task — NOT awaited (fire and forget)
analyzeController.processVideoGenerationBackground(videoId, imagePath, duration).catch(err => {
    console.error('[Background Gen Error]', err);
});

// 3. Return 200 within milliseconds
return response.success(res, { id: videoId, status: 'processing' });
```

The `processVideoGenerationBackground` promise runs in the Node.js event loop concurrently. Errors are caught by `.catch()` and logged — they don't propagate to the now-closed HTTP response.

#### `processVideoGenerationBackground(videoId, imagePath, duration)` — Detailed Walkthrough

![analyzeController Background Process](diagrams/14_analyze_controller.png)

#### `updateProgress(req, res)` — Internal Callback Handler

Called by Python after each pipeline step:

```javascript
async updateProgress(req, res) {
    const { video_id, step } = req.body;  // e.g., { video_id: "42", step: "images" }
    await Video.update(video_id, { processing_step: step });
    return res.json({ ok: true });
}
```

The React polling will pick up the new `processing_step` value and update the progress bar label:

| Step Value | Progress Bar Label |
|---|---|
| `vision` | "Identifying Location..." |
| `script` | "Generating Script..." |
| `images` | "Creating Images..." |
| `audio` | "Synthesizing Voice..." |
| `video` | "Assembling Video..." |
| `xai` | "Processing XAI Proofs..." |
| `complete` | "Done!" |

---

### 5.4 Database Models & Schema

![Database Entity-Relationship Diagram](diagrams/15_database_schema.png)

**`Video` Model Key Methods:**

| Method | SQL Operation |
|---|---|
| `create(videoData)` | `INSERT INTO videos (...) VALUES (?)` |
| `findById(id)` | `SELECT * FROM videos WHERE id = ?` |
| `findByIdAndUser(id, userId)` | `SELECT * FROM videos WHERE id = ? AND user_id = ?` (ownership check) |
| `findByUser(userId, {page, limit, search, status})` | Paginated SELECT with LIKE search and status filter |
| `update(id, data)` | `UPDATE videos SET ... WHERE id = ?` |
| `updateStatus(id, status, errorMsg)` | `UPDATE videos SET status = ?, processing_step = ? WHERE id = ?` |
| `delete(id)` | `DELETE FROM videos WHERE id = ?` |

**`Image` Model Key Methods:**

| Method | SQL Operation |
|---|---|
| `createMany(videoId, images[])` | Loops: `INSERT INTO images (video_id, url, prompt) VALUES (?)` |
| `findByVideoId(videoId)` | `SELECT * FROM images WHERE video_id = ?` |

---

## 6. React Frontend — The User Interface

**Location:** `frontend-react/src/`
**Build Tool:** Vite 5 | **Framework:** React 19 | **Router:** React Router DOM

![React Frontend Route Structure](diagrams/16_react_routing.png)

#### Page-by-Page Breakdown

---

**`Home.jsx`**

The marketing landing page. Shows:
- Hero section with tagline and "Get Started" button.
- Feature highlights (AI identification, UNESCO checking, documentary generation).
- Calls-to-action linking to `/signup` and `/login`.

No API calls. Pure static content.

---

**`Login.jsx` and `Signup.jsx`**

Standard controlled forms using React state. On submit:
1. `POST /api/auth/login` or `POST /api/auth/signup`.
2. On success: store JWT in `localStorage.setItem('token', token)`, update `AuthContext`.
3. Navigate to `/dashboard`.

---

**`Dashboard.jsx`** — The Core Action Page

![Dashboard Upload & Polling Flow](diagrams/17_dashboard_polling.png)

---

**`History.jsx`** — All Past Videos

1. On mount: `GET /api/videos?page=1&limit=10` → paginated list.
2. Renders each video as a card with: original image, landmark name, creation date, status badge, UNESCO badge (if applicable).
3. Search box: filters by `landmark_name` (client-side or via `?search=` query param).
4. Status filter: `completed | processing | failed | all`.
5. Delete button: `DELETE /api/videos/:id` → removes from list.

---

**`VideoDetail.jsx`** — The Result Showcase

Fetches `GET /api/videos/:id` and renders:

1. **HTML5 Video Player**: `<video src={video_url} controls />` with custom Lucide icon overlay for play/pause/volume.
2. **Narration Script**: Full Gemini-generated script text in a scrollable panel.
3. **UNESCO Badge**: Prominently displayed if `is_unesco === true`, with year.
4. **Location & GPS**: Shows `location` string and `latitude`/`longitude` on an interactive map.
5. **XAI Panel:**
   - Tier used badge (e.g., "Identified via Gemini VLM + FAISS").
   - LightGlue 3-panel visualization image.
   - DINOv2 attention heatmap image.
   - Top-5 FAISS matches table (similarity score, coordinates, LightGlue verified checkmark).
6. **Download Button**: Links to `/download?url={video_url}`, forces `Save As` dialog.
7. **Generated Images Gallery**: All SDXL-generated frames shown as thumbnails.

---

**`Navbar.jsx` and `Footer.jsx`**

`Navbar`: Reads `AuthContext` to determine login state. Shows: logo, navigation links, and either Login/Signup buttons (unauthenticated) or username + Logout (authenticated).

`Footer`: Static links. Social icons. Copyright.

---

## 7. Data Flow: End-to-End with Payloads

Complete JSON payload reference for every service boundary:

#### React → Node.js: `POST /api/analyze`

```
Content-Type: multipart/form-data
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

FormData fields:
  image    → (binary JPEG/PNG data)
  duration → "normal"  (or "fast")
```

#### Node.js → React: Immediate Response (< 100ms)

```json
{
  "success": true,
  "data": {
    "id": 42,
    "status": "processing",
    "message": "Video generation started in background"
  },
  "message": "Video generation started successfully"
}
```

#### Node.js → Python: `POST /generate`

```
Content-Type: multipart/form-data
X-AI-Service-Secret: <shared_secret_from_env>

FormData fields:
  image        → (binary JPEG/PNG read from disk via createReadStream)
  speed        → "normal"
  video_id     → "42"
  callback_url → "http://localhost:5000/api/analyze/progress"
```

#### Python → Node.js: Progress Callbacks (7 total)

```json
POST http://localhost:5000/api/analyze/progress
{"video_id": "42", "step": "vision"}
{"video_id": "42", "step": "script"}
{"video_id": "42", "step": "images"}
{"video_id": "42", "step": "audio"}
{"video_id": "42", "step": "video"}
{"video_id": "42", "step": "xai"}
{"video_id": "42", "step": "complete"}
```

#### Python → Node.js: Final Result JSON

```json
{
  "success": true,
  "landmark": "Shaniwar Wada",
  "location": {
    "name": "Shaniwar Wada", "city": "Pune",
    "state": "Maharashtra", "country": "India",
    "display_name": "Shaniwar Wada, Kasba Peth, Pune...",
    "lat": 18.5193, "lon": 73.8553
  },
  "gps": {"lat": 18.5193, "lon": 73.8553},
  "script": "Rising above the banks of the Mutha River...",
  "is_unesco": false,
  "unesco_year": null,
  "video_path": "http://localhost:5000/uploads/generated_videos/video_a1b2c3d4.mp4",
  "audio_path": "http://localhost:5000/uploads/generated_audio/narration_e5f6g7h8.mp3",
  "image_paths": [
    "http://localhost:5000/uploads/generated_images/gen_1741200000_1.png",
    "http://localhost:5000/uploads/generated_images/gen_1741200060_2.png",
    "http://localhost:5000/uploads/generated_images/gen_1741200120_3.png"
  ],
  "prompts": [
    "Aerial cinematic shot of Shaniwar Wada fort, photorealistic, 8k...",
    "Close-up of ancient stone battlements...",
    "Wide establishing shot at golden hour..."
  ],
  "xai_matches_url": "http://localhost:5000/uploads/xai/matches_i9j0k1l2.jpg",
  "xai_attention_url": "http://localhost:5000/uploads/xai/attention_i9j0k1l2.jpg",
  "xai_top_matches": [
    {"rank": 1, "similarity": 0.9234, "lat": 18.5193, "lon": 73.8553,
     "filename": "shaniwar_01.jpg", "inliers": 124, "verified": true},
    {"rank": 2, "similarity": 0.8921, "lat": 18.5195, "lon": 73.8551,
     "filename": "shaniwar_02.jpg", "inliers": 98, "verified": true},
    {"rank": 3, "similarity": 0.8476, "lat": 18.5191, "lon": 73.8549,
     "filename": "shaniwar_03.jpg", "inliers": 67, "verified": true}
  ],
  "xai_tier_used": "tier3_faiss_vlm"
}
```

#### React Polling Response: `GET /api/videos/42`

```json
{
  "id": 42,
  "user_id": 5,
  "landmark_name": "Shaniwar Wada",
  "script": "Rising above the banks...",
  "video_url": "http://localhost:5000/uploads/generated_videos/video_a1b2c3d4.mp4",
  "audio_url": "http://localhost:5000/uploads/generated_audio/narration_e5f6g7h8.mp3",
  "original_image_url": "/uploads/1741199850000-user-photo.jpg",
  "is_unesco": 0,
  "unesco_year": null,
  "location": "Shaniwar Wada",
  "latitude": "18.51930000",
  "longitude": "73.85530000",
  "status": "completed",
  "processing_step": "complete",
  "xai_matches_url": "http://localhost:5000/uploads/xai/matches_i9j0k1l2.jpg",
  "xai_attention_url": "http://localhost:5000/uploads/xai/attention_i9j0k1l2.jpg",
  "xai_top_matches": "[{\"rank\":1,\"similarity\":0.9234,...}]",
  "xai_tier_used": "tier3_faiss_vlm",
  "created_at": "2026-03-06T14:32:10.000Z"
}
```

---

## 8. XAI — Explainable AI System

HistoriClip's key differentiator: it **shows its work**. Every landmark identification includes visual proof of the AI reasoning process.

![XAI System — Explainable AI Artifacts](diagrams/18_xai_system.png)

#### Understanding the LightGlue Visualization

The 3-panel image in VideoDetail is visual mathematical proof:

**Panel 1 — Your Photo:** The original user-uploaded image.

**Panel 2 — Database Match:** The most geometrically-verified reference image from the FAISS database (the one with the most LightGlue inliers).

**Panel 3 — Keypoint Matches:** Both images side-by-side with green lines connecting matched keypoints.

Each green line = a proven geometric correspondence:
- A specific corner of an archway in your photo → same corner in the database image.
- A carved decorative element → same element at the same relative position.
- An edge of a column → same edge in the reference.

A random photo against a random reference produces 0–5 accidental matches. A photo of the same actual structure produces 50–300+ geometrically consistent matches (inliers). The `verified=True` flag in the match data indicates the inlier count exceeded the minimum threshold (configured in `config.dinov2.min_matches_verified`, default: 15).

#### `xai_tier_used` Values

| Value | Meaning |
|---|---|
| `tier1_landmark` | Google Vision identified with high confidence. |
| `tier2_gps` | EXIF GPS + Nominatim reverse geocode. |
| `tier3_faiss_geocode` | DINOv2/FAISS → best match GPS → Nominatim reverse geocode gave a meaningful name. |
| `tier3_faiss_vlm` | DINOv2/FAISS → GPS → Gemini VLM used location context to identify by name (novel fusion). |
| `tier3_faiss_unresolved` | FAISS found a GPS region but no method identified a specific landmark name. |

---

## 9. Configuration System

**Python AI Service:** `python-ai-service/modules/config.py`

All settings come from environment variables. `load_config_from_env()` returns a nested dataclass `LocationEngineConfig`.

```
LocationEngineConfig
├── dinov2 (DINOv2Config)
│   ├── model_name         → env: DINOV2_MODEL          | default: "facebook/dinov2-base"
│   ├── device             → env: DINOV2_DEVICE          | default: "auto"
│   ├── pooling_method     → env: POOLING_METHOD         | default: "gem"
│   ├── gem_power          → env: GEM_POWER              | default: 3.0
│   ├── top_k              → env: FAISS_TOP_K            | default: 5
│   ├── min_confidence     → env: MIN_CONFIDENCE         | default: 0.3
│   ├── use_lightglue      → env: USE_LIGHTGLUE          | default: True
│   ├── min_matches_verified → env: MIN_MATCHES_VERIFIED | default: 15
│   ├── lightglue_max_size → env: LIGHTGLUE_MAX_SIZE     | default: 1024
│   ├── max_viz_matches    → env: MAX_VIZ_MATCHES        | default: 50
│   └── batch_size         → env: BATCH_SIZE             | default: 8
│
├── visual (VisualConfig)
│   ├── gemini_api_key     → env: GEMINI_API_KEY         | (required)
│   ├── gemini_model       → env: GEMINI_MODEL           | default: "gemini-2.0-flash-exp"
│   ├── default_steps      → env: SDXL_STEPS             | default: 8
│   ├── default_guidance   → env: SDXL_GUIDANCE          | default: 0.0
│   └── resolution_laptop  → env: RESOLUTION             | default: (1024, 576)
│
├── information (InformationConfig)
│   ├── words_per_minute   → env: WORDS_PER_MINUTE       | default: 130
│   ├── default_duration_seconds → env: DEFAULT_DURATION | default: 60
│   ├── wikidata_endpoint  → env: WIKIDATA_ENDPOINT      | default: "https://query.wikidata.org/sparql"
│   └── wikidata_timeout   → env: WIKIDATA_TIMEOUT       | default: 30
│
├── audio (AudioConfig)
│   ├── voice              → env: TTS_VOICE              | e.g., "en-US-GuyNeural"
│   ├── rate               → env: TTS_RATE               | default: "+0%"
│   ├── volume             → env: TTS_VOLUME             | default: "+0%"
│   ├── pitch              → env: TTS_PITCH              | default: "+0Hz"
│   ├── output_format      → env: TTS_FORMAT             | default: "mp3"
│   └── generate_subtitles → env: TTS_SUBTITLES          | default: True
│
└── editor (EditorConfig)
    ├── transition_duration → env: EDITOR_TRANSITION_DUR  | default: 1.0
    ├── transition_type     → env: EDITOR_TRANSITION_TYPE | default: "fade"
    ├── ken_burns_enabled   → env: KEN_BURNS_ENABLED      | default: True
    ├── ken_burns_zoom_rate → env: KEN_BURNS_ZOOM_RATE    | default: 0.0015
    ├── video_codec         → env: VIDEO_CODEC            | default: "auto"
    ├── audio_codec         → env: AUDIO_CODEC            | default: "aac"
    └── audio_bitrate       → env: AUDIO_BITRATE          | default: "192k"
```

**Node.js Backend Configuration** (from root `.env`):

| Variable | Default | Description |
|---|---|---|
| `PORT` | `5000` | Express server listen port |
| `FLASK_PORT` | `5001` | Python AI service port |
| `DB_HOST` | `localhost` | MySQL host |
| `DB_PORT` | `3306` | MySQL port |
| `DB_USER` | `root` | MySQL username |
| `DB_PASSWORD` | (empty) | MySQL password |
| `DB_NAME` | `historyclip` | MySQL database name |
| `JWT_SECRET` | (required) | Secret for JWT signing |
| `AI_SERVICE_SECRET` | (required) | Shared secret for Node ↔ Python auth |
| `GOOGLE_VISION_API_KEY` | (optional) | Enables Tier 1 landmark detection |
| `GEMINI_API_KEY` | (required) | Powers script generation + Tier 3.5 VLM |
| `CORS_ORIGIN` | `http://localhost:5173` | Allowed frontend origins (comma-separated) |
| `CORS_ORIGINS` | `http://localhost:5000` | Allowed origins for Python AI service |

---

> **End of HistoriClip Technical Architecture Manual v3.0**
>
> Every diagram, function description, and data flow in this document has been verified against the actual source code. All corrections from the original documentation have been applied:
>
> - FAISS index type: **`IndexFlatIP`** (not `IndexFlatL2`)
> - Auth header: **`X-AI-Service-Secret`** (not `x-service-auth`)
> - Progress reporting: **POST callbacks** (not SSE streaming)
> - Backend response: **immediately returns 200**, frontend polls (not SSE)
> - `_identify_landmark_vlm` uses **Gemini** (not an unspecified VLM)
> - Scene count formula: **`max(3, int(duration/10))`** (auto-scaled)
> - Word count: **from `config.information.words_per_minute`** (not hardcoded 130 WPM)
> - LightGlue: **iterates top-5 FAISS matches** and promotes best geometric match (not just #1)
> - `visualize_matches` generates a **3-panel** image (not 2-panel)
