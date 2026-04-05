# Fine-Tuning Benchmarks

Evaluation results for Gemma 4 E4B SFT (Supervised Fine-Tuning) on veterinary
dermatology classification via narrative extraction.

## Files

| File | Status | Description |
|------|--------|-------------|
| `results_p0_comparison.json` | **Definitive** | P0 comparison: base vs narrative adapter, n=120 (15/class), keywords fixed, Wilson CIs. F1=0.873 but delta=0.0 (base matches fine-tuned). |
| `results_narrative_production.json` | Historical | Early production eval with wrong adapter path. Superseded by P0. |
| `results_narrative.json` | Historical | Second run, still with evaluation issues. Superseded by P0. |
| `results.json` | Historical | First eval run. Superseded by P0. |
| `eval_dermatology_sft.py` | Active | Evaluation script with strict keyword extraction, Wilson CIs, per-class metrics. |

## Key Finding

The narrative fine-tuned adapter achieves F1=0.873 but the **base model matches
it** (delta=0.0). The SFT did not improve classification accuracy over the
base Gemma 4 E4B model. This is an honest result documented in the P0
comparison file.

Possible explanations:
- Small dataset (20-30 templates per class) was insufficient for meaningful shift
- Gemma 4 E4B already has strong veterinary knowledge from pretraining
- Keyword extraction evaluation may not capture narrative quality improvements

## Adapter

The narrative LoRA adapter is at `training/checkpoints-narrative/lora_adapter/`.
It can be used to regenerate GGUF for the Unsloth track.
