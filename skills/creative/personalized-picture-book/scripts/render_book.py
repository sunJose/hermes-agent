#!/usr/bin/env python3
"""Render a personalized picture-book package to printable HTML.

The script intentionally uses only the Python standard library. Optional PDF
export uses Playwright if it is already installed in the active environment.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from typing import Any


IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".gif")


def load_json(path: Path | None, default: Any) -> Any:
    if path is None or not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc


def as_list(data: Any, *keys: str) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        for key in keys:
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def page_number(item: dict[str, Any], fallback: int) -> int:
    value = item.get("page", item.get("page_num", item.get("page_number", fallback)))
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def keyed_by_page(items: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    return {page_number(item, index): item for index, item in enumerate(items, start=1)}


def text_from_page(page: dict[str, Any]) -> str:
    for key in ("text", "narration", "copy", "content"):
        value = page.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    zh = page.get("zh")
    en = page.get("en")
    if isinstance(zh, str) and isinstance(en, str):
        return f"{zh.strip()}\n{en.strip()}"
    return ""


def first_existing_image(
    page_num: int,
    images_dir: Path | None,
    base_dir: Path | None,
    *candidates: Any,
) -> Path | None:
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(str(candidate))
        if not path.is_absolute():
            anchors: list[Path] = []
            if base_dir is not None:
                anchors.append(base_dir)
            if images_dir is not None:
                anchors.append(images_dir)
            for anchor in anchors:
                resolved = anchor / path
                if resolved.exists() and resolved.is_file():
                    return resolved
            # Final fallback: interpret relative to CWD.
            if path.exists() and path.is_file():
                return path
        elif path.exists() and path.is_file():
            return path

    if images_dir is None or not images_dir.exists():
        return None

    stems = [
        f"page_{page_num:02d}",
        f"page-{page_num:02d}",
        f"{page_num:02d}",
        f"page_{page_num}",
        f"page-{page_num}",
        str(page_num),
    ]
    for stem in stems:
        for ext in IMAGE_EXTENSIONS:
            candidate = images_dir / f"{stem}{ext}"
            if candidate.exists():
                return candidate
    return None


def file_uri(path: Path) -> str:
    return path.resolve().as_uri()


def css_class(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower())
    return value.strip("-") or "picture-book"


def html_block(text: str) -> str:
    escaped = html.escape(text)
    return "<br>\n".join(escaped.splitlines())


def render_prompt(prompt: dict[str, Any]) -> str:
    parts = []
    prompt_text = prompt.get("prompt")
    if isinstance(prompt_text, str) and prompt_text.strip():
        parts.append(prompt_text.strip())
    negative = prompt.get("negative_prompt")
    if isinstance(negative, str) and negative.strip():
        parts.append(f"Negative: {negative.strip()}")
    return "\n\n".join(parts)


def render_html(
    *,
    story: dict[str, Any],
    story_pages: list[dict[str, Any]],
    storyboard_by_page: dict[int, dict[str, Any]],
    prompts_by_page: dict[int, dict[str, Any]],
    images_dir: Path | None,
    base_dir: Path | None,
    paper: str,
    show_prompts: bool,
) -> str:
    title = str(story.get("title") or "Personalized Picture Book")
    subtitle = str(story.get("subtitle") or "")
    age_range = str(story.get("age_range") or story.get("reading_level") or "")
    moral_summary = str(story.get("moral_summary") or story.get("moral") or "")
    paper_class = css_class(paper)
    page_size = {
        "A4": "A4",
        "A5": "A5",
        "Letter": "Letter",
        "square": "148mm 148mm",
    }.get(paper, "A5")

    page_items: list[str] = []
    for index, story_page in enumerate(story_pages, start=1):
        number = page_number(story_page, index)
        storyboard = storyboard_by_page.get(number, {})
        prompt = prompts_by_page.get(number, {})
        image = first_existing_image(
            number,
            images_dir,
            base_dir,
            story_page.get("image_path"),
            storyboard.get("image_path"),
            prompt.get("image_path"),
        )
        narration = text_from_page(story_page) or str(storyboard.get("narration") or "")
        scene = str(storyboard.get("scene") or storyboard.get("scene_description") or "")
        action = str(storyboard.get("action") or "")
        mood = str(storyboard.get("mood") or "")
        lighting = str(storyboard.get("lighting") or "")
        prompt_text = render_prompt(prompt)

        if image:
            image_html = (
                f'<img class="page-image" src="{html.escape(file_uri(image))}" '
                f'alt="Illustration for page {number}">'
            )
        else:
            placeholder_text = prompt_text or scene or "Illustration placeholder"
            image_html = (
                '<div class="image-placeholder">'
                '<span>Illustration placeholder</span>'
                f'<p>{html_block(placeholder_text)}</p>'
                '</div>'
            )

        storyboard_bits = [
            ("Scene", scene),
            ("Action", action),
            ("Lighting", lighting),
            ("Mood", mood),
        ]
        storyboard_html = "\n".join(
            f"<li><strong>{label}:</strong> {html_block(value)}</li>"
            for label, value in storyboard_bits
            if value
        )

        prompt_html = ""
        if show_prompts and prompt_text:
            prompt_html = (
                '<details class="prompt-details">'
                '<summary>Image prompt</summary>'
                f'<pre>{html.escape(prompt_text)}</pre>'
                '</details>'
            )

        page_items.append(
            f"""
            <section class="book-page interior-page">
              <div class="page-art">{image_html}</div>
              <div class="page-copy">
                <div class="page-number">Page {number}</div>
                <p class="narration">{html_block(narration)}</p>
                <ul class="storyboard-notes">{storyboard_html}</ul>
                {prompt_html}
              </div>
            </section>
            """
        )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      --ink: #24201c;
      --muted: #6d655d;
      --paper: #fffaf1;
      --paper-deep: #f3e3ca;
      --accent: #4f8f8b;
      --line: #dbc8aa;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      background: #e8ddd0;
      font-family: ui-serif, Georgia, "Times New Roman", serif;
      line-height: 1.55;
    }}
    .book {{
      max-width: 980px;
      margin: 0 auto;
      padding: 24px;
    }}
    .book-page {{
      min-height: 720px;
      margin: 0 0 24px;
      padding: 36px;
      background: var(--paper);
      border: 1px solid var(--line);
      display: grid;
      grid-template-columns: minmax(0, 1.25fr) minmax(280px, 0.75fr);
      gap: 28px;
      break-after: page;
      page-break-after: always;
    }}
    .cover-page {{
      align-items: center;
      grid-template-columns: 1fr;
      text-align: center;
      background:
        linear-gradient(180deg, rgba(255,250,241,0.92), rgba(255,250,241,0.98)),
        radial-gradient(circle at 30% 20%, #d4ece8, transparent 30%),
        radial-gradient(circle at 70% 80%, #f6d8a8, transparent 28%);
    }}
    .cover-page h1 {{
      margin: 0;
      font-size: 52px;
      line-height: 1.05;
      letter-spacing: 0;
    }}
    .cover-page p {{
      margin: 16px auto 0;
      max-width: 620px;
      color: var(--muted);
      font-size: 22px;
    }}
    .cover-meta {{
      margin-top: 28px;
      color: var(--muted);
      font-size: 14px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .page-art {{
      min-height: 420px;
      display: flex;
      align-items: stretch;
    }}
    .page-image, .image-placeholder {{
      width: 100%;
      min-height: 420px;
      border-radius: 6px;
    }}
    .page-image {{
      object-fit: cover;
      border: 1px solid var(--line);
      background: #eee;
    }}
    .image-placeholder {{
      border: 2px dashed var(--line);
      background: linear-gradient(135deg, #fffdf8, var(--paper-deep));
      padding: 24px;
      display: flex;
      flex-direction: column;
      justify-content: center;
      color: var(--muted);
    }}
    .image-placeholder span {{
      display: block;
      color: var(--accent);
      font-family: ui-sans-serif, system-ui, sans-serif;
      font-size: 13px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .image-placeholder p {{
      margin: 14px 0 0;
      font-size: 13px;
      line-height: 1.45;
    }}
    .page-copy {{
      display: flex;
      flex-direction: column;
      justify-content: center;
    }}
    .page-number {{
      margin-bottom: 18px;
      color: var(--accent);
      font-family: ui-sans-serif, system-ui, sans-serif;
      font-size: 13px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .narration {{
      margin: 0;
      font-size: 28px;
      line-height: 1.42;
    }}
    .storyboard-notes {{
      margin: 24px 0 0;
      padding: 0;
      list-style: none;
      color: var(--muted);
      font-family: ui-sans-serif, system-ui, sans-serif;
      font-size: 13px;
    }}
    .storyboard-notes li + li {{ margin-top: 8px; }}
    .prompt-details {{
      margin-top: 20px;
      color: var(--muted);
      font-family: ui-sans-serif, system-ui, sans-serif;
      font-size: 13px;
    }}
    .prompt-details pre {{
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      padding: 12px;
      background: #f7eddf;
      border: 1px solid var(--line);
      border-radius: 4px;
    }}
    .back-cover {{
      min-height: 420px;
      grid-template-columns: 1fr;
      align-items: center;
      text-align: center;
    }}
    .back-cover p {{
      max-width: 640px;
      margin: 0 auto;
      font-size: 24px;
      color: var(--muted);
    }}
    @page {{
      size: {html.escape(page_size)};
      margin: 12mm;
    }}
    @media print {{
      body {{ background: #fff; }}
      .book {{ max-width: none; padding: 0; }}
      .book-page {{ margin: 0; border: 0; min-height: calc(100vh - 24mm); }}
      .prompt-details {{ display: none; }}
    }}
    @media (max-width: 760px) {{
      .book {{ padding: 12px; }}
      .book-page {{ grid-template-columns: 1fr; padding: 22px; }}
      .cover-page h1 {{ font-size: 38px; }}
      .narration {{ font-size: 23px; }}
    }}
  </style>
</head>
<body class="{paper_class}">
  <main class="book">
    <section class="book-page cover-page">
      <div>
        <h1>{html.escape(title)}</h1>
        {f'<p>{html_block(subtitle)}</p>' if subtitle else ''}
        <div class="cover-meta">{html.escape(age_range)}</div>
      </div>
    </section>
    {''.join(page_items)}
    {f'<section class="book-page back-cover"><p>{html_block(moral_summary)}</p></section>' if moral_summary else ''}
  </main>
</body>
</html>
"""


def write_pdf(html_path: Path, pdf_path: Path) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SystemExit(
            "PDF export requires Playwright. Install/configure Playwright or use browser Print to PDF from book.html."
        ) from exc

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(html_path.resolve().as_uri(), wait_until="networkidle")
        page.pdf(path=str(pdf_path), print_background=True, prefer_css_page_size=True)
        browser.close()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, help="Directory containing story.json/storyboard.json/prompts.json")
    parser.add_argument("--story", type=Path, help="Path to story.json")
    parser.add_argument("--storyboard", type=Path, help="Path to storyboard.json")
    parser.add_argument("--prompts", type=Path, help="Path to prompts.json")
    parser.add_argument("--images-dir", type=Path, help="Directory containing generated page images")
    parser.add_argument("--output", type=Path, help="Output HTML path")
    parser.add_argument("--pdf", type=Path, help="Optional PDF output path; requires Playwright")
    parser.add_argument("--paper", default="A5", choices=["A4", "A5", "Letter", "square"], help="Print page size")
    parser.add_argument("--hide-prompts", action="store_true", help="Hide prompt details in screen HTML")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    input_dir = args.input_dir

    story_path = args.story or (input_dir / "story.json" if input_dir else None)
    storyboard_path = args.storyboard or (input_dir / "storyboard.json" if input_dir else None)
    prompts_path = args.prompts or (input_dir / "prompts.json" if input_dir else None)
    images_dir = args.images_dir or (input_dir / "images" if input_dir else None)
    output = args.output or (input_dir / "book.html" if input_dir else Path("book.html"))

    story_data = load_json(story_path, {})
    storyboard_data = load_json(storyboard_path, {})
    prompts_data = load_json(prompts_path, {})
    if not isinstance(story_data, dict):
        raise SystemExit("story.json must be a JSON object")

    story_pages = as_list(story_data, "pages", "story_pages")
    if not story_pages:
        raise SystemExit("story.json must contain a non-empty pages array")

    storyboard_by_page = keyed_by_page(as_list(storyboard_data, "pages", "storyboard"))
    prompts_by_page = keyed_by_page(as_list(prompts_data, "prompts", "pages"))

    output.parent.mkdir(parents=True, exist_ok=True)
    base_dir = input_dir or (story_path.parent if story_path else None)
    rendered = render_html(
        story=story_data,
        story_pages=story_pages,
        storyboard_by_page=storyboard_by_page,
        prompts_by_page=prompts_by_page,
        images_dir=images_dir,
        base_dir=base_dir,
        paper=args.paper,
        show_prompts=not args.hide_prompts,
    )
    output.write_text(rendered, encoding="utf-8")
    print(f"Wrote {output}")

    if args.pdf:
        args.pdf.parent.mkdir(parents=True, exist_ok=True)
        write_pdf(output, args.pdf)
        print(f"Wrote {args.pdf}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
