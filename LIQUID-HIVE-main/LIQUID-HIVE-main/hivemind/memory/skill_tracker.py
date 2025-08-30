import json, pathlib, math

class SkillTracker:
    def __init__(self, path="./runs/skills.json"):
        self.path = pathlib.Path(path)
        self.state = {}
        if self.path.exists():
            try:
                self.state = json.loads(self.path.read_text())
            except Exception:
                self.state = {}

    def update(self, tag: str, win: bool, alpha: float = 0.2):
        s = self.state.get(tag, {"p": 0.5})
        s["p"] = alpha* (1.0 if win else 0.0) + (1-alpha)*s["p"]
        self.state[tag] = s
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.state, indent=2))
        return s["p"]
