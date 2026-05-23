"""Bench rápido: latência Ollama sequencial vs paralela + dicas Vulkan/VRAM."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

URL = "http://127.0.0.1:11434/api/generate"
SHORT_BODY = {
    "model": "qwen3:14b",
    "prompt": "Answer with exactly one word: OK",
    "stream": False,
    "options": {"num_predict": 12},
}


def one_call(i: int) -> tuple[int, float, str]:
    data = json.dumps({**SHORT_BODY, "prompt": SHORT_BODY["prompt"] + f" ({i})"}).encode()
    req = urllib.request.Request(URL, data=data, headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            r.read()
        dt = (time.perf_counter() - t0) * 1000
        return i, dt, "ok"
    except urllib.error.HTTPError as e:
        return i, (time.perf_counter() - t0) * 1000, f"http {e.code}"
    except Exception as e:
        return i, (time.perf_counter() - t0) * 1000, str(e)[:80]


def main() -> None:
    print("=== Ollama bench (127.0.0.1:11434) ===\n")

    # Warm-up (primeira chamada costuma ser mais lenta)
    print("Warm-up 1 request...")
    _, ms, st = one_call(0)
    print(f"  warm-up: {ms:.0f} ms ({st})\n")

    # Sequencial x3
    print("Sequencial (3 chamadas, uma apos a outra):")
    seq_ms = []
    for i in range(1, 4):
        _, ms, st = one_call(i)
        seq_ms.append(ms)
        print(f"  #{i}: {ms:.0f} ms ({st})")
    print(f"  media seq: {sum(seq_ms)/len(seq_ms):.0f} ms\n")

    # Paralelo x5
    n_parallel = 5
    print(f"Paralelo ({n_parallel} chamadas ao mesmo tempo - threads):")
    t_wall = time.perf_counter()
    results = []
    with ThreadPoolExecutor(max_workers=n_parallel) as ex:
        futs = [ex.submit(one_call, 100 + k) for k in range(n_parallel)]
        for fut in as_completed(futs):
            results.append(fut.result())
    wall_ms = (time.perf_counter() - t_wall) * 1000
    results.sort(key=lambda x: x[0])
    for i, ms, st in results:
        print(f"  task {i}: {ms:.0f} ms ({st})")
    print(f"  relogio total (wall): {wall_ms:.0f} ms")
    slowest = max(ms for _, ms, _ in results)
    sum_ms = sum(ms for _, ms, _ in results)
    print(f"  chamada mais lenta: {slowest:.0f} ms")
    print(f"  soma das latencias (cliente): {sum_ms:.0f} ms")
    print()
    # Paralelo no servidor: cada cliente mede do inicio ao fim; wall ~ max(latencias),
    # nao ~ soma (seria ~5x em fila puramente serial no servidor).
    if wall_ms <= slowest * 1.25 and sum_ms > wall_ms * 1.5:
        print(
            "Interpretacao: wall perto da mais lenta e bem menor que a soma ->"
            " varias requisicoes avancaram em paralelo no Ollama (ate o limite da GPU/fila).\n"
        )
    elif wall_ms >= sum_ms * 0.85:
        print(
            "Interpretacao: wall parece sequencial ou fila pesada (uma por vez no efeito global).\n"
        )
    else:
        print(
            "Interpretacao: paralelismo parcial ou mistura de fila + overlap.\n"
        )

    # /api/ps VRAM hint
    print("GET /api/ps (VRAM: modelo na GPU costuma ter size_vram alto):")
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/ps", timeout=10) as r:
            ps = json.loads(r.read().decode())
        for m in ps.get("models", []):
            name = m.get("model", "?")
            sv = m.get("size_vram")
            total = m.get("size")
            print(f"  {name}: size_vram={sv} bytes (~{sv // (1024**3) if sv else 0} GiB), size={total}")
    except Exception as e:
        print(f"  erro: {e}")

    print()
    print(
        "Vulkan: Ollama nao costuma imprimir 'Vulkan' no JSON.\n"
        "Sinais no Windows: (1) Adrenalin mostra GPU alta durante generate;\n"
        "(2) /api/ps com size_vram perto do tamanho do modelo => pesos na VRAM;\n"
        "(3) logs do ollama serve ou OLLAMA_DEBUG=1 podem citar o backend.\n"
    )


if __name__ == "__main__":
    main()
