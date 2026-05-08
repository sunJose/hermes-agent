from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "skills"
    / "creative"
    / "personalized-picture-book"
    / "scripts"
    / "render_book.py"
)
SKILL_PATH = (
    Path(__file__).resolve().parents[2]
    / "skills"
    / "creative"
    / "personalized-picture-book"
    / "SKILL.md"
)


def load_module():
    spec = importlib.util.spec_from_file_location("personalized_picture_book_render", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_skill_document_points_to_renderer():
    text = SKILL_PATH.read_text(encoding="utf-8")
    assert "name: personalized-picture-book" in text
    assert "scripts/render_book.py" in text
    assert "Privacy and Safety Rules" in text
    assert "multiple reference photos" in text


def test_render_book_creates_printable_html_with_prompt_placeholder(tmp_path: Path):
    mod = load_module()
    book_dir = tmp_path / "book"
    book_dir.mkdir()
    (book_dir / "story.json").write_text(
        json.dumps(
            {
                "title": "Moon Forest",
                "subtitle": "A gentle bedtime story",
                "age_range": "3-6",
                "moral_summary": "Courage can be quiet.",
                "pages": [
                    {
                        "page": 1,
                        "text": "Little Explorer heard a tiny tap at the window.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (book_dir / "storyboard.json").write_text(
        json.dumps(
            {
                "pages": [
                    {
                        "page": 1,
                        "scene": "A cozy bedroom under moonlight.",
                        "action": "The child sits up and listens.",
                        "lighting": "soft moonlight",
                        "mood": "curious and safe",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (book_dir / "prompts.json").write_text(
        json.dumps(
            {
                "prompts": [
                    {
                        "page": 1,
                        "prompt": "[STYLE] warm watercolor\n[SCENE] cozy bedroom",
                        "negative_prompt": "text, watermark",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    output = book_dir / "book.html"
    assert mod.main(["--input-dir", str(book_dir), "--output", str(output)]) == 0

    html = output.read_text(encoding="utf-8")
    assert "Moon Forest" in html
    assert "Little Explorer heard a tiny tap" in html
    assert "Illustration placeholder" in html
    assert "[STYLE] warm watercolor" in html
    assert "Courage can be quiet." in html


def test_render_book_renders_bilingual_pages(tmp_path: Path):
    mod = load_module()
    book_dir = tmp_path / "book"
    book_dir.mkdir()
    (book_dir / "story.json").write_text(
        json.dumps(
            {
                "title": "月光森林",
                "subtitle": "Moon Forest",
                "language": "bilingual",
                "pages": [
                    {
                        "page": 1,
                        "zh": "小探险家听到窗边轻轻一声。",
                        "en": "Little Explorer heard a tiny tap at the window.",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (book_dir / "storyboard.json").write_text(json.dumps({"pages": []}), encoding="utf-8")
    (book_dir / "prompts.json").write_text(json.dumps({"prompts": []}), encoding="utf-8")

    output = book_dir / "book.html"
    assert mod.main(["--input-dir", str(book_dir), "--output", str(output)]) == 0

    html = output.read_text(encoding="utf-8")
    assert "小探险家听到窗边轻轻一声。" in html
    assert "Little Explorer heard a tiny tap at the window." in html


def test_render_book_embeds_existing_page_image(tmp_path: Path):
    mod = load_module()
    book_dir = tmp_path / "book"
    images = book_dir / "images"
    images.mkdir(parents=True)
    image_path = images / "page_01.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    (book_dir / "story.json").write_text(
        json.dumps({"title": "Image Book", "pages": [{"page": 1, "text": "Page text."}]}),
        encoding="utf-8",
    )
    (book_dir / "storyboard.json").write_text(json.dumps({"pages": []}), encoding="utf-8")
    (book_dir / "prompts.json").write_text(json.dumps({"prompts": []}), encoding="utf-8")

    output = book_dir / "book.html"
    assert mod.main(["--input-dir", str(book_dir), "--output", str(output)]) == 0

    html = output.read_text(encoding="utf-8")
    assert image_path.resolve().as_uri() in html
    assert "Illustration placeholder" not in html
