---
name: personalized-picture-book
description: "Personalized children's picture book: characters → story → storyboard → prompts → printable HTML/PDF."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [picture-book, children-story, storyboard, image-prompt, creative, privacy, family]
    category: creative
    related_skills: [baoyu-comic, humanizer, claude-design]
---

# Personalized Picture Book

## When to Use

Use this skill when the user wants a personalized children's picture book, bedtime story book, family keepsake book, or prompt pack where a child, sibling, parent, pet, or other authorized family character becomes part of the story.

Use it especially when the user asks for any of these:

- Uploading multiple reference photos for one character.
- Multiple characters in one book.
- Choosing an illustration style.
- Story text plus storyboard plus image prompts.
- Printable HTML or PDF output.
- A reusable workflow rather than a one-off story.

Do not use this skill for a single standalone illustration with no story structure. Do not use it for unauthorized photos of children or families.

## Core Position

Hermes should orchestrate the workflow and produce durable files. Image generation is optional and backend-dependent.

Current baseline output:

```text
picture-book/<book-slug>/
  source.md             # optional: raw user notes / intake transcript (LLM-authored)
  character_cards.json  # LLM-authored, drives prompt anchors
  story.json            # consumed by renderer
  storyboard.json       # consumed by renderer
  prompts.json          # consumed by renderer
  prompts/page_01.md    # optional human-readable prompt copy (LLM-authored)
  images/               # optional, populated only when images are generated
  book.html             # produced by scripts/render_book.py
  metadata.json         # optional run-summary (LLM-authored)
```

Only `story.json`, `storyboard.json`, `prompts.json`, and any files under `images/` are read by `scripts/render_book.py`. The other files are LLM-authored artifacts that capture intake, character anchors, and run notes — keep them durable but do not expect the renderer to create them.

`scripts/render_book.py` works without third-party Python dependencies and leaves image placeholders when images do not exist.

## Privacy and Safety Rules

Children's photos are sensitive. Follow these rules before style, speed, or convenience:

1. Only use photos the user provided or clearly controls.
2. Do not upload original child/family photos to third-party image services unless the user explicitly confirms that tradeoff.
3. Convert reference images into short character cards first. Prompts should use stable visual anchors, not raw private identity details.
4. Do not include real full names, school names, addresses, birthdays, phone numbers, or other identifying facts in prompts.
5. Use nicknames or role names such as "Star", "Little Explorer", "older brother", or `child_01`.
6. Keep stories age-appropriate by default for ages 3-6: warm conflict, simple language, no horror, no humiliation, no adult themes.
7. Rewrite copyrighted or brand-heavy style requests into descriptive art direction. For example, do not prompt "Disney/Pixar/Ghibli style"; use "warm cinematic 3D children's illustration, rounded original characters, soft light" or "gentle hand-painted watercolor picture-book style".
8. If a generated image fails or looks inconsistent, keep the prompts and printable placeholder book instead of pretending generation succeeded.

## Inputs

Minimum required inputs:

| Field | Type | Notes |
| --- | --- | --- |
| `characters` | array | At least one character with `id`, `display_name` or nickname, `role`, `age` when relevant, `relationship`, and traits. Optional `reference_images` may contain local paths for visual analysis. |
| `theme` | string | Story theme, such as "bravely facing the dark", "sharing toys with a younger sister", or "first day of kindergarten". |

Useful optional inputs:

| Field | Default | Notes |
| --- | --- | --- |
| `age_range` | `3-6` | Controls vocabulary, sentence length, emotional intensity, and plot complexity. |
| `page_count` | `12` | Prefer 8, 12, 16, or 24 pages. More than 24 pages should become a series or chapters. |
| `style` | `soft-watercolor` | Use one of the style presets below. |
| `language` | `zh` | Use `zh`, `en`, or `bilingual`. |
| `aspect_ratio` | `portrait` | Use `portrait`, `square`, or `landscape`. |
| `output_modes` | `story, storyboard, prompts, html` | Generate images only when requested and feasible. |
| `moral` | none | Optional value theme, kept gentle and non-preachy. |
| `custom_style_description` | none | Use with `style=custom`; rewrite unsafe or copyrighted style terms. |

## Style Presets

| ID | Use For | Prompt Anchor |
| --- | --- | --- |
| `soft-watercolor` | Bedtime, warmth, growth | warm watercolor, soft edges, low saturation, textured paper, children's book illustration |
| `cute-cartoon` | Light adventure, toddler-friendly scenes | cute cartoon, rounded shapes, playful proportions, bright but gentle colors |
| `classic-picture-book` | Print-first keepsake books | timeless picture book illustration, balanced composition, visible paper texture |
| `crayon-handdrawn` | Childlike, handmade, playful output | crayon texture, hand-drawn, pastel colors, simple shapes |
| `clay-toy` | Cozy 3D toy feeling | clay toy style, soft handmade 3D texture, cozy lighting |
| `paper-cutout` | Craft, collage, classroom themes | paper cutout collage, layered paper texture, playful shapes |
| `nature-realistic` | Animals, plants, science themes | gentle realistic nature illustration, accurate animals, child-friendly detail |
| `dreamy-fantasy` | Moon, stars, forest, magic | dreamy fantasy, glowing forest, soft magical atmosphere, original characters |
| `minimal-bedtime` | Low-stimulation night reading | minimal bedtime illustration, simple shapes, muted palette, calm mood |
| `custom` | User-specific art direction | Use `custom_style_description` after privacy and copyright rewriting. |

## Workflow

### 1. Intake

Collect characters, theme, age range, page count, language, style, output modes, and whether the user wants actual image generation.

Reasonable defaults are allowed:

- `page_count=12`
- `language=zh`
- `age_range=3-6`
- `style=soft-watercolor`
- `output_modes=story, storyboard, prompts, html`

Only ask a clarifying question if the request lacks both a character and a theme, or if image upload to an external service is requested without consent.

### 2. Character Cards

Create `character_cards.json` before writing the story. For each character:

- Merge user text traits with visual traits inferred from authorized reference images.
- Prefer stable traits over one-photo accidents.
- Keep the prompt anchor short enough to repeat on every page.
- Avoid sensitive identity details.
- For multiple people, make each character visually distinct by role, outfit, age, and signature action.

Suggested character card:

```json
{
  "id": "child_01",
  "display_name": "Little Explorer",
  "role": "protagonist",
  "age": 5,
  "relationship": "main child",
  "visual_traits": {
    "face_hair": "round face, short black hair, bright eyes",
    "clothing": "blue hoodie, white sneakers",
    "signature": "raises both hands when excited"
  },
  "personality_traits": ["curious", "a little shy", "likes dinosaurs"],
  "prompt_anchor": "a 5-year-old child with a round face, short black hair, blue hoodie, white sneakers, cheerful and curious, consistent hairstyle and outfit"
}
```

### 3. Story

Create `story.json` with title, subtitle when useful, target age, moral summary, and one page object per page.

Writing constraints:

- Use 1-2 short sentences per page by default.
- Use repeated phrases and readable rhythm for young children.
- Make the emotional arc safe: small worry, gentle action, warm resolution.
- Keep educational/moral points embedded in action rather than lecture.
- For bilingual books, keep each page short in both languages.

### 4. Storyboard

Create `storyboard.json` with one page object per page. Each page should include:

- Page number.
- Narration.
- Scene.
- Characters in scene.
- Visual focus.
- Action.
- Expression.
- Lighting.
- Mood.
- Color palette.

For multi-character pages, state exactly who appears and who is the visual focus. Limit crowded scenes; if a page includes several characters, use clear positions such as left/right/center.

### 5. Image Prompts

Create `prompts.json` and `prompts/page_NN.md`. Each page prompt should combine:

- Style preset.
- Character anchors.
- Scene.
- Action.
- Lighting.
- Mood.
- Composition.
- Constraints.

Use this structure:

```text
[STYLE] warm watercolor children's book illustration, soft edges, low saturation, textured paper.
[CHARACTER CONSISTENCY] child_01: a 5-year-old child with a round face, short black hair, blue hoodie, white sneakers. Keep the same hairstyle and outfit across pages.
[SCENE] A glowing nighttime forest with leaves like tiny lanterns.
[ACTION] The child holds a small flashlight and walks beside a friendly tiny dinosaur.
[MOOD] curious, brave, cozy, safe.
[CONSTRAINTS] no text, no watermark, no scary elements, do not distort faces, do not merge characters.
```

Recommended negative prompt for tools that support it:

```text
text, watermark, logo, scary, horror, distorted face, extra fingers, merged characters, inconsistent outfit, adult themes, photorealistic identity match
```

### 6. Optional Image Generation

Default to prompt output and HTML placeholders. If the user asks to generate images:

1. Explain whether the available backend supports reference images or only text prompts.
2. Ask for explicit confirmation before any external upload of child/family photos.
3. Generate a 2-3 page sample first when possible.
4. Save generated images under `images/`.
5. Re-run `scripts/render_book.py` so `book.html` embeds the images.

### 7. Layout and Export

Use the bundled renderer:

```bash
python3 skills/creative/personalized-picture-book/scripts/render_book.py \
  --input-dir picture-book/my-book \
  --output picture-book/my-book/book.html
```

If `story.json`, `storyboard.json`, and `prompts.json` are in different locations:

```bash
python3 skills/creative/personalized-picture-book/scripts/render_book.py \
  --story /path/to/story.json \
  --storyboard /path/to/storyboard.json \
  --prompts /path/to/prompts.json \
  --images-dir /path/to/images \
  --output /path/to/book.html
```

For PDF, first produce `book.html`. Then either use browser Print to PDF or run the renderer with `--pdf /path/to/book.pdf` if Playwright is installed in the active environment.

## JSON Shape

The renderer accepts flexible JSON, but this shape is preferred:

`story.json`:

```json
{
  "title": "The Little Explorer and the Moon Forest",
  "subtitle": "A bedtime adventure",
  "language": "en",
  "age_range": "3-6",
  "moral_summary": "Courage can be quiet and gentle.",
  "pages": [
    {
      "page": 1,
      "text": "Little Explorer heard a tiny tap at the window. Tap, tap, tap."
    }
  ]
}
```

For `language: "bilingual"`, give each page parallel `zh` and `en` fields instead of `text` — the renderer concatenates them with a line break:

```json
{
  "title": "月光森林",
  "subtitle": "Moon Forest",
  "language": "bilingual",
  "pages": [
    {
      "page": 1,
      "zh": "小探险家听到窗边轻轻一声：嗒，嗒，嗒。",
      "en": "Little Explorer heard a tiny tap at the window. Tap, tap, tap."
    }
  ]
}
```

`storyboard.json`:

```json
{
  "pages": [
    {
      "page": 1,
      "scene": "A cozy bedroom under moonlight.",
      "characters_in_scene": ["child_01"],
      "visual_focus": "child_01",
      "action": "The child sits up and listens.",
      "lighting": "soft moonlight",
      "mood": "curious and safe"
    }
  ]
}
```

`prompts.json`:

```json
{
  "prompts": [
    {
      "page": 1,
      "prompt": "[STYLE] warm watercolor... [SCENE] cozy bedroom...",
      "negative_prompt": "text, watermark, scary elements",
      "image_path": "images/page_01.png"
    }
  ]
}
```

## Verification Checklist

- `character_cards.json` avoids real full names, school names, addresses, birthdays, and raw photo paths.
- `story.json` page count matches the requested page count.
- Every page has age-appropriate narration.
- `storyboard.json` includes scene, action, characters, visual focus, lighting, and mood.
- `prompts.json` repeats stable character anchors and style constraints.
- Multi-character prompts clearly separate roles and appearances.
- `book.html` opens locally and print preview is coherent.
- Image generation was either skipped, locally handled, or explicitly authorized if external services were used.

## Failure Handling

| Situation | Response |
| --- | --- |
| Missing character or theme | Ask for the smallest missing input. |
| Reference images are unreadable | Continue from text traits and say which images were skipped. |
| User requests external upload of child photos | Explain privacy risk and ask for explicit confirmation. |
| Multi-character prompts mix people | Reduce character count per page, restate visual focus, strengthen prompt anchors. |
| Image generation fails | Keep prompts and placeholder HTML; explain how to retry. |
| PDF export dependency is unavailable | Deliver `book.html` and suggest browser Print to PDF. |
