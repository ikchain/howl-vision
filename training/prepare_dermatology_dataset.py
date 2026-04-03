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

# ── Contexto clínico por clase (composicional) ───────────────────────
# Cada respuesta se compone de: hallazgo + severidad + distribución +
# diferenciales (subset variable) + incertidumbre + siguiente paso + urgencia.
# Esto genera cientos de combinaciones únicas por clase, evitando memorización.
# Ref: ml-eval-rigor P0 — mínimo 20-30 combinaciones efectivas por clase.
CLINICAL_CONTEXT = {
    "demodicosis": {
        "species_common": "canine",
        "findings": [
            "Observo áreas de alopecia con eritema difuso y posibles pústulas.",
            "Se aprecia pérdida de pelo con inflamación cutánea perifolicular.",
            "Alopecia focal con descamación y eritema. Folículos pilosos visiblemente afectados.",
            "Lesiones alopécicas con comedones y costras foliculares.",
            "Áreas de hipotricosis con piel engrosada y descamación furfurácea.",
            "Eritema periocular con alopecia y descamación fina.",
            "Placas alopécicas con hiperpigmentación secundaria y piel liquenificada.",
            "Pérdida de pelo multifocal con pústulas foliculares intactas.",
            "Áreas eritematosas con alopecia y formación de comedones.",
            "Lesiones costrosas con alopecia difusa y piel descamativa.",
        ],
        "differential_sets": [
            ["demodicosis localizada", "dermatofitosis", "foliculitis bacteriana"],
            ["demodicosis generalizada", "pioderma profunda", "dermatofitosis"],
            ["demodicosis localizada", "demodicosis generalizada", "alopecia endocrina"],
            ["demodicosis juvenil", "pioderma bacteriana", "dermatofitosis", "foliculitis"],
            ["demodicosis", "sarna sarcóptica", "dermatitis por Malassezia"],
        ],
        "next_steps": [
            "Raspado cutáneo profundo para confirmar presencia de Demodex canis.",
            "Raspado cutáneo profundo y tricograma para buscar ácaros y huevos.",
            "Raspado profundo de piel. Si se confirma, evaluar extensión para clasificar como localizada o generalizada.",
            "Raspado profundo en bordes de lesión. En casos generalizados, considerar evaluación de inmunosupresión subyacente.",
            "Tricograma y raspado profundo. Recuento de ácaros vivos vs. muertos para monitoreo de tratamiento.",
            "Raspado cutáneo profundo de múltiples sitios. Si generalizada, hemograma completo para descartar enfermedad sistémica.",
            "Biopsia de piel si raspados son negativos pero sospecha clínica persiste. Demodex a veces solo se ve en histopatología.",
            "Raspado profundo. En perros jóvenes (<18 meses) considerar resolución espontánea si localizada. Seguimiento en 4-6 semanas.",
        ],
    },
    "Dermatitis": {
        "species_common": "canine",
        "findings": [
            "Observo inflamación cutánea con eritema y signos de prurito.",
            "Zona inflamada con enrojecimiento cutáneo y posible liquenificación.",
            "Piel inflamada con eritema, excoriaciones y cambios de textura.",
            "Eritema difuso con descamación y posibles pápulas.",
            "Inflamación cutánea con engrosamiento epidérmico y eritema.",
            "Lesiones eritematosas con excoriaciones por rascado crónico.",
            "Piel enrojecida con hiperpigmentación secundaria y descamación.",
            "Área inflamada con máculas eritematosas y superficie irregular.",
            "Inflamación con edema cutáneo leve y cambio de coloración.",
            "Eritema con pápulas y posible exudación serosa superficial.",
        ],
        "differential_sets": [
            ["dermatitis atópica", "dermatitis de contacto", "pioderma bacteriana"],
            ["dermatitis atópica", "alergia alimentaria", "dermatitis por Malassezia"],
            ["dermatitis de contacto", "dermatitis bacteriana", "dermatofitosis"],
            ["dermatitis alérgica", "pioderma superficial", "demodicosis"],
            ["dermatitis atópica", "alergia alimentaria", "DAPP", "dermatitis de contacto"],
        ],
        "next_steps": [
            "Citología cutánea para descartar componente infeccioso. Historia clínica detallada sobre posibles alérgenos.",
            "Evaluación de historia de exposición y dieta. Considerar trial de eliminación si se sospecha alergia alimentaria.",
            "Citología de superficie, cultivo bacteriano si hay pústulas. Evaluar respuesta a tratamiento empírico.",
            "Raspado cutáneo para descartar ectoparásitos. Citología por impresión de zonas húmedas.",
            "Citología cutánea y evaluación de patrón de distribución. La localización orienta el diagnóstico etiológico.",
            "Historia ambiental detallada. Si hay estacionalidad, sospechar atopia. Iniciar diario de síntomas.",
            "Cultivo bacteriano y antibiograma si pústulas presentes. Biopsia si dermatitis es crónica y no responde a tratamiento.",
            "Trial de eliminación dietética de 8 semanas con proteína novel. Mantener diario de síntomas.",
        ],
    },
    "Fungal_infections": {
        "species_common": "canine",
        "findings": [
            "Lesiones cutáneas con patrón circular y descamación, sugestivas de infección fúngica.",
            "Áreas de alopecia con bordes definidos y descamación periférica.",
            "Lesiones con distribución y morfología consistentes con micosis cutánea.",
            "Placas alopécicas con escamas grisáceas y borde eritematoso activo.",
            "Áreas circulares de pelo quebradizo con descamación y costras.",
            "Lesiones anulares con centro pálido y periferia inflamada.",
            "Alopecia con pelos rotos a nivel de la superficie cutánea y descamación.",
            "Placas eritemato-escamosas con configuración arciforme o policíclica.",
            "Lesiones costrosas con distribución asimétrica y bordes bien definidos.",
            "Áreas de hipotricosis con descamación furfurácea y eritema moderado.",
        ],
        "differential_sets": [
            ["dermatofitosis por Microsporum canis", "Malassezia", "demodicosis"],
            ["dermatofitosis", "candidiasis cutánea", "pioderma bacteriana"],
            ["Microsporum canis", "Trichophyton mentagrophytes", "demodicosis"],
            ["micosis superficial", "dermatitis bacteriana", "alopecia areata"],
            ["dermatofitosis", "Malassezia", "dermatitis de contacto", "pénfigo"],
        ],
        "next_steps": [
            "Cultivo fúngico (DTM) y examen con lámpara de Wood. Tricograma para observar hifas.",
            "Cultivo dermatofítico y citología. Si se confirma, iniciar antifúngico sistémico.",
            "Lámpara de Wood como screening inicial, seguido de cultivo DTM para identificación de especie.",
            "Tricograma con KOH para visualizar artroconidias. Cultivo DTM en paralelo.",
            "Cultivo DTM de pelos del borde activo de la lesión. Resultado esperado en 7-14 días.",
            "Biopsia para histopatología si cultivos negativos pero clínica sugestiva. Tinción PAS para hongos.",
            "Lámpara de Wood y tricograma inmediato. Si positivo, iniciar tratamiento tópico + sistémico sin esperar cultivo.",
            "Cultivo fúngico. Recordar: zoonosis potencial — recomendar higiene de manos y evaluar contactos humanos.",
        ],
    },
    "Healthy": {
        "species_common": "canine",
        "findings": [
            "La piel se observa dentro de parámetros normales. No se identifican lesiones significativas.",
            "Piel y pelaje sin alteraciones patológicas evidentes. Aspecto saludable.",
            "No se observan lesiones, eritema, alopecia ni alteraciones dermatológicas.",
            "Piel con elasticidad, color y textura normales. Pelaje uniforme y brillante.",
            "Sin evidencia de inflamación, infección ni lesiones parasitarias.",
            "Manto piloso íntegro, piel bien hidratada, sin áreas de alopecia ni eritema.",
            "Evaluación dermatológica sin hallazgos patológicos. Piel clínicamente normal.",
            "No se detectan lesiones primarias ni secundarias. Estado dermatológico saludable.",
            "Piel rosada, flexible, sin engrosamiento ni cambios de pigmentación anormales.",
            "Examen cutáneo sin hallazgos relevantes. Folículos y glándulas de aspecto normal.",
        ],
        "differential_sets": [],
        "next_steps": [
            "No se requiere intervención dermatológica. Mantener controles preventivos regulares.",
            "Piel sana. Recomendar al propietario mantener higiene regular y monitoreo de cambios cutáneos.",
            "Sin hallazgos patológicos. Continuar con plan preventivo de salud dermatológica.",
            "No se necesitan pruebas adicionales. Programar revisión dermatológica de rutina.",
            "Estado dermatológico normal. Mantener desparasitación externa y nutrición adecuada.",
            "Sin patología. Si el propietario reporta prurito, considerar evaluación en momento de síntomas activos.",
            "Piel normal. Recomendar revisión si aparecen cambios en pelaje, prurito o lesiones nuevas.",
            "Sin necesidad de tratamiento. Enfatizar prevención: control de pulgas/garrapatas y dieta balanceada.",
        ],
    },
    "Hypersensitivity_Allergic_Dermatitis": {
        "species_common": "canine",
        "findings": [
            "Eritema intenso con signos de prurito marcado. Patrón consistente con dermatitis alérgica.",
            "Piel enrojecida con excoriaciones por rascado. Lesiones sugieren reacción de hipersensibilidad.",
            "Inflamación cutánea con distribución típica de dermatitis alérgica y prurito evidente.",
            "Eritema difuso con pápulas y auto-trauma por rascado persistente.",
            "Lesiones eritematosas en zonas de flexión con liquenificación secundaria.",
            "Prurito severo con alopecia auto-inducida y excoriaciones múltiples.",
            "Dermatitis eritematosa con distribución ventral y interdigital, patrón alérgico clásico.",
            "Otitis eritematosa bilateral con pododermatitis, fuertemente sugestivo de atopia.",
            "Piel inflamada con hiperpigmentación crónica por rascado repetitivo.",
            "Eritema periocular y perilabial con excoriaciones. Distribución facial típica de alergia.",
        ],
        "differential_sets": [
            ["dermatitis atópica", "alergia alimentaria", "DAPP"],
            ["dermatitis atópica", "hipersensibilidad de contacto", "pioderma secundaria"],
            ["alergia alimentaria", "dermatitis atópica", "sarna sarcóptica"],
            ["DAPP", "dermatitis atópica", "alergia alimentaria", "hipersensibilidad de contacto"],
            ["dermatitis alérgica", "pioderma superficial secundaria", "Malassezia secundaria"],
        ],
        "next_steps": [
            "Evaluación de control de pulgas, historia dietética y pruebas de alergia intradérmica o serológica.",
            "Descartar DAPP primero con control estricto de ectoparásitos. Si persiste, trial de eliminación dietética de 8 semanas.",
            "Citología para descartar infección secundaria. Plan escalonado: control de pulgas → dieta de eliminación → pruebas de alergia.",
            "Raspado cutáneo para descartar sarna. Si negativo, iniciar control de pulgas estricto por 8 semanas.",
            "Hemograma y perfil tiroideo para descartar endocrinopatía. Pruebas intradérmicas si atopia es sospecha principal.",
            "Dieta de eliminación con proteína hidrolizada durante 8-12 semanas. Sin premios ni extras durante el trial.",
            "Citología de oídos y piel para identificar infección secundaria por Malassezia o bacterias. Tratar infecciones antes de evaluar alergia.",
            "Prueba serológica de IgE alérgeno-específica. Considerar inmunoterapia si atopia se confirma.",
        ],
    },
    "ringworm": {
        "species_common": "canine",
        "findings": [
            "Lesiones anulares con alopecia central y borde activo. Patrón clásico de dermatofitosis.",
            "Áreas circulares de pérdida de pelo con descamación periférica.",
            "Lesiones en anillo con alopecia y costras. Morfología típica de infección por dermatofitos.",
            "Placas alopécicas circulares con escamas grisáceas en periferia.",
            "Alopecia focal con pelos rotos y descamación en configuración anular.",
            "Lesión única bien delimitada con borde escamoso activo y centro claro.",
            "Múltiples placas circulares alopécicas con costras y descamación.",
            "Área de alopecia con pelo quebradizo a nivel de superficie y halo eritematoso.",
            "Lesiones policíclicas con coalescencia parcial y descamación variable.",
            "Placa alopécica con bordes elevados y centro ligeramente atrófico.",
        ],
        "differential_sets": [
            ["Microsporum canis", "Trichophyton mentagrophytes", "demodicosis"],
            ["dermatofitosis", "pioderma bacteriana", "alopecia areata"],
            ["Microsporum canis", "demodicosis localizada", "foliculitis bacteriana"],
            ["dermatofitosis", "dermatitis de contacto", "pénfigo foliáceo"],
            ["Microsporum canis", "Trichophyton mentagrophytes", "Microsporum gypseum"],
        ],
        "next_steps": [
            "Cultivo DTM para confirmación e identificación de especie. Lámpara de Wood (positiva en ~50% de M. canis).",
            "Cultivo fúngico y tricograma. Iniciar tratamiento tópico mientras se esperan resultados. Evaluar contactos (zoonosis).",
            "Confirmar con cultivo DTM. Ringworm es zoonótico — advertir a propietarios sobre medidas de higiene.",
            "Lámpara de Wood inmediata. Si fluorescencia positiva, iniciar antifúngico sin esperar cultivo.",
            "Tricograma con KOH de pelos del borde activo. Cultivo DTM para identificación definitiva.",
            "Cultivo DTM y evaluación de todos los animales en contacto. Descontaminación ambiental recomendada.",
            "Biopsia si presentación atípica. En lesiones clásicas, cultivo DTM es suficiente para confirmación.",
            "Iniciar tratamiento tópico (miconazol/clotrimazol) y sistémico (itraconazol) si lesiones múltiples. Control cultivo en 4 semanas.",
        ],
    },
    # ── Clases felinas ────────────────────────────────────────────────
    "Flea_Allergy": {
        "species_common": "feline",
        "findings": [
            "Dermatitis miliar con pápulas costrosas, patrón clásico de alergia a pulgas en felinos.",
            "Prurito intenso con lesiones en zona lumbosacra y base de cola.",
            "Dermatitis con distribución típica de hipersensibilidad a picadura de pulga.",
            "Alopecia simétrica en abdomen ventral con dermatitis miliar dorsal.",
            "Pápulas costrosas múltiples en región dorsal con auto-trauma evidente.",
            "Lesiones de rascado intenso en cuello y base de cola con pérdida de pelo.",
            "Dermatitis miliar generalizada con excoriaciones cervicales.",
            "Alopecia ventral con granulomas eosinofílicos lineales.",
            "Placas erosivas en abdomen y muslos internos con prurito intenso.",
            "Costras miliares palpables en región dorsal con pelo ralo.",
        ],
        "differential_sets": [
            ["DAPP felina", "dermatitis atópica felina", "alergia alimentaria"],
            ["hipersensibilidad a pulgas", "dermatofitosis", "pénfigo foliáceo"],
            ["DAPP", "complejo granuloma eosinofílico", "alergia alimentaria"],
            ["alergia a pulgas", "dermatitis atópica", "infección por dermatofitos"],
            ["DAPP felina", "alergia alimentaria", "dermatitis por Cheyletiella"],
        ],
        "next_steps": [
            "Control estricto de pulgas con producto adecuado para felinos. Evaluar todos los animales del hogar.",
            "Antiparasitario externo de amplio espectro. Si no responde en 4-6 semanas, considerar otros diferenciales.",
            "Tratamiento antiparasitario y ambiental. Monitorear resolución de lesiones como confirmación diagnóstica.",
            "Selamectina o fluralaner tópico. Tratar TODOS los animales del hogar y descontaminar ambiente.",
            "Control de pulgas estricto durante mínimo 8 semanas. La resolución clínica confirma el diagnóstico.",
            "Aplicar antiparasitario y evaluar en 4 semanas. Si mejora parcial, añadir control ambiental.",
            "Citología de lesiones para descartar infección bacteriana secundaria. Iniciar control de pulgas inmediato.",
            "Peine de pulgas para buscar adultos/heces. Aún si negativo, no descarta DAPP — un solo piquete puede causar reacción.",
        ],
    },
    "Scabies": {
        "species_common": "feline",
        "findings": [
            "Prurito intenso con costras y alopecia en patrón compatible con sarna felina.",
            "Lesiones costrosas con excoriaciones severas. Morfología sugestiva de Notoedres cati.",
            "Dermatitis costrosa con distribución facial y auricular típica de sarna.",
            "Costras gruesas en pabellones auriculares con extensión a cara y cuello.",
            "Prurito extremo con costras amarillentas adherentes en zona periauricular.",
            "Lesiones hiperqueratósicas en bordes de orejas con engrosamiento cutáneo.",
            "Alopecia facial con costras confluentes y excoriaciones por rascado.",
            "Dermatitis costrosa severa en cara y orejas con afectación de patas delanteras.",
            "Costras y descamación intensa en región cefálica con prurito incoercible.",
            "Lesiones faciales bilaterales con costras grisáceas y alopecia periauricular.",
        ],
        "differential_sets": [
            ["Notoedres cati", "dermatofitosis", "pénfigo foliáceo"],
            ["sarna notoédrica", "Sarcoptes (raro en gatos)", "dermatitis por Demodex gatoi"],
            ["Notoedres cati", "otodectes", "dermatofitosis", "pénfigo foliáceo"],
            ["sarna felina", "lupus eritematoso", "complejo granuloma eosinofílico"],
            ["Notoedres cati", "Demodex gatoi", "dermatitis alérgica", "micosis"],
        ],
        "next_steps": [
            "Raspado cutáneo superficial para identificación de ácaros. Tratamiento con ivermectina o selamectina.",
            "Raspado de piel y tratamiento empírico antiparasitario. Tratar todos los contactos felinos.",
            "Confirmar con raspado superficial. Sarna felina responde bien a tratamiento — pronóstico favorable.",
            "Raspado superficial de borde de lesión. Si positivo, selamectina tópica cada 2 semanas × 3 dosis.",
            "Raspado cutáneo. Notoedres es altamente contagioso — aislar al paciente y tratar contactos.",
            "Citología para descartar infección bacteriana secundaria. Iniciar tratamiento antiparasitario empírico.",
            "Múltiples raspados superficiales de cara y orejas. Biopsia si raspados negativos pero sospecha alta.",
            "Tratamiento con ivermectina SC o selamectina tópica. Evaluar respuesta en 2-3 semanas.",
        ],
    },
}

# ── Ejes de variación composicional ──────────────────────────────────
# Se combinan con los hallazgos para evitar memorización de templates fijos.
SEVERITY_PREFIXES = [
    "Presentación leve.",
    "Presentación moderada.",
    "Presentación severa que requiere atención prioritaria.",
    "Caso en estadio temprano.",
    "Presentación crónica con cambios secundarios.",
]

UNCERTAINTY_FRAMES = [
    "La impresión diagnóstica principal es {label}.",
    "El cuadro es altamente sugestivo de {label}.",
    "La presentación es compatible con {label}, aunque se requiere confirmación.",
    "Considerando la morfología y distribución, {label} es el diagnóstico más probable.",
    "Los hallazgos orientan hacia {label}. Recomiendo confirmar con pruebas complementarias.",
]

DISTRIBUTION_NOTES = [
    "Distribución focal, área única afectada.",
    "Patrón multifocal con varias áreas comprometidas.",
    "Distribución difusa, afectación extensa.",
    "Lesiones de distribución asimétrica.",
    "Patrón bilateral simétrico.",
]

URGENCY_SUFFIXES = [
    "",
    "Seguimiento de rutina recomendado.",
    "Priorizar diagnóstico confirmatorio esta semana.",
    "Monitorear evolución en los próximos días.",
    "Considerar tratamiento empírico mientras se esperan resultados.",
]

# ── Prompts de usuario variados ───────────────────────────────────────
USER_PROMPTS = [
    "Analiza esta imagen dermatológica y dame tu evaluación clínica.",
    "¿Qué observas en esta lesión cutánea? Diagnóstico diferencial y siguientes pasos.",
    "Evalúa esta imagen de piel. ¿Cuál es tu impresión diagnóstica?",
    "Necesito tu opinión sobre esta presentación dermatológica.",
    "Analiza esta foto clínica y recomienda el siguiente paso diagnóstico.",
    "¿Qué patología dermatológica sugiere esta imagen?",
    "Como copiloto veterinario, ¿qué evaluación haces de esta lesión?",
    "Examina esta imagen y proporciona diagnósticos diferenciales.",
    "¿Cuál es tu impresión clínica sobre esta condición cutánea?",
    "Revisa esta imagen dermatológica. ¿Qué diagnóstico consideras más probable?",
    "Tengo un paciente con esta presentación cutánea. ¿Tu evaluación?",
    "Observa esta lesión de piel y sugiere un plan diagnóstico.",
    "¿Qué hallazgos dermatológicos identificas en esta imagen?",
    "Evalúa esta foto y dame diferenciales con siguiente paso recomendado.",
    "Analiza los hallazgos cutáneos de esta imagen clínica.",
]

SYSTEM_PROMPT = (
    "Eres un copiloto veterinario AI especializado en dermatología. "
    "Analiza imágenes clínicas y proporciona evaluaciones estructuradas: "
    "descripción de hallazgos, diagnóstico diferencial y siguientes pasos recomendados. "
    "Responde siempre en español con terminología veterinaria precisa."
)


def build_response(label: str, rng: random.Random, species: str = "canine") -> str:
    """Genera una respuesta clínica composicional para un label dado.

    Combina hallazgo + severidad + distribución + incertidumbre + diferenciales
    + siguiente paso + urgencia. Produce cientos de combinaciones únicas por clase.
    """
    ctx = CLINICAL_CONTEXT[label]
    finding = rng.choice(ctx["findings"])
    next_step = rng.choice(ctx["next_steps"])

    parts = []

    # Severidad (50% de las veces — no siempre es relevante)
    if rng.random() < 0.5:
        parts.append(rng.choice(SEVERITY_PREFIXES))

    # Hallazgo clínico principal
    parts.append(finding)

    # Distribución (60% de las veces, no aplica a Healthy)
    if label != "Healthy" and rng.random() < 0.6:
        parts.append(rng.choice(DISTRIBUTION_NOTES))

    parts.append("")

    # Diagnóstico / diferenciales
    if ctx["differential_sets"]:
        uncertainty = rng.choice(UNCERTAINTY_FRAMES).format(label=label)
        parts.append(uncertainty)
        diff_set = rng.choice(ctx["differential_sets"])
        diffs = ", ".join(diff_set)
        parts.append(f"**Diagnóstico diferencial:** {diffs}")
    else:
        parts.append("**Diagnóstico:** Piel clínicamente sana, sin patología evidente.")

    parts.append("")
    parts.append(f"**Siguiente paso:** {next_step}")

    # Urgencia (40% de las veces)
    urgency = rng.choice(URGENCY_SUFFIXES)
    if urgency:
        parts.append(urgency)

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
    """Genera dataset en formato conversación para fine-tuning multimodal.

    Usa species-conditional prompting para evitar contaminación de clases
    compartidas entre canino y felino (P1: ml-eval-rigor).
    """
    rng = random.Random(seed)
    dataset = []

    for ex in examples:
        species = CLINICAL_CONTEXT[ex["label"]]["species_common"]
        user_prompt = rng.choice(USER_PROMPTS)
        # Species-conditional: el prompt incluye la especie para que el modelo
        # aprenda a condicionar su diagnóstico por especie
        species_label = "canino" if species == "canine" else "felino"
        prompt_with_species = f"Especie: {species_label}. {user_prompt}"

        response = build_response(ex["label"], rng, species=species)

        record = {
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "image": ex["image_path"]},
                        {"type": "text", "text": prompt_with_species},
                    ],
                },
                {"role": "assistant", "content": response},
            ],
            "metadata": {
                "label": ex["label"],
                "split": ex["split"],
                "source_folder": ex["folder"],
                "species": species,
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
