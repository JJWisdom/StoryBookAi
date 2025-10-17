import re
import tkinter as tk
from tkinter import ttk, messagebox
from dataclasses import dataclass, field
from PIL import Image, ImageTk, ImageDraw, ImageFont

# ========= THEME (soft pink / purple) =========
BG          = "#F3CBE6"   # soft pink
SURFACE     = "#FFFFFF"   # white cards
ACCENT      = "#8A2BE2"   # purple
ACCENT_HOV  = "#6A1EAD"
DISABLED_BG = "#E8E1EE"
INK         = "#242424"
INK_MUTED   = "#6B6B6B"
BORDER      = "#C9B1D9"

IMG_W, IMG_H = 420, 300

TITLE_FONT = ("Georgia", 44, "bold")
H1_FONT    = ("Georgia", 34, "bold")
H2_FONT    = ("Segoe UI", 11, "bold")
BODY_FONT  = ("Segoe UI", 11)

S1, S2, S3, S4, S5, S6 = 4, 8, 12, 16, 24, 32


# ========= DATA =========
@dataclass
class Slide:
    subjects: list[str] = field(default_factory=lambda: [""])
    actions:  list[str] = field(default_factory=lambda: [""])
    texts:    list[str] = field(default_factory=lambda: [""])
    image:    object = None
    last_prompt: str = ""


# ========= APP =========
class StoryBookApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("StoryBook")
        self.geometry("1000x720")
        self.configure(bg=BG)

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TLabel", background=BG, foreground=INK)
        style.configure("Accent.TButton", font=("Segoe UI", 12, "bold"),
                        foreground="white", padding=(18, 10))
        style.map("Accent.TButton",
                  background=[("disabled", ACCENT), ("active", ACCENT_HOV), ("!disabled", ACCENT)])
        style.configure("Secondary.TButton", font=("Segoe UI", 11, "bold"),
                        foreground=INK, padding=(10, 6))
        style.map("Secondary.TButton",
                  background=[("disabled", DISABLED_BG), ("active", "#D7C4E4"), ("!disabled", "#EAD7F6")])
        style.configure("Nav.TButton", font=("Segoe UI", 11, "bold"),
                        padding=(12, 6))
        style.map("Nav.TButton",
                  background=[("disabled", DISABLED_BG), ("active", "#E1D6F1"), ("!disabled", "#EFE6FA")])

        self.slides: list[Slide] = []
        self.current_slide_index = 0

        container = tk.Frame(self, bg=BG)
        container.pack(fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.frames = {}
        for F in (StartFrame, SlideFrame):
            frame = F(container, self)
            self.frames[F.__name__] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.show_frame("StartFrame")

        # global autosave hooks
        self.bind("<FocusOut>", lambda e: self.frames["SlideFrame"].save_current_slide_data())
        self.bind("<Unmap>",    lambda e: self.frames["SlideFrame"].save_current_slide_data())
        self.bind("<Left>",  lambda e: self.navigate(-1))
        self.bind("<Right>", lambda e: self.navigate(1))
        self.bind("<Control-n>", lambda e: self.add_new_slide())
        self.bind("<Control-Return>", lambda e: self.illustrate_current_slide())

    def show_frame(self, name): self.frames[name].tkraise()

    # ----- story processing
    def process_initial_story(self, story_text: str):
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', story_text) if s.strip()]
        self.slides = [Slide(texts=[s]) for s in sentences] or [Slide()]
        self.current_slide_index = 0
        self.show_frame("SlideFrame")
        self.frames["SlideFrame"].update_display()
        self.illustrate_current_slide()

    # ----- slide nav
    def navigate(self, direction: int):
        if not self.slides: return
        self.frames["SlideFrame"].save_current_slide_data()
        idx = self.current_slide_index + direction
        if 0 <= idx < len(self.slides):
            self.current_slide_index = idx
            self.frames["SlideFrame"].update_display()

    def add_new_slide(self):
        sf = self.frames["SlideFrame"]; sf.save_current_slide_data()
        self.slides.insert(self.current_slide_index + 1, Slide())
        self.current_slide_index += 1
        sf.update_display()

    def delete_current_slide(self):
        if len(self.slides) <= 1: return
        sf = self.frames["SlideFrame"]; sf.save_current_slide_data()
        self.slides.pop(self.current_slide_index)
        if self.current_slide_index >= len(self.slides):
            self.current_slide_index = len(self.slides) - 1
        sf.update_display()

    # ----- per-section add/remove
    def add_subject(self):
        sf = self.frames["SlideFrame"]; sf.save_current_slide_data()
        self.slides[self.current_slide_index].subjects.append("")
        sf.update_display()

    def remove_subject(self):
        sf = self.frames["SlideFrame"]; sf.save_current_slide_data()
        subs = self.slides[self.current_slide_index].subjects
        if len(subs) > 1: subs.pop()
        sf.update_display()

    def add_action(self):
        sf = self.frames["SlideFrame"]; sf.save_current_slide_data()
        self.slides[self.current_slide_index].actions.append("")
        sf.update_display()

    def remove_action(self):
        sf = self.frames["SlideFrame"]; sf.save_current_slide_data()
        acts = self.slides[self.current_slide_index].actions
        if len(acts) > 1: acts.pop()
        sf.update_display()

    def add_text(self):
        sf = self.frames["SlideFrame"]; sf.save_current_slide_data()
        self.slides[self.current_slide_index].texts.append("")
        sf.update_display()

    def remove_text(self):
        sf = self.frames["SlideFrame"]; sf.save_current_slide_data()
        txts = self.slides[self.current_slide_index].texts
        if len(txts) > 1: txts.pop()
        sf.update_display()

    # ----- illustrate/publish
    def illustrate_current_slide(self):
        sf = self.frames["SlideFrame"]; sf.save_current_slide_data()
        slide = self.slides[self.current_slide_index]
        parts = (slide.subjects or []) + (slide.actions or []) + (slide.texts or [])
        prompt = ", ".join(p.strip() for p in parts if p and p.strip())
        if not prompt:
            messagebox.showinfo("Nothing to illustrate", "Add a Subject, Action, or Text first.")
            return
        slide.last_prompt = prompt
        # clean white panel; prompt shown below
        img = sf.create_placeholder_image(IMG_W, IMG_H)
        slide.image = img
        sf.update_display()


# ========= START =========
class StartFrame(tk.Frame):
    def __init__(self, parent, controller: StoryBookApp):
        super().__init__(parent, bg=BG)
        self.controller = controller

        # Title centered with subtle shadow
        tk.Label(self, text="StoryBook", font=TITLE_FONT, bg=BG, fg="#5A2A6E").place(relx=0.5, y=68, anchor="center")
        tk.Label(self, text="StoryBook", font=TITLE_FONT, bg=BG, fg=INK).place(relx=0.5, y=64, anchor="center")

        # Card
        card = tk.Frame(self, bg=SURFACE, highlightthickness=1, highlightbackground="#555")
        card.place(relx=0.5, rely=0.45, anchor="center", width=700, height=280)

        self.story_text = tk.Text(card, wrap="word", bd=0, font=BODY_FONT, bg=SURFACE, fg=INK)
        self.story_text.place(relx=0.5, rely=0.5, anchor="center", width=660, height=240)

        ttk.Button(self, text="Illustrate", style="Accent.TButton",
                   command=lambda: self.controller.process_initial_story(self.story_text.get("1.0", "end-1c"))
                   ).place(relx=0.5, rely=0.8, anchor="center", width=200)


# ========= SLIDE =========
class SlideFrame(tk.Frame):
    def __init__(self, parent, controller: StoryBookApp):
        super().__init__(parent, bg=BG)
        self.controller = controller

        # Title (center)
        tk.Label(self, text="Slide", font=H1_FONT, bg=BG, fg="#5A2A6E").place(relx=0.5, y=38, anchor="center")
        self.slide_title = tk.Label(self, text="Slide 1", font=H1_FONT, bg=BG, fg=INK)
        self.slide_title.place(relx=0.5, y=34, anchor="center")

        # Top-left and top-right nav cluster (+ and - for slide)
        self.back_btn = ttk.Button(self, text="◀", style="Nav.TButton",
                                   command=lambda: self.controller.navigate(-1))
        self.back_btn.place(x=S4, y=S4, width=80)

        # Right: [-] [ + ] [ > ]
        self.del_slide_btn = ttk.Button(self, text="–", style="Nav.TButton",
                                        command=self.controller.delete_current_slide)
        self.add_btn       = ttk.Button(self, text="+", style="Nav.TButton",
                                        command=self.controller.add_new_slide)
        self.fwd_btn       = ttk.Button(self, text="▶", style="Nav.TButton",
                                        command=lambda: self.controller.navigate(1))
        # position
        self.del_slide_btn.place(relx=1.0, x=-(S4+250), y=S4, width=80)
        self.add_btn.place(relx=1.0, x=-(S4+165), y=S4, width=80)
        self.fwd_btn.place(relx=1.0, x=-(S4+80), y=S4, width=80)

        # Main grid
        area = tk.Frame(self, bg=BG)
        area.place(x=S6, y=80, relwidth=1.0, relheight=1.0, anchor="nw", width=-S6*2, height=-S6*2)
        area.grid_columnconfigure(0, weight=1)
        area.grid_columnconfigure(1, weight=1)
        area.grid_rowconfigure(0, weight=1)

        # LEFT/RIGHT
        left = tk.Frame(area, bg=BG);  left.grid(row=0, column=0, sticky="nsew", padx=(0, S5))
        right = tk.Frame(area, bg=BG); right.grid(row=0, column=1, sticky="nsew")

        # Sections with +/- in header
        self.subject_section = self._section(left, "Subject",
                                             add_cb=self.controller.add_subject,
                                             remove_cb=self.controller.remove_subject)
        self.subject_row = tk.Frame(self.subject_section["body"], bg=BG)
        self.subject_row.pack(fill="x", padx=S3, pady=(S2, S3))

        self.action_section = self._section(left, "Action",
                                            add_cb=self.controller.add_action,
                                            remove_cb=self.controller.remove_action)
        self.action_row = tk.Frame(self.action_section["body"], bg=BG)
        self.action_row.pack(fill="x", padx=S3, pady=(S2, S3))

        self.text_section = self._section(left, "Text",
                                          add_cb=self.controller.add_text,
                                          remove_cb=self.controller.remove_text)
        self.text_list = tk.Frame(self.text_section["body"], bg=BG)
        self.text_list.pack(fill="x", padx=S3, pady=(S2, 0))

        # Home (bottom-left small cluster)
        controls = tk.Frame(left, bg=BG)
        controls.pack(fill="x", pady=(S3, 0))
        ttk.Button(controls, text="Home", style="Secondary.TButton",
                   command=lambda: self.controller.show_frame("StartFrame")).pack(side="left")

        # Right image stack
        img_wrap = tk.Frame(right, bg=BG); img_wrap.pack(fill="both", expand=True)
        self.img_border = tk.Frame(img_wrap, bg=ACCENT, highlightthickness=0); self.img_border.pack(pady=S2)
        self.image_label = tk.Label(self.img_border, bg=SURFACE, width=IMG_W, height=IMG_H); self.image_label.pack()
        self._blank_photo = self._blank_image(IMG_W, IMG_H)
        self.image_label.config(image=self._blank_photo); self.image_label.image = self._blank_photo

        self.illustrate_btn = ttk.Button(img_wrap, text="Illustrate", style="Accent.TButton",
                                         command=self.controller.illustrate_current_slide)
        self.illustrate_btn.pack(pady=S4, ipadx=20)

        self.prompt_caption = tk.Label(img_wrap, text="", bg=BG, fg=INK_MUTED, font=BODY_FONT, wraplength=420, justify="left")
        self.prompt_caption.pack(fill="x", pady=(S2, 0))

        # refs
        self.subject_entries: list[tk.Entry] = []
        self.action_entries:  list[tk.Entry] = []
        self.text_widgets:    list[tk.Text]  = []

    # Section with purple header and +/- buttons
    def _section(self, parent, title, add_cb, remove_cb):
        wrap = tk.Frame(parent, bg=BG); wrap.pack(fill="x", pady=(0, S3))
        header = tk.Frame(wrap, bg=ACCENT); header.pack(fill="x", padx=S2)
        tk.Label(header, text=title, bg=ACCENT, fg="white", font=H2_FONT).pack(side="left", padx=S3, pady=S1)
        # right side: [-] [+]
        minus_btn = ttk.Button(header, text="–", style="Secondary.TButton", command=remove_cb)
        plus_btn  = ttk.Button(header, text="+", style="Secondary.TButton", command=add_cb)
        minus_btn.pack(side="right", padx=(S1, S1), pady=S1)
        plus_btn.pack(side="right", padx=(S1, S2), pady=S1)
        body = tk.Frame(wrap, bg=BG); body.pack(fill="x")
        return {"root": wrap, "header": header, "body": body}

    def _bind_autosave(self, w):
        def save(_=None): self.save_current_slide_data()
        if isinstance(w, tk.Text):
            w.bind("<<Modified>>", lambda e: (w.edit_modified(0), save()))
            w.bind("<FocusOut>", save)
        else:
            w.bind("<KeyRelease>", save)
            w.bind("<FocusOut>",  save)

    def update_display(self):
        if not self.controller.slides: return
        slide = self.controller.slides[self.controller.current_slide_index]
        total = len(self.controller.slides)
        self.slide_title.config(text=f"Slide {self.controller.current_slide_index + 1}")
        # nav state
        self.back_btn.state(["!disabled"] if self.controller.current_slide_index > 0 else ["disabled"])
        self.fwd_btn.state(["!disabled"] if self.controller.current_slide_index < total - 1 else ["disabled"])
        self.del_slide_btn.state(["!disabled"] if total > 1 else ["disabled"])
        self.illustrate_btn.config(text="Publish" if self.controller.current_slide_index == total - 1 else "Illustrate")

        # clear rows
        for w in self.subject_row.winfo_children(): w.destroy()
        for w in self.action_row.winfo_children():  w.destroy()
        for w in self.text_list.winfo_children():   w.destroy()
        self.subject_entries.clear(); self.action_entries.clear(); self.text_widgets.clear()

        # SUBJECTS horizontal
        if not slide.subjects: slide.subjects = [""]
        for val in slide.subjects:
            cell = tk.Frame(self.subject_row, bg=BG)
            cell.pack(side="left", fill="x", expand=True, padx=S2)
            e = tk.Entry(cell, font=BODY_FONT, bd=0, highlightthickness=1)
            e.configure(highlightbackground=BORDER, highlightcolor=ACCENT,
                        background=SURFACE, insertbackground=INK)
            e.insert(0, val); e.pack(fill="x", ipady=3)
            self._bind_autosave(e)
            self.subject_entries.append(e)

        # ACTIONS horizontal
        if not slide.actions: slide.actions = [""]
        for val in slide.actions:
            cell = tk.Frame(self.action_row, bg=BG)
            cell.pack(side="left", fill="x", expand=True, padx=S2)
            e = tk.Entry(cell, font=BODY_FONT, bd=0, highlightthickness=1)
            e.configure(highlightbackground=BORDER, highlightcolor=ACCENT,
                        background=SURFACE, insertbackground=INK)
            e.insert(0, val); e.pack(fill="x", ipady=3)
            self._bind_autosave(e)
            self.action_entries.append(e)

        # TEXT blocks stacked
        if not slide.texts: slide.texts = [""]
        for text_content in slide.texts:
            card = tk.Frame(self.text_list, bg=SURFACE, highlightthickness=1, highlightbackground="#555")
            card.pack(fill="x", pady=(S1, S2))
            txt = tk.Text(card, height=8, wrap="word", bd=0, font=BODY_FONT, bg=SURFACE, fg=INK, insertbackground=INK)
            txt.insert("1.0", text_content); txt.pack(fill="both", expand=True, padx=S2, pady=S2)
            self._bind_autosave(txt)
            self.text_widgets.append(txt)

        # IMAGE
        if slide.image:
            self.image_label.config(image=slide.image); self.image_label.image = slide.image
        else:
            self.image_label.config(image=self._blank_photo); self.image_label.image = self._blank_photo

        # PROMPT
        self.prompt_caption.config(text=f"Prompt: {slide.last_prompt}" if slide.last_prompt else "")

    def save_current_slide_data(self):
        if not self.controller.slides: return
        slide = self.controller.slides[self.controller.current_slide_index]
        slide.subjects = [e.get() for e in self.subject_entries] or [""]
        slide.actions  = [e.get() for e in self.action_entries]  or [""]
        slide.texts    = [t.get("1.0", "end-1c") for t in self.text_widgets] or [""]

    def _blank_image(self, w, h):
        img = Image.new("RGB", (w, h), color=(255, 255, 255))
        return ImageTk.PhotoImage(img)

    def create_placeholder_image(self, w, h):
        return self._blank_image(w, h)


# ========= RUN =========
if __name__ == "__main__":
    app = StoryBookApp()
    app.mainloop()
