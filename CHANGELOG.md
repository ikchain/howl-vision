# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added (2026-04-04)
- **Vision Validation :** Formal held-out test eval with pre-registered protocol. Derma: 94.00% acc, F1=0.923, ECE=0.027 (n=433). Parasites: 99.87% acc, F1=0.997, ECE=0.002 (n=3032). 8 publishable figures + results.json — `f98c8a6`
- **Frontend Deep Ocean :** Brand overhaul — wolf logo, Inter font, Deep Ocean palette (navy-teal), About landing page, responsive grids, favicon, OG meta tags, 404 page — `78a97ec..6ac2a15`
- **SFT Pipeline :** 3 Unsloth QLoRA runs (v2, v3, narrative). Narrative conditioning dataset (5,314 imgs). Eval framework (T1-T4). Finding: base model = fine-tuned. Documented in Notion — `2659925`

### Changed (2026-04-04)
- **Frontend routes:** `/` is now About landing (was VetChat). VetChat moved to `/chat`
- **ToolStatus labels:** Spanish -> English for international judges
- **ImageUpload:** Replaced alert() with inline error state
- **About page:** Responsive layout (grid-cols-1/2/3/4 by breakpoint)

### Added
- **Scaffold:** Docker Compose with 6 services (backend, vision-service, qdrant, redis, postgres, frontend) + Ollama external. Dockerfiles, .env.example, deploy.sh — `ef3d17d`
- **Vision Service:** 3 models serving inference — dermatology (EfficientNetV2-S, 6 classes, 93.49% acc), parasites (EfficientNetV2-S, 8 classes, 99.83% acc), segmentation (smp.Unet, CPU). Verified with real images — `cdb31af`
- **SapBERT Embedder:** Singleton in vision-service with GET /embed endpoint (768d vectors). Loads from local weights — `6efe8bb`
- **RAG Indexer:** 7 CSV sources → 21,560 vectors in Qdrant (27s on GPU). Idempotent, batch upsert — `6efe8bb`
- **Semantic Search:** Backend → vision-service /embed → Qdrant. GET /api/v1/cases/search for CaseViewer — `2b776a1`
- **Pharma Lookup:** PostgreSQL tables drug_dosages (38 records) + drug_interactions (14 records). Sources: Merck Veterinary Manual, FDA/CVM. Lowercase normalized — `2b776a1`
- **Agent Orchestrator:** Gemma 4 E4B tool calling with 6 tools. Agent loop (max 3 iterations), fake streaming SSE, parallel tool execution via asyncio.gather. POST /api/v1/chat — `5008be7`
- **Frontend:** React 18 + Vite + Tailwind. VetChat (SSE streaming + image upload + tool_status), ImageDx (drag & drop + auto-analyze), CaseViewer (debounce 400ms search). 108KB gzip — `4fb5ef0`
- **Specs:** Design doc, implementation plan, RAG hybrid spec (v2 post-review), agent orchestrator spec (1040 lines, reviewed by Sonnet)

### Changed
- **Ollama:** Updated 0.18.0 → 0.20.0 (required for Gemma 4 E4B)
- **UFW:** Added rules for Docker subnets → port 11434 (Ollama connectivity from containers)
- **docker-compose.yml:** Added extra_hosts (host-gateway) for backend → Ollama on Linux
- **qdrant-client:** Pinned <1.13 for compatibility with Qdrant server 1.11.5

### Infrastructure
- Gemma 4 E4B downloaded (9.6GB) in Ollama
- Assets consolidated in data/: 4 vision .pt + 4 NLP models + 7 clinical datasets
- Serena MCP activated for gemma-4 project
- Jira: , , , , , , , ,  → Done
- Jira:  (Graph RAG Neo4j, LOW),  (QA RAG) → Created
