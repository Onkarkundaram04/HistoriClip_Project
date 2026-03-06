"""
HistoriClip - Audio Module (v3.0)
===================================
Text-to-Speech narration using Microsoft Edge Neural TTS (edge-tts).

  1. Preprocess script (strip markdown, normalize punctuation)
  2. Synthesize speech via edge-tts (async, with prosody config)
  3. Generate SRT subtitles alongside audio (optional)

Author: HistoriClip Team (Final Year Project)
"""

import os
import re
import asyncio
import logging
import uuid
from pathlib import Path
from typing import Optional

from .config import LocationEngineConfig, load_config_from_env

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Script Preprocessing
# ─────────────────────────────────────────────────────────────

def _preprocess_script(text: str) -> str:
    """Clean and normalize script text for natural TTS delivery."""
    if not text or not text.strip():
        return ""

    t = text.strip()

    # Strip markdown
    t = re.sub(r'^#{1,6}\s+', '', t, flags=re.MULTILINE)
    t = t.replace("**", "").replace("__", "")
    t = re.sub(r'(?<!\w)\*(?!\s)', '', t)
    t = re.sub(r'(?<!\s)\*(?!\w)', '', t)
    t = re.sub(r'`([^`]+)`', r'\1', t)
    t = re.sub(r'^\s*[-*•]\s+', '', t, flags=re.MULTILINE)
    t = re.sub(r'^\s*\d+\.\s+', '', t, flags=re.MULTILINE)
    t = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', t)

    # Smart quotes → straight quotes
    t = t.replace('\u201c', '"').replace('\u201d', '"')
    t = t.replace('\u2018', "'").replace('\u2019', "'")

    # Abbreviations for natural reading
    for abbr, expansion in {
        'B.C.': 'B C', 'A.D.': 'A D', 'B.C.E.': 'B C E', 'C.E.': 'C E',
        'e.g.': 'for example', 'i.e.': 'that is', 'etc.': 'etcetera',
        'vs.': 'versus', 'approx.': 'approximately', 'govt.': 'government',
    }.items():
        t = t.replace(abbr, expansion)

    # Normalize whitespace and line breaks
    t = re.sub(r'[ \t]+', ' ', t)
    t = re.sub(r'\n\s*\n', '. ', t)          # paragraph break → pause
    t = re.sub(r'\n', ' ', t)                 # single newline → space

    # Normalize punctuation
    t = re.sub(r'\.{2,}', '.', t)
    t = t.replace('—', ', ').replace('–', ', ')
    t = re.sub(r',\s*,', ',', t)
    t = re.sub(r'\s+([.,;:!?])', r'\1', t)
    t = re.sub(r'([.,;:!?])([A-Za-z])', r'\1 \2', t)
    t = re.sub(r'\.\s*\.', '.', t)
    t = re.sub(r'\s+', ' ', t).strip()

    if t and t[-1] not in '.!?':
        t += '.'
    return t


# ─────────────────────────────────────────────────────────────
# AudioGenerator — Public API (used by app.py)
# ─────────────────────────────────────────────────────────────

class AudioGenerator:
    """Edge-tts narration generator. app.py calls generate(script, speed) → audio path."""

    def __init__(self, config: LocationEngineConfig = None):
        """Load config. All settings from AudioConfig."""
        self._config = config if config is not None else load_config_from_env()
        self._cfg = self._config.audio
        self._cfg.output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"[Audio] Ready — Voice: {self._cfg.voice}, "
                    f"Rate: {self._cfg.rate}, Pitch: {self._cfg.pitch}")

    # ─────────────────────────────────────────────────────────
    # Speech Generation
    # ─────────────────────────────────────────────────────────

    def generate(self, script: str, output_path: str = None,
                 speed: str = 'normal') -> str:
        """
        Convert script to speech audio file. Returns absolute path to .mp3.
        speed: 'normal' (uses config rate) or 'fast' (+50%).
        """
        if not script or not script.strip():
            raise ValueError("[Audio] Cannot generate audio from empty script.")

        # Preprocess
        clean_text = _preprocess_script(script)
        logger.info(f"[Audio] Preprocessed: {len(clean_text.split())} words")

        # Output path
        if output_path is None:
            filename = f"narration_{uuid.uuid4().hex[:8]}.{self._cfg.output_format}"
            output_path = str(self._cfg.output_dir / filename)

        srt_path = os.path.splitext(output_path)[0] + ".srt" if self._cfg.generate_subtitles else None

        # Rate: config default or fast override
        rate = "+50%" if speed == 'fast' else self._cfg.rate

        logger.info(f"[Audio] Generating — Voice: {self._cfg.voice}, Rate: {rate}")
        self._run_tts(clean_text, output_path, rate, srt_path)

        # Verify
        if not os.path.exists(output_path):
            raise RuntimeError(f"[Audio] TTS failed — no output: {output_path}")
        if os.path.getsize(output_path) == 0:
            os.remove(output_path)
            raise RuntimeError("[Audio] TTS produced empty audio file.")

        logger.info(f"[Audio] ✅ {output_path} ({os.path.getsize(output_path) / 1024:.1f} KB)")
        if srt_path and os.path.exists(srt_path):
            logger.info(f"[Audio] ✅ Subtitles: {srt_path}")

        return output_path

    # ─────────────────────────────────────────────────────────
    # Edge-TTS Async Bridge
    # ─────────────────────────────────────────────────────────

    def _run_tts(self, text: str, audio_path: str, rate: str,
                 srt_path: str = None) -> None:
        """Execute edge-tts synthesis with async-to-sync bridging for Flask."""
        async def _synth():
            import edge_tts

            communicate = edge_tts.Communicate(
                text=text, voice=self._cfg.voice,
                rate=rate, volume=self._cfg.volume, pitch=self._cfg.pitch,
            )

            submaker = edge_tts.SubMaker() if srt_path else None

            with open(audio_path, "wb") as f:
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        f.write(chunk["data"])
                    elif submaker and chunk["type"] in ("WordBoundary", "SentenceBoundary"):
                        submaker.feed(chunk)

            if submaker and srt_path:
                with open(srt_path, "w", encoding="utf-8") as f:
                    f.write(submaker.get_srt())

        # Async-to-sync: handle both fresh and nested event loops
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            try:
                import nest_asyncio
                nest_asyncio.apply()
                loop.run_until_complete(_synth())
            except ImportError:
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    pool.submit(asyncio.run, _synth()).result()
        else:
            asyncio.run(_synth())


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    print("=" * 60)
    print("HistoriClip - Audio Module v3.0")
    print("Microsoft Edge Neural TTS")
    print("=" * 60)

    if len(sys.argv) < 2:
        print('\nUsage:')
        print('  python -m modules.audio "<script text>"')
        print('  python -m modules.audio --file <script.txt>')
        print('  python -m modules.audio --voices [language_code]')
        sys.exit(0)

    gen = AudioGenerator()

    if sys.argv[1] == "--voices":
        async def _list_voices():
            import edge_tts
            return await edge_tts.list_voices()

        lang = sys.argv[2] if len(sys.argv) >= 3 else None
        voices = asyncio.run(_list_voices())
        if lang:
            voices = [v for v in voices if v.get("ShortName", "").lower().startswith(lang.lower())]
        for v in sorted(voices, key=lambda x: x.get("ShortName", "")):
            print(f"  {v['ShortName']:35s}  {v.get('Gender', ''):8s}")
        print(f"\nTotal: {len(voices)} | Current: {gen._cfg.voice}")

    elif sys.argv[1] == "--file":
        if len(sys.argv) < 3 or not os.path.exists(sys.argv[2]):
            print("Error: provide a valid file path."); sys.exit(1)
        with open(sys.argv[2], "r", encoding="utf-8") as f:
            script = f.read()
        print(f"✅ {gen.generate(script)}")

    else:
        print(f"✅ {gen.generate(sys.argv[1])}")
