#!/usr/bin/env python3
"""Consolidate llama.cpp benchmark results into benchmark_e2b.json"""
import json
import os
import re
from datetime import datetime

BENCH_DIR = "benchmarks/llama-cpp"
GGUF_DIR = "data/models/gguf"


def load_bench(filename):
    """Load a llama-bench JSON result file."""
    path = os.path.join(BENCH_DIR, filename)
    if not os.path.exists(path):
        return None
    with open(path, "r") as f:
        content = f.read().strip()
        if not content:
            return None
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Try JSONL
            lines = [json.loads(line) for line in content.split("\n") if line.strip()]
            return lines


def extract_bench_summary(data):
    """Extract prompt processing and generation speeds from bench data."""
    if not data:
        return None
    summary = {}
    for entry in data:
        if entry.get("n_prompt", 0) > 0:
            summary["prompt_processing"] = {
                "n_prompt": entry["n_prompt"],
                "avg_tokens_per_sec": round(entry["avg_ts"], 1),
                "stddev_tokens_per_sec": round(entry["stddev_ts"], 1),
                "samples_tokens_per_sec": [round(s, 1) for s in entry["samples_ts"]],
                "avg_time_ms": round(entry["avg_ns"] / 1e6, 2),
                "flash_attn": entry.get("flash_attn", False),
            }
        elif entry.get("n_gen", 0) > 0:
            summary["generation"] = {
                "n_gen": entry["n_gen"],
                "avg_tokens_per_sec": round(entry["avg_ts"], 1),
                "stddev_tokens_per_sec": round(entry["stddev_ts"], 1),
                "samples_tokens_per_sec": [round(s, 1) for s in entry["samples_ts"]],
                "avg_time_ms": round(entry["avg_ns"] / 1e6, 2),
                "flash_attn": entry.get("flash_attn", False),
            }
    return summary


# Model info
model_file = "gemma-4-E2B-it-Q4_K_M.gguf"
model_path = os.path.join(GGUF_DIR, model_file)
model_size = os.path.getsize(model_path) if os.path.exists(model_path) else 0

results = {
    "metadata": {
        "date": datetime.now().isoformat(),
        "llama_cpp_commit": "761797f",
        "model": "Gemma 4 E2B-it",
        "model_params": "4.65B",
        "quantization": "Q4_K_M",
        "bits_per_weight": 5.32,
        "format": "GGUF",
        "source_repo": "unsloth/gemma-4-E2B-it-GGUF",
        "gpu": "NVIDIA RTX 4070 Ti SUPER",
        "gpu_vram_mib": 16376,
        "gpu_compute_capability": "8.9",
        "cpu": "AMD Ryzen 9 9900X 12-Core",
        "framework": "llama.cpp",
        "hackathon_track": "llama.cpp ($10K)",
    },
    "model_info": {
        "file": model_file,
        "size_bytes": model_size,
        "size_mb": round(model_size / (1024 * 1024), 1),
        "size_gb": round(model_size / (1024 * 1024 * 1024), 2),
        "architecture": "gemma4",
        "context_train": 131072,
        "n_layers": 35,
        "n_embd": 1536,
        "n_head": 8,
        "n_head_kv": 1,
        "vocab_size": 262144,
        "sliding_window": 512,
    },
    "benchmarks": {},
    "generation_test": {},
    "memory_usage": {},
}

# Parse llama-bench results
bench_configs = {
    "pp512_tg128_fa": ("bench_pp512.json", "512-token prompt, 128-token generation, flash attention ON"),
    "pp128_tg256_fa": ("bench_pp128.json", "128-token prompt, 256-token generation, flash attention ON"),
    "pp1024_tg128_fa": ("bench_pp1024.json", "1024-token prompt, 128-token generation, flash attention ON"),
    "pp2048_tg128_fa": ("bench_pp2048.json", "2048-token prompt, 128-token generation, flash attention ON"),
    "pp512_tg128_no_fa": ("bench_pp512_nofa.json", "512-token prompt, 128-token generation, flash attention OFF"),
}

for key, (filename, description) in bench_configs.items():
    data = load_bench(filename)
    summary = extract_bench_summary(data)
    if summary:
        summary["description"] = description
        results["benchmarks"][key] = summary

# Parse generation test
cli_output_path = os.path.join(BENCH_DIR, "cli_output.txt")
if os.path.exists(cli_output_path):
    with open(cli_output_path, "r") as f:
        cli_content = f.read()

    # Extract perf line: [ Prompt: 1290,3 t/s | Generation: 231,4 t/s ]
    perf_match = re.search(
        r"\[\s*Prompt:\s*([\d,\.]+)\s*t/s\s*\|\s*Generation:\s*([\d,\.]+)\s*t/s\s*\]",
        cli_content,
    )
    if perf_match:
        # Handle comma as decimal separator (locale)
        pp_speed = float(perf_match.group(1).replace(",", "."))
        gen_speed = float(perf_match.group(2).replace(",", "."))
    else:
        pp_speed = None
        gen_speed = None

    results["generation_test"] = {
        "prompt_type": "veterinary diagnostic scenario",
        "max_tokens": 256,
        "context_size": 2048,
        "temperature": 0.7,
        "flash_attn": True,
        "prompt_processing_tokens_per_sec": pp_speed,
        "generation_tokens_per_sec": gen_speed,
    }

# Parse stderr for memory breakdown
cli_stderr_path = os.path.join(BENCH_DIR, "cli_stderr.txt")
if os.path.exists(cli_stderr_path):
    with open(cli_stderr_path, "r") as f:
        stderr_content = f.read()

    # Extract memory breakdown
    cuda_match = re.search(
        r"CUDA0.*?\|\s*(\d+)\s*=\s*(\d+)\s*\+\s*\(\s*(\d+)\s*=\s*(\d+)\s*\+\s*(\d+)\s*\+\s*(\d+)\s*\)",
        stderr_content,
    )
    if cuda_match:
        results["memory_usage"]["gpu"] = {
            "total_vram_mib": int(cuda_match.group(1)),
            "free_after_load_mib": int(cuda_match.group(2)),
            "model_total_mib": int(cuda_match.group(3)),
            "model_weights_mib": int(cuda_match.group(4)),
            "kv_cache_mib": int(cuda_match.group(5)),
            "compute_buffer_mib": int(cuda_match.group(6)),
        }

    host_match = re.search(r"Host\s*\|\s*(\d+)\s*=\s*(\d+)", stderr_content)
    if host_match:
        results["memory_usage"]["host"] = {
            "total_mib": int(host_match.group(1)),
            "model_weights_mib": int(host_match.group(2)),
        }

# GPU memory snapshot
gpu_mem_path = os.path.join(BENCH_DIR, "gpu_memory.txt")
if os.path.exists(gpu_mem_path):
    with open(gpu_mem_path, "r") as f:
        mem_line = f.read().strip()
    parts = [p.strip() for p in mem_line.split(",")]
    if len(parts) >= 2:
        results["memory_usage"]["nvidia_smi_snapshot"] = {
            "used": parts[0],
            "total": parts[1],
            "gpu_utilization": parts[2] if len(parts) > 2 else "N/A",
        }

# Summary for quick reference
pp_speeds = []
gen_speeds = []
for key, bench in results["benchmarks"].items():
    if "fa" in key and "no_fa" not in key:
        if "prompt_processing" in bench:
            pp_speeds.append(bench["prompt_processing"]["avg_tokens_per_sec"])
        if "generation" in bench:
            gen_speeds.append(bench["generation"]["avg_tokens_per_sec"])

results["summary"] = {
    "prompt_processing_range_tokens_per_sec": f"{min(pp_speeds):.0f} - {max(pp_speeds):.0f}" if pp_speeds else "N/A",
    "generation_range_tokens_per_sec": f"{min(gen_speeds):.0f} - {max(gen_speeds):.0f}" if gen_speeds else "N/A",
    "flash_attn_pp_speedup": None,
    "model_fits_in_vram": True,
    "gpu_memory_used_mib": results["memory_usage"].get("gpu", {}).get("model_total_mib"),
    "host_memory_used_mib": results["memory_usage"].get("host", {}).get("total_mib"),
    "verdict": "Gemma 4 E2B Q4_K_M runs fully on GPU with excellent performance for edge deployment",
}

# Calculate flash attention speedup
fa_bench = results["benchmarks"].get("pp512_tg128_fa", {})
nofa_bench = results["benchmarks"].get("pp512_tg128_no_fa", {})
if fa_bench and nofa_bench:
    fa_pp = fa_bench.get("prompt_processing", {}).get("avg_tokens_per_sec", 0)
    nofa_pp = nofa_bench.get("prompt_processing", {}).get("avg_tokens_per_sec", 0)
    if nofa_pp > 0:
        results["summary"]["flash_attn_pp_speedup"] = f"{fa_pp / nofa_pp:.2f}x"

    fa_gen = fa_bench.get("generation", {}).get("avg_tokens_per_sec", 0)
    nofa_gen = nofa_bench.get("generation", {}).get("avg_tokens_per_sec", 0)
    if nofa_gen > 0:
        results["summary"]["flash_attn_gen_speedup"] = f"{fa_gen / nofa_gen:.2f}x"


# Write final output
output_path = os.path.join(BENCH_DIR, "benchmark_e2b.json")
with open(output_path, "w") as f:
    json.dump(results, f, indent=2)

print(f"Results written to: {output_path}")
print()
print("=== SUMMARY ===")
print(f"Model: {results['metadata']['model']} ({results['metadata']['quantization']})")
print(f"Size: {results['model_info']['size_gb']} GB ({results['model_info']['size_mb']} MB)")
print(f"GPU: {results['metadata']['gpu']}")
print()

for key, bench in results["benchmarks"].items():
    pp = bench.get("prompt_processing", {})
    gen = bench.get("generation", {})
    desc = bench.get("description", key)
    print(f"  {desc}:")
    if pp:
        print(f"    Prompt:     {pp['avg_tokens_per_sec']:>10.1f} t/s (+/- {pp['stddev_tokens_per_sec']:.1f})")
    if gen:
        print(f"    Generation: {gen['avg_tokens_per_sec']:>10.1f} t/s (+/- {gen['stddev_tokens_per_sec']:.1f})")

print()
gt = results.get("generation_test", {})
if gt.get("prompt_processing_tokens_per_sec"):
    print(f"  Real-world veterinary prompt:")
    print(f"    Prompt:     {gt['prompt_processing_tokens_per_sec']:>10.1f} t/s")
    print(f"    Generation: {gt['generation_tokens_per_sec']:>10.1f} t/s")

print()
mem = results.get("memory_usage", {}).get("gpu", {})
if mem:
    print(f"  GPU Memory: {mem.get('model_total_mib')} MiB model / {mem.get('total_vram_mib')} MiB total")
    print(f"  Host Memory: {results.get('memory_usage', {}).get('host', {}).get('total_mib')} MiB")

fa_speedup = results.get("summary", {}).get("flash_attn_pp_speedup")
if fa_speedup:
    print(f"  Flash Attention PP speedup: {fa_speedup}")
