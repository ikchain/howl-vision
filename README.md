# Howl Vision

**Accessible veterinary diagnosis where there is no specialist.**

A pet owner at 3am with a worried dog. A lab technician in a rural clinic with a microscope and no dermatologist. A shelter volunteer screening 40 dogs after a rescue. They all need the same thing: a second opinion from someone who has seen this before.

Howl Vision is a veterinary AI copilot that puts dermatology classification, blood parasite detection, clinical knowledge search, and drug interaction checks into a single PWA — usable on any phone, with or without internet.

Built for the [Gemma 4 Good Hackathon](https://www.kaggle.com/competitions/gemma-4-good-hackathon) (Kaggle / Google DeepMind, 2026).

**Live demo:** [app.howlvision.com](https://app.howlvision.com)

## What it does

The app works in three modes depending on connectivity:

| Mode | What's available | Requires |
|------|-----------------|----------|
| **Offline** | Skin lesion classification via ONNX (sub-second, 20MB model) + symptom triage | Nothing — works on the phone alone |
| **Clinic Hub** | Full analysis: Gemma 4 narratives + RAG + parasitology + pharma | Local server via QR connect |
| **Cloud** | Same as Clinic Hub | Internet connection to app.howlvision.com |

When connected, Gemma 4 E4B acts as an agent that autonomously selects which tools to call:

| Tool | What it does | Model |
|------|-------------|-------|
| `classify_dermatology` | 6 canine + 5 feline skin conditions | EfficientNetV2-S (94.0% / 90.1%) |
| `detect_parasites` | Blood parasites in microscopy images | EfficientNetV2-S (99.87%) |
| `segment_ultrasound` | Ultrasound structure segmentation | UNet + EfficientNet-B0 |
| `search_clinical_cases` | Semantic search across 22K clinical records | Qdrant + SapBERT 768d |
| `calculate_dosage` | Drug dosage by species and weight | PostgreSQL (38 drugs, Merck source) |
| `check_drug_interactions` | Known interactions between drugs | PostgreSQL (14 interactions) |

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
| [vet-dermatology-feline](https://huggingface.co/ikchain/vet-dermatology-feline) | 5 (fungal, healthy, ringworm, scabies, sporotrichosis) | 90.1% | 0.902 | ikchain/vet-dermatology-feline |
| [vet-parasites-blood](https://huggingface.co/ikchain/vet-parasites-blood) | 12 (Leishmania, Plasmodium, Babesia, Toxoplasma, etc.) | 99.87% | 0.997 | ikchain/vet-parasites-blood |

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

## License

Apache 2.0

## Author

**Darío Ávalos** — [Quantum AI Lab](https://quantumhowl.com)
