"""
Vectra: Pydantic request and response models for the FastAPI layer.
Using Pydantic v2 for validation, serialisation, and OpenAPI schema generation.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Any


class SearchFilters(BaseModel):
    """
    Optional business logic filters applied as hard SQL WHERE constraints
    BEFORE the vector similarity search.
    """
    category: str | None = Field(
        default=None,
        description="Product category: 'Apparel', 'Electronics', 'Home', 'Footwear', 'Beauty'",
        examples=["Apparel"],
    )
    max_price: float | None = Field(
        default=None,
        ge=0,
        description="Maximum product price (inclusive)",
        examples=[2000.0],
    )
    in_stock_only: bool = Field(
        default=True,
        description="If true, only return products currently in stock",
    )
    text_modifier: str | None = Field(
        default=None,
        max_length=200,
        description="Optional text to blend with image embedding, e.g. 'but in black'",
        examples=["but in black"],
    )
    text_weight: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Weight of text embedding in multi-modal fusion (0.0 = image only, 1.0 = text only)",
    )
    top_n: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Number of final results to return after reranking",
    )
    skip_rerank: bool = Field(
        default=False,
        description="If true, skip cross-encoder reranking and return raw CLIP ordering",
    )


class ProductResult(BaseModel):
    """A single product in the search results."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: str
    subcategory: str | None
    color: str | None
    price: float
    in_stock: bool
    image_path: str | None
    description: str | None
    similarity: float = Field(description="Cosine similarity from CLIP bi-encoder (0-1)")
    rerank_score: float | None = Field(
        default=None,
        description="Cross-encoder relevance score (higher = more relevant)"
    )
    attr_bonus: float | None = Field(
        default=None,
        description="Attribute metadata match bonus (0-1, from size/color/category matching)"
    )
    size_min: float | None = None
    size_max: float | None = None
    rank_delta: int = Field(
        default=0,
        description="How many positions this product moved after reranking (positive = moved up)"
    )
    pre_rerank_rank: int = Field(
        default=0,
        description="Rank before cross-encoder reranking (by CLIP similarity)"
    )


class SearchResponse(BaseModel):
    """Response envelope for the /search endpoint."""
    results: list[ProductResult]
    total_retrieved: int = Field(description="Number of bi-encoder candidates before reranking")
    total_returned: int = Field(description="Number of results after reranking")
    embed_ms: float = Field(default=0.0, description="CLIP embedding time in ms")
    retrieval_ms: float = Field(default=0.0, description="pgvector retrieval time in ms")
    rerank_ms: float = Field(default=0.0, description="Cross-encoder reranking time in ms")
    filters_applied: dict[str, Any]
