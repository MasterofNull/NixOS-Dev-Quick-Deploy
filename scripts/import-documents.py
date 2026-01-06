#!/usr/bin/env python3
"""
Document Import CLI Tool
Imports project files into Qdrant knowledge base for RAG
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "ai-stack" / "mcp-servers" / "aidb"))

from document_importer import DocumentImporter
from qdrant_client import QdrantClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("import-documents")


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Import project files into Qdrant knowledge base",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Import all project files
  %(prog)s --directory ~/Documents/try/NixOS-Dev-Quick-Deploy

  # Import only markdown files from docs directory
  %(prog)s --directory ./docs --extensions .md

  # Import with custom chunk size
  %(prog)s --directory ./scripts --chunk-size 1024 --overlap 256

  # Import non-recursively (current directory only)
  %(prog)s --directory ./templates --no-recursive

  # Dry run (show what would be imported)
  %(prog)s --directory . --dry-run
        """
    )

    parser.add_argument(
        '--directory', '-d',
        type=str,
        default='.',
        help='Directory to scan for documents (default: current directory)'
    )

    parser.add_argument(
        '--collection', '-c',
        type=str,
        default='codebase-context',
        help='Qdrant collection to import into (default: codebase-context)'
    )

    parser.add_argument(
        '--qdrant-url',
        type=str,
        default=os.getenv('QDRANT_URL', 'http://localhost:6333'),
        help='Qdrant server URL (default: http://localhost:6333)'
    )

    parser.add_argument(
        '--embedding-url',
        type=str,
        default=os.getenv('EMBEDDING_SERVICE_URL', 'http://localhost:8081'),
        help='Embedding service URL (default: http://localhost:8081 for TEI service)'
    )

    parser.add_argument(
        '--chunk-size',
        type=int,
        default=512,
        help='Token chunk size (default: 512)'
    )

    parser.add_argument(
        '--overlap',
        type=int,
        default=128,
        help='Token overlap between chunks (default: 128)'
    )

    parser.add_argument(
        '--no-recursive',
        action='store_true',
        help='Do not scan subdirectories'
    )

    parser.add_argument(
        '--extensions',
        type=str,
        nargs='+',
        help='Only import specific file extensions (e.g., .md .py .sh)'
    )

    parser.add_argument(
        '--skip-patterns',
        type=str,
        nargs='+',
        default=[
            'node_modules', '.git', '__pycache__', 'venv', '.venv',
            'dist', 'build', '.cache', '*.pyc', '*.log', 'target',
            '.next', '.nuxt', 'coverage', '.pytest_cache'
        ],
        help='Glob patterns to skip (default: common build/cache directories)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be imported without actually importing'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose output (DEBUG level)'
    )

    return parser.parse_args()


async def ensure_collection_exists(
    qdrant: QdrantClient,
    collection_name: str,
    vector_size: int = 384
):
    """Ensure Qdrant collection exists with correct schema"""
    from qdrant_client.models import Distance, VectorParams

    try:
        # Check if collection exists
        qdrant.get_collection(collection_name)
        logger.info(f"✓ Collection '{collection_name}' exists")
    except Exception:
        # Create collection
        logger.info(f"Creating collection '{collection_name}' with {vector_size}D vectors...")
        qdrant.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=vector_size,
                distance=Distance.COSINE
            )
        )
        logger.info(f"✓ Collection '{collection_name}' created")


def filter_by_extensions(files: list, extensions: list) -> list:
    """Filter files by allowed extensions"""
    if not extensions:
        return files

    allowed_exts = set(ext if ext.startswith('.') else f'.{ext}' for ext in extensions)
    return [f for f in files if f.suffix in allowed_exts]


async def main():
    """Main entry point"""
    args = parse_args()

    # Set log level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Resolve directory path
    directory = Path(args.directory).expanduser().resolve()
    if not directory.exists():
        logger.error(f"Directory not found: {directory}")
        return 1

    if not directory.is_dir():
        logger.error(f"Not a directory: {directory}")
        return 1

    logger.info(f"Scanning directory: {directory}")
    logger.info(f"Recursive: {not args.no_recursive}")
    logger.info(f"Target collection: {args.collection}")
    logger.info(f"Chunk size: {args.chunk_size} tokens, overlap: {args.overlap} tokens")

    # Initialize Qdrant client
    try:
        qdrant = QdrantClient(url=args.qdrant_url)
        logger.info(f"✓ Connected to Qdrant at {args.qdrant_url}")
    except Exception as e:
        logger.error(f"Failed to connect to Qdrant: {e}")
        return 1

    # Ensure collection exists
    await ensure_collection_exists(qdrant, args.collection)

    # Initialize DocumentImporter
    importer = DocumentImporter(
        qdrant_client=qdrant,
        embedding_url=args.embedding_url,
        chunk_size=args.chunk_size,
        overlap=args.overlap
    )

    # If extensions specified, update importer's file type filters
    if args.extensions:
        logger.info(f"Filtering by extensions: {args.extensions}")
        # Filter code_extensions
        importer.code_extensions = {
            k: v for k, v in importer.code_extensions.items()
            if k in args.extensions
        }
        # Filter markdown_extensions
        importer.markdown_extensions = {
            ext for ext in importer.markdown_extensions
            if ext in args.extensions
        }

    # Dry run: just show what would be imported
    if args.dry_run:
        logger.info("DRY RUN MODE - No files will be imported")
        logger.info("-" * 60)

        files_to_import = []
        if not args.no_recursive:
            for file_path in directory.rglob("*"):
                if file_path.is_file() and importer.should_import(file_path, args.skip_patterns):
                    files_to_import.append(file_path)
        else:
            for file_path in directory.glob("*"):
                if file_path.is_file() and importer.should_import(file_path, args.skip_patterns):
                    files_to_import.append(file_path)

        logger.info(f"Would import {len(files_to_import)} files:")
        for i, file_path in enumerate(sorted(files_to_import)[:50], 1):
            rel_path = file_path.relative_to(directory)
            file_type = importer.code_extensions.get(file_path.suffix, 'markdown')
            logger.info(f"  {i:3d}. {rel_path} [{file_type}]")

        if len(files_to_import) > 50:
            logger.info(f"  ... and {len(files_to_import) - 50} more files")

        logger.info("-" * 60)
        logger.info(f"Total: {len(files_to_import)} files")
        return 0

    # Perform actual import
    try:
        logger.info("Starting import...")
        logger.info("=" * 60)

        stats = await importer.import_directory(
            directory=directory,
            recursive=not args.no_recursive,
            skip_patterns=args.skip_patterns
        )

        logger.info("=" * 60)
        logger.info("Import complete!")
        logger.info("")
        logger.info(f"Statistics:")
        logger.info(f"  Files scanned:  {stats['files_scanned']}")
        logger.info(f"  Files imported: {stats['files_imported']}")
        logger.info(f"  Files skipped:  {stats['files_skipped']}")
        logger.info(f"  Chunks created: {stats['chunks_created']}")
        logger.info(f"  Errors:         {len(stats['errors'])}")

        if stats['errors']:
            logger.info("")
            logger.warning("Errors encountered:")
            for error in stats['errors'][:10]:
                logger.warning(f"  {error['file']}: {error['error']}")
            if len(stats['errors']) > 10:
                logger.warning(f"  ... and {len(stats['errors']) - 10} more errors")

        logger.info("")
        logger.info(f"✓ Imported {stats['chunks_created']} chunks from {stats['files_imported']} files")

        return 0

    except KeyboardInterrupt:
        logger.warning("\nImport interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Import failed: {e}", exc_info=args.verbose)
        return 1


if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
