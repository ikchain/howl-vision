# Howl Vision

**Accessible veterinary diagnosis where there is no specialist.**

A pet owner at 3am with a worried dog. A lab technician in a rural clinic with a microscope and no dermatologist. A shelter volunteer screening 40 dogs after a rescue. They all need the same thing: a second opinion from someone who has seen this before.

Howl Vision is a veterinary AI copilot that puts dermatology classification, blood parasite detection, clinical knowledge search, and drug interaction checks into a single PWA — usable on any phone, with or without internet.

Built for the [Gemma 4 Good Hackathon](https://www.kaggle.com/competitions/gemma-4-good-hackathon) (Kaggle / Google DeepMind, 2026).

**Live demo:** [app.howlvision.com](https://app.howlvision.com)

## What it does

There are two ways to ask Howl Vision about an animal: take a photo, or describe what you see in writing. Both flows live on the same screen, behind a single toggle.

The app works in three modes depending on connectivity:

| Mode | What's available | Requires |
|------|-----------------|----------|
| **Offline** | Skin lesion classification via ONNX (sub-second, 20MB model) + symptom triage by text with emergency keyword detection | Nothing — works on the phone alone |
| **Clinic Hub** | Full analysis: Gemma 4 narratives + RAG + parasitology + pharma | Local server via QR connect |
| **Cloud** | Same as Clinic Hub | Internet connection to app.howlvision.com |

When connected, Gemma 4 E4B acts as an agent that autonomously selects which tools to call:

| Tool | What it does | Model |
|------|-------------|-------|
| `classify_dermatology` | 6 canine + 4 feline skin conditions | EfficientNetV2-S (94.0% / 90.1%) |
| `detect_parasites` | 8 blood parasite classes in microscopy images | EfficientNetV2-S (99.87%) |
| `segment_ultrasound` | Ultrasound structure segmentation | UNet + EfficientNet-B0 |
| `search_clinical_cases` | Semantic search across 22K clinical records | Qdrant + SapBERT 768d |
| `calculate_dosage` | Drug dosage by species and weight | PostgreSQL (38 drugs, Merck source) |
| `check_drug_interactions` | Known interactions between drugs | PostgreSQL (14 interactions) |

### Symptom triage and the safety override

Owners can describe what they see in writing — vomiting, scratching, limping, anything — without ever taking a photo. The text goes through three layers in order:

1. **Emergency keyword override.** A client-side filter scans the input for ~70 substances and acute signs (chocolate, xylitol, permethrin, ibuprofen, antifreeze, seizure, collapse, blocked bladder, dystocia, anaphylaxis, and more). If any match, the app immediately surfaces a "contact a veterinarian now" banner and **never calls the matcher or the server**. This is a client-side last firewall, and it applies even if the server would otherwise return a non-emergency reading.
2. **Server triage** when connected. Gemma 4 E4B receives the symptom text plus species and returns a structured triage: top conditions, urgency levels, and a plain-language recommendation in the user's language.
3. **Offline keyword search** as a fallback. When there is no server reachable, the app falls through to a local keyword matcher against ~500 documented veterinary records, with stop-word filtering to remove common contaminants. The result is labeled honestly in the UI as **"Keyword Search — Offline"** and carries an inline disclaimer reading "Based on keyword matching. Not a diagnosis." It is not AI. It is substring matching, and the UI says so.

The relevance score in the offline path is shown as three discrete tiers (low / medium / high) instead of a percentage, because a percentage would imply a calibration the matcher does not have.

**Limitations of the safety override.** The keyword list is a starting point, not a comprehensive toxicology database. It uses substring matching, so it catches `chocolate` but not `cocoa`, `acetaminophen` but not the brand name `Tylenol`, `rodenticide` but not `mouse poison`, and it has no entry for `marijuana`, `cannabis`, `weed`, `theobromine`, `naproxen`, or several other known toxins. The list is published openly so anyone — users, veterinarians, contributors — can audit it and propose additions. Pull requests adding keywords or flagging gaps are welcome. The override exists to make the offline mode safer than substring matching against random clinical notes; it does not pretend to replace a poison-control hotline.

## Architecture

```
Phone (PWA)
  ├── Offline: ONNX Runtime Web (WASM) + IndexedDB history
  └── Online: POST /api/v1/analyze
                    │
        ┌───────────┴───────────┐
        │    Backend (FastAPI)   │
        │    Gemma 4 E4B Agent   │
        │    ↕ function calling  │
        ├────────────────────────┤
        │ Vision    │ RAG       │
        │ Service   │ Qdrant    │
        │ (PyTorch) │ 22K vecs  │
        ├────────────────────────┤
        │ PostgreSQL │ Redis    │
        └────────────────────────┘
```

## Vision models

All models trained on public datasets (Apache 2.0) and published on HuggingFace:

| Model | Classes | Accuracy | F1 | Published |
|-------|---------|----------|----|-----------|
| [vet-dermatology-canine](https://huggingface.co/ikchain/vet-dermatology-canine) | 6 (demodicosis, dermatitis, fungal, healthy, hypersensitivity, ringworm) | 94.0% | 0.923 | ikchain/vet-dermatology-canine |
| [vet-dermatology-feline](https://huggingface.co/ikchain/vet-dermatology-feline) | 4 (flea allergy, healthy, ringworm, scabies) | 90.1% | 0.902 | ikchain/vet-dermatology-feline |
| [vet-parasites-blood](https://huggingface.co/ikchain/vet-parasites-blood) | 8 (Babesia, Leishmania, Plasmodium, Toxoplasma, Trichomonad, Trypanosome + RBC and leukocyte controls) | 99.87% | 0.997 | ikchain/vet-parasites-blood |

Canine dermatology exported to ONNX INT8 (19.7MB) for offline browser inference at 675ms on mid-range Android.

## Quick start

```bash
# Prerequisites: Docker, NVIDIA GPU (16GB VRAM), Ollama with gemma4:e4b
git clone https://github.com/ikchain/howl-vision.git
cd howl-vision
cp .env.example .env
docker-compose up -d

# Open the PWA
open http://localhost:20000
```

Services start with health checks. Backend runs PostgreSQL migrations and Qdrant collection setup automatically on startup.

## Tech stack

- **LLM:** Gemma 4 E4B-it via Ollama — 8B params, multimodal, native function calling, 128K context
- **Vision:** PyTorch + timm (EfficientNetV2-S) + ONNX Runtime Web for offline
- **RAG:** Qdrant + SapBERT 768d embeddings, 22K veterinary records
- **Backend:** FastAPI + Python 3.12, agent loop with SSE streaming
- **Frontend:** React 18 + Vite + Tailwind CSS + TypeScript, PWA with service worker
- **Infra:** Docker Compose (7 services), nginx reverse proxy

## Benchmarks

| Benchmark | Result |
|-----------|--------|
| llama.cpp E2B Q4_K_M | 240 tok/s generation, 15K tok/s prompt processing, 1.9GB VRAM |
| ONNX INT8 mobile | 675ms inference, 19.7MB model size |
| Vision ECE (calibration) | 0.027 dermatology, 0.002 parasites |

Full benchmark data in [`benchmarks/`](benchmarks/).

## Design rationale

The emergency override list, the stopword filter, and the score-tier thresholds in the offline triage matcher were all derived empirically against the real corpus, not picked by intuition. The relevant logic lives in [`frontend/src/lib/triage.ts`](frontend/src/lib/triage.ts).

The matcher pre-fix returned `"Ear Infections"` for inputs like `"my dog ate chocolate"` because a handful of high-frequency tokens (`dog`, `and`) were matching uniformly across the corpus. The current implementation applies an emergency keyword override **before** the matcher runs, plus a stopword filter inside `tokenize()`, plus a discrete score tier so low-signal matches are shown as low-confidence rather than as diagnoses.

## License

Apache 2.0

## Author

**Darío Ávalos** — [Quantum AI Lab](https://quantumhowl.com)
