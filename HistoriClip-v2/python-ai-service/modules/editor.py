"""
HistoriClip - Video Editor Module (v3.0)
==========================================
FFmpeg-based video assembly with hardware acceleration.

  - NVENC (h264_nvenc) with auto-fallback to libx264
  - Ken Burns zoom effect on static images
  - Audio-synced image timing with xfade transitions
  - Uses imageio-ffmpeg for bundled ffmpeg binary

Author: HistoriClip Team (Final Year Project)
"""

import os
import re
import subprocess
import logging
import uuid
from pathlib import Path
from typing import List

import imageio_ffmpeg

from .config import LocationEngineConfig, load_config_from_env

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VideoEditor:
    """FFmpeg video assembler. app.py calls create_video(image_paths, audio_path) → video path."""

    def __init__(self, config: LocationEngineConfig = None):
        """Load config, detect ffmpeg binary and NVENC capability."""
        self._config = config if config is not None else load_config_from_env()
        self._cfg = self._config.editor
        self._cfg.output_dir.mkdir(parents=True, exist_ok=True)

        self._ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        self._has_nvenc = self._detect_nvenc()

    # ─────────────────────────────────────────────────────────
    # FFmpeg Capability Detection
    # ─────────────────────────────────────────────────────────

    def _detect_nvenc(self) -> bool:
        """Check if h264_nvenc hardware encoder is available."""
        try:
            result = subprocess.run(
                [self._ffmpeg, "-encoders"], capture_output=True, text=True)
            found = "h264_nvenc" in result.stdout
            logger.info(f"[Editor] NVENC: {'available' if found else 'not found (using libx264)'}")
            return found
        except Exception as e:
            logger.warning(f"[Editor] NVENC probe failed: {e}")
            return False

    def _get_audio_duration(self, audio_path: str) -> float:
        """Get audio duration in seconds via ffmpeg -i stderr parsing."""
        try:
            result = subprocess.run(
                [self._ffmpeg, "-i", audio_path], capture_output=True, text=True)
            match = re.search(r"Duration: (\d{2}):(\d{2}):(\d{2}\.\d+)", result.stderr)
            if match:
                h, m, s = map(float, match.groups())
                return h * 3600 + m * 60 + s
        except Exception as e:
            logger.error(f"[Editor] Audio duration probe failed: {e}")
        return 0.0

    # ─────────────────────────────────────────────────────────
    # Video Assembly
    # ─────────────────────────────────────────────────────────

    def create_video(self, image_paths: List[str], audio_path: str,
                     output_filename: str = None) -> str:
        """Assemble video from images + audio. Returns absolute path to .mp4."""
        if not image_paths:
            raise ValueError("[Editor] No images provided.")
        if not audio_path or not os.path.exists(audio_path):
            raise ValueError(f"[Editor] Audio not found: {audio_path}")

        # Output path
        if output_filename:
            out_path = str(self._cfg.output_dir / output_filename)
        else:
            out_path = str(self._cfg.output_dir / f"video_{uuid.uuid4().hex[:8]}.mp4")

        # Timing: sync images to audio duration
        audio_duration = self._get_audio_duration(audio_path)
        if audio_duration <= 0:
            logger.warning("[Editor] Audio duration unknown, defaulting to 10s.")
            audio_duration = 10.0

        n = len(image_paths)
        tr_dur = self._cfg.transition_duration
        slide_dur = max((audio_duration + (n - 1) * tr_dur) / n, tr_dur + 0.1)

        logger.info(f"[Editor] {n} images, {audio_duration:.1f}s audio, {slide_dur:.2f}s/slide")

        # Resolution from config (no hardcoded fallback)
        width, height = self._config.visual.resolution_laptop

        # Build ffmpeg command
        cmd = [self._ffmpeg]
        for img in image_paths:
            cmd.extend(["-loop", "1", "-t", str(slide_dur), "-i", img])
        cmd.extend(["-i", audio_path])

        # Filter complex: scale + Ken Burns zoom + xfade transitions
        filters = []
        stream_names = []
        zoom_rate = self._cfg.ken_burns_zoom_rate if self._cfg.ken_burns_enabled else 0

        for i in range(n):
            zoom_expr = f"min(zoom+{zoom_rate},1.5)"
            f = (
                f"[{i}:v]"
                f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
                f"setsar=1,format=yuv420p,"
                f"zoompan=z='{zoom_expr}':d={int(slide_dur * 25 * 2)}:s={width}x{height}"
                f"[v{i}]"
            )
            filters.append(f)
            stream_names.append(f"[v{i}]")

        # Daisy-chain xfade transitions
        curr = stream_names[0]
        for i in range(1, n):
            out = f"[f{i}]"
            offset = i * (slide_dur - tr_dur)
            filters.append(
                f"{curr}{stream_names[i]}"
                f"xfade=transition={self._cfg.transition_type}:"
                f"duration={tr_dur}:offset={offset}{out}"
            )
            curr = out

        cmd.extend(["-filter_complex", ";".join(filters)])
        cmd.extend(["-map", curr, "-map", f"{n}:a"])

        # Encoding: NVENC or libx264
        if self._cfg.video_codec == "auto" and self._has_nvenc:
            cmd.extend(["-c:v", "h264_nvenc", "-preset", "p1", "-cq", "20"])
        else:
            cmd.extend(["-c:v", "libx264", "-preset", "ultrafast", "-crf", "23"])

        cmd.extend(["-c:a", self._cfg.audio_codec, "-b:a", self._cfg.audio_bitrate])
        cmd.extend(["-shortest", "-y", out_path])

        # Execute
        logger.info("[Editor] Running FFmpeg...")
        try:
            subprocess.run(cmd, check=True, text=True, capture_output=True)
            logger.info(f"[Editor] ✅ Video: {out_path}")
            return out_path
        except subprocess.CalledProcessError as e:
            logger.error(f"[Editor] FFmpeg failed: {e.stderr}")
            raise RuntimeError(f"FFmpeg encoding failed: {e.stderr}")


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    print("=" * 60)
    print("HistoriClip - Video Editor v3.0")
    print("FFmpeg + NVENC + Ken Burns")
    print("=" * 60)

    if len(sys.argv) < 3:
        print("\nUsage: python -m modules.editor <audio.mp3> <img1.jpg> <img2.jpg> ...")
        sys.exit(0)

    ed = VideoEditor()
    vid = ed.create_video(sys.argv[2:], sys.argv[1])
    print(f"\n✅ {vid}")
