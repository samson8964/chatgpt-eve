import ast
import base64
import gzip
import hashlib
import math
from pathlib import Path

EXPECTED_SOURCE_SHA256 = "a509a25578b2d596123d6443d9caa5c213f33b11dbd9c5f240b7866bb3540154"


def safe_int(value):
    try:
        if value is None:
            return 0
        number = float(value)
        if not math.isfinite(number):
            return 0
        return int(number)
    except (TypeError, ValueError, OverflowError):
        return 0


class ScoreRowIntGuard(ast.NodeTransformer):
    """Only harden one-argument int(...) calls inside score_row."""

    def __init__(self):
        self.in_score_row = False

    def visit_FunctionDef(self, node):
        previous = self.in_score_row
        if node.name == "score_row":
            self.in_score_row = True
        self.generic_visit(node)
        self.in_score_row = previous
        return node

    def visit_Call(self, node):
        self.generic_visit(node)
        if (
            self.in_score_row
            and isinstance(node.func, ast.Name)
            and node.func.id == "int"
            and len(node.args) == 1
            and not node.keywords
        ):
            node.func = ast.copy_location(ast.Name(id="__safe_int", ctx=ast.Load()), node.func)
        return node


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
    tree = ast.parse(source, filename="scanner_payload.py")
    tree = ScoreRowIntGuard().visit(tree)
    ast.fix_missing_locations(tree)

    print(f"Loaded scanner from {len(chunks)} chunks; source SHA256 verified; NaN int guard enabled.")
    exec(
        compile(tree, "scanner_payload.py", "exec"),
        {"__name__": "__main__", "__safe_int": safe_int},
    )


if __name__ == "__main__":
    main()
