import asyncio

MAX_RETRIES = 3
BASE_DELAY = 1

async def simulative_service(name: str, delay: float) -> dict:
    if name == "B":
        raise ConnectionError("Service unavailable")
    await asyncio.sleep(delay)
    return {"name": name, "status": "ok", "latency": delay}

async def check_services(configs: list[dict], timeout_per_service: float):
    results = [None] * len(configs)

    async def run_one(i, cfg):
        name = cfg["name"]
        delay = cfg["delay"]
        for attempt in range(MAX_RETRIES + 1):
            try:
                async with asyncio.timeout(2):
                    res = await simulative_service(name, delay)
                    res["attempts"] = attempt + 1
                    results[i] = res
                    return

            except (asyncio.TimeoutError, ConnectionError):
                results[i] = {
                    "name": name,
                    "status": "timeout",
                    "latency": timeout_per_service,
                    "attempts": attempt + 1
                }
                if (attempt < MAX_RETRIES):
                    backoff = BASE_DELAY * (2 ** attempt)
                    print(f"{name}: retry in {backoff} sec")
                    await asyncio.sleep(backoff)
                if (attempt == MAX_RETRIES):
                        results[i] = {
                            "name": name,
                            "status": "error"
                        }

    async with asyncio.TaskGroup() as group:
        for i, cfg in enumerate(configs):
            group.create_task(run_one(i, cfg))

    return results

async def main():
    configs = [
        {"name": "A", "delay": 1},
        {"name": "B", "delay": 3},
        {"name": "C", "delay": 2}
    ]

    res = await check_services(configs, timeout_per_service=2)
    print(res)

asyncio.run(main())