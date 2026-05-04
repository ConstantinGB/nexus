from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path


class NotesData:
    """Notes storage — ported from Thallid, PyQt6 removed."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.data_dir / "index.json"
        self.notes: list[dict] = self._load()

    def _load(self) -> list[dict]:
        if self.index_file.exists():
            with open(self.index_file) as f:
                return json.load(f)
        return []

    def _save_index(self) -> None:
        with open(self.index_file, "w") as f:
            json.dump(self.notes, f, indent=2)

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def create_note(self, title: str, content: str = "", tags: list[str] | None = None) -> dict:
        note_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        note = {
            "id": note_id,
            "title": title,
            "created": datetime.now().isoformat(),
            "modified": datetime.now().isoformat(),
            "tags": tags or [],
            "file": f"{note_id}.md",
        }
        note_file = self.data_dir / note["file"]
        note_file.write_text(content, encoding="utf-8")
        self.notes.append(note)
        self._save_index()
        return note

    def update_note(self, note_id: str, content: str) -> None:
        for note in self.notes:
            if note["id"] == note_id:
                note["modified"] = datetime.now().isoformat()
                (self.data_dir / note["file"]).write_text(content, encoding="utf-8")
                break
        self._save_index()

    def delete_note(self, note_id: str) -> None:
        for note in self.notes:
            if note["id"] == note_id:
                path = self.data_dir / note["file"]
                if path.exists():
                    path.unlink()
                self.notes.remove(note)
                break
        self._save_index()

    def get_content(self, note_id: str) -> str:
        for note in self.notes:
            if note["id"] == note_id:
                path = self.data_dir / note["file"]
                return path.read_text(encoding="utf-8") if path.exists() else ""
        return ""

    # ── Queries ───────────────────────────────────────────────────────────────

    def search(self, query: str) -> list[dict]:
        q = query.lower()
        return [
            n for n in self.notes
            if q in n["title"].lower()
            or any(q in t.lower() for t in n.get("tags", []))
        ]

    def get_by_id(self, note_id: str) -> dict | None:
        return next((n for n in self.notes if n["id"] == note_id), None)
