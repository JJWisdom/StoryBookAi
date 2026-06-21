"""
storybookgui.py

Drop-in GUI for StoryBook AI.
- preserves original layout/behavior
- integrates with ForgeHandler (start_forge(), generate_image())
- uses get_image_processor().overlay_text(...) for text overlay
- generates images in background threads and updates UI safely
"""

import os
import re
import json
import time
import threading
import logging
import zipfile
from datetime import datetime
from typing import List, Optional
import requests  # Add this near the other imports
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext

from PIL import Image, ImageTk, ImageDraw

# Local modules (must exist in project)
from forge_handler import ForgeHandler
from claude_prompt_transformer import ClaudePromptTransformer
import claude_prompt_transformer as _cpt_module
from image_processor import get_image_processor

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - storybookgui - %(levelname)s - %(message)s")
logger = logging.getLogger("storybookgui")

# Theme constants (adapted from original)
BG = "#F3CBE6"
SURFACE = "#FFFFFF"
ACCENT = "#8A2BE2"
ACCENT_HOV = "#6A1EAD"
DISABLED_BG = "#E8E1EE"
INK = "#242424"
INK_MUTED = "#6B6B6B"
BORDER = "#C9B1D9"

IMG_W, IMG_H = 420, 300
TITLE_FONT = ("Georgia", 44, "bold")
H2_FONT = ("Segoe UI", 11, "bold")
BODY_FONT = ("Segoe UI", 11)

# Limits
MAX_PROMPT_LENGTH = 380
MAX_TEXT_OVERLAY = 1400

# Initialize transformer and image processor
transformer = ClaudePromptTransformer()
image_processor = get_image_processor()

_VIOLATION_CACHE_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generated_images")
_VIOLATION_DELIBERATE = os.path.join(_VIOLATION_CACHE_DIR, "violation-intent.png")
_VIOLATION_ACCIDENTAL = os.path.join(_VIOLATION_CACHE_DIR, "violation-unintent.png")


# ===== Data model =====
class Slide:
    def __init__(self, text: str = ""):
        self.subjects: List[str] = [""]
        self.actions: List[str] = [""]
        self.text: str = text
        self.base_image_path: str = ""
        self.text_image_path: str = ""
        self.last_prompt: str = ""
        self.photo_image = None  # ImageTk.PhotoImage for UI
        self.was_violation: bool = False
        self.was_accidental: bool = False
        self.negative_prompt: str = ""


class SlideManager:
    def __init__(self):
        self.slides: List[Slide] = []
        self.current_index: int = 0
    def count(self) -> int:
        return len(self.slides)

    def create_from_story(self, story_text: str):
        text = (story_text or "").strip()
        if not text:
            self.slides = [Slide()]
            self.current_index = 0
            return

        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
        if not sentences:
            self.slides = [Slide()]
        else:
            self.slides = [Slide() for _ in sentences]
            for i, s in enumerate(sentences):
                self.slides[i].text = s
        self.current_index = 0

    def get_current(self) -> Optional[Slide]:
        if 0 <= self.current_index < len(self.slides):
            return self.slides[self.current_index]
        return None

    def add_slide(self, index: Optional[int] = None):
        if index is None:
            index = self.current_index + 1
        self.slides.insert(index, Slide())

    def remove_slide(self, index: int) -> bool:
        if 0 <= index < len(self.slides) and len(self.slides) > 1:
            self.slides.pop(index)
            if self.current_index >= len(self.slides):
                self.current_index = len(self.slides) - 1
            return True
        return False

    def get_missing_images(self) -> List[int]:
        return [i for i, s in enumerate(self.slides) if not s.text_image_path or not os.path.exists(s.text_image_path)]


# ===== Application =====
class StoryBookApp(tk.Tk):
    
    def __init__(self, forge_root: Optional[str] = None, forge_port: int = 7860):
        super().__init__()
        self.title("StoryBook AI")
        self.geometry("1000x720")
        self.configure(bg=BG)

        # state
        self.slide_manager = SlideManager()
        self.forge_handler: Optional[ForgeHandler] = None
        self.forge_root = forge_root
        self.forge_port = forge_port
        self.is_generating = False
        self.generating_slide_index: Optional[int] = None
        try:
            # prefer module-level singleton (already created at import), but
            # call get_image_processor() defensively in case import order differs
            self.image_processor = image_processor if 'image_processor' in globals() else get_image_processor()
        except Exception:
            # fallback: create a new one — this should be rare
            self.image_processor = get_image_processor()
            # UI & logic helpers
        self._setup_styles()
        self._create_frames()
        self.show_frame("StartupFrame")  # Start with startup frame
        _cpt_module.set_parent(self)    # give the Claude dialog a Tk parent

        # Check if we should skip startup (Forge already running)
        self.after(100, self._check_forge_status)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _setup_styles(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("TLabel", background=BG, foreground=INK)
        style.configure("Accent.TButton", font=("Segoe UI", 12, "bold"), foreground="white", padding=(18, 10))
        style.map("Accent.TButton", background=[("disabled", ACCENT), ("active", ACCENT_HOV), ("!disabled", ACCENT)])
        style.configure("Secondary.TButton", font=("Segoe UI", 11, "bold"), foreground=INK, padding=(8, 4))
        style.map("Secondary.TButton", background=[("disabled", DISABLED_BG), ("active", "#D7C4E4"), ("!disabled", "#EAD7F6")])
        style.configure("Nav.TButton", font=("Segoe UI", 11, "bold"), padding=(12, 6))

    def _create_frames(self):
        container = tk.Frame(self, bg=BG)
        container.pack(fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.frames = {}
        for cls in (StartupFrame, StartFrame, SlideFrame):  # Add StartupFrame
            frame = cls(container, self)
            self.frames[cls.__name__] = frame
            frame.grid(row=0, column=0, sticky="nsew")

    def show_frame(self, name: str):
        frame = self.frames.get(name)
        if frame:
            frame.tkraise()

    # ----------------- Forge init -----------------
    def _check_forge_status(self):
        """Check if Forge is already running, otherwise start it."""
        startup_frame = self.frames["StartupFrame"]
        startup_frame.update_status("Checking if Forge is already running...")

        # Probe the port before touching ForgeHandler so we never create two instances.
        already_running = False
        try:
            response = requests.get(
                f"http://127.0.0.1:{self.forge_port}/sdapi/v1/sd-models", timeout=5
            )
            already_running = response.status_code == 200
        except requests.exceptions.RequestException:
            pass

        if already_running:
            try:
                self.forge_handler = ForgeHandler(self.forge_root, self.forge_port)
                self.forge_handler.running = True
                self.forge_handler.startup_complete = True
                startup_frame.update_status("✓ Connected to existing Forge instance")
                self.after(1000, lambda: self.show_frame("StartFrame"))
            except Exception as e:
                logger.error("Failed to create ForgeHandler for existing Forge: %s", e)
                startup_frame.update_status(f"❌ Handler error: {e}")
                self.after(3000, lambda: self.show_frame("StartFrame"))
            return

        # Forge is not running — start it (ForgeHandler created inside this thread).
        startup_frame.update_status("Starting Forge AI Engine...")
        threading.Thread(target=self._start_forge_with_progress, daemon=True).start()

    def _start_forge_with_progress(self):
        """Start Forge with progress updates — runs on a background thread."""
        startup_frame = self.frames["StartupFrame"]

        def status(text: str):
            # All widget calls must happen on the main thread.
            self.after(0, startup_frame.update_status, text)

        try:
            cfg = self._load_config()
            if not cfg:
                status("⚠ No config found. Please run setup first.")
                self.after(3000, lambda: self.show_frame("StartFrame"))
                return

            forge_cfg = cfg.get("forge", {})
            forge_root = forge_cfg.get("path") or self.forge_root
            port = forge_cfg.get("port", self.forge_port)

            if not forge_root or not os.path.exists(forge_root):
                status("❌ Forge path not found. Please check config.")
                self.after(3000, lambda: self.show_frame("StartFrame"))
                return

            status(f"Starting Forge at: {forge_root}")

            self.forge_handler = ForgeHandler(forge_root, port)

            if self.forge_handler.start_forge():
                status("✓ Forge started successfully!")
                status("✓ Ready to create storybooks!")
                self.after(2000, lambda: self.show_frame("StartFrame"))
            else:
                status("❌ Failed to start Forge.")
                status("Please check logs and try again.")
                self.after(5000, lambda: self.show_frame("StartFrame"))

        except Exception as e:
            status(f"❌ Error: {str(e)}")
            logger.error("Forge startup error: %s", e)
    def _load_config(self) -> Optional[dict]:
        cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "storybook_config.json")
        try:
            if os.path.exists(cfg_path):
                with open(cfg_path, "r", encoding="utf-8") as fh:
                    return json.load(fh)
        except Exception as e:
            logger.error("Failed to load config: %s", e)
        return None

    # ----------------- Story handling -----------------
    def process_initial_story(self, story_text: str):
        try:
            self.frames["SlideFrame"].save_current_slide_data()
        except Exception:
            pass
        self.slide_manager.create_from_story(story_text)
        self.show_frame("SlideFrame")
        self.frames["SlideFrame"].update_display()

    def navigate(self, direction: int):
        self.frames["SlideFrame"].save_current_slide_data()
        new_idx = self.slide_manager.current_index + direction
        if 0 <= new_idx < len(self.slide_manager.slides):
            self.slide_manager.current_index = new_idx
            self.frames["SlideFrame"].update_display()

    def add_new_slide(self):
        self.frames["SlideFrame"].save_current_slide_data()
        self.slide_manager.add_slide(self.slide_manager.current_index + 1)
        self.slide_manager.current_index += 1
        self.frames["SlideFrame"].update_display()

    def delete_current_slide(self):
        if self.slide_manager.remove_slide(self.slide_manager.current_index):
            self.frames["SlideFrame"].update_display()

    def add_person_pair(self):
        sf = self.frames["SlideFrame"]
        sf.save_current_slide_data()
        slide = self.slide_manager.get_current()
        if slide:
            slide.subjects.append("")
            slide.actions.append("")
            sf.update_display()

    def remove_person_pair(self):
        sf = self.frames["SlideFrame"]
        sf.save_current_slide_data()
        slide = self.slide_manager.get_current()
        if slide and len(slide.subjects) > 1 and len(slide.actions) > 1:
            slide.subjects.pop()
            slide.actions.pop()
            sf.update_display()

    # ----------------- Prompt building -----------------
    def _build_prompt_from_slide(self, slide: Slide) -> str:
        if not slide:
            return ""

        text_content = (slide.text or "").strip()

        pairs = []
        n = min(len(slide.subjects), len(slide.actions))
        for i in range(n):
            subj = (slide.subjects[i] or "").strip()
            act  = (slide.actions[i] or "").strip()
            if subj and act:
                pairs.append(f"{subj} ({act})")
            elif subj:
                pairs.append(subj)
            elif act:
                pairs.append(f"someone ({act})")

        if not text_content and not pairs:
            return ""

        lines = []
        if text_content:
            lines.append("SLIDE TEXT: " + text_content)
        if pairs:
            lines.append("SUBJECTS: " + ", ".join(pairs))

        base = "\n".join(lines).strip()
        enhanced = transformer.enhance_for_storybook(base)

        # Store the Claude-provided negative on the slide for use in generation
        slide.negative_prompt = _cpt_module.get_last_negative()

        # Skip quality boosters on deliberate violation (punishment) images
        if _cpt_module.peek_violation():
            final = enhanced or base
        else:
            final = f"masterpiece, best quality, detailed, {enhanced}" if enhanced else base

        if len(final) > MAX_PROMPT_LENGTH:
            final = final[:MAX_PROMPT_LENGTH].rsplit(",", 1)[0] + "..."
        return final

    # ----------------- Image generation -----------------
    def illustrate_current_slide(self, max_retries: int = 2):
        if self.is_generating:
            messagebox.showinfo("Please wait", "Image generation already in progress.")
            return

        # First press: configure Claude, then prompt user to press again.
        if not _cpt_module.is_configured():
            _cpt_module._ensure_configured()
            sf = self.frames["SlideFrame"]
            if _cpt_module.is_configured():
                sf.status_var.set("Ready -- press Illustrate to generate.")
                sf.status_label.config(fg=ACCENT)
            return

        sf = self.frames["SlideFrame"]
        sf.save_current_slide_data()
        slide = self.slide_manager.get_current()
        if not slide:
            return
        prompt = self._build_prompt_from_slide(slide)
        if not prompt.strip():
            messagebox.showwarning("No content", "Please add subjects, actions, or text before illustrating.")
            return
        slide.was_violation  = _cpt_module.was_violation()
        slide.was_accidental = _cpt_module.was_accidental_violation()
        slide.last_prompt    = prompt

        sf.show_placeholder_image()
        self.is_generating           = True
        self.generating_slide_index  = self.slide_manager.current_index

        # Lock generate/publish buttons and the current slide's text boxes.
        sf._set_generate_locked(True)
        sf._lock_entries(True)

        # Show violation text immediately (before image is ready) so user sees it first.
        if slide.was_violation or slide.was_accidental:
            sf.show_violation_status(generation_complete=False)
        else:
            sf.status_var.set("Generating...")
            sf.status_label.config(fg=INK_MUTED)

        thread = threading.Thread(
            target=self._generate_with_retry,
            args=(slide, prompt, max_retries, sf),
            daemon=True,
        )
        thread.start()

    def _generate_with_retry(self, slide: Slide, prompt: str, max_retries: int, sf):
        # Violation slides use a cached image rather than an original generation each time.
        if slide.was_violation or slide.was_accidental:
            self._handle_violation_image(slide, slide.was_violation, sf)
            return

        last_exc = None
        for attempt in range(max_retries):
            try:
                ok = self._generate_single_image(slide, prompt, sf)
                if ok:
                    return
                else:
                    logger.warning("Generation attempt %d failed (no exception).", attempt + 1)
            except Exception as e:
                last_exc = e
                logger.error("Generation attempt %d exception: %s", attempt + 1, e)
            time.sleep(1 + attempt * 2)
        self.after(0, lambda: messagebox.showerror("Generation failed", f"Failed after {max_retries} attempts.\n{last_exc}"))
        self.after(0, sf.show_generation_status, False)
        self.after(0, lambda: setattr(self, "is_generating", False))
        self.after(0, lambda: setattr(self, "generating_slide_index", None))

    def _handle_violation_image(self, slide: Slide, deliberate: bool, sf) -> None:
        """Background thread: load cached violation image or generate-and-cache it."""
        import shutil
        cache_path = _VIOLATION_DELIBERATE if deliberate else _VIOLATION_ACCIDENTAL
        os.makedirs(_VIOLATION_CACHE_DIR, exist_ok=True)

        if not os.path.exists(cache_path):
            # First occurrence — generate via Forge and save to cache.
            if not self.forge_handler or not self.forge_handler.running:
                logger.error("Forge unavailable for violation image generation.")
                self.after(0, lambda: setattr(self, "is_generating", False))
                self.after(0, lambda: setattr(self, "generating_slide_index", None))
                self.after(0, sf.show_generation_status, False)
                return
            try:
                cfg     = self._load_config() or {}
                gen_cfg = cfg.get("generation", {})
                negative = (_cpt_module.SAFE_NEGATIVE_DELIBERATE if deliberate
                            else _cpt_module.SAFE_NEGATIVE)
                raw_path = self.forge_handler.generate_image(
                    slide.last_prompt,
                    output_dir=_VIOLATION_CACHE_DIR,
                    negative_prompt=negative,
                    width=gen_cfg.get("width", 512),
                    height=gen_cfg.get("height", 512),
                    steps=gen_cfg.get("steps", 25),
                    cfg_scale=gen_cfg.get("cfg_scale", 7.0),
                    sampler_name=gen_cfg.get("sampler", "Euler a"),
                    seed=42,          # fixed seed → consistent violation image
                    request_timeout=180,
                )
                if raw_path and os.path.exists(raw_path):
                    shutil.copy2(raw_path, cache_path)
                else:
                    raise RuntimeError("Forge returned no image path")
            except Exception as e:
                logger.error("Failed to generate violation image: %s", e)
                self.after(0, lambda: setattr(self, "is_generating", False))
                self.after(0, lambda: setattr(self, "generating_slide_index", None))
                self.after(0, sf.show_generation_status, False)
                return

        # Load and display cached image.
        try:
            pil = Image.open(cache_path)
            pil.thumbnail((IMG_W, IMG_H), Image.LANCZOS)
            tkimg = ImageTk.PhotoImage(pil)
            slide.photo_image       = tkimg
            slide.base_image_path   = cache_path
            slide.text_image_path   = cache_path
            self.after(0, self._update_slide_image, slide, tkimg)
        except Exception as e:
            logger.error("Failed to load cached violation image: %s", e)
            self.after(0, lambda: setattr(self, "is_generating", False))
            self.after(0, lambda: setattr(self, "generating_slide_index", None))
            self.after(0, sf.show_generation_status, False)

    def _generate_single_image(self, slide: Slide, prompt: str, slide_frame) -> bool:
        # Ensure Forge handler exists and running
        if not self.forge_handler:
            self.after(0, self._handle_forge_not_ready)
            return False
        # Ensure Forge API seems available
        try:
            started = True
            # If it's not running yet try to start it (non-blocking)
            if not self.forge_handler.running:
                started = self.forge_handler.start_forge()
            if not started:
                logger.error("Forge failed to start.")
                return False
        except Exception as e:
            logger.error("Error ensuring Forge is running: %s", e)
            return False

        # Read generation settings from config; fall back to safe defaults if missing.
        gen_cfg = {}
        forge_cfg = {}
        out_cfg = {}
        try:
            cfg = self._load_config() or {}
            gen_cfg = cfg.get("generation", {})
            forge_cfg = cfg.get("forge", {})
            out_cfg = cfg.get("output", {})
        except Exception as e:
            logger.warning("Could not load generation config, using defaults: %s", e)

        try:
            outpath = self.forge_handler.generate_image(
                prompt,
                output_dir=out_cfg.get("output_dir", "generated_images"),
                width=gen_cfg.get("width", 512),
                height=gen_cfg.get("height", 512),
                steps=gen_cfg.get("steps", 25),
                cfg_scale=gen_cfg.get("cfg_scale", 7.0),
                sampler_name=gen_cfg.get("sampler", "Euler a"),
                negative_prompt=slide.negative_prompt or gen_cfg.get("negative_prompt", "blurry, bad quality, deformed, ugly"),
                seed=gen_cfg.get("seed", -1),
                request_timeout=forge_cfg.get("request_timeout", 180),
            )
            if not outpath or not os.path.exists(outpath):
                logger.error("No image returned from Forge or file missing.")
                return False
            slide.base_image_path = str(outpath)
        except Exception as e:
            logger.error("Error during Forge generation: %s", e)
            return False

        # Overlay text if present
        text_overlay = (slide.text or "").strip()
        display_path = slide.base_image_path
        if text_overlay:
            try:
                if len(text_overlay) > MAX_TEXT_OVERLAY:
                    text_overlay = text_overlay[:MAX_TEXT_OVERLAY].rsplit(" ", 1)[0] + "..."
                over = self.image_processor.overlay_text(base_image_path=slide.base_image_path, text=text_overlay, position="bottom")
                if over and os.path.exists(over):
                    slide.text_image_path = str(over)
                    display_path = slide.text_image_path
                else:
                    slide.text_image_path = slide.base_image_path
            except Exception as e:
                logger.error("Overlay text failed: %s", e)
                slide.text_image_path = slide.base_image_path

        # Create thumbnail and update UI
        try:
            pil = Image.open(display_path)
            pil.thumbnail((IMG_W, IMG_H), Image.LANCZOS)
            tkimg = ImageTk.PhotoImage(pil)
            slide.photo_image = tkimg
            self.after(0, self._update_slide_image, slide, tkimg)
            return True
        except Exception as e:
            logger.error("Failed to open or display image: %s", e)
            return False

    # ----------------- Publishing -----------------
    def publish_story(self):
        if not self.slide_manager.slides:
            messagebox.showwarning("No slides", "There are no slides to publish.")
            return
        missing = self.slide_manager.get_missing_images()
        if missing:
            res = messagebox.askyesno("Missing images", f"{len(missing)} slides missing images. Generate now?")
            if not res:
                messagebox.showwarning("Publish aborted", "All slides must have images to publish.")
                return
            # Pick format first so the file dialog runs on the main thread before
            # the background generation starts.
            fmt, fname = self._pick_publish_format()
            if not fname:
                return
            def on_complete(ok: bool):
                if ok:
                    self._do_publish(fmt, fname)
                else:
                    messagebox.showwarning("Partial", "Some images failed to generate; publishing what was created.")
                    self._do_publish(fmt, fname)
            self._generate_missing_images(missing, on_complete)
            return

        fmt, fname = self._pick_publish_format()
        if fname:
            self._do_publish(fmt, fname)

    def _pick_publish_format(self):
        """Ask user for PDF vs ZIP and a save path. Returns (is_pdf: bool, fname: str)."""
        if self._check_pdf_support():
            is_pdf = messagebox.askyesno("Publish format", "Create PDF file? Yes for PDF, No for ZIP.")
        else:
            messagebox.showinfo("PDF not available", "ReportLab missing; creating ZIP instead.")
            is_pdf = False
        default_name = f"storybook_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        if is_pdf:
            fname = filedialog.asksaveasfilename(
                defaultextension=".pdf", filetypes=[("PDF", "*.pdf")],
                initialfile=f"{default_name}.pdf")
        else:
            fname = filedialog.asksaveasfilename(
                defaultextension=".zip", filetypes=[("ZIP", "*.zip")],
                initialfile=f"{default_name}.zip")
        return is_pdf, fname

    def _do_publish(self, is_pdf: bool, fname: str):
        if not fname:
            return
        if is_pdf:
            self._create_pdf(fname)
        else:
            self._create_zip(fname)

    def _generate_missing_images(self, indices: List[int], on_complete) -> None:
        """
        Generate images for the given slide indices in a background thread.
        Calls on_complete(success: bool) on the main thread when finished.
        """
        total = len(indices)
        sf = self.frames["SlideFrame"]

        progress = tk.Toplevel(self)
        progress.title("Generating Images")
        progress.geometry("360x160")
        progress.transient(self)
        progress.grab_set()
        ttk.Label(progress, text=f"Generating {total} missing image(s)...").pack(pady=10)
        pvar = tk.DoubleVar()
        ttk.Progressbar(progress, maximum=total, variable=pvar, length=320).pack(pady=8)
        status_lbl = tk.Label(progress, text="Starting...")
        status_lbl.pack(pady=4)
        progress.update()

        sf._set_generate_locked(True)

        def worker():
            success = 0
            for i, idx in enumerate(indices):
                def _upd(i=i, idx=idx):
                    status_lbl.config(text=f"Slide {idx + 1} of {self.slide_manager.count()}...")
                    pvar.set(i + 1)
                self.after(0, _upd)
                ok = self._generate_slide_image_batch(idx)
                if ok:
                    success += 1
                else:
                    logger.warning("Batch generation failed for slide %d", idx)

            def finish():
                try:
                    progress.destroy()
                except Exception:
                    pass
                sf._set_generate_locked(False)
                on_complete(success == total)

            self.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def _generate_slide_image_batch(self, slide_index: int) -> bool:
        """
        Generate an image for one slide without touching current_index or firing
        any UI callbacks. Safe to call from a background thread.
        """
        slide = self.slide_manager.slides[slide_index] if 0 <= slide_index < len(self.slide_manager.slides) else None
        if not slide:
            return False

        prompt = self._build_prompt_from_slide(slide)
        if not prompt:
            return False
        slide.last_prompt = prompt

        if not self.forge_handler or not self.forge_handler.running:
            return False

        cfg     = self._load_config() or {}
        gen_cfg = cfg.get("generation", {})
        out_cfg = cfg.get("output", {})
        forge_cfg = cfg.get("forge", {})

        try:
            negative = slide.negative_prompt or gen_cfg.get("negative_prompt", "blurry, bad quality, deformed, ugly")
            outpath = self.forge_handler.generate_image(
                prompt,
                output_dir=out_cfg.get("output_dir", "generated_images"),
                negative_prompt=negative,
                width=gen_cfg.get("width", 512),
                height=gen_cfg.get("height", 512),
                steps=gen_cfg.get("steps", 25),
                cfg_scale=gen_cfg.get("cfg_scale", 7.0),
                sampler_name=gen_cfg.get("sampler", "Euler a"),
                seed=gen_cfg.get("seed", -1),
                request_timeout=forge_cfg.get("request_timeout", 180),
            )
            if not outpath or not os.path.exists(outpath):
                return False
            slide.base_image_path = str(outpath)
        except Exception as e:
            logger.error("Batch generate_image error: %s", e)
            return False

        text_overlay = (slide.text or "").strip()
        if text_overlay:
            try:
                over = self.image_processor.overlay_text(
                    base_image_path=slide.base_image_path,
                    text=text_overlay[:MAX_TEXT_OVERLAY],
                    position="bottom",
                )
                slide.text_image_path = str(over) if over and os.path.exists(over) else slide.base_image_path
            except Exception:
                slide.text_image_path = slide.base_image_path
        else:
            slide.text_image_path = slide.base_image_path

        return True

    def _check_pdf_support(self) -> bool:
        try:
            import reportlab  # type: ignore
            return True
        except Exception:
            return False

    def _create_pdf(self, filename: str):
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Spacer, Image as RLImage, Paragraph
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib.units import inch
            doc = SimpleDocTemplate(filename, pagesize=letter)
            story = []
            styles = getSampleStyleSheet()
            story.append(Paragraph("StoryBook", styles["Title"]))
            story.append(Spacer(1, 12))
            for i, sl in enumerate(self.slide_manager.slides):
                if sl.text_image_path and os.path.exists(sl.text_image_path):
                    try:
                        img = RLImage(sl.text_image_path, width=6*inch, height=4*inch)
                        story.append(img)
                        story.append(Spacer(1, 12))
                    except Exception:
                        story.append(Paragraph("[Image unavailable]", styles["Normal"]))
                        story.append(Spacer(1, 12))
            doc.build(story)
            messagebox.showinfo("Success", f"PDF created: {filename}")
        except Exception as e:
            logger.error("PDF creation failed: %s", e)
            messagebox.showerror("PDF Error", f"Failed to create PDF: {e}")

    def _create_zip(self, filename: str):
        try:
            with zipfile.ZipFile(filename, "w", zipfile.ZIP_DEFLATED) as zf:
                for i, sl in enumerate(self.slide_manager.slides):
                    if sl.text_image_path and os.path.exists(sl.text_image_path):
                        arc = f"slide_{i+1:03d}.png"
                        zf.write(sl.text_image_path, arc)
                storytxt = "StoryBook\nCreated: " + datetime.now().isoformat() + "\n\n"
                for i, sl in enumerate(self.slide_manager.slides):
                    storytxt += f"Slide {i+1}:\n"
                    if sl.subjects and any(s.strip() for s in sl.subjects):
                        storytxt += "Subjects: " + ", ".join(s for s in sl.subjects if s.strip()) + "\n"
                    if sl.actions and any(a.strip() for a in sl.actions):
                        storytxt += "Actions: " + ", ".join(a for a in sl.actions if a.strip()) + "\n"
                    if sl.text and sl.text.strip():
                        storytxt += "Text: " + sl.text + "\n"
                    if sl.last_prompt:
                        storytxt += "Prompt: " + sl.last_prompt[:300] + "...\n"
                    storytxt += "\n"
                zf.writestr("story.txt", storytxt)
            messagebox.showinfo("Success", f"ZIP created: {filename}")
        except Exception as e:
            logger.error("ZIP creation failed: %s", e)
            messagebox.showerror("ZIP Error", f"Failed to create ZIP: {e}")

    # ----------------- UI updates -----------------
    def _update_slide_image(self, slide: "Slide", photo_image):
        slide.photo_image = photo_image
        sf = self.frames["SlideFrame"]
        if self.slide_manager.get_current() is slide:
            sf.image_label.config(image=photo_image)
            sf.image_label.image = photo_image
            sf.prompt_view.configure(state="normal")
            sf.prompt_view.delete("1.0", "end")
            if slide.last_prompt:
                sf.prompt_view.insert("1.0", slide.last_prompt)
            sf.prompt_view.configure(state="disabled")
        self.is_generating          = False
        self.generating_slide_index = None
        sf._lock_entries(False)
        if slide.was_violation or slide.was_accidental:
            sf.show_violation_status(generation_complete=True)
        else:
            sf.show_generation_status(False)

    def _handle_forge_not_ready(self):
        messagebox.showwarning("Forge not ready", "Forge is not started or not configured. Check storybook_config.json and run.bat.")

    def on_closing(self):
        """Called when the main window is closed via the window manager (X) or programmatically."""
        try:
            # Call shutdown which will stop Forge (if running) and destroy the Tk app
            self.shutdown()
        except Exception as e:
            logger.error("Error during on_closing: %s", e, exc_info=True)
            try:
                # best-effort destroy to avoid leaving GUI running
                self.destroy()
            except Exception:
                pass

    def shutdown(self):
        if self.forge_handler:
            try:
                # shutdown() kills the full process tree via psutil; stop_forge() only
                # terminates the top-level cmd.exe and leaves Forge's Python workers alive.
                self.forge_handler.shutdown()
            except Exception:
                logger.debug("Error stopping forge", exc_info=True)
        try:
            self.destroy()
        except Exception:
            pass


# ===== UI Frames (preserve original design) =====
class StartFrame(tk.Frame):
    def __init__(self, parent, controller: StoryBookApp):
        super().__init__(parent, bg=BG)
        self.controller = controller
        self._build()

    def _build(self):
        # Title (preserve original styling)
        tk.Label(self, text="StoryBook AI", font=TITLE_FONT, bg=BG, fg=INK).place(relx=0.5, y=64, anchor="center")
        tk.Label(self, text="Create Illustrated Stories with AI", font=("Segoe UI", 14), bg=BG, fg=INK_MUTED).place(relx=0.5, y=110, anchor="center")

        card = tk.Frame(self, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
        card.place(relx=0.5, rely=0.52, anchor="center", width=760, height=340)

        placeholder = "Once upon a time, in a magical forest, there lived a friendly dragon."
        self.story_text = tk.Text(card, wrap="word", bd=0, font=BODY_FONT, bg=SURFACE, fg="#666")
        self.story_text.insert("1.0", placeholder)
        self.story_text.place(relx=0.5, rely=0.5, anchor="center", width=720, height=300)

        def on_focus_in(_):
            if self.story_text.get("1.0", "end-1c") == placeholder:
                self.story_text.delete("1.0", "end")
                self.story_text.config(fg=INK)
        def on_focus_out(_):
            if not self.story_text.get("1.0", "end-1c").strip():
                self.story_text.insert("1.0", placeholder)
                self.story_text.config(fg="#666")

        self.story_text.bind("<FocusIn>", on_focus_in)
        self.story_text.bind("<FocusOut>", on_focus_out)

        ttk.Button(self, text="Create Storybook", style="Accent.TButton",
                   command=lambda: self.controller.process_initial_story(self.story_text.get("1.0", "end-1c"))).place(relx=0.5, rely=0.88, anchor="center", width=220)


class SlideFrame(tk.Frame):
    def __init__(self, parent, controller: StoryBookApp):
        super().__init__(parent, bg=BG)
        self.controller = controller
        self._build()

    def _build(self):
        # ── Bottom bar (packed first so content can expand into remaining space) ──
        bottom = tk.Frame(self, bg=BG)
        bottom.pack(side="bottom", fill="x", padx=12, pady=(4, 8))
        self.publish_btn = ttk.Button(bottom, text="Publish", style="Accent.TButton",
                                      command=self.controller.publish_story)
        self.publish_btn.pack(side="right")
        self.del_btn = ttk.Button(bottom, text="Delete Slide", style="Secondary.TButton",
                                  command=self.controller.delete_current_slide)
        self.del_btn.pack(side="left")

        # ── Nav strip: Home | ◀ ▶ | [1][2][3] | + Slide ──
        nav = tk.Frame(self, bg=BG)
        nav.pack(fill="x", padx=12, pady=(8, 4))

        ttk.Button(nav, text="⌂ Home", style="Secondary.TButton",
                   command=lambda: self.controller.show_frame("StartFrame")).pack(side="left", padx=(0, 12))

        self.prev_btn = ttk.Button(nav, text="◀", style="Nav.TButton", width=3,
                                   command=lambda: self._navigate_to(self.controller.slide_manager.current_index - 1))
        self.prev_btn.pack(side="left")
        self.next_btn = ttk.Button(nav, text="▶", style="Nav.TButton", width=3,
                                   command=lambda: self._navigate_to(self.controller.slide_manager.current_index + 1))
        self.next_btn.pack(side="left", padx=(2, 8))

        self.slide_nav_frame = tk.Frame(nav, bg=BG)
        self.slide_nav_frame.pack(side="left", fill="x", expand=True)
        self.slide_nav_buttons: List[tk.Button] = []

        ttk.Button(nav, text="+ Slide", style="Secondary.TButton",
                   command=self.controller.add_new_slide).pack(side="left", padx=(8, 0))

        # ── Content area ──
        content = tk.Frame(self, bg=BG)
        content.pack(fill="both", expand=True, padx=12, pady=(0, 4))

        # Left panel: Subjects/Actions + Text overlay
        left = tk.Frame(content, bg=BG)
        left.pack(side="left", fill="y", padx=(0, 12))

        sa_frame = tk.LabelFrame(left, text="Subjects & Actions", bg=BG)
        sa_frame.pack(fill="x", pady=(0, 8))
        self.sa_container = tk.Frame(sa_frame, bg=BG)
        self.sa_container.pack(fill="x", padx=6, pady=6)

        pair_controls = tk.Frame(sa_frame, bg=BG)
        pair_controls.pack(fill="x", pady=(4, 0))
        ttk.Button(pair_controls, text="Add Person", style="Secondary.TButton",
                   command=self.controller.add_person_pair).pack(side="left", padx=6)
        ttk.Button(pair_controls, text="Remove Person", style="Secondary.TButton",
                   command=self.controller.remove_person_pair).pack(side="left", padx=6)

        text_frame = tk.LabelFrame(left, text="Slide Text (Overlay)", bg=BG)
        text_frame.pack(fill="both", expand=True, pady=(8, 0))
        self.text_widget = scrolledtext.ScrolledText(text_frame, width=38, height=8, wrap=tk.WORD)
        self.text_widget.pack(fill="both", expand=True, padx=6, pady=6)
        self.text_widget.bind("<KeyRelease>", self._update_prompt_preview)

        # Right panel: image → Illustrate (centred below image) → prompt preview → status
        right = tk.Frame(content, bg=BG)
        right.pack(side="left", fill="both", expand=True)

        self.image_label = tk.Label(right, bg="#F0F0F0", width=IMG_W, height=IMG_H)
        self.image_label.pack(padx=6, pady=(6, 4))

        self.illustrate_btn = ttk.Button(right, text="Illustrate", style="Accent.TButton",
                                         command=self.controller.illustrate_current_slide)
        self.illustrate_btn.pack(pady=(0, 8))  # naturally centres under the image

        pv_frame = tk.LabelFrame(right, text="Prompt Preview", bg=BG)
        pv_frame.pack(fill="x", padx=6, pady=(0, 4))
        self.prompt_view = scrolledtext.ScrolledText(pv_frame, width=40, height=5, wrap=tk.WORD)
        self.prompt_view.pack(fill="both", padx=6, pady=6)
        self.prompt_view.configure(state="disabled")

        self.status_var = tk.StringVar(value="Idle")
        self.status_label = tk.Label(right, textvariable=self.status_var, bg=BG, fg=INK_MUTED)
        self.status_label.pack(padx=6, pady=(2, 4))

        # Internal state
        self.subject_entries: List[tk.Entry] = []
        self.action_entries: List[tk.Entry] = []
        self._placeholders: dict = {}  # maps id(entry) -> placeholder string


    def update_display(self):
        if not self.controller.slide_manager.slides:
            return
        slide = self.controller.slide_manager.get_current()
        if not slide:
            return
        total = self.controller.slide_manager.count()
        cur = self.controller.slide_manager.current_index + 1

        # Rebuild the live numbered slide navigator
        self._rebuild_slide_nav()

        # clear subject/action containers
        for w in list(self.sa_container.winfo_children()):
            w.destroy()
        self.subject_entries.clear()
        self.action_entries.clear()
        self._placeholders.clear()

        # ensure arrays
        n = max(len(slide.subjects), len(slide.actions), 1)
        while len(slide.subjects) < n:
            slide.subjects.append("")
        while len(slide.actions) < n:
            slide.actions.append("")

        for i in range(n):
            block = tk.Frame(self.sa_container, bg=BG)
            block.pack(fill="x", pady=4)
            tk.Label(block, text="Who is the subject?", bg=BG, fg=INK_MUTED,
                     font=("Segoe UI", 9)).pack(anchor="w")
            subj = tk.Entry(block)
            subj.insert(0, slide.subjects[i])
            subj.pack(fill="x", pady=(2, 6))
            subj.bind("<KeyRelease>", self._update_prompt_preview)
            tk.Label(block, text="What are they doing?", bg=BG, fg=INK_MUTED,
                     font=("Segoe UI", 9)).pack(anchor="w")
            act = tk.Entry(block)
            act.insert(0, slide.actions[i])
            act.pack(fill="x", pady=(2, 0))
            act.bind("<KeyRelease>", self._update_prompt_preview)
            self.subject_entries.append(subj)
            self.action_entries.append(act)

        # text
        self.text_widget.delete("1.0", "end")
        if slide.text:
            self.text_widget.insert("1.0", slide.text)

        # prompt preview — last generated prompt, or raw input draft (no transformer call)
        self.prompt_view.configure(state="normal")
        self.prompt_view.delete("1.0", "end")
        if slide.last_prompt:
            self.prompt_view.insert("1.0", slide.last_prompt)
        else:
            raw = self._raw_prompt_base(slide)
            if raw:
                self.prompt_view.insert("1.0", raw)
        self.prompt_view.configure(state="disabled")

        # image
        if slide.photo_image:
            self.image_label.config(image=slide.photo_image)
            self.image_label.image = slide.photo_image
        else:
            self.show_placeholder_image()

        self.status_var.set(f"Slide {cur} / {total}")
        self.status_label.config(fg=INK_MUTED)

        # Lock entries if this slide is currently generating.
        if (self.controller.is_generating and
                self.controller.generating_slide_index == self.controller.slide_manager.current_index):
            self._lock_entries(True)

    def _rebuild_slide_nav(self):
        for btn in self.slide_nav_buttons:
            btn.destroy()
        self.slide_nav_buttons.clear()

        total = self.controller.slide_manager.count()
        cur = self.controller.slide_manager.current_index

        for i in range(total):
            is_cur = (i == cur)
            btn = tk.Button(
                self.slide_nav_frame,
                text=str(i + 1),
                width=3,
                bg=ACCENT if is_cur else SURFACE,
                fg="white" if is_cur else INK,
                activebackground=ACCENT_HOV,
                activeforeground="white",
                relief="flat",
                bd=0,
                font=("Segoe UI", 9, "bold" if is_cur else "normal"),
                cursor="hand2",
                command=lambda idx=i: self._navigate_to(idx),
            )
            btn.pack(side="left", padx=2, pady=2)
            self.slide_nav_buttons.append(btn)

        self.prev_btn.state(["!disabled"] if cur > 0 else ["disabled"])
        self.next_btn.state(["!disabled"] if cur < total - 1 else ["disabled"])

    def _navigate_to(self, index: int):
        total = self.controller.slide_manager.count()
        if not (0 <= index < total):
            return
        self.save_current_slide_data()
        self.controller.slide_manager.current_index = index
        self.update_display()

    def _raw_prompt_base(self, slide) -> str:
        """Build the raw combined input string without calling the transformer."""
        parts = []
        n = min(len(slide.subjects), len(slide.actions))
        for i in range(n):
            subj = (slide.subjects[i] or "").strip()
            act  = (slide.actions[i] or "").strip()
            if subj and act:
                parts.append(f"{subj} {act}")
            elif subj:
                parts.append(subj)
            elif act:
                parts.append(f"someone {act}")
        tclean = (slide.text or "").strip()
        if tclean:
            parts.append(tclean)
        return ", ".join(parts)

    def _get_entry_value(self, entry: tk.Entry) -> str:
        """Return the real value of an entry, empty string if it shows placeholder."""
        val = entry.get()
        if val == self._placeholders.get(id(entry), ""):
            return ""
        return val.strip()

    def _update_prompt_preview(self, _event=None):
        slide = self.controller.slide_manager.get_current()
        if not slide:
            return
        parts = []
        for subj_e, act_e in zip(self.subject_entries, self.action_entries):
            subj = self._get_entry_value(subj_e)
            act  = self._get_entry_value(act_e)
            if subj and act:
                parts.append(f"{subj} {act}")
            elif subj:
                parts.append(subj)
            elif act:
                parts.append(f"someone {act}")
        text = self.text_widget.get("1.0", "end").strip()
        if text:
            parts.append(text)
        raw = ", ".join(parts)
        self.prompt_view.configure(state="normal")
        self.prompt_view.delete("1.0", "end")
        if raw:
            self.prompt_view.insert("1.0", raw)
        self.prompt_view.configure(state="disabled")

    def save_current_slide_data(self):
        slide = self.controller.slide_manager.get_current()
        if not slide:
            return
        subjects = [e.get().strip() for e in self.subject_entries] if self.subject_entries else [""]
        actions = [e.get().strip() for e in self.action_entries] if self.action_entries else [""]
        text = self.text_widget.get("1.0", "end").strip()
        slide.subjects = subjects or [""]
        slide.actions = actions or [""]
        slide.text = text

    def show_placeholder_image(self):
        try:
            img = Image.new("RGB", (IMG_W, IMG_H), (240, 240, 240))
            draw = ImageDraw.Draw(img)
            draw.text((IMG_W // 2 - 40, IMG_H // 2 - 8), "No Image", fill=(100, 100, 100))
            tkimg = ImageTk.PhotoImage(img)
            self.image_label.config(image=tkimg)
            self.image_label.image = tkimg
        except Exception:
            pass

    def _set_generate_locked(self, locked: bool) -> None:
        """Enable or disable the Illustrate and Publish buttons only."""
        state = ["disabled"] if locked else ["!disabled"]
        self.illustrate_btn.state(state)
        self.publish_btn.state(state)

    def _lock_entries(self, locked: bool) -> None:
        """Lock or unlock the text/subject/action entries for the currently displayed slide."""
        state = "disabled" if locked else "normal"
        try:
            self.text_widget.config(state=state)
        except Exception:
            pass
        for e in self.subject_entries + self.action_entries:
            try:
                e.config(state=state)
            except Exception:
                pass

    def show_generation_status(self, generating: bool) -> None:
        self._set_generate_locked(generating)
        if generating:
            self.status_var.set("Generating...")
            self.status_label.config(fg=INK_MUTED)
        else:
            idx = self.controller.slide_manager.current_index + 1
            cnt = self.controller.slide_manager.count()
            self.status_var.set(f"Slide {idx} / {cnt}")
            self.status_label.config(fg=INK_MUTED)

    def show_violation_status(self, generation_complete: bool = False) -> None:
        """Show 'This is a children's program.' warning. Pass generation_complete=True to also re-enable buttons."""
        self.status_var.set("This is a children's program.")
        self.status_label.config(fg="#CC0000")
        if generation_complete:
            self._set_generate_locked(False)

class StartupFrame(tk.Frame):
    """Frame that shows while Forge is starting"""
    def __init__(self, parent, controller):
        super().__init__(parent, bg=BG)
        self.controller = controller
        self._build()
        
    def _build(self):
        # Title
        tk.Label(self, text="StoryBook AI", font=TITLE_FONT, bg=BG, fg=INK).place(relx=0.5, y=120, anchor="center")
        
        # Status
        self.status_label = tk.Label(self, text="Starting Forge AI Engine...", font=("Segoe UI", 14), bg=BG, fg=INK)
        self.status_label.place(relx=0.5, y=200, anchor="center")
        
        # Progress bar
        self.progress = ttk.Progressbar(self, mode='indeterminate', length=400)
        self.progress.place(relx=0.5, y=250, anchor="center")
        self.progress.start(10)
        
        # Log area
        log_frame = tk.Frame(self, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
        log_frame.place(relx=0.5, y=400, anchor="center", width=800, height=200)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, bd=0, font=("Consolas", 9), 
                                                 bg=SURFACE, fg=INK, height=8)
        self.log_text.pack(fill="both", expand=True, padx=2, pady=2)
        self.log_text.configure(state="disabled")
        
        # Cancel button
        ttk.Button(self, text="Cancel", style="Secondary.TButton", 
                  command=self.controller.shutdown).place(relx=0.5, y=550, anchor="center", width=120)
    
    def update_status(self, text: str):
        self.status_label.config(text=text)
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"{text}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
        self.update()
# ===== Entry point =====
def main():
    app = StoryBookApp()
    try:
        app.mainloop()
    except KeyboardInterrupt:
        try:
            app.shutdown()
        finally:
            pass


if __name__ == "__main__":
    main()
