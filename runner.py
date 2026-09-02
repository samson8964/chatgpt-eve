import ast
import base64
import gzip
from pathlib import Path


def main():
    text = Path("scanner.py").read_text(encoding="utf-8")
    tree = ast.parse(text, filename="scanner.py")

    payload = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "b64decode" and node.args:
                arg = node.args[0]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    payload = arg.value
                    break

    if not payload:
        raise RuntimeError("Could not locate embedded scanner payload")

    # Base64 padding may be stripped when the compact scanner is generated.
    payload += "=" * (-len(payload) % 4)
    compressed = base64.b64decode(payload)
    source = gzip.decompress(compressed).decode("utf-8")
    exec(compile(source, "scanner_payload.py", "exec"), {"__name__": "__main__"})


if __name__ == "__main__":
    main()
