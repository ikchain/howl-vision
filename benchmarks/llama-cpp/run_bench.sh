#!/usr/bin/env bash
# llama.cpp Gemma 4 E2B benchmark — RTX 4070 Ti SUPER
set -uo pipefail

LLAMA_BENCH="/tmp/llama.cpp/build/bin/llama-bench"
LLAMA_CLI="/tmp/llama.cpp/build/bin/llama-cli"
MODEL="data/models/gguf/gemma-4-E2B-it-Q4_K_M.gguf"
BENCH_DIR="benchmarks/llama-cpp"

# llama-bench does NOT have -c flag. Context is set by -p (prompt) + -n (gen).
# We vary -p to simulate different prompt lengths.

echo "=== Bench 1: pp512 tg128 (standard) ==="
${LLAMA_BENCH} -m "${MODEL}" -p 512 -n 128 -ngl 999 -fa 1 -r 3 -o json \
  > "${BENCH_DIR}/bench_pp512.json" 2>"${BENCH_DIR}/bench_pp512_stderr.txt"
echo "Exit: $?"

echo "=== Bench 2: pp128 tg256 (short prompt, long gen) ==="
${LLAMA_BENCH} -m "${MODEL}" -p 128 -n 256 -ngl 999 -fa 1 -r 3 -o json \
  > "${BENCH_DIR}/bench_pp128.json" 2>"${BENCH_DIR}/bench_pp128_stderr.txt"
echo "Exit: $?"

echo "=== Bench 3: pp1024 tg128 (longer prompt) ==="
${LLAMA_BENCH} -m "${MODEL}" -p 1024 -n 128 -ngl 999 -fa 1 -r 3 -o json \
  > "${BENCH_DIR}/bench_pp1024.json" 2>"${BENCH_DIR}/bench_pp1024_stderr.txt"
echo "Exit: $?"

echo "=== Bench 4: pp2048 tg128 (large context) ==="
${LLAMA_BENCH} -m "${MODEL}" -p 2048 -n 128 -ngl 999 -fa 1 -r 3 -o json \
  > "${BENCH_DIR}/bench_pp2048.json" 2>"${BENCH_DIR}/bench_pp2048_stderr.txt"
echo "Exit: $?"

echo "=== Bench 5: pp512 tg128 NO flash-attn (comparison) ==="
${LLAMA_BENCH} -m "${MODEL}" -p 512 -n 128 -ngl 999 -fa 0 -r 3 -o json \
  > "${BENCH_DIR}/bench_pp512_nofa.json" 2>"${BENCH_DIR}/bench_pp512_nofa_stderr.txt"
echo "Exit: $?"

echo "=== Generation test (veterinary prompt) ==="
VET_PROMPT="You are a veterinary AI assistant. A farmer brings a cow with lethargy, reduced milk, pale membranes, fever 39.8C, tick exposure history. Differential diagnoses?"
${LLAMA_CLI} -m "${MODEL}" -p "${VET_PROMPT}" -n 256 -ngl 999 -c 2048 --temp 0.7 -fa 1 \
  2>"${BENCH_DIR}/cli_stderr.txt" > "${BENCH_DIR}/cli_output.txt"
echo "Exit: $?"

echo "=== GPU memory snapshot ==="
nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu --format=csv,noheader \
  > "${BENCH_DIR}/gpu_memory.txt" 2>/dev/null
echo "Exit: $?"

echo "=== All benchmarks complete ==="
