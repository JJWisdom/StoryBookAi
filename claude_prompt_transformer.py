"""
claude_prompt_transformer.py

Drop-in replacement for simple_prompt_transformer.py.

Uses Claude Haiku (cheapest model) to convert slide content into
semantically rich Stable Diffusion prompts.  Falls back to keyword
extraction if no API key is supplied.

Cost at personal scale: ~$0.00003 per 10-slide storybook.

Configurable constants (top of file):
    CLAUDE_MODEL   — model ID to call
    MAX_TOKENS     — cap on output length (tokens)
"""

import logging
import threading
import webbrowser
import tkinter as tk
from tkinter import messagebox
from typing import Optional

from simple_prompt_transformer import SimplePromptTransformer as _SimpleTransformer

_simple_transformer = _SimpleTransformer()

# Optional dependency — imported at module level so ImportError surfaces at startup.
try:
    import anthropic as _anthropic
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    _anthropic = None  # type: ignore
    _ANTHROPIC_AVAILABLE = False

logger = logging.getLogger(__name__)

# -- Configurable ---------------------------------------------------------------
CLAUDE_MODEL = "claude-haiku-4-5-20251001"  # cheapest available model
MAX_TOKENS   = 320                           # enough for prompt + negative JSON

ANTHROPIC_CONSOLE_URL = "https://console.anthropic.com/"

# What to generate when content is flagged as inappropriate.
# ACCIDENTAL — ambiguous/borderline wording → replace with something wholesome.
SAFE_PROMPT_ACCIDENTAL = (
    "sleeping golden retriever puppy, curled up, soft fur, "
    "warm afternoon sunlight, peaceful cozy scene, serene"
)
# DELIBERATE — clear intent to misuse the app → ominous watching eye.
SAFE_PROMPT_DELIBERATE = (
    "extreme close-up, single dark eye, shadowed, sinister gaze, deep shadows, "
    "low key lighting, ominous, foreboding, unsettling atmosphere"
)
SAFE_NEGATIVE = "lowres, (worst quality, bad quality:1.2), bad anatomy, sketch, jpeg artifacts, signature, watermark, old, oldest, censored, bar_censor, simple background, conjoined, scary, violent, dark, disturbing"
SAFE_NEGATIVE_DELIBERATE = "lowres, (worst quality, bad quality:1.2), bad anatomy, sketch, jpeg artifacts, signature, watermark, old, oldest, censored, bar_censor, simple background, conjoined, happy, cute, bright colors, cheerful, colorful"
# -------------------------------------------------------------------------------

# Prompt format sections — selected by config "claude.prompt_style".
# ASCII-only: Windows httpx transport rejects non-ASCII characters in request bodies.

_PROMPT_FORMAT_TAGS = """\
=== PROMPT FORMAT - STRICT TAG RULES ===
Output ONLY short comma-separated tags. No sentences. No connective words (no "with", "in a", "who is", "named", "that", "of a").

WRONG: "boy named Bob with sad expression, downturned mouth, soft natural lighting"
RIGHT: "boy, sad, soft light, portrait"

WRONG: "little star twinkling brightly in night sky, warm golden glow, celestial scene"
RIGHT: "star, night sky, golden glow"

Each tag: 1-3 words. Aim for 5-8 tags. 10 maximum.

Order (only include what is clearly implied):
1. SUBJECT - gender + age: "boy", "old woman", "baby dragon", "puppy"
2. EXPRESSION - 1 word: "sad", "laughing", "scared", "surprised"
3. ACTION - verb phrase: "running", "reading book", "climbing tree"
4. SETTING - 1-2 words: "forest", "bedroom", "night sky", "kitchen"
5. LIGHTING - 1-2 words: "warm light", "moonlight", "bright sun"
6. MOOD - 1 word, only if strongly implied: "cozy", "magical", "tense"

When the scene has a prominent background add "scenery" after the setting tag.
When depth or atmosphere matters add "volumetric lighting" after the lighting tag."""

_PROMPT_FORMAT_NATURAL = """\
=== PROMPT FORMAT - NATURAL LANGUAGE ===
Output descriptive phrases separated by commas. This model understands full descriptions, not single tags.

WRONG: "boy, sad, forest, warm light"
RIGHT: "sad young boy, standing in a sunlit forest, warm dappled light filtering through trees"

WRONG: "star, night sky, golden glow"
RIGHT: "single glowing star in a vast dark night sky, soft golden radiance"

15-25 words total. Ordering:
1. SUBJECT with attributes: "sad young boy", "elderly woman with kind eyes", "small golden retriever puppy"
2. ACTION in context: "standing quietly", "running through tall grass", "gazing up in wonder"
3. SETTING with detail: "sunlit forest clearing", "cozy bedroom at night", "open meadow at sunrise"
4. LIGHTING: "warm afternoon light", "soft moonlight", "bright midday sun"
5. MOOD if strongly implied: "peaceful and serene", "mysterious", "joyful\""""


# -- Session state — held in memory only, never written to disk -----------------
_api_key:             Optional[str]  = None
_use_claude:          Optional[bool] = None   # None = user has not been asked yet
_parent_win:          Optional[tk.Misc] = None
_was_violation:       bool           = False
_was_accidental:      bool           = False
_last_negative:       str            = ""
_max_prompt_chars:    int            = 380    # overridden by configure_from_model_config
_active_system_prompt: str           = ""     # built by configure_from_model_config
# -------------------------------------------------------------------------------


def is_configured() -> bool:
    """Return True if the user has already answered the Claude prompt-choice dialog."""
    return _use_claude is not None


def was_violation() -> bool:
    """
    Return True if the last enhance_for_storybook call hit a deliberate safety block,
    then reset the flag. Call once immediately after _build_prompt_from_slide returns.
    """
    global _was_violation
    result = _was_violation
    _was_violation = False
    return result


def was_accidental_violation() -> bool:
    """Return True if the last call was an accidental safety block (puppy), then reset."""
    global _was_accidental
    result = _was_accidental
    _was_accidental = False
    return result


def peek_violation() -> bool:
    """True if the last call was a deliberate violation, WITHOUT resetting the flag."""
    return _was_violation


def get_last_negative() -> str:
    """Return the negative_prompt string from the most recent Claude call."""
    return _last_negative


def get_safe_negative(deliberate: bool) -> str:
    """Return the safe negative prompt used for violation images."""
    return SAFE_NEGATIVE_DELIBERATE if deliberate else SAFE_NEGATIVE


def ensure_configured() -> None:
    """Public entry point: run the one-time Claude setup dialog if not already done."""
    _ensure_configured()


def set_parent(window: tk.Misc) -> None:
    """
    Wire up the Tkinter root so dialogs have a proper parent.
    Call once in StoryBookApp.__init__:

        import claude_prompt_transformer
        claude_prompt_transformer.set_parent(self)
    """
    global _parent_win
    _parent_win = window


def get_max_prompt_chars() -> int:
    """Return the character budget for the final SD prompt (model-dependent)."""
    return _max_prompt_chars


def configure_from_model_config(cfg: dict) -> None:
    """
    Rebuild the active system prompt and character limit from the loaded
    storybook_config dict.  Call once at startup and again on config switch.
    """
    global _active_system_prompt, _max_prompt_chars
    gen_cfg   = cfg.get("generation", {})
    clude_cfg = cfg.get("claude", {})

    style         = clude_cfg.get("prompt_style", "tags")
    quality_note  = gen_cfg.get(
        "quality_prefix",
        "masterpiece, best quality, amazing quality, very aesthetic, absurdres, newest",
    )
    base_negative = clude_cfg.get(
        "base_negative",
        "lowres, (worst quality, bad quality:1.2), bad anatomy, sketch, jpeg artifacts, "
        "signature, watermark, old, oldest, censored, bar_censor, simple background, conjoined",
    )
    _max_prompt_chars = int(clude_cfg.get("max_prompt_chars", 380))

    format_section    = _PROMPT_FORMAT_NATURAL if style == "natural" else _PROMPT_FORMAT_TAGS
    _active_system_prompt = _assemble_system_prompt(format_section, quality_note, base_negative)
    logger.info("Prompt style: %s | max chars: %d", style, _max_prompt_chars)


def _assemble_system_prompt(format_section: str, quality_note: str, base_negative: str) -> str:
    return f"""You are a Stable Diffusion image prompt engineer in a children's storybook app for young readers.

Convert the story content into a clean SD image prompt by calling the generate_slide_prompt tool.

=== INPUT FORMAT ===
Input may include labeled sections:
  SLIDE TEXT: [the story sentence - infer setting, mood, and context from this]
  SUBJECTS: [name (action), name (action) - these take PRIORITY over subjects in SLIDE TEXT]

When SUBJECTS is present, build the prompt around those subjects and their actions first.
SLIDE TEXT provides background context (setting, mood) but its character names are secondary.

=== SAFETY (check first - highest priority) ===
Screen the input for: sexual content, illegal activity (violence, drugs, abuse, weapons, crime), gore, horror, or content that sexualises or harms children.

IMPORTANT - do NOT flag common idioms, figures of speech, or dramatic storytelling language. These are safe:
  "died of laughter", "killing it", "I'm dead tired", "it was murder on my feet",
  "she fell", "he was dying of embarrassment", "broke her heart", "scared to death"
  Treat all such phrases by their INTENDED meaning, not by the literal words.

Only flag content where the ACTUAL intended meaning describes violence, illegal acts, or sexual content.

If ACCIDENTALLY inappropriate (genuinely ambiguous, borderline):
  Call the tool with: prompt="{SAFE_PROMPT_ACCIDENTAL}", negative_prompt="{SAFE_NEGATIVE}", violation="accidental"

If DELIBERATELY inappropriate (clear misuse intent - e.g. "person X kills person Y", explicit sexual acts, drug use):
  Call the tool with: prompt="{SAFE_PROMPT_DELIBERATE}", negative_prompt="{SAFE_NEGATIVE_DELIBERATE}", violation="deliberate"

=== STYLE ===
Do NOT include art style descriptors (no "children's book illustration", "watercolor", "cartoon", "anime", "digital art").
Style is enforced by LoRA and VAE in the pipeline.
Focus purely on: subjects, actions, setting, lighting, mood.

=== GENDER INFERENCE ===
Infer gender from names and context. Replace names with a gender/species description - do NOT keep the name:
  Male names (Bob, John, Tom, James, Max, Jake, etc.) -> "boy" or "man" based on context
  Female names (Alice, Mary, Sarah, Emma, Lily, Rose, etc.) -> "girl" or "woman" based on context
  Animals -> species only ("dog", "cat", "rabbit", "lion")
  Ambiguous -> "child", "person", or "figure"

{format_section}

=== WHAT TO EXCLUDE ===
- No character names (replace with gender/species)
- No quality boosters - the pipeline appends these after your output: {quality_note}
- No style tags - handled by LoRA/VAE
- No verbatim story text
- No text, logos, or UI elements

=== negative_prompt ===
Use this base for all non-violation slides:
{base_negative}
Add content-specific terms only if the scene genuinely risks them."""


def _ask_first_use() -> bool:
    return messagebox.askyesno(
        "Enable Claude AI Prompts",
        "Would you like Claude AI to write better image prompts?\n\n"
        "This needs an Anthropic API key.  Low personal usage costs\n"
        "fractions of a cent per storybook.\n\n"
        "Click Yes to enter your key, or No to use the built-in\n"
        "basic prompt builder instead.",
        parent=_parent_win,
    )


def _test_api_key(key: str) -> Optional[str]:
    """Validate key with a minimal API call. Returns error string or None on success."""
    if not _ANTHROPIC_AVAILABLE:
        return "anthropic package not installed -- run: pip install anthropic"
    try:
        client = _anthropic.Anthropic(api_key=key)
        client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=5,
            messages=[{"role": "user", "content": "hi"}],
        )
        return None
    except _anthropic.AuthenticationError:
        return "Invalid or expired API key"
    except _anthropic.APIConnectionError:
        return "Cannot reach api.anthropic.com - check internet connection"
    except Exception as e:
        return str(e)[:100]


def _show_key_dialog() -> Optional[str]:
    """Modal dialog that collects and validates the API key. Returns the key or None."""
    dialog = tk.Toplevel(_parent_win)
    dialog.title("Anthropic API Key")
    dialog.geometry("520x270")
    dialog.resizable(False, False)
    dialog.grab_set()
    if _parent_win:
        dialog.transient(_parent_win)

    result: dict = {"key": None}

    tk.Label(
        dialog,
        text="Paste your Anthropic API key below.\n"
             "It is stored only in memory for this session -- never saved to disk.",
        justify="center",
        pady=10,
    ).pack()

    tk.Button(
        dialog,
        text="Get a free key at console.anthropic.com  ->",
        fg="#0066CC",
        cursor="hand2",
        relief="flat",
        activeforeground="#0044AA",
        command=lambda: webbrowser.open(ANTHROPIC_CONSOLE_URL),
    ).pack(pady=(0, 8))

    entry_var = tk.StringVar()
    entry = tk.Entry(dialog, textvariable=entry_var, show="*", width=56)
    entry.pack(padx=20, pady=(0, 8))
    entry.focus_set()

    status_label = tk.Label(dialog, text="", font=("Segoe UI", 9), pady=4)
    status_label.pack()

    btn_row = tk.Frame(dialog)
    btn_row.pack(pady=(4, 0))
    btn_confirm = tk.Button(btn_row, text="Use Claude", width=14)
    btn_confirm.pack(side="left", padx=6)
    btn_skip = tk.Button(btn_row, text="Skip -- use basic", width=14, command=dialog.destroy)
    btn_skip.pack(side="left", padx=6)

    def on_confirm(_event=None):
        key = entry_var.get().strip()
        if not key:
            return
        btn_confirm.config(state="disabled", text="Testing...")
        btn_skip.config(state="disabled")
        status_label.config(text="Connecting to api.anthropic.com...", fg="#0066CC")
        dialog.update()

        def do_test():
            err = _test_api_key(key)
            if err:
                dialog.after(0, lambda: [
                    status_label.config(text=f"Failed: {err}", fg="red"),
                    btn_confirm.config(state="normal", text="Use Claude"),
                    btn_skip.config(state="normal"),
                ])
            else:
                result["key"] = key
                dialog.after(0, lambda: status_label.config(
                    text="Key accepted! Connecting...", fg="green"
                ))
                dialog.after(1000, dialog.destroy)

        threading.Thread(target=do_test, daemon=True).start()

    btn_confirm.config(command=on_confirm)
    entry.bind("<Return>", on_confirm)
    dialog.wait_window()
    return result["key"]


def _ensure_configured() -> None:
    """
    Runs once per session on the first Illustrate press.
    Safe to call repeatedly — returns immediately after the first run.
    """
    global _api_key, _use_claude
    if _use_claude is not None:
        return

    if not _ask_first_use():
        _use_claude = False
        return

    key = _show_key_dialog()
    if key:
        _api_key    = key
        _use_claude = True
        logger.info("Claude enabled -- model: %s", CLAUDE_MODEL)
        messagebox.showinfo(
            "Claude Connected!",
            "Claude AI is now active.\nYour prompts will be AI-enhanced.",
            parent=_parent_win,
        )
    else:
        _use_claude = False
        logger.info("No API key entered; using basic prompt builder")


def _notify_and_disable(title: str, message: str) -> None:
    """Show an error popup and disable Claude for the rest of the session."""
    global _use_claude
    _use_claude = False
    messagebox.showerror(title, message, parent=_parent_win)


# Tool schema — the API enforces types, required fields, and the violation enum,
# replacing all manual JSON extraction and key-name guessing.
_TOOL: dict = {
    "name": "generate_slide_prompt",
    "description": "Output the Stable Diffusion prompt for this storybook slide.",
    "input_schema": {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Comma-separated SD tags, 5-10 tags, 10 maximum.",
            },
            "negative_prompt": {
                "type": "string",
                "description": "Comma-separated negative SD tags, max 120 characters.",
            },
            "violation": {
                "type": "string",
                "enum": ["none", "accidental", "deliberate"],
                "description": "Content safety classification.",
            },
        },
        "required": ["prompt", "negative_prompt", "violation"],
    },
}


def _call_claude(base_text: str) -> Optional[str]:
    """
    Call Claude Haiku via tool use and return the SD prompt string, or None on failure.
    Errors are surfaced as visible popups so they are never silently swallowed.
    """
    global _was_violation, _was_accidental, _last_negative
    _was_violation  = False
    _was_accidental = False
    _last_negative  = ""

    if not _ANTHROPIC_AVAILABLE:
        logger.warning("anthropic package not installed -- run: pip install anthropic")
        return None

    if not _api_key:
        return None

    client = _anthropic.Anthropic(api_key=_api_key)

    try:
        msg = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=MAX_TOKENS,
            system=[
                {
                    "type": "text",
                    "text": _active_system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            tools=[_TOOL],
            tool_choice={"type": "tool", "name": "generate_slide_prompt"},
            messages=[{"role": "user", "content": base_text}],
        )

        # tool_choice forces exactly one tool_use block — find it.
        data = None
        for block in msg.content:
            if block.type == "tool_use" and block.name == "generate_slide_prompt":
                data = block.input  # already a validated Python dict
                break

        if data is None:
            messagebox.showwarning(
                "Claude Prompt Error",
                "Claude did not return a tool call.\n"
                "The basic prompt builder will be used for this slide.",
                parent=_parent_win,
            )
            return None

        violation_type  = data.get("violation", "none")
        _was_violation  = (violation_type == "deliberate")
        _was_accidental = (violation_type == "accidental")
        _last_negative  = str(data.get("negative_prompt", "") or "")

        prompt = data.get("prompt")
        if not prompt:
            logger.warning("Tool response missing 'prompt' field.")
            return None
        return str(prompt).strip()

    except _anthropic.AuthenticationError:
        _notify_and_disable(
            "Invalid API Key",
            "The Anthropic API key was rejected.\n\n"
            "Please restart the app and enter a valid key from console.anthropic.com.\n\n"
            "Switching to the basic prompt builder for now."
        )
        return None

    except _anthropic.RateLimitError:
        messagebox.showwarning(
            "Claude Rate Limit",
            "You have hit the Claude API rate limit.\n"
            "The basic prompt builder will be used for this slide.",
            parent=_parent_win,
        )
        return None

    except _anthropic.APIConnectionError as e:
        _notify_and_disable(
            "Cannot Reach Claude API",
            "Failed to connect to api.anthropic.com.\n\n"
            "Possible causes:\n"
            "  - No internet connection\n"
            "  - Firewall or antivirus blocking outbound HTTPS\n"
            "  - VPN or proxy interfering\n\n"
            f"Detail: {e}\n\nSwitching to the basic prompt builder for this session."
        )
        return None

    except _anthropic.APIStatusError as e:
        messagebox.showwarning(
            "Claude API Error",
            f"Claude returned HTTP {e.status_code}.\n"
            "The basic prompt builder will be used for this slide.",
            parent=_parent_win,
        )
        return None

    except Exception as e:
        messagebox.showwarning(
            "Claude Error",
            f"Unexpected error calling Claude:\n{e}\n\n"
            "The basic prompt builder will be used for this slide.",
            parent=_parent_win,
        )
        return None


def _fallback_enhance(text: str) -> str:
    """Strip structured labels before delegating to SimplePromptTransformer."""
    plain_parts = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("SLIDE TEXT:"):
            plain_parts.append(stripped[len("SLIDE TEXT:"):].strip())
        elif stripped.startswith("SUBJECTS:"):
            plain_parts.append(stripped[len("SUBJECTS:"):].strip())
        elif stripped:
            plain_parts.append(stripped)
    plain = ", ".join(p for p in plain_parts if p)
    return _simple_transformer.enhance_for_storybook(plain)


# -- Public interface - matches SimplePromptTransformer -------------------------

class ClaudePromptTransformer:
    """
    Drop-in replacement for SimplePromptTransformer.
    storybookgui.py only calls enhance_for_storybook().
    """

    def enhance_for_storybook(self, text: str) -> str:
        """
        Convert slide text → Stable Diffusion prompt string.
        Triggers the API-key dialog on the very first call.
        """
        _ensure_configured()

        if _use_claude and _api_key:
            prompt = _call_claude(text)
            if prompt:
                return prompt

        return _fallback_enhance(text)


# Build the default system prompt at import time so _active_system_prompt is
# never an empty string even if configure_from_model_config is never called.
configure_from_model_config({})
