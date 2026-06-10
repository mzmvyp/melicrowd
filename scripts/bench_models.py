"""Benchmark comparativo de modelos Ollama para as decisões JSON do MeliCrowd.

Compara qwen3:14b vs qwen3:8b (ou os modelos passados em argv) usando EXATAMENTE
as opções que o ``llm/qwen_client.py`` usa em produção (``format=json``,
``think=false``, ``temperature=0.3``, ``num_predict=256``, ``num_ctx=4096``) e um
prompt de decisão realista (estilo ``decide_session``).

Mede, por modelo:
- Latência de warm-up e sequencial (média de N chamadas).
- Throughput paralelo (decisões/s) e wall time a uma dada concorrência.
- Taxa de JSON válido (parse com sucesso e é objeto).
- Tokens de saída/s (do campo ``eval_count``/``eval_duration`` do Ollama).

Uso:
    python scripts/bench_models.py                       # 14b vs 8b, concorrência 8
    python scripts/bench_models.py qwen3:8b --concurrency 8 --parallel 24
    python scripts/bench_models.py qwen3:14b qwen3:8b -c 4 -p 16 -s 3

Não depende de libs externas (só stdlib) — roda no Python do host sem venv.
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

URL = "http://127.0.0.1:11434/api/generate"

# Prompt de decisão realista (estilo decide_session) — força JSON pequeno.
PROMPT = (
    "Você é um comprador online brasileiro. Persona: Ana, 34 anos, classe B, "
    "analista, São Paulo/SP, sensibilidade a preço 0.6, propensão a abandono 0.4, "
    "categorias preferidas: eletrônicos, casa. É terça à noite.\n"
    "Decida a intenção da sessão e responda APENAS com um objeto JSON com as chaves: "
    '"session_intent" (um de: browse, research, compare, purchase), '
    '"target_categories" (lista de strings), "budget_brl" (número ou null), '
    '"purchase_probability" (0.0 a 1.0), "reasoning" (string curta).'
)

# Mesmas options do llm/qwen_client.py.
BASE_OPTIONS = {"temperature": 0.3, "num_predict": 256, "num_ctx": 4096}


def _body(model: str, salt: int) -> bytes:
    return json.dumps(
        {
            "model": model,
            "prompt": f"{PROMPT}\n(variação {salt})",
            "stream": False,
            "format": "json",
            "think": False,
            "options": BASE_OPTIONS,
        }
    ).encode()


def one_call(model: str, salt: int) -> dict:
    """Faz 1 chamada e retorna métricas: latência, json_ok, tokens/s."""
    req = urllib.request.Request(
        URL, data=_body(model, salt), headers={"Content-Type": "application/json"}
    )
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            payload = json.loads(r.read().decode())
        latency_ms = (time.perf_counter() - t0) * 1000
    except urllib.error.HTTPError as e:
        return {"ok": False, "latency_ms": (time.perf_counter() - t0) * 1000, "err": f"http {e.code}", "json_ok": False, "tok_s": 0.0}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "latency_ms": (time.perf_counter() - t0) * 1000, "err": str(e)[:80], "json_ok": False, "tok_s": 0.0}

    resp_text = payload.get("response", "")
    json_ok = False
    try:
        parsed = json.loads(resp_text)
        json_ok = isinstance(parsed, dict) and bool(parsed)
    except json.JSONDecodeError:
        json_ok = False

    eval_count = payload.get("eval_count") or 0
    eval_dur_ns = payload.get("eval_duration") or 0
    tok_s = (eval_count / (eval_dur_ns / 1e9)) if eval_dur_ns else 0.0

    return {
        "ok": True,
        "latency_ms": latency_ms,
        "err": "",
        "json_ok": json_ok,
        "tok_s": tok_s,
        "eval_count": eval_count,
    }


def bench_model(model: str, *, seq: int, parallel: int, concurrency: int) -> dict:
    print(f"\n{'='*70}\nModelo: {model}\n{'='*70}")

    print("Warm-up (carrega o modelo na VRAM)...")
    w = one_call(model, 0)
    print(f"  warm-up: {w['latency_ms']:.0f} ms ({'ok' if w['ok'] else w['err']}), "
          f"json_ok={w['json_ok']}, {w['tok_s']:.1f} tok/s")

    print(f"\nSequencial ({seq} chamadas):")
    seq_lat, seq_tok = [], []
    seq_json_ok = 0
    for i in range(1, seq + 1):
        r = one_call(model, i)
        seq_lat.append(r["latency_ms"])
        if r["tok_s"]:
            seq_tok.append(r["tok_s"])
        seq_json_ok += int(r["json_ok"])
        print(f"  #{i}: {r['latency_ms']:.0f} ms | json_ok={r['json_ok']} | {r['tok_s']:.1f} tok/s")
    med_lat = statistics.median(seq_lat) if seq_lat else 0.0
    avg_tok = statistics.mean(seq_tok) if seq_tok else 0.0

    print(f"\nParalelo ({parallel} chamadas, concorrência {concurrency}):")
    t_wall = time.perf_counter()
    results = []
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        futs = [ex.submit(one_call, model, 1000 + k) for k in range(parallel)]
        for fut in as_completed(futs):
            results.append(fut.result())
    wall_s = time.perf_counter() - t_wall
    ok = [r for r in results if r["ok"]]
    par_json_ok = sum(int(r["json_ok"]) for r in results)
    throughput = parallel / wall_s if wall_s else 0.0
    par_lat = [r["latency_ms"] for r in ok]
    p95 = sorted(par_lat)[int(len(par_lat) * 0.95)] if par_lat else 0.0

    print(f"  wall: {wall_s:.1f} s | throughput: {throughput:.2f} decisões/s")
    print(f"  latência paralela média: {statistics.mean(par_lat):.0f} ms | p95: {p95:.0f} ms" if par_lat else "  sem sucesso")
    print(f"  JSON válido: {par_json_ok}/{parallel} ({100*par_json_ok/parallel:.0f}%)")
    errs = [r["err"] for r in results if not r["ok"]]
    if errs:
        print(f"  erros: {len(errs)} (ex.: {errs[0]})")

    return {
        "model": model,
        "seq_median_ms": med_lat,
        "seq_tok_s": avg_tok,
        "seq_json_ok": f"{seq_json_ok}/{seq}",
        "par_throughput": throughput,
        "par_wall_s": wall_s,
        "par_p95_ms": p95,
        "par_json_ok_pct": 100 * par_json_ok / parallel if parallel else 0,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Bench comparativo de modelos Ollama (decisões JSON).")
    ap.add_argument("models", nargs="*", default=["qwen3:14b", "qwen3:8b"], help="modelos a comparar")
    ap.add_argument("-s", "--seq", type=int, default=3, help="chamadas sequenciais")
    ap.add_argument("-p", "--parallel", type=int, default=24, help="total de chamadas paralelas")
    ap.add_argument("-c", "--concurrency", type=int, default=8, help="concorrência (workers)")
    args = ap.parse_args()

    models = args.models or ["qwen3:14b", "qwen3:8b"]
    print(f"=== MeliCrowd bench de modelos ===\nmodelos={models} seq={args.seq} "
          f"parallel={args.parallel} concurrency={args.concurrency}")

    summary = [bench_model(m, seq=args.seq, parallel=args.parallel, concurrency=args.concurrency) for m in models]

    print(f"\n\n{'='*70}\nRESUMO COMPARATIVO\n{'='*70}")
    hdr = f"{'modelo':<14}{'seq med(ms)':>13}{'tok/s':>9}{'thrpt(dec/s)':>14}{'p95(ms)':>10}{'json%':>8}"
    print(hdr)
    print("-" * len(hdr))
    for s in summary:
        print(f"{s['model']:<14}{s['seq_median_ms']:>13.0f}{s['seq_tok_s']:>9.1f}"
              f"{s['par_throughput']:>14.2f}{s['par_p95_ms']:>10.0f}{s['par_json_ok_pct']:>7.0f}%")
    print()
    if len(summary) >= 2:
        best = max(summary, key=lambda s: s["par_throughput"])
        print(f"Maior throughput paralelo: {best['model']} "
              f"({best['par_throughput']:.2f} decisões/s)")


if __name__ == "__main__":
    main()
