"""Tiny load benchmark for objective (e) — performance evaluation.

Measures latency percentiles and throughput for two representative paths:
  1. POST /auth/login        — CPU-bound (bcrypt verify), the expensive path.
  2. GET  /users/me          — token-validation + single indexed query.

Credentials and URL are read from the environment / .env (no secrets in this
file). Override per-run with CLI flags if needed.

Usage (server must be running):
    # uses ADMIN_USERNAME / ADMIN_PASSWORD from .env
    python scripts/benchmark.py -n 200 -c 20

    # or override explicitly
    python scripts/benchmark.py --url http://127.0.0.1:8000 \
        --username someuser --password somepass -n 200 -c 20
"""
import argparse
import asyncio
import os
import statistics
import time

import httpx
from dotenv import load_dotenv

load_dotenv()


async def _timed(client: httpx.AsyncClient, method: str, path: str, **kw) -> tuple[int, float]:
    t0 = time.perf_counter()
    resp = await client.request(method, path, **kw)
    return resp.status_code, (time.perf_counter() - t0) * 1000  # ms


async def run_batch(client, method, path, n, concurrency, **kw):
    sem = asyncio.Semaphore(concurrency)
    latencies: list[float] = []
    codes: list[int] = []

    async def one():
        async with sem:
            code, ms = await _timed(client, method, path, **kw)
            codes.append(code)
            latencies.append(ms)

    wall0 = time.perf_counter()
    await asyncio.gather(*[one() for _ in range(n)])
    wall = time.perf_counter() - wall0
    return latencies, codes, wall


def report(label, latencies, codes, wall, n):
    latencies.sort()
    p50 = statistics.median(latencies)
    p95 = latencies[int(len(latencies) * 0.95) - 1]
    p99 = latencies[int(len(latencies) * 0.99) - 1]
    ok = sum(1 for c in codes if 200 <= c < 300)
    print(f"\n[{label}]  n={n}")
    print(f"  success     : {ok}/{n}")
    print(f"  throughput  : {n / wall:8.1f} req/s")
    print(f"  latency p50 : {p50:8.2f} ms")
    print(f"  latency p95 : {p95:8.2f} ms")
    print(f"  latency p99 : {p99:8.2f} ms")
    print(f"  latency max : {max(latencies):8.2f} ms")


def _default_url() -> str:
    host = os.getenv("APP_HOST", "127.0.0.1")
    port = os.getenv("APP_PORT", "8000")
    return f"http://{host}:{port}"


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=_default_url())
    ap.add_argument("--username", default=os.getenv("ADMIN_USERNAME"))
    ap.add_argument("--password", default=os.getenv("ADMIN_PASSWORD"))
    ap.add_argument("-n", type=int, default=200, help="requests per scenario")
    ap.add_argument("-c", type=int, default=20, help="concurrency")
    args = ap.parse_args()

    if not args.username or not args.password:
        ap.error(
            "credentials missing: set ADMIN_USERNAME and ADMIN_PASSWORD in .env "
            "or pass --username/--password"
        )

    async with httpx.AsyncClient(base_url=args.url, timeout=30) as client:
        # warm up + get a token
        login_body = {"username": args.username, "password": args.password}
        r = await client.post("/auth/login", json=login_body)
        r.raise_for_status()
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        lat, codes, wall = await run_batch(
            client, "POST", "/auth/login", args.n, args.c, json=login_body
        )
        report("POST /auth/login  (bcrypt verify)", lat, codes, wall, args.n)

        lat, codes, wall = await run_batch(
            client, "GET", "/users/me", args.n, args.c, headers=headers
        )
        report("GET /users/me  (token + query)", lat, codes, wall, args.n)


if __name__ == "__main__":
    asyncio.run(main())
