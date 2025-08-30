import logging
from pathlib import Path
from typing import List

log = logging.getLogger(__name__)

class AlignmentCore:
    """Loads immutable alignment principles and exposes them for runtime checks."""
    def __init__(self, principles_file: str = "core_principles/alignment_core.txt"):
        self.principles_file = Path(principles_file)
        self.principles: List[str] = []
        self.load()

    def load(self) -> None:
        try:
            if self.principles_file.exists():
                self.principles = [ln.strip() for ln in self.principles_file.read_text(encoding="utf-8").splitlines() if ln.strip()]
            else:
                self.principles = ["Do no harm.", "Be truthful.", "Respect operator control."]
            log.info("Alignment principles loaded: %d", len(self.principles))
        except Exception as e:
            log.error("Failed to load alignment principles: %s", e)
            self.principles = []

    def list(self) -> List[str]:
        return list(self.principles)
