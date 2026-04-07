# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added (2026-04-07)
- **Text Triage UI :** Toggle `[Photo | Symptoms]` en Capture.tsx con ARIA radiogroup. Modo Symptoms con textarea (5-2000 chars), char counter, submit deshabilitado hasta válido, integración con `triage()` lib existente. Loading UX progresivo (`Checking symptoms...` → `Still working...` a los 3.5s). Resultado renderizado via nuevo `TriageResultCard.tsx` (~145 líneas) — emergency banner / source badge / inline disclaimer / tier indicator (3 dots discretos low/medium/high) / empty state. Module selector se oculta en symptoms mode. State cleared on toggle entre modos. Mergeado en `ca442dc`.
- **Discriminated union HistoryRecord:** `types/index.ts` refactor — `AnalysisRecord` renamed a `ImageAnalysisRecord` con campo `kind:"image"` añadido. Nueva interface `TriageRecord` con `kind:"triage"`, `symptomsText`, `topCondition`, `urgency`, `recommendationSummary`, `fullResult` (no opcional). `HistoryRecord = ImageAnalysisRecord | TriageRecord` discriminated union. Constant `TRIAGE_SUMMARY_MAX_LEN = 200`.
- **IndexedDB v1→v2 migration:** `db.ts` `DB_VERSION` bumped a 2. Upgrade callback usa `oldVersion` parameter explícito y `transaction.objectStore()` (NO `db.transaction()` que lanza `InvalidStateError`). Records v1 reciben `kind:"image"` automáticamente. `saveTriage()` añadido (separado de `saveAnalysis()` porque triage no tiene File ni thumbnail).
- **History.tsx render union:** Switch sobre `record.kind` PRIMERO. `ImageRow` (thumbnail + classification) y `TriageRow` (FileText icon + "Symptom check" label) componentes separados. Detail view discriminado por kind: image → ResultCard, triage → blockquote `"You wrote: ..."` + TriageResultCard.
- **Profile triageHint:** `profile.ts` `ProfileConfig` extendido con `triageHint` per profile (pet_owner / lab_tech / field_worker).
- **Spec  (889 líneas):** `docs/superpowers/specs/2026-04-07-text-triage-ui-design.md` con 16 design decisions, 26 acceptance criteria, schemas TypeScript formales, score tier thresholds empíricamente derivados, 3 reviews de agentes integrados (senior-code-engineer ×2, senior-ui-architect, ml-eval-rigor ×2), §13 self-review substantive (no performativa).

### Fixed (2026-04-07) — SAFETY BLOCKING 
- **Emergency keyword override en triage.ts:** ~70 keywords en `triage()` entry point, escaneadas ANTES de decidir entre server y offline. Aplica incluso si el server responde — client-side last firewall. Lista incluye toxic ingestion (chocolate, xylitol, grape, raisin, onion, garlic, ibuprofen, acetaminophen, paracetamol, aspirin, metaldehyde, rat poison, rodenticide, antifreeze, ethylene glycol, **permethrin** crítico para gatos, lilies, sago palm, macadamia, avocado, alcohol, ethanol), neurológico/cardiopulmonar (seizure, convulsion, unconscious, collapse, can't breathe, gasping, blue/pale gums), GDV (bloat, torsion, distended abdomen), hemorragia (bleeding, blood in urine/stool, vomiting blood), trauma (hit by car, broken bone, shock), térmico (heatstroke, hypothermia, electrocution), urinario felino (can't urinate, blocked bladder), dystocia, anaphylaxis. **Smoking gun verificado empíricamente**: matcher pre-fix devolvía "Ear Infections monitor" para `"my dog ate chocolate and is vomiting"` porque el token `"and"` matcheaba 54/104 records.
- **Stopword filter en triage.ts:** ~50 stopwords en `tokenize()` antes del matching offline. Incluye especies (dog, cat, rabbit — todas matcheaban uniformemente), function words inglesas (`"and"` era el #1 contaminator), SOAP boilerplate validado contra el corpus real (seems, noted, condition, suspected).
- **Honest source badge:** `"Local AI"` reemplazado por `"Keyword Search — Offline"` para el modo offline. `"Clinic Hub"` mantenido para server (consistencia visual con ResultCard). Inline disclaimer obligatorio cuando offline: `"Based on keyword matching. Not a diagnosis."` (text-content-muted xs, NO tooltip).
- **Score metric:** `matchScore` cambiado de `Math.min(hits / total, 1)` a `hits / total` post-stopwords (clamp innecesario). Display tier discreto: `>=0.20 high`, `>=0.08 medium`, `>0 low`, `0 null` (empty state). Cuts derivados empíricamente del corpus por ml-eval-rigor.
- **Server timeout:** `serverTriage()` `15000ms → 10000ms` (rural connectivity reality).

### Fixed (2026-04-07) — Writeup  verification (3 correcciones críticas)
- **Atribución epitafio Byron:** la frase famosa `"Beauty without Vanity, Strength without Insolence, Courage without Ferocity, and all the virtues of Man without his Vices"` NO la escribió Byron — la escribió su amigo John Hobhouse (Wikipedia confirma). Cierre del writeup reescrito atribuyendo correctamente: versos a Byron (`"I never knew but one — and here he lies"`), prosa famosa a Hobhouse, dato añadido del monumento de Boatswain en Newstead Abbey siendo más grande que la futura tumba de Byron. Commits `ec5d66b`.
- **Parásitos AUROC sobreestimado:** writeup decía `1.000`, real medido `0.9995` → corregido a `0.999` en ambos drafts.
- **Enumeración 6 tools incorrecta:** writeup conflagaba canine + feline dermatology como 2 tools y olvidaba `check_drug_interactions`. Corregido para reflejar `backend/src/agent/tools.py` 1:1 (classify_dermatology, detect_parasites, segment_ultrasound, search_clinical_cases, calculate_dosage, check_drug_interactions).
- **Cifra OMS rabia 59 000 muertes/año** insertada (verificada contra WHO Fact Sheet).

### Added (2026-04-06)
- **Hetzner Deploy :** app.howlvision.com live. SSH tunnel (40220/40221) from home PC GPU to Hetzner Docker. Nginx SSL, iptables, docker-compose.prod.yml. $0 cost (no ORI needed).
- **GitHub Public Repo :** github.com/ikchain/howl-vision with full commit history. README rewritten with narrative + HF model links.
- **History Detail View:** Tap analysis record to open full ResultCard in full-screen scrollable overlay.
- **Backend Startup Init:** Lifespan handler runs PostgreSQL migrations + Qdrant collection setup automatically.

### Fixed (2026-04-06)
- **E2E Polish (10 fixes):** Source badge on ResultCard, ONNX loading feedback, file input retry, object URL leak (W3), profile change in About, history timestamps+loading, About subtitle One Health, QR port configurable (W7), offline triage species (W5).
- **Ollama routing:** routes_triage.py + executor.py replaced bare `ollama.chat()` with httpx via settings.ollama_base_url (required for tunnel deploy).
- **Same-origin API:** getEffectiveServerUrl() falls back to window.location.origin for deployed PWA.
- **ConnectionBadge:** Uses same-origin health check. Nginx proxies /health to backend.
- **Onboarding gate:** Profile selection re-renders via tick counter (navigate /capture→/capture was a no-op).
- **About page:** /chat link fixed to /capture, min-h-screen removed, mobile-first layout, pipeline row.
- **Gitignore:** Training artifacts (~198MB), .claude/, .superpowers/, .env.*, *.tsbuildinfo protected.

### Added (2026-04-05)
- **One Health Pivot :** PWA mobile-first with 3 modes (offline text, offline ONNX, server). BottomTabBar, QR Connect (jsQR), Onboarding (3 profiles), ConnectionBadge, Capture with species/module selector, IndexedDB history, ONNX INT8 browser inference (675ms), offline triage (500 symptoms + 38 pharma) — `ab6c264..c5aad57`
- **Feline Dermatology Model :** EfficientNetV2-S retrained 58%→90.1% (F1=0.902, n=152). Training script with augmentation, Wilson CIs, early stopping — `56c5978`
- **HuggingFace Models :** 3 models published: ikchain/vet-dermatology-canine, vet-dermatology-feline, vet-parasites-blood
- **llama.cpp Benchmark :** E2B Q4_K_M: 240 t/s gen, 15K t/s PP, 1.9GB VRAM on RTX 4070 Ti SUPER — `cd04a1f`
- **Consolidated Benchmarks :** benchmarks_final.json with all metrics (vision + ONNX + SFT + llama.cpp) — `82c08ab..a6e3df2`
- **Backend endpoints:** POST /api/v1/analyze (FormData), POST /api/v1/triage (JSON), GET /api/v1/qr — `62cabdf`

### Fixed (2026-04-05)
- **Vision response contract (C1):** Backend now correctly reads predictions array from vision service — `17ae97c`
- **Triage response contract (C2):** Added possible_conditions to TriageResponse — `17ae97c`
- **Feline urgency class (C3):** Added "Health" to HEALTHY_CLASSES in both backend and frontend — `17ae97c`
- **CORS for QR mobile (W1):** Wildcard CORS for LAN device connections — `17ae97c`
- **Analyze timeout (W4):** 60s AbortSignal on /api/v1/analyze fetch — `17ae97c`
- **Pharma species mapping (W6):** canine→dog, feline→cat in lookupDrug — `17ae97c`
- **ONNX lazy load:** Dynamic import() instead of eager 20MB load on module init — `c5aad57`
- **ResultCard source distinction:** Gray border (local_ai) vs teal (server) — `c5aad57`

### Changed (2026-04-05)
- **Vision Service:** 3→4 models (added feline dermatology with species dispatch on /dermatology?species=)
- **Frontend routing:** Added /connect (QR), /onboarding. Onboarding gate before main app
- **Benchmarks README:** Clarified P0 comparison as definitive, historical files documented

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
