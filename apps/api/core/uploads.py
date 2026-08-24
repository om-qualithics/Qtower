from fastapi import UploadFile


class UploadTooLargeError(Exception):
    pass


async def read_limited(file: UploadFile, max_bytes: int) -> bytes:
    """Reads an UploadFile in bounded chunks, bailing out as soon as
    max_bytes is exceeded rather than buffering an arbitrarily large body
    into memory first and only checking the size afterward - a plain
    `await file.read()` lets any authenticated user hand the process a
    multi-GB body and exhaust its RAM before either the endpoint's own
    size check or the eventual 413/400 response ever runs."""
    chunk_size = 1024 * 1024
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise UploadTooLargeError(f"File exceeds the {max_bytes} byte limit")
        chunks.append(chunk)
    return b"".join(chunks)
