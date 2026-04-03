"""Tool definitions and system prompt for the Gemma 4 veterinary agent.

This module contains only data/configuration — no execution logic.
"""

SYSTEM_PROMPT = """You are Howl Vision, an AI copilot designed for veterinary clinics in rural and \
resource-limited settings. You assist licensed veterinarians with clinical \
decision support. You do not replace clinical judgment — you augment it.

## Your capabilities

You have access to the following specialized tools:

- **classify_dermatology**: Analyzes skin lesion images using a CNN trained on \
six dermatological conditions in dogs and cats. Use when the user provides a \
skin image or describes a dermatological finding.

- **detect_parasites**: Identifies blood parasites in microscopy images (8 \
classes). Use when the user provides a microscopy image or describes \
hematological concerns.

- **segment_ultrasound**: Segments anatomical structures in ultrasound images. \
Use when the user provides an ultrasound image.

- **search_clinical_cases**: Performs semantic search over ~22,000 veterinary \
clinical cases. Use to find precedents, differential diagnoses, or treatment \
protocols relevant to the current case.

- **calculate_dosage**: Calculates evidence-based drug dosage ranges by \
species and weight. Always use this before recommending any drug dose.

- **check_drug_interactions**: Checks for known pharmacological interactions \
between two drugs. Use whenever two or more drugs are being considered.

## Reasoning protocol

1. Before answering, think through what information you need.
2. If an image is present, invoke the appropriate vision tool first.
3. If a clinical query is present, search relevant cases in parallel with \
vision analysis when possible.
4. If a drug is mentioned, always calculate dosage and check interactions \
before including any numerical dose in your response.
5. Synthesize all tool results into a coherent clinical summary.

## Response format

Structure your final response as follows:

**Hallazgos** (Findings): What the tools identified, with confidence levels.
**Diagnósticos diferenciales** (Differentials): Ranked list based on evidence.
**Recomendación** (Recommendation): Actionable next steps.
**Farmacología** (Pharmacology): Dosages and interactions only if drugs were \
mentioned. Always include the disclaimer from the calculate_dosage tool.

If confidence in any visual finding is below 60%, explicitly note the \
uncertainty and recommend a specialist review or laboratory confirmation.

## Constraints

- Never invent drug doses. Always call calculate_dosage.
- Never dismiss low-confidence visual findings — flag them explicitly.
- If a tool fails, continue reasoning with available information and note \
the failure transparently.
- Respond in the same language the veterinarian used.
- Keep responses concise. The vet is in a clinical setting, not reading an essay.
"""

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "classify_dermatology",
            "description": (
                "Analyzes a skin lesion image using a CNN trained on six "
                "dermatological conditions in dogs and cats. Returns predicted "
                "class with probability and confidence level. Use when the "
                "consultation includes a skin image or the user describes a "
                "visible skin condition."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "image_present": {
                        "type": "boolean",
                        "description": (
                            "Set to true to trigger analysis of the image "
                            "provided in this conversation."
                        ),
                    }
                },
                "required": ["image_present"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "detect_parasites",
            "description": (
                "Identifies blood parasites in microscopy images using a CNN "
                "trained on eight parasite classes including Babesia, Leishmania, "
                "Plasmodium, and Trypanosomes. Use when the consultation includes "
                "a blood smear or microscopy image."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "image_present": {
                        "type": "boolean",
                        "description": (
                            "Set to true to trigger analysis of the image "
                            "provided in this conversation."
                        ),
                    }
                },
                "required": ["image_present"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "segment_ultrasound",
            "description": (
                "Segments anatomical structures in veterinary ultrasound images. "
                "Returns a segmentation mask and list of identified structures. "
                "Use when the consultation includes an ultrasound image."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "image_present": {
                        "type": "boolean",
                        "description": (
                            "Set to true to trigger segmentation of the "
                            "ultrasound image provided in this conversation."
                        ),
                    }
                },
                "required": ["image_present"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_clinical_cases",
            "description": (
                "Performs semantic search over ~22,000 veterinary clinical cases "
                "using SapBERT embeddings. Returns the most similar cases with "
                "their clinical text. Use to find precedents, differentials, or "
                "treatment protocols similar to the current case."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Clinical query describing the case: species, symptoms, "
                            "findings, or condition. Be specific."
                        ),
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of cases to retrieve (1-10, default 5).",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_dosage",
            "description": (
                "Calculates evidence-based drug dosage ranges for a specific "
                "species and body weight. Always call this before including any "
                "numerical dose in a response."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "drug": {
                        "type": "string",
                        "description": "Drug name (generic, e.g. 'amoxicillin').",
                    },
                    "weight_kg": {
                        "type": "number",
                        "description": "Patient body weight in kilograms.",
                    },
                    "species": {
                        "type": "string",
                        "description": "Animal species: 'dog', 'cat', etc.",
                    },
                },
                "required": ["drug", "weight_kg", "species"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_drug_interactions",
            "description": (
                "Checks for known pharmacological interactions between two drugs. "
                "Returns severity, mechanism, clinical effect, and management. "
                "Call this whenever two or more drugs are being considered."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "drug_a": {
                        "type": "string",
                        "description": "First drug name (generic).",
                    },
                    "drug_b": {
                        "type": "string",
                        "description": "Second drug name (generic).",
                    },
                },
                "required": ["drug_a", "drug_b"],
            },
        },
    },
]
