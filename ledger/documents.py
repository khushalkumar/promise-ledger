from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader


@dataclass(frozen=True)
class LoadedDocument:
    name: str
    text: str


def load_document(path: Path) -> LoadedDocument:
    if path.suffix.lower() == ".pdf":
        reader = PdfReader(path)
        pages = [
            f"--- Page {number} ---\n{page.extract_text() or ''}"
            for number, page in enumerate(reader.pages, start=1)
        ]
        text = "\n\n".join(pages)
    else:
        text = path.read_text()
    return LoadedDocument(name=path.name, text=text)
