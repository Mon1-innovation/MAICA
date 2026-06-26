import asyncio
from pymilvus import AsyncMilvusClient

async def main():
    # 1. Initialize AsyncMilvusClient with Milvus Lite (local .db file)
    client = AsyncMilvusClient(uri="http://localhost:19530")

    # 2. Check if collection exists and drop it (for fresh run)
    if await client.has_collection(collection_name="demo_collection"):
        await client.drop_collection(collection_name="demo_collection")

    # 3. Create a collection
    await client.create_collection(
        collection_name="demo_collection",
        dimension=4,
        # enable_dynamic_field=True
    )

    data = [
        {"id": 1, "vector": [0.1, 0.2, 0.3, 0.4], "color": "red"},
        {"id": 2, "vector": [0.5, 0.6, 0.7, 0.8], "color": "blue"}
    ]


    # await client.load_collection("demo_collection")

    await client.insert(collection_name="demo_collection", data=data)

    await client.flush(collection_name="demo_collection")

    res = await client.search(
        collection_name="demo_collection",
        data=[[0.1, 0.2, 0.3, 0.4]],
        limit=10,
        output_fields=["*"]
    )
    print(f"Search Response: {res}")

    # 7. Close the client
    await client.close()

# Run the async loop
if __name__ == "__main__":
    asyncio.run(main())