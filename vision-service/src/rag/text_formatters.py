"""Format each dataset's rows into text suitable for SapBERT embedding.

Each formatter produces a clinically coherent string that captures the
diagnostic context: species/breed first, then symptoms, then diagnosis.
"""


def fmt_veterinary_clinical(row: dict) -> str:
    symptoms = " ".join(
        s for s in [row.get(f"Symptom_{i}", "") for i in range(1, 6)] if s
    )
    return (
        f"{row['AnimalName']} {row['Breed']} {row['Age']}yo "
        f"{row['Weight_kg']}kg. "
        f"History: {row['MedicalHistory']}. "
        f"Symptoms: {symptoms}"
    )


def fmt_vet_med(row: dict) -> str:
    return row["story"].strip()


def fmt_pet_health_symptoms(row: dict) -> str:
    return f"{row['record_type']}: {row['text']}. Condition: {row['condition']}"


def fmt_dog_cat_qa(row: dict) -> str:
    return f"Q: {row['Question']} A: {row['Answer']}"


def fmt_vet_health_assessment(row: dict) -> str:
    return f"Q: {row['Question']} A: {row['Answer']}. Labels: {row['Labels']}"


def fmt_animal_disease_prediction(row: dict) -> str:
    symptoms = " ".join(
        s for s in [row.get(f"Symptom_{i}", "") for i in range(1, 5)] if s
    )
    return (
        f"{row['Animal_Type']} {row['Breed']} {row['Age']}yo "
        f"{row['Gender']} {row['Weight']}kg. "
        f"Symptoms: {symptoms}. "
        f"Duration: {row['Duration']}. "
        f"Diagnosis: {row['Disease_Prediction']}"
    )


def fmt_vet_pet_care(row: dict) -> str:
    follow_up = row.get("follow_up_result", "")
    base = (
        f"{row['species']} {row['breed']} {row['age']}. "
        f"Symptoms: {row['symptoms']}. "
        f"Diagnosis: {row['diagnosis']}. "
        f"Treatment: {row['treatment_plan']}"
    )
    if follow_up:
        base += f". Follow-up: {follow_up}"
    return base
