"""CLIP embeddings for tiles, text queries and uploaded images.

Hillshade tiles are embedded as the mean over four 90-degree rotations, so the
vector describes terrain *shape* rather than which direction the sun came from
(LOLA and ASTER hillshades are lit from different azimuths).
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import torch
from PIL import Image

from . import config as C

DEVICE = "mps" if torch.backends.mps.is_available() else (
    "cuda" if torch.cuda.is_available() else "cpu")

PROMPTS = [
    "a satellite image of {}",
    "an aerial view of {}",
    "a grayscale orbital photograph of {}",
    "a shaded relief map of {}",
]


@lru_cache(maxsize=1)
def load_model():
    import open_clip
    model, _, preprocess = open_clip.create_model_and_transforms(
        C.CLIP_ARCH, pretrained=C.CLIP_WEIGHTS, device=DEVICE)
    model.eval()
    return model, preprocess, open_clip.get_tokenizer(C.CLIP_ARCH)


def _norm(x: torch.Tensor) -> torch.Tensor:
    return x / x.norm(dim=-1, keepdim=True)


@torch.no_grad()
def embed_images(images: list[Image.Image], rotations: bool = False) -> np.ndarray:
    model, pre, _ = load_model()
    views = [0, 90, 180, 270] if rotations else [0]
    out = 0
    for angle in views:
        batch = torch.stack([pre(im.convert("RGB").rotate(angle)) for im in images]).to(DEVICE)
        out = out + _norm(model.encode_image(batch).float())
    return _norm(out).cpu().numpy().astype(np.float32)


@torch.no_grad()
def embed_text(query: str) -> np.ndarray:
    """Prompt-ensembled text embedding (averaging several phrasings is more
    robust than a single prompt)."""
    model, _, tok = load_model()
    t = tok([p.format(query) for p in PROMPTS]).to(DEVICE)
    e = _norm(model.encode_text(t).float()).mean(0, keepdim=True)
    return _norm(e).cpu().numpy()[0].astype(np.float32)
