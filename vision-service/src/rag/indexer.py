"""One-shot indexer: reads CSV datasets, generates SapBERT embeddings,
and upserts vectors into Qdrant vet_cases collection.

Run inside the vision-service container:
    docker exec gemma-4-vision-service-1 python -m src.rag.indexer
"""

import csv
import logging
import os
import time

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

from src.rag.embedder import SapBERTEmbedder
from src.rag.text_formatters import (
    fmt_animal_disease_prediction,
    fmt_dog_cat_qa,
    fmt_pet_health_symptoms,
    fmt_vet_health_assessment,
    fmt_vet_med,
    fmt_vet_pet_care,
    fmt_veterinary_clinical,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

QDRANT_HOST = os.getenv("QDRANT_HOST", "qdrant")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
COLLECTION = "vet_cases"
EMBED_BATCH = 64
UPSERT_BATCH = 100

# Dataset definitions: (prefix, csv_path, formatter, record_type)
DATASETS_BASE = "/app/datasets"
SOURCES = [
    (
        "vetclin",
        f"{DATASETS_BASE}/clinical_cases/clinical_cases/veterinary-clinical/veterinary_clinical_data.csv",
        fmt_veterinary_clinical,
        "case",
    ),
    (
        "vetmed",
        f"{DATASETS_BASE}/embeddings/embeddings/vet_med.csv",
        fmt_vet_med,
        "narrative",
    ),
    (
        "phs",
        f"{DATASETS_BASE}/clinical_cases/clinical_cases/pet-health-symptoms/pet-health-symptoms-dataset.csv",
        fmt_pet_health_symptoms,
        "symptoms",
    ),
    (
        "qa",
        f"{DATASETS_BASE}/text/text/qa/dog_cat_qa.csv",
        fmt_dog_cat_qa,
        "qa",
    ),
    (
        "vha",
        f"{DATASETS_BASE}/clinical_cases/clinical_cases/vet_health_assessment.csv",
        fmt_vet_health_assessment,
        "qa",
    ),
    (
        "adp",
        f"{DATASETS_BASE}/clinical_cases/clinical_cases/animal-disease-prediction/cleaned_animal_disease_prediction.csv",
        fmt_animal_disease_prediction,
        "case",
    ),
    (
        "vpc",
        f"{DATASETS_BASE}/clinical_cases/clinical_cases/vet_pet_care.csv",
        fmt_vet_pet_care,
        "case",
    ),
]


def _read_csv(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main() -> None:
    embedder = SapBERTEmbedder.get()
    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

    total_indexed = 0
    total_errors = 0
    t0 = time.time()

    for prefix, csv_path, formatter, record_type in SOURCES:
        if not os.path.exists(csv_path):
            logger.warning("SKIP %s — file not found: %s", prefix, csv_path)
            continue

        rows = _read_csv(csv_path)
        logger.info("Processing %s: %d rows from %s", prefix, len(rows), csv_path)

        # Format all rows into text
        texts = []
        ids = []
        for i, row in enumerate(rows):
            try:
                text = formatter(row)
                if text.strip():
                    texts.append(text)
                    ids.append(f"{prefix}_{i:05d}")
            except Exception as e:
                logger.warning("Format error %s row %d: %s", prefix, i, e)
                total_errors += 1

        # Embed in batches
        all_vectors = []
        for batch_start in range(0, len(texts), EMBED_BATCH):
            batch_texts = texts[batch_start : batch_start + EMBED_BATCH]
            vectors = embedder.encode_batch(batch_texts)
            all_vectors.extend(vectors)

        # Upsert to Qdrant in batches
        points = []
        for j, (point_id, text, vector) in enumerate(zip(ids, texts, all_vectors)):
            points.append(
                PointStruct(
                    id=total_indexed + j,
                    vector=vector,
                    payload={
                        "point_id": point_id,
                        "text": text,
                        "source": prefix,
                        "record_type": record_type,
                    },
                )
            )

            if len(points) >= UPSERT_BATCH:
                client.upsert(collection_name=COLLECTION, points=points)
                points = []

        if points:
            client.upsert(collection_name=COLLECTION, points=points)

        total_indexed += len(all_vectors)
        logger.info("  → %d vectors indexed for %s", len(all_vectors), prefix)

    elapsed = time.time() - t0
    logger.info(
        "Indexing complete: %d vectors, %d errors, %.1fs",
        total_indexed,
        total_errors,
        elapsed,
    )


if __name__ == "__main__":
    main()
