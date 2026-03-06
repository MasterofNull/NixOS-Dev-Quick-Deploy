"""
Path validation utilities for preventing path traversal attacks.

Provides safe file access within constrained directory boundaries.

Usage:
    from shared.path_validation import validate_path_within_base, SafePathError

    # Validate and resolve path
    safe_path = validate_path_within_base(user_input, base_dir="/allowed/path")

    # Or use the context manager
    with safe_file_read(user_input, base_dir="/allowed/path") as f:
        content = f.read()
"""

import os
from pathlib import Path
from typing import Optional, Union


class SafePathError(ValueError):
    """Raised when a path fails security validation."""
    pass


def validate_path_within_base(
    user_path: str,
    base_dir: Union[str, Path],
    *,
    must_exist: bool = True,
    allow_symlinks: bool = False,
) -> Path:
    """
    Validate that a user-provided path resolves within a base directory.

    Prevents path traversal attacks by ensuring the resolved path is a
    descendant of the base directory.

    Args:
        user_path: The user-provided path (may be relative or contain ..)
        base_dir: The allowed base directory
        must_exist: If True, raise error if path doesn't exist
        allow_symlinks: If True, allow symlinks (still validates target)

    Returns:
        The validated, resolved Path object

    Raises:
        SafePathError: If path validation fails
        FileNotFoundError: If must_exist=True and path doesn't exist

    Examples:
        >>> validate_path_within_base("Dockerfile", "/app")
        PosixPath('/app/Dockerfile')

        >>> validate_path_within_base("../etc/passwd", "/app")
        SafePathError: Path escapes base directory

        >>> validate_path_within_base("/etc/passwd", "/app")
        SafePathError: Absolute path not within base directory
    """
    if not user_path:
        raise SafePathError("Empty path provided")

    base = Path(base_dir).resolve()
    if not base.is_dir():
        raise SafePathError(f"Base directory does not exist: {base_dir}")

    # Handle both absolute and relative paths
    user_path_obj = Path(user_path)

    if user_path_obj.is_absolute():
        # Absolute path: must be within base
        candidate = user_path_obj.resolve()
    else:
        # Relative path: join with base and resolve
        candidate = (base / user_path_obj).resolve()

    # Check symlinks if not allowed
    if not allow_symlinks:
        # Check if any component is a symlink
        try:
            for parent in candidate.parents:
                if parent.is_symlink():
                    raise SafePathError(f"Symlink in path not allowed: {parent}")
            if candidate.exists() and candidate.is_symlink():
                raise SafePathError(f"Symlink target not allowed: {candidate}")
        except OSError:
            pass  # Path doesn't exist yet, which is fine

    # Ensure resolved path is within base directory
    try:
        candidate.relative_to(base)
    except ValueError:
        raise SafePathError(
            f"Path escapes base directory: {user_path} resolves to {candidate}, "
            f"which is not within {base}"
        )

    # Check existence if required
    if must_exist and not candidate.exists():
        raise FileNotFoundError(f"Path does not exist: {candidate}")

    return candidate


def validate_filename(
    filename: str,
    *,
    allowed_extensions: Optional[list[str]] = None,
    max_length: int = 255,
) -> str:
    """
    Validate a filename (not a path) for safety.

    Args:
        filename: The filename to validate
        allowed_extensions: List of allowed extensions (e.g., ['.json', '.txt'])
        max_length: Maximum filename length

    Returns:
        The validated filename

    Raises:
        SafePathError: If filename fails validation
    """
    if not filename:
        raise SafePathError("Empty filename provided")

    # Check for path separators
    if "/" in filename or "\\" in filename:
        raise SafePathError(f"Filename contains path separator: {filename}")

    # Check for path traversal attempts
    if filename in (".", "..") or filename.startswith(".."):
        raise SafePathError(f"Invalid filename: {filename}")

    # Check length
    if len(filename) > max_length:
        raise SafePathError(f"Filename too long: {len(filename)} > {max_length}")

    # Check null bytes
    if "\x00" in filename:
        raise SafePathError("Filename contains null byte")

    # Check extension if specified
    if allowed_extensions:
        ext = Path(filename).suffix.lower()
        if ext not in [e.lower() for e in allowed_extensions]:
            raise SafePathError(
                f"File extension not allowed: {ext}. "
                f"Allowed: {allowed_extensions}"
            )

    return filename


class safe_file_read:
    """
    Context manager for safely reading a file within a base directory.

    Usage:
        with safe_file_read("config.json", base_dir="/app/data") as f:
            config = json.load(f)
    """

    def __init__(
        self,
        user_path: str,
        base_dir: Union[str, Path],
        mode: str = "r",
        encoding: str = "utf-8",
        **kwargs,
    ):
        self.user_path = user_path
        self.base_dir = base_dir
        self.mode = mode
        self.encoding = encoding
        self.kwargs = kwargs
        self._file = None

    def __enter__(self):
        safe_path = validate_path_within_base(
            self.user_path,
            self.base_dir,
            must_exist=True,
        )
        self._file = open(safe_path, self.mode, encoding=self.encoding, **self.kwargs)
        return self._file

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._file:
            self._file.close()
        return False
