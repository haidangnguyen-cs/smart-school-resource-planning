"""Memory-efficient, deterministic CSV readers supporting encoding fallback."""

import codecs
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pandas as pd


def read_csv_robust(
    filepath: Path | str,
    encoding_cascade: list[str] | None = None,
    dtype: dict[str, Any] | None = None,
    usecols: list[str] | None = None,
    nrows: int | None = None,
    **kwargs: Any,
) -> tuple[pd.DataFrame, str]:
    """Read a CSV file using a deterministic encoding cascade.

    Attempts encodings in order (default: ['utf-8', 'windows-1252']).
    Does not allow leading latin-1 and prohibits silent decoding error suppression.

    Args:
        filepath: Path to the CSV file.
        encoding_cascade: List of encodings to attempt in priority order.
        dtype: Optional dictionary of column data types.
        usecols: Optional list of columns to load.
        nrows: Optional number of rows to read.
        **kwargs: Additional keyword arguments passed to pandas.read_csv.

    Returns:
        Tuple of (loaded DataFrame, successful encoding string).

    Raises:
        FileNotFoundError: If the specified file does not exist.
        UnicodeDecodeError: If all candidate encodings fail.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Source file not found: {path}")

    if encoding_cascade is None:
        encoding_cascade = ["utf-8", "windows-1252"]

    last_error: Exception | None = None
    for enc in encoding_cascade:
        try:
            df = pd.read_csv(
                path,
                encoding=enc,
                dtype=dtype,
                usecols=usecols,
                nrows=nrows,
                low_memory=False,
                **kwargs,
            )
            return df, enc
        except UnicodeDecodeError as exc:
            last_error = exc
            continue

    if last_error is not None:
        raise last_error
    raise ValueError(f"Failed to read {path} with provided encoding cascade: {encoding_cascade}")


def determine_encoding(
    filepath: Path | str,
    encoding_cascade: list[str] | None = None,
    chunk_size: int = 8 * 1024 * 1024,
) -> str:
    """Determine the successful encoding from the cascade by testing file validity.

    Attempts candidate encodings in strict priority order (default: ['utf-8', 'windows-1252']).
    If UTF-8 encounters any invalid byte sequence anywhere in the file stream,
    it falls back deterministically to Windows-1252.
    Uses an incremental decoder to safely handle multi-byte characters straddling chunk boundaries.

    Args:
        filepath: Path to the CSV file.
        encoding_cascade: List of encodings to attempt in priority order.
        chunk_size: Chunk size in bytes for reading the stream (default: 8 MiB).

    Returns:
        The detected encoding name.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Source file not found: {path}")

    if encoding_cascade is None:
        encoding_cascade = ["utf-8", "windows-1252"]

    for enc in encoding_cascade:
        try:
            decoder = codecs.getincrementaldecoder(enc)(errors="strict")
            with open(path, "rb") as f:
                while chunk := f.read(chunk_size):
                    decoder.decode(chunk, final=False)
                decoder.decode(b"", final=True)
            return enc
        except UnicodeDecodeError:
            continue

    raise ValueError(f"Could not decode {path} with any candidate encoding in {encoding_cascade}")


def stream_csv_chunks(
    filepath: Path | str,
    chunksize: int = 100_000,
    encoding: str | None = None,
    encoding_cascade: list[str] | None = None,
    dtype: dict[str, Any] | None = None,
    usecols: list[str] | None = None,
    **kwargs: Any,
) -> Iterator[pd.DataFrame]:
    """Stream a large CSV file in chunks using the deterministic encoding cascade.

    Args:
        filepath: Path to the CSV file.
        chunksize: Number of rows per chunk (default: 100,000).
        encoding: Optional explicit encoding override.
        encoding_cascade: List of encodings to attempt in priority order.
        dtype: Optional dictionary of column data types.
        usecols: Optional list of columns to load.
        **kwargs: Additional keyword arguments passed to pandas.read_csv.

    Yields:
        Chunks of pd.DataFrame.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Source file not found: {path}")

    resolved_encoding = encoding if encoding is not None else determine_encoding(path, encoding_cascade=encoding_cascade)

    reader = pd.read_csv(
        path,
        encoding=resolved_encoding,
        chunksize=chunksize,
        dtype=dtype,
        usecols=usecols,
        low_memory=False,
        **kwargs,
    )
    yield from reader
