"""
Vectra: Multi-Modal Embedding Module.

Uses CLIP ViT-B/32 to generate 512-dimensional embeddings for:
  - Images (PIL Image or file path)
  - Text strings
  - Combined image + text (multi-modal query)

Why CLIP for multi-modal fusion?
  CLIP is trained with contrastive loss to align image and text representations
  in a SHARED embedding space. This means the vector for an image of a red shoe
  and the text "red shoe" are geometrically close. Linear interpolation between
  an image embedding and a text modifier embedding is therefore a principled
  operation: we navigate the shared space toward the region that matches both.

  This is distinct from "late fusion" (where modalities are encoded and fused
  AFTER the retrieval step) or cross-attention reranking (where both modalities
  are processed jointly at inference time). Linear fusion is chosen here for
  speed — it adds zero inference cost at query time.
"""

import os
import logging
import numpy as np
from PIL import Image
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

logger = logging.getLogger("vectra.embedder")

load_dotenv()

# Model is loaded once at module import time.
# SentenceTransformer wraps CLIP so both image and text share the same .encode() API.
_MODEL_NAME = os.getenv("CLIP_MODEL", "clip-ViT-B-32")
_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        logger.info("Loading CLIP model: %s", _MODEL_NAME)
        _model = SentenceTransformer(_MODEL_NAME)
        logger.info("Model loaded.")
    return _model


def embed_image(image: Image.Image) -> np.ndarray:
    """
    Encode a PIL Image into a 512-dim L2-normalised vector.
    CLIP images are always normalised by the model internally.
    """
    model = _get_model()
    embedding = model.encode(image, convert_to_numpy=True)
    norm = np.linalg.norm(embedding)
    if norm == 0:
        raise ValueError("Zero-norm image embedding — check input image")
    return embedding / norm


def embed_text(text: str) -> np.ndarray:
    """
    Encode a text string into a 512-dim L2-normalised vector.
    The vector lives in the same space as image embeddings.
    """
    model = _get_model()
    embedding = model.encode(text, convert_to_numpy=True)
    norm = np.linalg.norm(embedding)
    if norm == 0:
        raise ValueError("Zero-norm text embedding — check input text")
    return embedding / norm


def embed_multimodal(
    image: Image.Image,
    text_modifier: str | None = None,
    text_weight: float = 0.3,
) -> np.ndarray:
    """
    Produce a combined query vector from an image and an optional text modifier.

    Formula:
        query = normalize(image_emb + text_weight * text_emb)

    Why 0.3 as default weight?
        The user's intent is primarily visual — they are uploading an image.
        The text modifier refines, not overrides, the query. A weight of 0.3
        means the text contributes ~23% of the final vector direction,
        which empirically keeps the image intent dominant while allowing
        meaningful textual refinement (e.g., "but in black").

        This weight is a hyperparameter exposed in .env and tunable via A/B
        testing against nDCG@10 on the evaluation dataset.

    Args:
        image: PIL Image from user upload
        text_modifier: Optional text refinement, e.g. "but in black"
        text_weight: How strongly to blend the text embedding (0.0–1.0)

    Returns:
        L2-normalised 512-dim numpy array
    """
    image_emb = embed_image(image)

    if text_modifier and text_modifier.strip():
        text_emb = embed_text(text_modifier)
        combined = image_emb + text_weight * text_emb
    else:
        combined = image_emb

    # L2 normalise so cosine similarity = dot product in pgvector
    norm = np.linalg.norm(combined)
    if norm == 0:
        raise ValueError("Zero-norm combined embedding — check input image or text")
    return combined / norm
