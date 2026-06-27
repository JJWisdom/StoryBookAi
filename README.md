# StoryForge
Formerly StoryBookAI

StoryForge is a Windows desktop app that turns a short story into an illustrated storybook. You write a story, it splits into per-sentence slides, generates a local AI image for each slide via Stable Diffusion Forge, overlays the story text onto the images, and exports the result as a PDF or ZIP.

Built as a personal project and Claude Corps portfolio piece.

<!-- TODO: screenshot or GIF here -->

---

## What It Does

- Write a story and auto-split it into slides, one per sentence
- Generate an image for each slide locally via Stable Diffusion Forge
- Optional Claude prompt enhancement, falls back to a built-in keyword builder if no key is provided
- Cross-slide context so characters and settings stay consistent
- Text overlay rendered onto each generated image
- Export to PDF or ZIP

---

## Requirements

- Windows 10/11
- Python 3.8+
- A local Stable Diffusion Forge portable build
- A Stable Diffusion model, SD1.5 or anime models recommended
- An Anthropic API key, optional

---

## Setup

```bat
python -m venv venv
venv\Scripts\activate.bat
pip install -r requirements.txt
python setup_project.py
```

Or run the launcher, it activates the venv and offers to run setup on first launch.

```bat
run.bat
```

---

## Configuration

Config files are personal and git-ignored. Copy the template and fill it in.

```bat
copy storybook_config_template.json storybook_config.json
```

Key fields:

| Field | What it does |
|---|---|
| `forge.path` | Absolute path to your Forge portable build folder |
| `forge.port` | API port Forge listens on |
| `generation.sampler` | Must match exactly what your Forge build has loaded |
| `generation.cfg_scale` | How closely the image follows the prompt |
| `generation.quality_prefix` | Appended after the scene description on normal slides, skipped on blocked content |
| `claude.prompt_style` | `tags` for SD1.5 and anime models, `natural` for SDXL |
| `claude.max_prompt_chars` | Prompt length cap, set to match your model's encoder |

The right values depend on your model. See `storybook_config_template.json` for the full annotated reference, it explains each field and what to set for SD1.5 versus SDXL.

Two things about Forge that are not obvious. The API has to be explicitly enabled in ForgeUI settings. The localhost popup also has to be turned off or it interferes with the headless startup.

### Claude API Key

On the first Illustrate press you will be asked whether to enable Claude prompt enhancement. If yes, enter your Anthropic API key. It is validated immediately with a test call and held in memory for the session only. It is never written to disk.

---

## Usage

1. Run `run.bat` and wait for Forge to start. First launch takes a few minutes.
2. Type your story and click Create Storybook.
3. For each slide, review the subjects and actions, edit the overlay text, click Illustrate.
4. Navigate with the arrows or numbered slide buttons. Add or remove slides as needed.
5. Click Publish to export as PDF or ZIP.

---

## Project Structure

| File | Role |
|---|---|
| `storybookgui.py` | Main Tkinter app, startup, story input, per-slide editor, generation pipeline |
| `forge_handler.py` | Launches Forge, monitors startup, calls the txt2img REST API |
| `claude_prompt_transformer.py` | Claude prompt enhancement with content safety handling |
| `simple_prompt_transformer.py` | Built-in keyword prompt builder, offline fallback |
| `image_processor.py` | Text overlay, font handling, image saving |
| `setup_project.py` / `setup_forge.py` | First-time setup |
| `run.bat` | Windows launcher |
| `storybook_config_template.json` | Annotated config reference |

---

## Safety

The app is built for kids. The Claude integration includes a content gate that runs before any prompt reaches Forge.

When `enhance_for_storybook()` is called, Claude evaluates the story text against a system prompt that includes:

- An explicit list of content categories to block, sexual content, illegal activity (violence, drugs, abuse, weapons, crime), gore, horror, and anything that sexualizes or harms children
- An idiom exclusion list so figurative language does not get flagged, phrases like "died of laughter", "killing it", "scared to death" are read by intended meaning, not literal words
- A `violation` field in the tool response schema, with values `none`, `accidental`, or `deliberate`

The classification comes back through tool use, so it is part of the structured response rather than something parsed out of free text.

If `violation` is `none`, the prompt goes to Forge as normal.

If `violation` is `accidental` (genuinely ambiguous or borderline), Claude returns a wholesome replacement prompt instead of the original. The first time this happens the app generates that image through Forge and caches it as `violation-unintent.png`, then reuses the cached file on later accidental hits.

If `violation` is `deliberate` (clear misuse, like "person X kills person Y"), Claude returns a different replacement prompt, cached as `violation-intent.png`. The accidental case gets a soft fallback image. The deliberate case gets a deliberately off-putting one.

Each violation type uses its own fixed safe negative prompt, chosen at generation time by `get_safe_negative()`.

This does not apply to the keyword transformer fallback. If Claude is not configured there is no content gate, because the safety screening lives inside the Claude call. The app does not filter prompts going to Forge on its own.

---

## Claude Details

A few things about how the Claude integration works that are not obvious from the config.

**Model-matched prompting.** Claude does not prompt the same way for every model, but you set this, the app does not detect it for you. `claude.prompt_style` switches between two formats. `tags` produces short comma-separated Danbooru-style keywords for SD1.5 and anime models. `natural` produces descriptive English phrases for SDXL. The character budget (`max_prompt_chars`) changes with it because the two encoders fit different amounts. Set both to match whatever model you have loaded.

**Prompt caching.** The system prompt is the largest fixed cost on every call, so it is sent with `cache_control` set to ephemeral. Repeat calls read it from cache instead of paying full input cost each time.

**Tool use over JSON parsing.** Claude is forced to call a single tool with a fixed schema. The response comes back as a validated dict with `prompt`, `negative_prompt`, and `violation` fields. There is no string parsing, no markdown fence stripping, no guessing at key names.

**Name stripping for accuracy.** The system prompt replaces character names with a gender or species descriptor. Stable Diffusion has no idea what "Bob" looks like, so a name produces an inconsistent character. Claude turns it into something like "a man" or "a small dog", which gives the model something concrete to render and keeps the character consistent across slides.

**Cost.** Roughly $0.00003 per ten-slide storybook on Haiku. Fractions of a cent.

**Failure handling.** Auth errors, rate limits, connection failures, and API status errors are each caught separately with their own message. Some disable Claude for the rest of the session and fall back to the keyword builder. The user always sees what happened rather than a silent failure.

---

## Troubleshooting

**Forge won't start or times out.** Run `quick_test.py` with Forge already running to confirm the API is reachable. Make sure `forge.path` points to the folder containing `run.bat`.

**Wrong sampler name.** Sampler names have to match exactly what your Forge installation has. Check the Forge web UI dropdown.

**PDF export unavailable.** Install `reportlab` with `pip install reportlab`. The app falls back to ZIP if it is not found.

**Images generating at the wrong size.** Check `generation.width` and `generation.height` in your config. The right resolution depends on your model, the template explains what to use for SD1.5 versus SDXL.

---

## Notes

`Roadie1.png` is the first image that went through the pipeline during development. It stays in the repo because I think it's funny.