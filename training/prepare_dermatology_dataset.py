"""
Prepara dataset de dermatología canina para fine-tuning multimodal de Gemma 4 E4B con Unsloth.

Genera pares instruction-tuning (imagen + prompt → diagnóstico clínico) en formato
compatible con Unsloth/HuggingFace chat templates.

Uso:
    python training/prepare_dermatology_dataset.py [--include-feline] [--output-dir training/output]
"""

import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

# ── Mapeo carpeta → label del modelo ──────────────────────────────────
# Definido en vision-service/src/models/dermatology.py → DermatologyModel.CLASS_NAMES
# Los pesos .pt están mapeados por índice ordinal a estos nombres.
# NO renombrar sin reentrenar el modelo.
CANINE_FOLDER_TO_LABEL = {
    "demodicosis": "demodicosis",
    "Dermatitis": "Dermatitis",
    "Fungal_infections": "Fungal_infections",
    "Healthy": "Healthy",
    "Hypersensitivity": "Hypersensitivity_Allergic_Dermatitis",  # ÚNICO MISMATCH
    "ringworm": "ringworm",
}

FELINE_FOLDER_TO_LABEL = {
    "Flea_Allergy": "Flea_Allergy",
    "Health": "Healthy",
    "Ringworm": "ringworm",
    "Scabies": "Scabies",
}

# ── Contexto clínico por clase ────────────────────────────────────────
# Cada clase tiene múltiples templates de respuesta para evitar que el modelo
# memorice una respuesta fija. La variedad mejora generalización.
CLINICAL_CONTEXT = {
    "demodicosis": {
        "species_common": "canine",
        "description_templates": [
            "Observo áreas de alopecia con eritema difuso y posibles pústulas, patrón consistente con demodicosis canina.",
            "Se aprecia pérdida de pelo localizada con inflamación cutánea. Las lesiones sugieren infestación por Demodex canis.",
            "Imagen muestra alopecia focal con descamación y eritema. Morfología compatible con demodicosis.",
        ],
        "differentials": ["demodicosis localizada", "demodicosis generalizada", "dermatofitosis", "pioderma bacteriana"],
        "next_steps": [
            "Raspado cutáneo profundo para confirmar presencia de Demodex canis.",
            "Recomiendo raspado cutáneo profundo y tricograma. Si se confirma, evaluar extensión para clasificar como localizada o generalizada.",
            "Raspado profundo de piel como siguiente paso diagnóstico. En casos generalizados, considerar evaluación de inmunosupresión subyacente.",
        ],
    },
    "Dermatitis": {
        "species_common": "canine",
        "description_templates": [
            "Observo inflamación cutánea con eritema y posible prurito. Patrón compatible con dermatitis.",
            "Se aprecia zona inflamada con enrojecimiento cutáneo difuso. Las lesiones son consistentes con dermatitis.",
            "Imagen muestra piel inflamada con eritema. Dermatitis es el diagnóstico más probable basado en la presentación.",
        ],
        "differentials": ["dermatitis atópica", "dermatitis de contacto", "dermatitis bacteriana", "alergia alimentaria"],
        "next_steps": [
            "Citología cutánea para descartar componente infeccioso. Historia clínica detallada sobre posibles alérgenos.",
            "Evaluación de historia de exposición y dieta. Considerar trial de eliminación si se sospecha alergia alimentaria.",
            "Citología de superficie, cultivo bacteriano si hay pústulas. Evaluar respuesta a tratamiento empírico.",
        ],
    },
    "Fungal_infections": {
        "species_common": "canine",
        "description_templates": [
            "Observo lesiones cutáneas con patrón circular y descamación, sugestivas de infección fúngica.",
            "Se aprecian áreas de alopecia con bordes definidos y descamación. Morfología compatible con micosis cutánea.",
            "Imagen muestra lesiones con distribución y morfología consistentes con infección fúngica dermatológica.",
        ],
        "differentials": ["dermatofitosis", "Malassezia", "candidiasis cutánea", "demodicosis"],
        "next_steps": [
            "Cultivo fúngico (DTM) y examen con lámpara de Wood. Tricograma para observar hifas.",
            "Recomiendo cultivo dermatofítico y citología. Si se confirma, iniciar antifúngico sistémico.",
            "Lámpara de Wood como screening inicial, seguido de cultivo DTM para identificación de especie.",
        ],
    },
    "Healthy": {
        "species_common": "canine",
        "description_templates": [
            "La piel se observa dentro de parámetros normales. No se identifican lesiones dermatológicas significativas.",
            "Imagen muestra piel y pelaje sin alteraciones patológicas evidentes. Aspecto saludable.",
            "No se observan lesiones, eritema, alopecia ni otras alteraciones dermatológicas. Piel clínicamente sana.",
        ],
        "differentials": [],
        "next_steps": [
            "No se requiere intervención dermatológica. Mantener controles preventivos regulares.",
            "Piel sana. Recomendar al propietario mantener higiene regular y monitoreo de cambios cutáneos.",
            "Sin hallazgos patológicos. Continuar con plan preventivo de salud dermatológica.",
        ],
    },
    "Hypersensitivity_Allergic_Dermatitis": {
        "species_common": "canine",
        "description_templates": [
            "Observo eritema intenso con signos de prurito marcado. Patrón distribuido consistente con dermatitis alérgica.",
            "Se aprecia piel enrojecida con excoriaciones por rascado. Las lesiones sugieren reacción de hipersensibilidad.",
            "Imagen muestra inflamación cutánea con distribución típica de dermatitis alérgica. Prurito evidente por lesiones secundarias.",
        ],
        "differentials": ["dermatitis atópica", "alergia alimentaria", "dermatitis alérgica por pulgas (DAPP)", "hipersensibilidad de contacto"],
        "next_steps": [
            "Evaluación de control de pulgas, historia dietética y pruebas de alergia intradérmica o serológica.",
            "Descartar DAPP primero con control estricto de ectoparásitos. Si persiste, considerar trial de eliminación dietética de 8 semanas.",
            "Citología para descartar infección secundaria. Plan escalonado: control de pulgas → dieta de eliminación → pruebas de alergia.",
        ],
    },
    "ringworm": {
        "species_common": "canine",
        "description_templates": [
            "Observo lesiones anulares con alopecia central y borde activo. Patrón clásico de dermatofitosis (tiña).",
            "Se aprecian áreas circulares de pérdida de pelo con descamación periférica. Altamente sugestivo de ringworm.",
            "Imagen muestra lesiones en anillo con alopecia y costras. Morfología típica de infección por dermatofitos.",
        ],
        "differentials": ["Microsporum canis", "Trichophyton mentagrophytes", "demodicosis", "pioderma bacteriana"],
        "next_steps": [
            "Cultivo DTM para confirmación e identificación de especie. Lámpara de Wood (positiva en ~50% de M. canis).",
            "Recomiendo cultivo fúngico y tricograma. Iniciar tratamiento tópico mientras se esperan resultados. Evaluar contactos (zoonosis).",
            "Confirmar con cultivo DTM. Importante: ringworm es zoonótico — advertir a propietarios sobre medidas de higiene.",
        ],
    },
    # Clases felinas
    "Flea_Allergy": {
        "species_common": "feline",
        "description_templates": [
            "Observo dermatitis miliar con pápulas costrosas, patrón clásico de alergia a pulgas en felinos.",
            "Se aprecia prurito intenso con lesiones en zona lumbosacra. Consistente con DAPP felina.",
            "Imagen muestra dermatitis con distribución típica de hipersensibilidad a picadura de pulga en gato.",
        ],
        "differentials": ["DAPP felina", "dermatitis atópica felina", "alergia alimentaria", "dermatofitosis"],
        "next_steps": [
            "Control estricto de pulgas con producto adecuado para felinos. Evaluar todos los animales del hogar.",
            "Administrar antiparasitario externo de amplio espectro. Si no responde en 4-6 semanas, considerar otros diferenciales.",
            "Tratamiento antiparasitario y ambiental. Monitorear resolución de lesiones como confirmación diagnóstica.",
        ],
    },
    "Scabies": {
        "species_common": "feline",
        "description_templates": [
            "Observo prurito intenso con costras y alopecia. Patrón compatible con sarna en felinos.",
            "Se aprecian lesiones costrosas con excoriaciones severas. Morfología sugestiva de sarna (Notoedres cati).",
            "Imagen muestra dermatitis costrosa con distribución facial/auricular típica de sarna felina.",
        ],
        "differentials": ["Notoedres cati", "Sarcoptes (menos común en gatos)", "dermatofitosis", "pénfigo foliáceo"],
        "next_steps": [
            "Raspado cutáneo superficial para identificación de ácaros. Tratamiento con ivermectina o selamectina.",
            "Raspado de piel y tratamiento empírico antiparasitario. Tratar todos los contactos felinos.",
            "Confirmar con raspado superficial. Sarna felina responde bien a tratamiento — pronóstico favorable.",
        ],
    },
}

# ── Prompts de usuario variados ───────────────────────────────────────
USER_PROMPTS = [
    "Analiza esta imagen dermatológica y dame tu evaluación clínica.",
    "¿Qué observas en esta lesión cutánea? Diagnóstico diferencial y siguientes pasos.",
    "Evalúa esta imagen de piel. ¿Cuál es tu impresión diagnóstica?",
    "Necesito tu opinión sobre esta presentación dermatológica.",
    "Analiza esta foto clínica y recomienda el siguiente paso diagnóstico.",
    "¿Qué patología dermatológica sugiere esta imagen?",
]

SYSTEM_PROMPT = (
    "Eres un copiloto veterinario AI especializado en dermatología. "
    "Analiza imágenes clínicas y proporciona evaluaciones estructuradas: "
    "descripción de hallazgos, diagnóstico diferencial y siguientes pasos recomendados. "
    "Responde siempre en español con terminología veterinaria precisa."
)


def build_response(label: str, rng: random.Random) -> str:
    """Genera una respuesta clínica variada para un label dado."""
    ctx = CLINICAL_CONTEXT[label]
    desc = rng.choice(ctx["description_templates"])
    next_step = rng.choice(ctx["next_steps"])

    parts = [desc, ""]
    if ctx["differentials"]:
        diffs = ", ".join(ctx["differentials"])
        parts.append(f"**Diagnóstico diferencial:** {diffs}")
    else:
        parts.append("**Diagnóstico:** Piel clínicamente sana, sin patología evidente.")
    parts.append("")
    parts.append(f"**Siguiente paso:** {next_step}")

    return "\n".join(parts)


def scan_image_dataset(
    base_path: Path,
    folder_to_label: dict[str, str],
    splits: list[str] | None = None,
) -> list[dict]:
    """Escanea un directorio de imágenes organizado por clase y devuelve ejemplos."""
    if splits is None:
        splits = ["train", "valid", "test"]

    examples = []
    for split_dir in base_path.iterdir():
        if not split_dir.is_dir() or split_dir.name not in splits:
            continue
        for class_dir in split_dir.iterdir():
            if not class_dir.is_dir():
                continue
            folder_name = class_dir.name
            if folder_name not in folder_to_label:
                print(f"  WARN: carpeta '{folder_name}' no tiene mapeo, saltando", file=sys.stderr)
                continue
            label = folder_to_label[folder_name]
            for img_path in sorted(class_dir.iterdir()):
                if img_path.suffix.lower() in (".jpg", ".jpeg", ".png"):
                    examples.append({
                        "image_path": str(img_path),
                        "label": label,
                        "split": split_dir.name,
                        "folder": folder_name,
                    })
    return examples


def generate_conversations(
    examples: list[dict],
    seed: int = 42,
) -> list[dict]:
    """Genera dataset en formato conversación para fine-tuning multimodal."""
    rng = random.Random(seed)
    dataset = []

    for ex in examples:
        user_prompt = rng.choice(USER_PROMPTS)
        response = build_response(ex["label"], rng)

        record = {
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "image": ex["image_path"]},
                        {"type": "text", "text": user_prompt},
                    ],
                },
                {"role": "assistant", "content": response},
            ],
            "metadata": {
                "label": ex["label"],
                "split": ex["split"],
                "source_folder": ex["folder"],
            },
        }
        dataset.append(record)

    return dataset


def print_stats(examples: list[dict], name: str) -> None:
    """Imprime estadísticas del dataset."""
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")
    total = len(examples)
    print(f"  Total: {total} imágenes\n")

    by_split = Counter(ex["split"] for ex in examples)
    for split in ["train", "valid", "test"]:
        if split in by_split:
            print(f"  {split}: {by_split[split]}")

    print(f"\n  Distribución por clase (total):")
    by_label = Counter(ex["label"] for ex in examples)
    max_count = max(by_label.values())
    for label, count in sorted(by_label.items(), key=lambda x: -x[1]):
        bar = "#" * int(30 * count / max_count)
        ratio = count / total * 100
        print(f"    {label:45s} {count:5d} ({ratio:5.1f}%) {bar}")


def main():
    parser = argparse.ArgumentParser(description="Prepara dataset dermatología para fine-tuning Gemma 4")
    parser.add_argument("--include-feline", action="store_true", help="Incluir dataset felino")
    parser.add_argument("--output-dir", type=Path, default=Path("training/output"), help="Directorio de salida")
    parser.add_argument("--seed", type=int, default=42, help="Seed para reproducibilidad")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    args.output_dir = project_root / args.output_dir

    # ── Escanear canino ───────────────────────────────────────────────
    canine_base = project_root / "data/datasets/canine/canine/dermatology"
    if not canine_base.exists():
        print(f"ERROR: no se encontró {canine_base}", file=sys.stderr)
        sys.exit(1)

    canine_examples = scan_image_dataset(canine_base, CANINE_FOLDER_TO_LABEL)
    print_stats(canine_examples, "Canine Dermatology")

    all_examples = list(canine_examples)

    # ── Escanear felino (opcional) ────────────────────────────────────
    if args.include_feline:
        feline_base = project_root / "data/datasets/feline/feline/dermatology/feline_skin_splits"
        if feline_base.exists():
            feline_examples = scan_image_dataset(feline_base, FELINE_FOLDER_TO_LABEL)
            print_stats(feline_examples, "Feline Dermatology")
            all_examples.extend(feline_examples)
        else:
            print(f"WARN: no se encontró {feline_base}", file=sys.stderr)

    # ── Generar conversaciones ────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  Generando dataset de fine-tuning")
    print(f"{'='*60}")

    train_examples = [ex for ex in all_examples if ex["split"] == "train"]
    valid_examples = [ex for ex in all_examples if ex["split"] == "valid"]
    test_examples = [ex for ex in all_examples if ex["split"] == "test"]

    train_convos = generate_conversations(train_examples, seed=args.seed)
    valid_convos = generate_conversations(valid_examples, seed=args.seed + 1)

    # ── Escribir outputs ──────────────────────────────────────────────
    args.output_dir.mkdir(parents=True, exist_ok=True)

    train_path = args.output_dir / "dermatology_train.jsonl"
    valid_path = args.output_dir / "dermatology_valid.jsonl"
    stats_path = args.output_dir / "dermatology_stats.json"

    for path, data in [(train_path, train_convos), (valid_path, valid_convos)]:
        with open(path, "w", encoding="utf-8") as f:
            for record in data:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(f"  {path.name}: {len(data)} ejemplos")

    # ── Estadísticas ──────────────────────────────────────────────────
    train_dist = Counter(ex["label"] for ex in train_examples)
    valid_dist = Counter(ex["label"] for ex in valid_examples)
    test_dist = Counter(ex["label"] for ex in test_examples)

    stats = {
        "total_images": len(all_examples),
        "train": {"count": len(train_examples), "distribution": dict(sorted(train_dist.items()))},
        "valid": {"count": len(valid_examples), "distribution": dict(sorted(valid_dist.items()))},
        "test": {"count": len(test_examples), "distribution": dict(sorted(test_dist.items()))},
        "class_mapping_canine": CANINE_FOLDER_TO_LABEL,
        "include_feline": args.include_feline,
        "seed": args.seed,
    }
    if args.include_feline:
        stats["class_mapping_feline"] = FELINE_FOLDER_TO_LABEL

    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f"  {stats_path.name}: estadísticas guardadas")

    print(f"\n  Output: {args.output_dir}/")
    print(f"  Train: {len(train_convos)} | Valid: {len(valid_convos)} | Test (held out): {len(test_examples)}")


if __name__ == "__main__":
    main()
