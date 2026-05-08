import asyncio

async def simulative_service(name: str, delay: float) -> dict:
    await asyncio.sleep(delay)
    return {"name": name, "status": "ok", "latency": delay}

async def check_services(configs: list[dict], timeout_per_service: float):
    results = [None] * len(configs)

    async def run_one(i, cfg):
        name = cfg["name"]
        delay = cfg["delay"]

        try:
            async with asyncio.timeout(2):
                res = await simulative_service(name, delay)
                results.append(res)

        except asyncio.TimeoutError:
            results[i] = {
                "name": name,
                "status": "timeout",
                "latency": timeout_per_service
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