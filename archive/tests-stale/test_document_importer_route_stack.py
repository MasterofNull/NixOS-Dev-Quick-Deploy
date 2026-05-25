import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch
import sys

TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_DIR))

from document_importer import ChunkingStrategy, DocumentImporter, MetadataExtractor


def test_enrich_route_stack_metadata_marks_owner_files():
    metadata = MetadataExtractor.enrich_route_stack_metadata(
        Path("ai-stack/mcp-servers/hybrid-coordinator/search_router.py")
    )

    assert "ai-stack/mcp-servers/hybrid-coordinator/search_router.py" in metadata["owner_paths"]
    assert "route-stack" in metadata["subsystem_tags"]
    assert "search_router" in metadata["route_stack_hints"]


def test_import_file_skips_upsert_when_embeddings_fail():
    qdrant = Mock()
    importer = DocumentImporter(
        qdrant_client=qdrant,
        embedding_url="http://127.0.0.1:8081",
    )
    importer.generate_embedding = AsyncMock(return_value=[])

    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "route_handler.py"
        file_path.write_text("def route_search():\n    return True\n", encoding="utf-8")

        try:
            asyncio.run(importer.import_file(file_path))
        except Exception as exc:
            assert "Failed to generate embedding" in str(exc)
        else:
            raise AssertionError("expected import_file to fail when embeddings are unavailable")

    qdrant.upsert.assert_not_called()


def test_generate_embedding_uses_openai_embeddings_path_for_8081():
    qdrant = Mock()
    importer = DocumentImporter(
        qdrant_client=qdrant,
        embedding_url="http://127.0.0.1:8081",
    )
    response = Mock(status_code=200)
    response.json.return_value = {"data": [{"embedding": [0.1, 0.2, 0.3]}]}

    client = Mock()
    client.post = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)

    with patch("document_importer.httpx.AsyncClient", return_value=client):
        embedding = asyncio.run(importer.generate_embedding("route stack"))

    assert embedding == [0.1, 0.2, 0.3]
    called_url = client.post.await_args.args[0]
    assert called_url.endswith("/v1/embeddings")


def test_chunk_code_by_functions_splits_oversized_python_blocks():
    large_body = "\n".join(f"    value_{i} = {i}" for i in range(900))
    code = f"def route_search():\n{large_body}\n    return True\n"

    chunks = ChunkingStrategy.chunk_code_by_functions(code, "python", chunk_size=320)

    assert len(chunks) > 1
    for chunk_text, _ in chunks:
        assert ChunkingStrategy.estimate_tokens(chunk_text) <= 320


def test_chunks_created_only_counts_successful_upserts():
    qdrant = Mock()
    importer = DocumentImporter(qdrant_client=qdrant, embedding_url="http://127.0.0.1:8081")
    importer.generate_embedding = AsyncMock(return_value=[])

    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "route_handler.py"
        file_path.write_text("def route_search():\n    return True\n", encoding="utf-8")

        try:
            asyncio.run(importer.import_file(file_path))
        except Exception:
            pass

    assert importer.stats["chunks_created"] == 0
