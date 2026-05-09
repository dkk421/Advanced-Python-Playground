import asyncio
import argparse
import json
import sys

BASE_DELAY = 1

async def simulative_service(name: str, delay: float) -> dict:
    if name == "B":
        raise ConnectionError("Service unavailable")
    await asyncio.sleep(delay)
    return {"name": name, "status": "ok", "latency": delay}

async def check_services(
        configs: list[dict],
        timeout_per_service: float,
        max_retries: int,
        concurrency: int
        ):
    results = [None] * len(configs)
    completed = 0
    semaphore = asyncio.Semaphore(concurrency)

    async def run_one(i, cfg):
        nonlocal completed
        name = cfg["name"]
        delay = cfg["delay"]
        
        async with semaphore:
            for attempt in range(max_retries + 1):
                try:
                    async with asyncio.timeout(timeout_per_service):
                        res = await simulative_service(name, delay)
                        res["attempts"] = attempt + 1
                        results[i] = res
                        completed += 1
                        print(
                            f"Progress: "
                            f"{completed}/{len(configs)} completed",
                            flush=True
                        )
                        return

                except (asyncio.TimeoutError, ConnectionError) as e:
                    print(
                        f"{name}: "
                        f"attempt {attempt+1} failed "
                        f"({type(e).__name__})"
                    )
                    results[i] = {
                        "name": name,
                        "status": "timeout",
                        "latency": timeout_per_service,
                        "attempts": attempt + 1
                    }
                    if (attempt < max_retries):
                        backoff = BASE_DELAY * (2 ** attempt)
                        print(f"{name}: retry in {backoff} sec")
                        await asyncio.sleep(backoff)
                        continue
                    if (attempt == max_retries):
                            results[i] = {
                                "name": name,
                                "status": "error"
                            }
                    completed += 1
                    print(
                        f' Progress: {completed}/{len(configs)} completed',
                        end=' ', 
                        flush=True
                    )

    async with asyncio.TaskGroup() as group:
        for i, cfg in enumerate(configs):
            group.create_task(run_one(i, cfg))

    return results

async def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--timeout",
        type=float,
        default=2
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=3
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=2
    )
    parser.add_argument(
        "--output",
        type=str,
        default="report.json"
    )

    args = parser.parse_args()

    configs = [
        {"name": "A", "delay": 1},
        {"name": "B", "delay": 3},
        {"name": "C", "delay": 2}
    ]

    res = await check_services(
        configs,
        timeout_per_service=args.timeout,
        max_retries=args.retries,
        concurrency=args.concurrency
    )

    print(res)

    with open(args.output, "w") as f:
        json.dump(res, f, indent=4)
    print(f"\nReport saved to {args.output}")

    has_errors = any(result["status"] != "ok" for result in res)
    if has_errors:
        sys.exit(1)
        

asyncio.run(main())