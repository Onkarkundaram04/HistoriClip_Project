"""
HistoriClip - Location Engine (v3.0)
======================================
Visual geolocation: DINOv2 + GeM Pooling + FAISS + LightGlue

OFFLINE (one-time):
  1. Extract GeM-pooled DINOv2 features from reference images → 768-dim vectors
  2. Store L2-normalized vectors in FAISS IndexFlatIP (= cosine similarity)

ONLINE (per query):
  1. Extract query fingerprint → FAISS top-K retrieval
  2. GPS consensus from spatially-consistent top-K matches
  3. LightGlue geometric verification (optional, XAI proof)

References:
  - DINOv2 (Meta AI, 2023) | AnyLoc (ICRA 2024) | LightGlue (ICCV 2023)
  - GeM Pooling (Radenović et al., TPAMI 2019)

Author: HistoriClip Team (Final Year Project)
"""

import os
import json
import csv
import math
import numpy as np
from pathlib import Path
from typing import Optional, List, Dict
from PIL import Image

from .config import LocationEngineConfig, load_config_from_env


class LocationEngine:
    """
    Visual geolocation engine.

    Usage:
        engine = LocationEngine()
        engine.build_index()                   # one-time
        result = engine.search("photo.jpg")    # query
        engine.visualize_matches("photo.jpg")  # XAI proof
    """

    def __init__(self, config: Optional[LocationEngineConfig] = None):
        """Load config from environment if not provided. All heavy models are lazy-loaded."""
        self.config = config if config is not None else load_config_from_env()
        self._d = self.config.dinov2

        self._model = None
        self._processor = None
        self._index = None
        self._metadata = None
        self._device = None
        self._feature_dim = None
        self._lightglue_matcher = None
        self._lightglue_extractor = None

        print("[LocationEngine] Ready.")

    # ─────────────────────────────────────────────────────────
    # Device & Model Loading
    # ─────────────────────────────────────────────────────────

    def _detect_device(self) -> str:
        """Auto-detect CUDA GPU or fall back to CPU."""
        if self._device is not None:
            return self._device

        import torch

        if self._d.device != "auto":
            self._device = self._d.device
        elif torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            mem = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            print(f"[LocationEngine] GPU: {name} ({mem:.1f} GB)")
            self._device = "cuda"
        else:
            print("[LocationEngine] No GPU, using CPU")
            self._device = "cpu"

        return self._device

    def _load_model(self):
        """Lazy-load DINOv2 + processor from HuggingFace."""
        if self._model is not None:
            return

        import torch
        from transformers import AutoImageProcessor, AutoModel

        device = self._detect_device()
        model_name = self._d.model_name

        print(f"[LocationEngine] Loading {model_name}...")
        self._processor = AutoImageProcessor.from_pretrained(model_name)
        self._model = AutoModel.from_pretrained(model_name).to(device).eval()
        self._feature_dim = self._model.config.hidden_size

        pooling = "GeM (AnyLoc)" if self._d.pooling_method == "gem" else "CLS"
        print(f"[LocationEngine] Loaded! dim={self._feature_dim}, pooling={pooling}")

    # ─────────────────────────────────────────────────────────
    # Feature Extraction (GeM Pooling)
    # ─────────────────────────────────────────────────────────

    @staticmethod
    def gem_pool(features: 'torch.Tensor', power: float = 3.0) -> 'torch.Tensor':
        """GeM(x) = (mean(x^p))^(1/p). p=1→avg, p=3→AnyLoc default, p→∞→max."""
        import torch
        features = features.clamp(min=1e-6)
        return features.pow(power).mean(dim=1).pow(1.0 / power)

    def extract_features(self, image_path: str) -> np.ndarray:
        """Extract a single L2-normalized 768-dim fingerprint from an image."""
        import torch

        self._load_model()

        image = Image.open(image_path).convert("RGB")
        inputs = self._processor(images=image, return_tensors="pt")
        inputs = {k: v.to(self._device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self._model(**inputs)
            if self._d.pooling_method == "gem":
                features = self.gem_pool(outputs.last_hidden_state[:, 1:, :], self._d.gem_power)
            else:
                features = outputs.last_hidden_state[:, 0, :]

        features = features.cpu().numpy().flatten()
        return features / np.linalg.norm(features)

    def extract_features_batch(self, image_paths: List[str]) -> np.ndarray:
        """Extract L2-normalized features from multiple images in batches."""
        import torch

        self._load_model()

        all_features = []
        total = len(image_paths)

        for i in range(0, total, self._d.batch_size):
            batch_paths = image_paths[i:i + self._d.batch_size]

            images = []
            for path in batch_paths:
                try:
                    images.append(Image.open(path).convert("RGB"))
                except Exception as e:
                    print(f"[LocationEngine] Skip {path}: {e}")

            if not images:
                continue

            inputs = self._processor(images=images, return_tensors="pt")
            inputs = {k: v.to(self._device) for k, v in inputs.items()}

            with torch.no_grad():
                outputs = self._model(**inputs)
                if self._d.pooling_method == "gem":
                    features = self.gem_pool(outputs.last_hidden_state[:, 1:, :], self._d.gem_power)
                else:
                    features = outputs.last_hidden_state[:, 0, :]

            all_features.append(features.cpu().numpy())
            done = min(i + self._d.batch_size, total)
            print(f"[LocationEngine] {done}/{total} images ({done*100//total}%)")

        if all_features:
            features = np.vstack(all_features)
            return features / np.linalg.norm(features, axis=1, keepdims=True)
        return np.array([])

    # ─────────────────────────────────────────────────────────
    # FAISS Index: Build / Save / Load
    # ─────────────────────────────────────────────────────────

    def build_index(self, images_folder: str = None, locations_csv: str = None):
        """Build FAISS index from reference images listed in locations.csv."""
        import faiss

        images_folder = images_folder or str(self.config.images_dir)
        locations_csv = locations_csv or str(self.config.locations_csv)

        print(f"\n{'='*60}")
        print(f"Building Location Index")
        print(f"  Images:  {images_folder}")
        print(f"  CSV:     {locations_csv}")
        print(f"  Pooling: {self._d.pooling_method.upper()}")
        print(f"{'='*60}\n")

        image_paths, metadata = [], []
        with open(locations_csv, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                img_path = os.path.join(images_folder, row['filename'])
                if os.path.exists(img_path):
                    image_paths.append(img_path)
                    metadata.append({
                        'filename': row['filename'],
                        'lat': float(row['lat']),
                        'lon': float(row['lon']),
                        'name': row.get('name', 'Unknown'),
                        'source': row.get('source', 'unknown')
                    })

        print(f"[LocationEngine] Found {len(image_paths)} images")
        if not image_paths:
            print("[LocationEngine] ERROR: No images found! Run data_collector.py first.")
            return

        features = self.extract_features_batch(image_paths)
        if features.size == 0:
            print("[LocationEngine] ERROR: Feature extraction failed.")
            return

        self._index = faiss.IndexFlatIP(self._feature_dim)
        self._index.add(features.astype(np.float32))
        self._metadata = metadata
        self._save_index()

        print(f"\n  Index Built! {self._index.ntotal} vectors, dim={self._feature_dim}")
        print(f"  Saved to: {self.config.index_file}\n")

    def _save_index(self):
        """Persist FAISS index + metadata JSON to disk."""
        import faiss
        faiss.write_index(self._index, str(self.config.index_file))
        with open(str(self.config.metadata_file), 'w', encoding='utf-8') as f:
            json.dump(self._metadata, f, indent=2)

    def load_index(self) -> bool:
        """Load a previously built FAISS index from disk. Returns True on success."""
        import faiss

        idx = str(self.config.index_file)
        meta = str(self.config.metadata_file)

        if not os.path.exists(idx) or not os.path.exists(meta):
            print(f"[LocationEngine] No index at {idx}")
            return False

        self._index = faiss.read_index(idx)
        with open(meta, 'r', encoding='utf-8') as f:
            self._metadata = json.load(f)

        self._load_model()
        print(f"[LocationEngine] Loaded: {self._index.ntotal} locations")
        return True

    # ─────────────────────────────────────────────────────────
    # Search: FAISS Retrieval + GPS Consensus
    # ─────────────────────────────────────────────────────────

    def search(self, query_image_path: str) -> Dict:
        """Find the best matching location for a query image. Returns result dict with GPS consensus."""
        if self._index is None and not self.load_index():
            return {'success': False, 'error': 'No index. Run build_index() first.'}
        if self._index.ntotal == 0:
            return {'success': False, 'error': 'Empty index.'}

        print(f"[LocationEngine] Analyzing: {query_image_path}")
        qf = self.extract_features(query_image_path).reshape(1, -1).astype(np.float32)
        scores, indices = self._index.search(qf, self._d.top_k)

        matches = []
        for rank, (score, idx) in enumerate(zip(scores[0], indices[0])):
            if idx < 0:
                continue
            matches.append({
                'rank': rank + 1,
                'similarity': float(score),
                'lat': self._metadata[idx]['lat'],
                'lon': self._metadata[idx]['lon'],
                'name': self._metadata[idx]['name'],
                'filename': self._metadata[idx]['filename']
            })

        best = matches[0] if matches else None
        success = best is not None and best['similarity'] >= self._d.min_confidence

        consensus = self._compute_gps_consensus(matches)

        if success and consensus['num_consistent'] >= 2:
            best['lat'] = consensus['consensus_lat']
            best['lon'] = consensus['consensus_lon']

        result = {
            'success': success,
            'method': f'dinov2_{self._d.pooling_method}_faiss',
            'query_image': query_image_path,
            'best_match': best,
            'matches': matches,
            'gps_consensus': consensus,
            'confidence': best['similarity'] if best else 0,
            'message': 'Location found!' if success else 'No confident match.',
            'verification': None
        }

        # ── LightGlue Top-K Verification Loop ──
        # Loop over the top-5 FAISS matches and geometrically verify each.
        # The match with the most inliers is promoted to best_match,
        # overriding DINOv2's potentially incorrect ranking.
        if success and self._d.use_lightglue and best:
            top_n_verify = min(5, len(matches))
            best_ver = None
            best_ver_idx = 0
            best_ver_inliers = 0

            for i in range(top_n_verify):
                m = matches[i]
                ver = self._verify_with_lightglue(query_image_path, m['filename'])
                if ver:
                    m['inliers'] = ver.get('num_matches', 0)
                    m['verified'] = ver.get('verified', False)
                    if ver.get('num_matches', 0) > best_ver_inliers:
                        best_ver = ver
                        best_ver_idx = i
                        best_ver_inliers = ver['num_matches']
                else:
                    m['inliers'] = 0
                    m['verified'] = False

            if best_ver:
                result['verification'] = best_ver
                result['confidence_geometric'] = best_ver.get('inlier_ratio', 0)

                # If a non-#1 match won geometric verification, promote it
                if best_ver_idx > 0 and best_ver.get('verified', False):
                    promoted = matches[best_ver_idx]
                    print(f"[LocationEngine] LightGlue promoted rank #{best_ver_idx + 1} "
                          f"({promoted['lat']:.4f}, {promoted['lon']:.4f}) "
                          f"over rank #1 with {best_ver_inliers} inliers")
                    best['lat'] = promoted['lat']
                    best['lon'] = promoted['lon']
                    best['filename'] = promoted['filename']
                    best['name'] = promoted['name']
                    result['best_match'] = best

        if success:
            print(f"[LocationEngine] Match: "
                  f"({best['lat']:.4f}, {best['lon']:.4f}) "
                  f"sim={best['similarity']:.3f} "
                  f"spread={consensus['spatial_spread_meters']:.0f}m "
                  f"consensus={consensus['num_consistent']}/{len(matches)}")

        return result

    # ─────────────────────────────────────────────────────────
    # GPS Consensus (Spatial Clustering of Top-K)
    # ─────────────────────────────────────────────────────────

    @staticmethod
    def _haversine_meters(lat1, lon1, lat2, lon2) -> float:
        """Haversine distance in meters between two GPS coordinates."""
        R = 6_371_000
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
        a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def _compute_gps_consensus(self, matches: List[Dict],
                                max_spread_meters: float = 500.0) -> Dict:
        """Median GPS from top-K matches within max_spread_meters of #1. Filters distant outliers."""
        if not matches:
            return {'consensus_lat': 0, 'consensus_lon': 0,
                    'spatial_spread_meters': float('inf'), 'num_consistent': 0}

        best = matches[0]
        blat, blon = best['lat'], best['lon']

        consistent = [m for m in matches
                      if self._haversine_meters(blat, blon, m['lat'], m['lon']) <= max_spread_meters]
        if not consistent:
            consistent = [best]

        med_lat = float(np.median([m['lat'] for m in consistent]))
        med_lon = float(np.median([m['lon'] for m in consistent]))

        spread = 0.0
        for i, m1 in enumerate(consistent):
            for m2 in consistent[i + 1:]:
                spread = max(spread, self._haversine_meters(
                    m1['lat'], m1['lon'], m2['lat'], m2['lon']))

        return {
            'consensus_lat': med_lat,
            'consensus_lon': med_lon,
            'spatial_spread_meters': round(spread, 1),
            'num_consistent': len(consistent)
        }

    # ─────────────────────────────────────────────────────────
    # LightGlue: Geometric Verification
    # ─────────────────────────────────────────────────────────

    def _load_lightglue(self):
        """Lazy-load DISK extractor + LightGlue matcher from kornia."""
        if self._lightglue_matcher is not None:
            return
        try:
            from kornia.feature import DISK, LightGlueMatcher
            device = self._detect_device()
            print("[LocationEngine] Loading LightGlue...")
            self._lightglue_extractor = DISK.from_pretrained("depth").to(device)
            self._lightglue_matcher = LightGlueMatcher("disk").to(device)
            print("[LocationEngine] LightGlue ready!")
        except ImportError:
            print("[LocationEngine] kornia not installed — LightGlue disabled")
            self._d.use_lightglue = False
        except Exception as e:
            print(f"[LocationEngine] LightGlue error: {e}")
            self._d.use_lightglue = False

    def _verify_with_lightglue(self, query_path: str, match_filename: str) -> Optional[Dict]:
        """Run LightGlue keypoint matching between query and FAISS match. Returns match stats."""
        self._load_lightglue()
        if self._lightglue_matcher is None:
            return None

        import torch
        from kornia.utils import image_to_tensor

        match_path = str(self.config.images_dir / match_filename)
        if not os.path.exists(match_path):
            return None

        try:
            device = self._detect_device()
            max_size = self._d.lightglue_max_size

            img_q = Image.open(query_path).convert("RGB")
            img_m = Image.open(match_path).convert("RGB")
            img_q = img_q.resize(self._resize_keep_aspect(img_q.size, max_size))
            img_m = img_m.resize(self._resize_keep_aspect(img_m.size, max_size))

            t_q = image_to_tensor(np.array(img_q)).float().unsqueeze(0).to(device) / 255.0
            t_m = image_to_tensor(np.array(img_m)).float().unsqueeze(0).to(device) / 255.0

            # Pad to nearest multiple of 16 for DISK compatibility
            def _pad_to_multiple(tensor, multiple=16):
                _, _, h, w = tensor.shape
                pad_h = (multiple - h % multiple) % multiple
                pad_w = (multiple - w % multiple) % multiple
                if pad_h or pad_w:
                    tensor = torch.nn.functional.pad(tensor, (0, pad_w, 0, pad_h))
                return tensor

            t_q = _pad_to_multiple(t_q)
            t_m = _pad_to_multiple(t_m)

            with torch.no_grad():
                feat_q = self._lightglue_extractor(t_q)
                feat_m = self._lightglue_extractor(t_m)
                from kornia.feature import laf_from_center_scale_ori
                laf_q = laf_from_center_scale_ori(feat_q[0].keypoints.unsqueeze(0))
                laf_m = laf_from_center_scale_ori(feat_m[0].keypoints.unsqueeze(0))
                mscores, matches = self._lightglue_matcher(
                    feat_q[0].descriptors,
                    feat_m[0].descriptors,
                    laf_q,
                    laf_m
                )

            if matches is not None and len(matches) > 0:
                valid = len(matches)
                total_kp = len(feat_q[0].keypoints)
            else:
                valid, total_kp = 0, 0

            ratio = valid / max(total_kp, 1)
            verified = int(valid) >= self._d.min_matches_verified
            print(f"[LocationEngine] LightGlue: {valid} matches ({'VERIFIED' if verified else 'WEAK'})")

            return {
                'num_matches': int(valid), 'total_keypoints': total_kp,
                'inlier_ratio': round(ratio, 3), 'match_image': match_path,
                'verified': verified
            }
        except Exception as e:
            print(f"[LocationEngine] Verification error: {e}")
            return None

    @staticmethod
    def _resize_keep_aspect(size: tuple, max_dim: int) -> tuple:
        """Resize dimensions to fit within max_dim while preserving aspect ratio."""
        w, h = size
        scale = max_dim / max(w, h)
        return size if scale >= 1.0 else (int(w * scale), int(h * scale))

    # ─────────────────────────────────────────────────────────
    # XAI Visualizations
    # ─────────────────────────────────────────────────────────

    def visualize_matches(self, query_image_path: str,
                          match_filename: str = None,
                          output_path: str = None) -> Optional[str]:
        """Generate a 3-panel side-by-side keypoint match visualization (LightGlue XAI)."""
        self._load_lightglue()
        if self._lightglue_matcher is None:
            return self.visualize_attention(query_image_path, output_path)

        import torch
        from kornia.utils import image_to_tensor

        device = self._detect_device()
        max_size = self._d.lightglue_max_size

        if match_filename is None:
            res = self.search(query_image_path)
            if not res.get('success') or not res.get('best_match'):
                return None
            match_filename = res['best_match']['filename']

        match_path = str(self.config.images_dir / match_filename)
        if not os.path.exists(match_path):
            return None

        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt

            img_q = Image.open(query_image_path).convert("RGB")
            img_m = Image.open(match_path).convert("RGB")
            img_q = img_q.resize(self._resize_keep_aspect(img_q.size, max_size))
            img_m = img_m.resize(self._resize_keep_aspect(img_m.size, max_size))

            t_q = image_to_tensor(np.array(img_q)).float().unsqueeze(0).to(device) / 255.0
            t_m = image_to_tensor(np.array(img_m)).float().unsqueeze(0).to(device) / 255.0

            # Pad to nearest multiple of 16 for DISK compatibility
            def _pad_to_multiple(tensor, multiple=16):
                _, _, h, w = tensor.shape
                pad_h = (multiple - h % multiple) % multiple
                pad_w = (multiple - w % multiple) % multiple
                if pad_h or pad_w:
                    tensor = torch.nn.functional.pad(tensor, (0, pad_w, 0, pad_h))
                return tensor

            t_q = _pad_to_multiple(t_q)
            t_m = _pad_to_multiple(t_m)

            with torch.no_grad():
                fq = self._lightglue_extractor(t_q)
                fm = self._lightglue_extractor(t_m)
                from kornia.feature import laf_from_center_scale_ori
                laf_q = laf_from_center_scale_ori(fq[0].keypoints.unsqueeze(0))
                laf_m = laf_from_center_scale_ori(fm[0].keypoints.unsqueeze(0))
                mscores, matches = self._lightglue_matcher(
                    fq[0].descriptors,
                    fm[0].descriptors,
                    laf_q,
                    laf_m
                )

            kp_q = fq[0].keypoints.cpu().numpy()
            kp_m = fm[0].keypoints.cpu().numpy()
            matched_q, matched_m = [], []

            if matches is not None and len(matches) > 0:
                for idxs in matches.cpu().numpy():
                    matched_q.append(kp_q[idxs[0]])
                    matched_m.append(kp_m[idxs[1]])

            matched_q = np.array(matched_q) if matched_q else np.array([])
            matched_m = np.array(matched_m) if matched_m else np.array([])

            fig, axes = plt.subplots(1, 3, figsize=(20, 7))
            axes[0].imshow(img_q); axes[0].set_title("Your Photo", fontsize=14, fontweight='bold'); axes[0].axis("off")
            axes[1].imshow(img_m); axes[1].set_title("Database Match", fontsize=14, fontweight='bold'); axes[1].axis("off")

            w_q = img_q.size[0]
            combined = Image.new('RGB', (w_q + img_m.size[0], max(img_q.size[1], img_m.size[1])))
            combined.paste(img_q, (0, 0)); combined.paste(img_m, (w_q, 0))
            axes[2].imshow(combined)

            n_draw = min(len(matched_q), self._d.max_viz_matches)
            if n_draw > 0:
                idx = np.linspace(0, len(matched_q) - 1, n_draw, dtype=int)
                for i in idx:
                    x1, y1 = matched_q[i]; x2, y2 = matched_m[i]
                    axes[2].plot([x1, x2+w_q], [y1, y2], color='lime', lw=0.8, alpha=0.7)
                    axes[2].plot(x1, y1, 'o', color='lime', ms=3)
                    axes[2].plot(x2+w_q, y2, 'o', color='lime', ms=3)

            axes[2].set_title(f"Keypoint Matches ({len(matched_q)} verified)", fontsize=14, fontweight='bold')
            axes[2].axis("off")
            plt.suptitle("HistoriClip — LightGlue Geometric Verification", fontsize=16, fontweight='bold', y=0.98)
            plt.tight_layout()

            if output_path is None:
                output_path = os.path.splitext(query_image_path)[0] + "_matches.jpg"
            plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor='white')
            plt.close()
            print(f"[LocationEngine] Saved: {output_path}")
            return output_path
        except Exception as e:
            print(f"[LocationEngine] Visualization error: {e}")
            return None

    def get_attention_map(self, image_path: str) -> np.ndarray:
        """Extract DINOv2 CLS attention map as a normalized 2D heatmap."""
        import torch
        self._load_model()

        image = Image.open(image_path).convert("RGB")
        inputs = self._processor(images=image, return_tensors="pt")
        inputs = {k: v.to(self._device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self._model(**inputs, output_attentions=True)
            att = outputs.attentions[-1].mean(dim=1)
            cls_att = att[0, 0, 1:]

        n = int(cls_att.shape[0] ** 0.5)
        att_map = cls_att.reshape(n, n).cpu().numpy()
        return (att_map - att_map.min()) / (att_map.max() - att_map.min() + 1e-8)

    def visualize_attention(self, image_path: str, output_path: str = None) -> str:
        """Generate a 3-panel attention heatmap visualization (fallback XAI)."""
        import matplotlib; matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        att_map = self.get_attention_map(image_path)
        original = Image.open(image_path).convert("RGB")
        att_pil = Image.fromarray((att_map * 255).astype(np.uint8))
        att_resized = np.array(att_pil.resize(original.size, Image.BILINEAR))

        fig, axes = plt.subplots(1, 3, figsize=(15, 5))
        axes[0].imshow(original); axes[0].set_title("Original"); axes[0].axis("off")
        axes[1].imshow(att_resized, cmap="hot"); axes[1].set_title("Attention Map"); axes[1].axis("off")
        axes[2].imshow(original); axes[2].imshow(att_resized, cmap="hot", alpha=0.5)
        axes[2].set_title("Overlay (XAI)"); axes[2].axis("off")
        plt.tight_layout()

        if output_path is None:
            base, ext = os.path.splitext(image_path)
            output_path = f"{base}_attention{ext}"
        plt.savefig(output_path, dpi=150, bbox_inches="tight"); plt.close()
        print(f"[LocationEngine] Saved: {output_path}")
        return output_path


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────

def main():
    import sys

    print("=" * 60)
    print("HistoriClip Location Engine v3.0")
    print("DINOv2 + GeM + FAISS + LightGlue")
    print("=" * 60)

    if len(sys.argv) < 2:
        print("\nCommands:")
        print("  build              Build index from downloaded images")
        print("  search <image>     Find location of an image")
        print("  match <image>      LightGlue keypoint visualization")
        print("  attention <image>  Attention heatmap")
        print("  info               Show index statistics")
        return

    cmd = sys.argv[1].lower()
    engine = LocationEngine()

    if cmd == "build":
        engine.build_index()
    elif cmd == "search" and len(sys.argv) >= 3:
        if not os.path.exists(sys.argv[2]):
            print(f"Not found: {sys.argv[2]}"); return
        print(json.dumps(engine.search(sys.argv[2]), indent=2, default=str))
    elif cmd == "match" and len(sys.argv) >= 3:
        if not os.path.exists(sys.argv[2]):
            print(f"Not found: {sys.argv[2]}"); return
        out = engine.visualize_matches(sys.argv[2])
        print(f"Done! → {out}" if out else "Failed.")
    elif cmd == "attention" and len(sys.argv) >= 3:
        if not os.path.exists(sys.argv[2]):
            print(f"Not found: {sys.argv[2]}"); return
        print(f"Done! → {engine.visualize_attention(sys.argv[2])}")
    elif cmd == "info":
        if engine.load_index():
            print(f"  Locations: {engine._index.ntotal}")
            print(f"  Dim:       {engine._feature_dim}")
            print(f"  Pooling:   {engine._d.pooling_method.upper()}")
            print(f"  LightGlue: {engine._d.use_lightglue}")
        else:
            print("No index. Run 'build' first.")
    else:
        print(f"Unknown: {cmd}")


if __name__ == "__main__":
    main()
