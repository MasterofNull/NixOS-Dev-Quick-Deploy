import asyncio

from memory_broker import MemoryBroker


def test_memory_broker_write_supplies_summary_to_store_contract():
    calls = []

    async def _store(**kwargs):
        calls.append(kwargs)
        return {"status": "stored", "memory_id": "memory-1"}

    async def _recall(**_kwargs):
        return {"results": []}

    result = asyncio.run(MemoryBroker(_store, _recall).write("semantic", "broker content"))

    assert result["status"] == "stored"
    assert calls[0]["summary"] == "broker content"
    assert calls[0]["content"] == "broker content"
