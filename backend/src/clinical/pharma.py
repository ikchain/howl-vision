"""Pharmacological lookup — dosage calculation and drug interactions.

Uses PostgreSQL for deterministic queries. All drug names normalized
to lowercase before querying to match the seed data convention.
"""

import logging

import psycopg2

from src.config import settings

logger = logging.getLogger(__name__)

DISCLAIMER = "Reference only. Confirm dosage with current veterinary formulary."


def _get_conn():
    return psycopg2.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        dbname=settings.postgres_db,
        user=settings.postgres_user,
        password=settings.postgres_password,
    )


def calculate_dosage(drug: str, weight_kg: float, species: str) -> dict:
    """Calculate drug dosage range for a given weight and species."""
    drug = drug.lower().strip()
    species = species.lower().strip()

    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT dose_mg_kg_min, dose_mg_kg_max, frequency_h, route, notes
                FROM drug_dosages
                WHERE drug_name = %s AND species = %s
                ORDER BY route
                """,
                (drug, species),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        return {
            "found": False,
            "drug": drug,
            "species": species,
            "message": f"No dosage data found for {drug} in {species}.",
        }

    dosages = []
    for dose_min, dose_max, freq_h, route, notes in rows:
        dose_min_f = float(dose_min) if dose_min else 0
        dose_max_f = float(dose_max) if dose_max else 0
        dosages.append({
            "route": route,
            "dose_mg_kg_min": dose_min_f,
            "dose_mg_kg_max": dose_max_f,
            "dose_total_min_mg": round(dose_min_f * weight_kg, 2),
            "dose_total_max_mg": round(dose_max_f * weight_kg, 2),
            "frequency_hours": freq_h,
            "notes": notes,
        })

    return {
        "found": True,
        "drug": drug,
        "species": species,
        "weight_kg": weight_kg,
        "dosages": dosages,
        "disclaimer": DISCLAIMER,
    }


def check_drug_interactions(drug_a: str, drug_b: str) -> dict:
    """Check for known interactions between two drugs."""
    # Normalize: lowercase + alphabetical order (matches CHECK constraint)
    a, b = sorted([drug_a.lower().strip(), drug_b.lower().strip()])

    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT severity, mechanism, clinical_effect, management
                FROM drug_interactions
                WHERE drug_a = %s AND drug_b = %s
                """,
                (a, b),
            )
            row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        return {
            "found": False,
            "drug_a": a,
            "drug_b": b,
            "message": f"No known interaction found between {a} and {b}.",
        }

    severity, mechanism, effect, management = row
    return {
        "found": True,
        "drug_a": a,
        "drug_b": b,
        "severity": severity,
        "mechanism": mechanism,
        "clinical_effect": effect,
        "management": management,
    }
