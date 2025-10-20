import asyncio, random

async def wait_random_delay(delay_range):
    seconds = random.randint(*delay_range)
    print(f"Waiting {seconds}s before next action...")
    await asyncio.sleep(seconds)
