import json
from pathlib import Path


class Save:
    def __init__(self, path: Path):
        try:
            with open(path, "r") as f:
                data = json.load(f)
            self.last_stage = data["last_stage"]
        except (OSError, json.JSONDecodeError, KeyError):
            print(f"Could not read save file {path!r}")
            print("But that's okay.")
            self.last_stage = "title-screen"
        self.path = path

    def save(self):
        try:
            with open(self.path, "w") as f:
                json.dump({ "last_stage": self.last_stage }, f)
        except (OSError, ValueError):
            print(f"Could not write to save file {self.path!r}")
