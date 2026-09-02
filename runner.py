import base64
import gzip
import hashlib
from pathlib import Path

EXPECTED_SOURCE_SHA256 = "a509a25578b2d596123d6443d9caa5c213f33b11dbd9c5f240b7866bb3540154"


def main():
    payload_dir = Path("payload")
    chunks = sorted(payload_dir.glob("*.txt"))
    if not chunks:
        raise RuntimeError("No payload chunks found")

    payload = "".join(p.read_text(encoding="utf-8").strip() for p in chunks)
    compressed = base64.b64decode(payload, validate=True)
    source_bytes = gzip.decompress(compressed)
    digest = hashlib.sha256(source_bytes).hexdigest()
    if digest != EXPECTED_SOURCE_SHA256:
        raise RuntimeError(
            f"Scanner source checksum mismatch: got {digest}, expected {EXPECTED_SOURCE_SHA256}"
        )

    source = source_bytes.decode("utf-8")
    print(f"Loaded scanner from {len(chunks)} chunks; source SHA256 verified.")
    exec(compile(source, "scanner_payload.py", "exec"), {"__name__": "__main__"})


if __name__ == "__main__":
    main()
