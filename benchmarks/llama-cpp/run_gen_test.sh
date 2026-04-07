#!/usr/bin/env bash
set -uo pipefail

LLAMA_CLI="/tmp/llama.cpp/build/bin/llama-cli"
MODEL="data/models/gguf/gemma-4-E2B-it-Q4_K_M.gguf"
BENCH_DIR="benchmarks/llama-cpp"

VET_PROMPT="You are a veterinary AI assistant for rural clinics. A farmer brings a 3-year-old dairy cow with lethargy, reduced milk production, pale mucous membranes, and mild fever of 39.8C. The cow has been on pasture with tick exposure history. What are the most likely differential diagnoses and recommended diagnostic steps?"

echo "=== Generation test via llama-cli with --jinja ==="
${LLAMA_CLI} \
  -m "${MODEL}" \
  --jinja \
  --single-turn \
  -p "${VET_PROMPT}" \
  -n 256 \
  -ngl 999 \
  -c 2048 \
  --temp 0.7 \
  -fa on \
  --perf \
  2>"${BENCH_DIR}/cli_stderr.txt" > "${BENCH_DIR}/cli_output.txt"
echo "Exit: $?"

echo "=== GPU memory after generation ==="
nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu --format=csv,noheader \
  > "${BENCH_DIR}/gpu_memory.txt" 2>/dev/null
echo "Exit: $?"

echo "=== Done ==="
