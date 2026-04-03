"""Qdrant collection setup for veterinary clinical cases."""

import logging

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    HnswConfigDiff,
    PayloadSchemaType,
    VectorParams,
)

from src.config import settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "vet_cases"
VECTOR_SIZE = 768  # SapBERT output dimensions


def get_qdrant_client() -> QdrantClient:
    return QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)


def ensure_collection() -> None:
    """Create the vet_cases collection if it doesn't exist."""
    client = get_qdrant_client()
    collections = [c.name for c in client.get_collections().collections]

    if COLLECTION_NAME in collections:
        logger.info("Collection '%s' already exists", COLLECTION_NAME)
        return

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(
            size=VECTOR_SIZE,
            distance=Distance.COSINE,
            hnsw_config=HnswConfigDiff(m=16, ef_construct=200),
        ),
    )

    # Payload indexes for filtered search
    client.create_payload_index(
        collection_name=COLLECTION_NAME,
        field_name="source",
        field_schema=PayloadSchemaType.KEYWORD,
    )
    client.create_payload_index(
        collection_name=COLLECTION_NAME,
        field_name="record_type",
        field_schema=PayloadSchemaType.KEYWORD,
    )

    logger.info("Collection '%s' created with payload indexes", COLLECTION_NAME)
