# Howl Vision — Veterinary AI Copilot

AI copilot for veterinary clinics in rural and resource-limited settings. Runs 100% locally using **Gemma 4 E4B** as a multimodal agent that orchestrates specialized vision models, a clinical knowledge base, and pharmacological tools — no internet, no cloud, no data leaving the clinic.

Built for the [Gemma 4 Good Hackathon](https://www.kaggle.com/competitions/gemma-4-good-hackathon) (Kaggle / Google DeepMind).

## How it works

A veterinarian describes symptoms and uploads a clinical image. Gemma 4 E4B (via Ollama) autonomously decides which tools to invoke:

| Tool | What it does | Backend |
|------|-------------|---------|
| `classify_dermatology` | Classify skin lesions into 6 categories | EfficientNetV2-S (93.49% acc) |
| `detect_parasites` | Identify blood parasites in microscopy | EfficientNetV2-S (99.83% acc) |
| `segment_ultrasound` | Segment structures in ultrasound images | UNet + EfficientNet-B0 (CPU) |
| `search_clinical_cases` | Find similar cases from ~22K records | Qdrant + SapBERT 768d |
| `calculate_dosage` | Drug dosage by species and weight | PostgreSQL lookup |
| `check_drug_interactions` | Known interactions between drugs | PostgreSQL lookup |

The response streams back via SSE with a structured clinical format: Findings, Differentials, Recommendation, Pharmacology.

## Architecture

```
Frontend (React 18)  →  Backend (FastAPI)  →  Gemma 4 E4B (Ollama)
                              ↕                      ↕ function calling
                         PostgreSQL            Vision Service (PyTorch)
                         Redis                 Qdrant (RAG)
```

7 services orchestrated via Docker Compose.

## Quick start

```bash
# Prerequisites: Docker, NVIDIA GPU (16GB VRAM), Ollama with gemma4:e4b
cp .env.example .env
docker-compose up -d

# Index the RAG knowledge base (one-time, ~30s on GPU)
docker exec gemma-4-vision-service-1 python -m src.rag.indexer

# Run pharma migrations
docker exec -i gemma-4-postgres-1 psql -U howl -d howlvision < backend/src/migrations/001_pharma.sql

# Frontend dev server
cd frontend && npm install && npm run dev
```

Open http://localhost:20000

## Services

| Service | Port | Description |
|---------|------|-------------|
| frontend | 20000 | React 18 + Vite + Tailwind |
| backend | 20001 | FastAPI gateway + agent orchestrator |
| vision-service | 20002 | Vision models + SapBERT embedder |
| qdrant | 20003 | Vector DB for RAG (~22K cases) |
| redis | 20004 | Cache + sessions |
| postgres | 20005 | Pharma data + conversations |
| ollama | 11434 | Gemma 4 E4B (shared, external) |

## Tech stack

- **LLM:** Gemma 4 E4B-it via Ollama (8B params, multimodal, function calling, 128K context)
- **Backend:** FastAPI + Python 3.12
- **Vision:** PyTorch + timm (EfficientNetV2-S) + segmentation-models-pytorch
- **RAG:** Qdrant + SapBERT 768d embeddings
- **Frontend:** React 18 + Vite + Tailwind CSS + TypeScript
- **Infra:** Docker Compose

## Project structure

```
backend/src/
  agent/       # Orchestrator, tools, executor
  api/         # FastAPI routes (chat SSE, cases search)
  rag/         # Qdrant schema, semantic search
  clinical/    # Pharma dosage + interactions

vision-service/src/
  models/      # Dermatology, parasites, segmentation
  rag/         # SapBERT embedder, indexer, formatters
  api/         # Vision endpoints + /embed

frontend/src/
  pages/       # VetChat, ImageDx, CaseViewer
  components/  # ChatMessage, ToolStatus, ImageUpload, etc.
  lib/         # SSE parser, API client
```

## Hackathon tracks

| Track | Prize | Status |
|-------|-------|--------|
| Main Track | $50,000 | Primary target |
| Health & Sciences | $10,000 | Writeup track |
| Ollama | $10,000 | Gemma 4 E4B via Ollama |
| Unsloth | $10,000 | Fine-tune pending |
| llama.cpp | $10,000 | GGUF benchmark pending |

## License

CC-BY 4.0 (if awarded). Code is public.

## Team

**Quantum AI Lab** — Dario Avalos
