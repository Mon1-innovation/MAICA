"""Manual connectivity smoke test for a configured Milvus server."""

import asyncio
import os

from pymilvus import AsyncMilvusClient


async def main() -> None:
    client = AsyncMilvusClient(uri=os.getenv("MAICA_MILVUS_ADDR", "http://localhost:19530"))
    try:
        print(await client.list_collections())
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
