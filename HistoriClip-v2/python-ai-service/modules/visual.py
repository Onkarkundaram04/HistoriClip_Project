"""
HistoriClip - Visual Module (v3.0)
====================================
Image generation using SDXL Lightning 8-Step + TinyVAE.

  Model:     SDXL Lightning 8-Step (.safetensors)
  VAE:       TinyVAE (madebyollin/taesdxl, 10MB)
  Scheduler: EulerDiscrete, trailing spacing
  Memory:    CPU offload + xformers (6GB VRAM)

Author: HistoriClip Team (Final Year Project)
"""

import time
import logging
from pathlib import Path
from typing import List

from .config import LocationEngineConfig, load_config_from_env

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_BASE_DIR = Path(__file__).resolve().parent.parent
_MODEL_PATH = str(_BASE_DIR / "models" / "sdxlLightning_8Steps.safetensors")
_TINY_VAE_ID = "madebyollin/taesdxl"
_OUTPUT_DIR = _BASE_DIR.parent / "backend" / "uploads" / "generated_images"


class ImageGenerator:
    """SDXL Lightning image generator. app.py calls generate(prompts) → list of paths."""

    def __init__(self, config: LocationEngineConfig = None):
        """Load config. Pipeline is lazy-loaded on first generate() call."""
        self._config = config if config is not None else load_config_from_env()
        self._visual_cfg = self._config.visual
        self._pipe = None
        self._img2img_pipe = None
        self._vae = None
        self._loaded = False

    # ─────────────────────────────────────────────────────────
    # Pipeline Loading
    # ─────────────────────────────────────────────────────────

    def _load_pipeline(self):
        """Load SDXL Lightning + TinyVAE + EulerDiscrete scheduler. Only runs once."""
        if self._loaded:
            return

        import torch
        from diffusers import (
            StableDiffusionXLPipeline, StableDiffusionXLImg2ImgPipeline,
            EulerDiscreteScheduler, AutoencoderTiny
        )

        logger.info("[Visual] Loading SDXL Lightning pipeline...")
        load_start = time.time()

        # TinyVAE (10MB, critical speedup for 6GB VRAM)
        try:
            self._vae = AutoencoderTiny.from_pretrained(_TINY_VAE_ID, torch_dtype=torch.float16)
            logger.info("[Visual] ✅ TinyVAE loaded")
        except Exception as e:
            logger.warning(f"[Visual] TinyVAE failed ({e}), falling back to standard VAE")
            self._vae = None

        # SDXL Lightning txt2img
        load_args = dict(torch_dtype=torch.float16, variant="fp16")
        if self._vae:
            load_args['vae'] = self._vae
        self._pipe = StableDiffusionXLPipeline.from_single_file(_MODEL_PATH, **load_args)

        # Img2img shares same components (zero extra memory)
        self._img2img_pipe = StableDiffusionXLImg2ImgPipeline(**self._pipe.components)

        # CPU offload (critical for 6GB VRAM)
        self._pipe.enable_model_cpu_offload()

        # Scheduler: EulerDiscrete + trailing spacing (required for Lightning)
        self._pipe.scheduler = EulerDiscreteScheduler.from_config(
            self._pipe.scheduler.config, timestep_spacing="trailing"
        )

        # Memory optimizations
        try:
            self._pipe.enable_xformers_memory_efficient_attention()
            logger.info("[Visual] ✅ xformers enabled")
        except Exception:
            logger.info("[Visual] xformers not available")

        if not self._vae:
            self._pipe.enable_vae_slicing()
            self._pipe.enable_vae_tiling()

        self._loaded = True
        logger.info(f"[Visual] ✅ Pipeline ready ({time.time() - load_start:.1f}s)")

    # ─────────────────────────────────────────────────────────
    # Image Generation
    # ─────────────────────────────────────────────────────────

    def generate(self, prompts: List[str], input_image=None,
                 strength: float = 0.75) -> List[str]:
        """Generate images from prompts. Uses img2img if input_image is provided, else txt2img."""
        if not prompts:
            logger.warning("[Visual] No prompts provided.")
            return []

        self._load_pipeline()
        if not self._pipe:
            logger.error("[Visual] Pipeline failed to load.")
            return []

        import torch
        from PIL import Image

        output_dir = Path(_OUTPUT_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)

        width, height = self._visual_cfg.resolution_laptop
        steps = self._visual_cfg.default_steps
        guidance = self._visual_cfg.default_guidance

        logger.info(f"[Visual] Generating {len(prompts)} images at {width}x{height}")

        if input_image:
            input_image = input_image.convert("RGB").resize(
                (width, height), Image.Resampling.LANCZOS)

        paths = []
        for i, prompt in enumerate(prompts, 1):
            logger.info(f"[Visual] [{i}/{len(prompts)}] {prompt[:60]}...")
            gen_start = time.time()

            with torch.inference_mode():
                if input_image:
                    image = self._img2img_pipe(
                        prompt=prompt, image=input_image, strength=strength,
                        num_inference_steps=steps, guidance_scale=guidance,
                    ).images[0]
                else:
                    image = self._pipe(
                        prompt=prompt, num_inference_steps=steps,
                        guidance_scale=guidance, width=width, height=height
                    ).images[0]

            filename = f"gen_{int(time.time())}_{i}.png"
            out_path = output_dir / filename
            image.save(out_path)

            logger.info(f"[Visual] ✅ {filename} ({time.time() - gen_start:.1f}s)")
            paths.append(str(out_path))

        return paths


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    print("=" * 60)
    print("HistoriClip - Visual Module v3.0")
    print("SDXL Lightning 8-Step + TinyVAE")
    print("=" * 60)

    if len(sys.argv) < 2:
        print('\nUsage: python -m modules.visual "<prompt>"')
        sys.exit(0)

    gen = ImageGenerator()
    paths = gen.generate([sys.argv[1]])
    print(f"\n✅ {paths[0]}" if paths else "\n❌ Failed.")
