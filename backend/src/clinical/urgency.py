"""Rule-based urgency determination from classification + confidence."""

EMERGENCY_CLASSES = {"Leishmania", "Plasmodium", "Toxoplasma", "Trypanosome"}
SOON_CLASSES = {"demodicosis", "Scabies", "ringworm", "Fungal_infections", "Babesia", "Trichomonad"}
MONITOR_CLASSES = {"Dermatitis", "Hypersensitivity_Allergic_Dermatitis", "Flea_Allergy"}
HEALTHY_CLASSES = {"Healthy", "RBCs", "Leukocyte"}


def determine_urgency(label: str, confidence: float) -> str:
    """Return urgency level from classification label and model confidence.

    Low confidence (< 0.70) always resolves to 'soon' regardless of label,
    because uncertainty warrants professional evaluation.

    Returns: 'emergency' | 'soon' | 'monitor' | 'healthy'
    """
    if confidence < 0.70:
        return "soon"  # Uncertainty = see a vet
    if label in EMERGENCY_CLASSES:
        return "emergency"
    if label in HEALTHY_CLASSES and confidence >= 0.85:
        return "healthy"
    if label in SOON_CLASSES:
        return "soon"
    if label in MONITOR_CLASSES:
        return "monitor"
    return "soon"  # Default: err on caution
