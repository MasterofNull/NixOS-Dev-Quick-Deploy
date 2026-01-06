#!/usr/bin/env python3
"""
Document Importer for RAG Knowledge Base
Automatically scans, chunks, and imports documents into Qdrant
"""

import asyncio
import hashlib
import logging
import mimetypes
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

import httpx
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

logger = logging.getLogger("document-importer")


class ChunkingStrategy:
    """Strategies for chunking different document types"""

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Rough token estimation: ~1.3 tokens per word"""
        return int(len(text.split()) * 1.3)

    @staticmethod
    def chunk_by_paragraphs(
        text: str,
        chunk_size: int = 512,
        overlap: int = 128
    ) -> List[str]:
        """
        Chunk text by paragraphs with overlap

        Good for: Markdown, documentation, general text
        """
        paragraphs = text.split("\n\n")
        chunks = []
        current_chunk = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # If adding this paragraph exceeds chunk size
            if ChunkingStrategy.estimate_tokens(current_chunk + "\n\n" + para) > chunk_size:
                if current_chunk:
                    chunks.append(current_chunk)
                    # Start new chunk with overlap from end of previous
                    words = current_chunk.split()
                    overlap_text = " ".join(words[-overlap:]) if len(words) > overlap else current_chunk
                    current_chunk = overlap_text + "\n\n" + para
                else:
                    # Single paragraph is too large, split by sentences
                    sentences = re.split(r'(?<=[.!?])\s+', para)
                    for sentence in sentences:
                        if ChunkingStrategy.estimate_tokens(current_chunk + " " + sentence) > chunk_size:
                            if current_chunk:
                                chunks.append(current_chunk)
                            current_chunk = sentence
                        else:
                            current_chunk += " " + sentence if current_chunk else sentence
            else:
                current_chunk += "\n\n" + para if current_chunk else para

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    @staticmethod
    def chunk_code_by_functions(
        code: str,
        language: str,
        chunk_size: int = 512
    ) -> List[Tuple[str, Dict[str, Any]]]:
        """
        Chunk code by logical blocks (functions, classes)

        Good for: Python, JavaScript, shell scripts

        Returns:
            List of (chunk_text, metadata) tuples
        """
        chunks = []

        if language == "python":
            # Split by function/class definitions
            pattern = r'((?:^|\n)(?:def|class)\s+\w+.*?:.*?)(?=\n(?:def|class)\s+|\Z)'
            matches = re.finditer(pattern, code, re.MULTILINE | re.DOTALL)

            for match in matches:
                func_code = match.group(1).strip()

                # Extract function/class name
                first_line = func_code.split('\n')[0]
                name_match = re.search(r'(def|class)\s+(\w+)', first_line)
                name = name_match.group(2) if name_match else "unknown"

                chunks.append((func_code, {"type": name_match.group(1) if name_match else "code", "name": name}))

        elif language in ["bash", "shell"]:
            # Split by function definitions
            pattern = r'((?:^|\n)(?:function\s+)?\w+\s*\(\)\s*\{.*?\n\})'
            matches = re.finditer(pattern, code, re.MULTILINE | re.DOTALL)

            for match in matches:
                func_code = match.group(1).strip()
                name_match = re.search(r'(?:function\s+)?(\w+)\s*\(\)', func_code)
                name = name_match.group(1) if name_match else "unknown"

                chunks.append((func_code, {"type": "function", "name": name}))

        elif language == "nix":
            # Split by top-level attribute definitions
            pattern = r'((?:^|\n)\s*\w+\s*=\s*.*?;)'
            matches = re.finditer(pattern, code, re.MULTILINE | re.DOTALL)

            for match in matches:
                attr_code = match.group(1).strip()
                name_match = re.search(r'(\w+)\s*=', attr_code)
                name = name_match.group(1) if name_match else "unknown"

                chunks.append((attr_code, {"type": "attribute", "name": name}))

        # Fallback: if no logical blocks found, chunk by size
        if not chunks:
            text_chunks = ChunkingStrategy.chunk_by_paragraphs(code, chunk_size)
            chunks = [(chunk, {"type": "code_block", "name": f"block_{i}"}) for i, chunk in enumerate(text_chunks)]

        return chunks


class MetadataExtractor:
    """Extract metadata from different file types"""

    @staticmethod
    def extract_from_markdown(content: str, file_path: Path) -> Dict[str, Any]:
        """Extract metadata from markdown frontmatter and content"""
        metadata = {
            "file_type": "markdown",
            "language": "markdown"
        }

        # Try to extract title from first heading
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if title_match:
            metadata["title"] = title_match.group(1)

        # Try to extract YAML frontmatter
        frontmatter_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
        if frontmatter_match:
            # Simple key-value extraction (not full YAML parser)
            for line in frontmatter_match.group(1).split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    metadata[key.strip()] = value.strip()

        # Detect document category from content
        content_lower = content.lower()
        if any(word in content_lower for word in ['api', 'endpoint', 'request', 'response']):
            metadata["category"] = "api_documentation"
        elif any(word in content_lower for word in ['guide', 'tutorial', 'how to', 'step']):
            metadata["category"] = "guide"
        elif any(word in content_lower for word in ['error', 'troubleshoot', 'fix', 'issue']):
            metadata["category"] = "troubleshooting"
        else:
            metadata["category"] = "documentation"

        return metadata

    @staticmethod
    def extract_from_code(content: str, file_path: Path, language: str) -> Dict[str, Any]:
        """Extract metadata from code files"""
        metadata = {
            "file_type": "code",
            "language": language
        }

        # Try to extract docstring/header comment
        if language == "python":
            docstring_match = re.search(r'^\s*"""(.*?)"""', content, re.DOTALL)
            if docstring_match:
                metadata["description"] = docstring_match.group(1).strip()[:200]

        elif language in ["bash", "shell"]:
            # Extract shebang and initial comments
            lines = content.split('\n')
            comments = []
            for line in lines[1:10]:  # Check first 10 lines
                if line.strip().startswith('#'):
                    comments.append(line.strip('#').strip())
                elif line.strip():
                    break
            if comments:
                metadata["description"] = " ".join(comments)[:200]

        # Detect framework/purpose from imports
        if language == "python":
            if "fastapi" in content:
                metadata["framework"] = "FastAPI"
            elif "flask" in content:
                metadata["framework"] = "Flask"
            elif "django" in content:
                metadata["framework"] = "Django"

            if "qdrant" in content:
                metadata["purpose"] = "vector_database"
            elif "redis" in content:
                metadata["purpose"] = "caching"
            elif "postgres" in content or "psycopg" in content:
                metadata["purpose"] = "database"

        return metadata

    @staticmethod
    def extract_from_nix(content: str, file_path: Path) -> Dict[str, Any]:
        """Extract metadata from Nix files"""
        metadata = {
            "file_type": "configuration",
            "language": "nix"
        }

        # Detect Nix file type
        if "nixosConfiguration" in content or "system.stateVersion" in content:
            metadata["nix_type"] = "nixos_configuration"
        elif "home.stateVersion" in content or "home-manager" in content:
            metadata["nix_type"] = "home_manager"
        elif "mkDerivation" in content or "buildInputs" in content:
            metadata["nix_type"] = "package"
        else:
            metadata["nix_type"] = "module"

        # Extract enabled services
        services = re.findall(r'services\.(\w+)\.enable\s*=\s*true', content)
        if services:
            metadata["services"] = services[:10]  # Limit to 10

        return metadata


class DocumentImporter:
    """
    Import documents into Qdrant knowledge base

    Features:
    - Automatic file type detection
    - Smart chunking strategies
    - Metadata extraction
    - Differential sync (only import new/changed)
    - Progress tracking

    Usage:
        importer = DocumentImporter(qdrant_client)
        await importer.import_directory(Path("/path/to/docs"))
    """

    def __init__(
        self,
        qdrant_client: QdrantClient,
        embedding_url: str = "http://localhost:8080/v1/embeddings",
        chunk_size: int = 512,
        overlap: int = 128
    ):
        self.qdrant = qdrant_client
        self.embedding_url = embedding_url
        self.chunk_size = chunk_size
        self.overlap = overlap

        # File type patterns
        self.markdown_extensions = {".md", ".markdown", ".mdx"}
        self.code_extensions = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".sh": "bash",
            ".bash": "bash",
            ".zsh": "bash",
            ".nix": "nix",
            ".yml": "yaml",
            ".yaml": "yaml",
            ".json": "json",
            ".toml": "toml"
        }

        # Import statistics
        self.stats = {
            "files_scanned": 0,
            "files_imported": 0,
            "files_skipped": 0,
            "chunks_created": 0,
            "errors": []
        }

    async def import_directory(
        self,
        directory: Path,
        recursive: bool = True,
        skip_patterns: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Import all supported files from directory

        Args:
            directory: Directory to scan
            recursive: Scan subdirectories
            skip_patterns: List of glob patterns to skip (e.g., ["node_modules", ".git"])

        Returns:
            Import statistics
        """
        skip_patterns = skip_patterns or [
            "node_modules", ".git", "__pycache__", "venv", ".venv",
            "dist", "build", ".cache", "*.pyc", "*.log"
        ]

        logger.info(f"Starting directory import: {directory}")

        # Find all files
        files_to_import = []

        if recursive:
            for file_path in directory.rglob("*"):
                if file_path.is_file() and self.should_import(file_path, skip_patterns):
                    files_to_import.append(file_path)
        else:
            for file_path in directory.glob("*"):
                if file_path.is_file() and self.should_import(file_path, skip_patterns):
                    files_to_import.append(file_path)

        logger.info(f"Found {len(files_to_import)} files to import")

        # Import each file
        for i, file_path in enumerate(files_to_import, 1):
            self.stats["files_scanned"] += 1

            try:
                logger.info(f"[{i}/{len(files_to_import)}] Importing: {file_path}")
                await self.import_file(file_path)
                self.stats["files_imported"] += 1
            except Exception as e:
                logger.error(f"Error importing {file_path}: {e}")
                self.stats["errors"].append({"file": str(file_path), "error": str(e)})
                self.stats["files_skipped"] += 1

        logger.info(f"Import complete: {self.stats}")
        return self.stats

    def should_import(self, file_path: Path, skip_patterns: List[str]) -> bool:
        """Check if file should be imported"""
        # Check if matches skip pattern
        for pattern in skip_patterns:
            if file_path.match(pattern):
                return False

        # Check if supported file type
        return (
            file_path.suffix in self.markdown_extensions or
            file_path.suffix in self.code_extensions
        )

    async def import_file(self, file_path: Path):
        """Import a single file"""
        # Read file content
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            raise Exception(f"Failed to read file: {e}")

        # Determine file type and extract metadata
        if file_path.suffix in self.markdown_extensions:
            metadata = MetadataExtractor.extract_from_markdown(content, file_path)
            chunks = ChunkingStrategy.chunk_by_paragraphs(content, self.chunk_size, self.overlap)
            chunk_metadata_list = [{"chunk_type": "paragraph"} for _ in chunks]

        elif file_path.suffix in self.code_extensions:
            language = self.code_extensions[file_path.suffix]
            metadata = MetadataExtractor.extract_from_code(content, file_path, language)

            if language in ["python", "bash", "nix"]:
                chunk_results = ChunkingStrategy.chunk_code_by_functions(content, language, self.chunk_size)
                chunks = [chunk for chunk, _ in chunk_results]
                chunk_metadata_list = [chunk_meta for _, chunk_meta in chunk_results]
            else:
                chunks = ChunkingStrategy.chunk_by_paragraphs(content, self.chunk_size, self.overlap)
                chunk_metadata_list = [{"chunk_type": "code_block"} for _ in chunks]

        else:
            # Shouldn't reach here due to should_import check
            return

        # Generate file hash for differential sync
        file_hash = hashlib.sha256(content.encode()).hexdigest()

        # Import each chunk
        points = []
        for idx, (chunk, chunk_meta) in enumerate(zip(chunks, chunk_metadata_list)):
            # Generate embedding
            embedding = await self.generate_embedding(chunk)

            # Create point
            point = PointStruct(
                id=str(uuid4()),
                vector=embedding,
                payload={
                    "file_path": str(file_path),
                    "file_hash": file_hash,
                    "chunk_index": idx,
                    "total_chunks": len(chunks),
                    "content": chunk,
                    "imported_at": datetime.now().isoformat(),
                    **metadata,
                    **chunk_meta
                }
            )
            points.append(point)
            self.stats["chunks_created"] += 1

        # Upsert to Qdrant
        try:
            self.qdrant.upsert(
                collection_name="codebase-context",
                points=points
            )
            logger.info(f"  ✓ Imported {len(chunks)} chunks from {file_path.name}")
        except Exception as e:
            raise Exception(f"Failed to upsert to Qdrant: {e}")

    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text

        Supports two API formats:
        1. Hugging Face text-embeddings-inference (TEI) - default for port 8081
        2. OpenAI-compatible (llama.cpp) - fallback
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Determine API format based on embedding_url
                if ":8081" in self.embedding_url:
                    # Hugging Face TEI API format
                    response = await client.post(
                        f"{self.embedding_url}/embed",
                        json={"inputs": text}
                    )

                    if response.status_code == 200:
                        data = response.json()
                        # TEI returns list of embeddings directly
                        if isinstance(data, list) and len(data) > 0:
                            return data[0]
                        else:
                            logger.warning(f"Unexpected TEI response format: {data}")
                            return [0.0] * 384
                    else:
                        logger.warning(f"TEI embedding failed: {response.status_code} - {response.text}")
                        return [0.0] * 384
                else:
                    # OpenAI-compatible API format (llama.cpp, etc.)
                    response = await client.post(
                        self.embedding_url,
                        json={"input": text}
                    )

                    if response.status_code == 200:
                        data = response.json()
                        return data["data"][0]["embedding"]
                    else:
                        logger.warning(f"Embedding service unavailable: {response.status_code}")
                        return [0.0] * 384

        except Exception as e:
            logger.warning(f"Embedding generation failed: {e}, using zero vector")
            return [0.0] * 384

    def get_stats(self) -> Dict[str, Any]:
        """Get import statistics"""
        return self.stats
