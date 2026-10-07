from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class RejectionFunnel:
    stages: dict[str, int] = field(default_factory=dict)
    reasons: Counter = field(default_factory=Counter)

    def stage(self, name: str, count: int) -> None:
        self.stages[str(name)] = max(0, int(count))

    def reject(self, reason: str, count: int = 1) -> None:
        if count > 0:
            self.reasons[str(reason)] += int(count)

    def to_dict(self) -> dict:
        return {"stages": dict(self.stages), "rejection_reasons": dict(self.reasons)}

    def write_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n", "utf-8")

    def markdown(self, title: str = "V3 Rejection Funnel") -> str:
        lines = [f"# {title}", "", "## Stages", ""]
        for name, value in self.stages.items():
            lines.append(f"- {name}: `{value}`")
        lines += ["", "## Rejection reasons", ""]
        if not self.reasons:
            lines.append("- none")
        else:
            for reason, value in self.reasons.most_common():
                lines.append(f"- {reason}: `{value}`")
        return "\n".join(lines) + "\n"
