import re
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter import scrolledtext
from dataclasses import dataclass, field
from PIL import Image, ImageTk, Image

# ========= THEME =========
BG          = "#F3CBE6"   # soft pink
SURFACE     = "#FFFFFF"
ACCENT      = "#8A2BE2"
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
                        foreground=INK, padding=(8, 4))
        style.map("Secondary.TButton",
                  background=[("disabled", DISABLED_BG), ("active", "#D7C4E4"), ("!disabled", "#EAD7F6")])
        style.configure("Nav.TButton", font=("Segoe UI", 11, "bold"), padding=(12, 6))
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

        # Auto-save / shortcuts
        self.bind("<FocusOut>", lambda e: self.frames["SlideFrame"].save_current_slide_data())
        self.bind("<Unmap>",    lambda e: self.frames["SlideFrame"].save_current_slide_data())
        self.bind("<Left>",  lambda e: self.navigate(-1))
        self.bind("<Right>", lambda e: self.navigate(1))
        self.bind("<Control-n>", lambda e: self.add_new_slide())
        self.bind("<Control-Return>", lambda e: self.illustrate_current_slide())

    def show_frame(self, name): self.frames[name].tkraise()

    # ----- story processing -----
    def process_initial_story(self, story_text: str):
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', story_text) if s.strip()]
        self.slides = [Slide(texts=[s]) for s in sentences] or [Slide()]
        self.current_slide_index = 0
        self.show_frame("SlideFrame")
        self.frames["SlideFrame"].update_display()
        self.illustrate_current_slide()

    # ----- navigation -----
    def navigate(self, direction: int):
        if not self.slides: return
        self.frames["SlideFrame"].save_current_slide_data()
        idx = self.current_slide_index + direction
        if 0 <= idx < len(self.slides):
            self.current_slide_index = idx
            self.frames["SlideFrame"].update_display()

    def add_new_slide(self):
        sf = self.frames["SlideFrame"]
        sf.save_current_slide_data()
        self.slides.insert(self.current_slide_index + 1, Slide())
        self.current_slide_index += 1
        sf.update_display()

    def delete_current_slide(self):
        if len(self.slides) <= 1: return
        sf = self.frames["SlideFrame"]
        sf.save_current_slide_data()
        self.slides.pop(self.current_slide_index)
        if self.current_slide_index >= len(self.slides):
            self.current_slide_index = len(self.slides) - 1
        sf.update_display()

    # ----- Subject & Action paired logic -----
    def add_person_pair(self):
        sf = self.frames["SlideFrame"]
        # Persist current Subject/Action values only; do not touch Text
        if getattr(sf, "subject_vars", None):
            self.slides[self.current_slide_index].subjects = [v.get() for v in sf.subject_vars] or [""]
        if getattr(sf, "action_vars", None):
            self.slides[self.current_slide_index].actions  = [v.get() for v in sf.action_vars] or [""]
        slide = self.slides[self.current_slide_index]
        slide.subjects.append("")
        slide.actions.append("")
        sf.update_display()

    def remove_person_pair(self):
        sf = self.frames["SlideFrame"]
        if getattr(sf, "subject_vars", None):
            self.slides[self.current_slide_index].subjects = [v.get() for v in sf.subject_vars] or [""]
        if getattr(sf, "action_vars", None):
            self.slides[self.current_slide_index].actions  = [v.get() for v in sf.action_vars] or [""]
        slide = self.slides[self.current_slide_index]
        if len(slide.subjects) > 1 and len(slide.actions) > 1:
            slide.subjects.pop()
            slide.actions.pop()
        sf.update_display()

    # ----- illustrate/publish -----
    def illustrate_current_slide(self):
        sf = self.frames["SlideFrame"]
        sf.save_current_slide_data()
        slide = self.slides[self.current_slide_index]

        n = max(len(slide.subjects), len(slide.actions))
        slide.subjects += [""] * (n - len(slide.subjects))
        slide.actions  += [""] * (n - len(slide.actions))

        parts = slide.subjects + slide.actions + slide.texts
        prompt = ", ".join(p.strip() for p in parts if p.strip())
        slide.last_prompt = prompt or ""

        img = Image.new("RGB", (IMG_W, IMG_H), color=(255, 255, 255))
        slide.image = ImageTk.PhotoImage(img)
        sf.update_display()


# ========= HOME SCREEN =========
class StartFrame(tk.Frame):
    def __init__(self, parent, controller: StoryBookApp):
        super().__init__(parent, bg=BG)
        self.controller = controller

        # Title with subtle shadow
        tk.Label(self, text="StoryBook", font=TITLE_FONT, bg=BG, fg="#5A2A6E").place(relx=0.5, y=68, anchor="center")
        tk.Label(self, text="StoryBook", font=TITLE_FONT, bg=BG, fg=INK).place(relx=0.5, y=64, anchor="center")

        # Card container
        card = tk.Frame(self, bg=SURFACE, highlightthickness=1, highlightbackground="#555")
        card.place(relx=0.5, rely=0.45, anchor="center", width=700, height=280)

        # Typing affordance + placeholder
        placeholder = "Write your story here..."
        self.story_text = tk.Text(
            card,
            wrap="word",
            bd=0,
            font=BODY_FONT,
            bg=SURFACE,
            fg="#888",                 # placeholder color
            insertbackground=INK,      # caret color
            cursor="xterm",            # I-beam on hover
            highlightthickness=1,
            highlightbackground="#AAA",
            highlightcolor=ACCENT,
            insertofftime=0,           # caret always visible when focused
            insertwidth=2              # thicker caret
        )
        self.story_text.insert("1.0", placeholder)
        self.story_text.place(relx=0.5, rely=0.5, anchor="center", width=660, height=240)

        def clear_placeholder(_):
            if self.story_text.get("1.0", "end-1c") == placeholder:
                self.story_text.delete("1.0", "end")
                self.story_text.config(fg=INK)

        def restore_placeholder(_):
            if not self.story_text.get("1.0", "end-1c").strip():
                self.story_text.insert("1.0", placeholder)
                self.story_text.config(fg="#888")

        # Focus behaviors
        self.story_text.bind("<FocusIn>", clear_placeholder)
        self.story_text.bind("<FocusOut>", restore_placeholder)
        self.story_text.bind("<Button-1>", lambda e: self.story_text.focus_set())
        card.bind("<Button-1>", lambda e: self.story_text.focus_set())  # click anywhere on card

        ttk.Button(
            self, text="Illustrate", style="Accent.TButton",
            command=lambda: self.controller.process_initial_story(self.story_text.get("1.0", "end-1c"))
        ).place(relx=0.5, rely=0.8, anchor="center", width=200)


# ========= SLIDE EDITOR =========
class SlideFrame(tk.Frame):
    def __init__(self, parent, controller: StoryBookApp):
        super().__init__(parent, bg=BG)
        self.controller = controller

        # Title
        tk.Label(self, text="Slide", font=H1_FONT, bg=BG, fg="#5A2A6E").place(relx=0.5, y=38, anchor="center")
        self.slide_title = tk.Label(self, text="Slide 1", font=H1_FONT, bg=BG, fg=INK)
        self.slide_title.place(relx=0.5, y=34, anchor="center")

        # Top navigation: [◀] [–] ... [＋] [▶]
        self.back_btn = ttk.Button(self, text="◀", style="Nav.TButton",
                                   command=lambda: self.controller.navigate(-1))
        self.back_btn.place(x=S4, y=S4, width=80)

        self.del_slide_btn = ttk.Button(self, text="–", style="Nav.TButton",
                                        command=self.controller.delete_current_slide)
        self.del_slide_btn.place(x=S4+88, y=S4, width=80)

        self.add_btn = ttk.Button(self, text="+", style="Nav.TButton",
                                  command=self.controller.add_new_slide)
        self.add_btn.place(relx=1.0, x=-(S4+168), y=S4, width=80, anchor="ne")

        self.fwd_btn = ttk.Button(self, text="▶", style="Nav.TButton",
                                  command=lambda: self.controller.navigate(1))
        self.fwd_btn.place(relx=1.0, x=-(S4+80), y=S4, width=80, anchor="ne")

        # Layout grid
        area = tk.Frame(self, bg=BG)
        area.place(x=S6, y=80, relwidth=1.0, relheight=1.0, anchor="nw", width=-S6*2, height=-S6*2)
        area.grid_columnconfigure(0, weight=1)
        area.grid_columnconfigure(1, weight=1)
        area.grid_rowconfigure(0, weight=1)

        left  = tk.Frame(area, bg=BG); left.grid(row=0, column=0, sticky="nsew", padx=(0, S5))
        right = tk.Frame(area, bg=BG); right.grid(row=0, column=1, sticky="nsew")

        # Sections
        self.subject_section = self._section(left, "Subject")
        self.subject_tabs = tk.Frame(self.subject_section["body"], bg=BG)
        self.subject_tabs.pack(fill="x", padx=S3, pady=(S2, 0))
        self.subject_row = tk.Frame(self.subject_section["body"], bg=BG)
        self.subject_row.pack(fill="x", padx=S3, pady=(S2, S3))

        self.action_section = self._section(left, "Action")
        self.action_tabs = tk.Frame(self.action_section["body"], bg=BG)
        self.action_tabs.pack(fill="x", padx=S3, pady=(S2, 0))
        self.action_row = tk.Frame(self.action_section["body"], bg=BG)
        self.action_row.pack(fill="x", padx=S3, pady=(S2, S3))

        self.text_section = self._section(left, "Text", show_buttons=False)
        self.text_list = tk.Frame(self.text_section["body"], bg=BG)
        self.text_list.pack(fill="x", padx=S3, pady=(S2, 0))

        # Home
        controls = tk.Frame(left, bg=BG)
        controls.pack(fill="x", pady=(S3, 0))
        ttk.Button(controls, text="Home", style="Secondary.TButton",
                   command=lambda: self.controller.show_frame("StartFrame")).pack(side="left")

        # Right column
        img_wrap = tk.Frame(right, bg=BG); img_wrap.pack(fill="x", pady=(0, S2))
        self.img_border = tk.Frame(img_wrap, bg=ACCENT, highlightthickness=0); self.img_border.pack()
        self.image_label = tk.Label(self.img_border, bg=SURFACE, width=IMG_W, height=IMG_H); self.image_label.pack()
        self._blank_photo = ImageTk.PhotoImage(Image.new("RGB", (IMG_W, IMG_H), color=(255, 255, 255)))
        self.image_label.config(image=self._blank_photo); self.image_label.image = self._blank_photo

        self.illustrate_btn = ttk.Button(right, text="Illustrate", style="Accent.TButton",
                                         command=self.controller.illustrate_current_slide)
        self.illustrate_btn.pack(pady=S4, ipadx=20)

        # Prompt (read-only, tight, black 1px frame)
        prompt_box = tk.Frame(right, bg=BG); prompt_box.pack(fill="x")
        tk.Label(prompt_box, text="Prompt", bg=BG, fg=INK_MUTED, font=H2_FONT).pack(anchor="w", padx=2, pady=(0, S1))

        prompt_frame = tk.Frame(prompt_box, bg="black", highlightbackground="black", highlightthickness=1, bd=0)
        prompt_frame.pack(fill="x", padx=0, pady=0)

        self.prompt_view = scrolledtext.ScrolledText(
            prompt_frame, wrap="word", font=BODY_FONT, height=6,
            bg=SURFACE, fg=INK, insertbackground=INK,
            relief="flat", bd=0, borderwidth=0, highlightthickness=0,
            padx=0, pady=0, takefocus=0
        )
        self.prompt_view.pack(fill="x", expand=False, padx=0, pady=0)
        self.prompt_view.configure(state="disabled")
        for seq in ("<Key>", "<Button-2>", "<Button-3>"):
            self.prompt_view.bind(seq, lambda e: "break")

        # runtime vars
        self.subject_vars: list[tk.StringVar] = []
        self.action_vars:  list[tk.StringVar] = []
        self.text_widgets: list[tk.Text]      = []

        # header +/- (packed dynamically)
        self.subject_plus_btn  = ttk.Button(self.subject_section["header"], text="+",
                                            style="Secondary.TButton",
                                            command=self.controller.add_person_pair)
        self.subject_minus_btn = ttk.Button(self.subject_section["header"], text="–",
                                            style="Secondary.TButton",
                                            command=self.controller.remove_person_pair)
        self.action_plus_btn   = ttk.Button(self.action_section["header"], text="+",
                                            style="Secondary.TButton",
                                            command=self.controller.add_person_pair)
        self.action_minus_btn  = ttk.Button(self.action_section["header"], text="–",
                                            style="Secondary.TButton",
                                            command=self.controller.remove_person_pair)

    def _section(self, parent, title, show_buttons=True):
        wrap = tk.Frame(parent, bg=BG); wrap.pack(fill="x", pady=(0, S3))
        header = tk.Frame(wrap, bg=ACCENT); header.pack(fill="x", padx=S2)
        tk.Label(header, text=title, bg=ACCENT, fg="white", font=H2_FONT).pack(side="left", padx=S3, pady=S1)
        body = tk.Frame(wrap, bg=BG); body.pack(fill="x")
        return {"root": wrap, "header": header, "body": body}

    # ===== Rendering & State =====
    def update_display(self):
        if not self.controller.slides: return
        slide = self.controller.slides[self.controller.current_slide_index]
        total = len(self.controller.slides)
        self.slide_title.config(text=f"Slide {self.controller.current_slide_index + 1}")

        # nav disabled states
        on_first   = (self.controller.current_slide_index == 0)
        can_delete = (total > 1) and not on_first
        can_forward= (total > 1) and (self.controller.current_slide_index < total - 1)
        self.back_btn.state(["!disabled"] if not on_first else ["disabled"])
        self.del_slide_btn.state(["!disabled"] if can_delete else ["disabled"])
        self.fwd_btn.state(["!disabled"] if can_forward else ["disabled"])
        self.illustrate_btn.config(text="Publish" if self.controller.current_slide_index == total - 1 else "Illustrate")

        # normalize pair lengths
        n = max(len(slide.subjects or [""]), len(slide.actions or [""]), 1)
        slide.subjects += [""] * (n - len(slide.subjects))
        slide.actions  += [""] * (n - len(slide.actions))

        # clear rows
        for w in (self.subject_tabs.winfo_children() + self.subject_row.winfo_children()
                  + self.action_tabs.winfo_children() + self.action_row.winfo_children()
                  + self.text_list.winfo_children()):
            w.destroy()
        self.subject_vars.clear(); self.action_vars.clear(); self.text_widgets.clear()

        # Subject chips + entries
        for i, val in enumerate(slide.subjects):
            tk.Label(self.subject_tabs, text=f"Pair {i+1}", bg="#E6D4F5", fg=INK,
                     font=("Segoe UI", 9, "bold"), bd=0, padx=8, pady=2).pack(side="left", padx=(0, 4))
            v = tk.StringVar(value=val); self.subject_vars.append(v)
        for v in self.subject_vars:
            cell = tk.Frame(self.subject_row, bg=BG); cell.pack(side="left", fill="x", expand=True, padx=S2)
            e = tk.Entry(cell, textvariable=v, font=BODY_FONT, bd=1, relief="solid",
                         highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT,
                         background="#FAF8FC", fg=INK, insertbackground=INK)
            e.pack(fill="x", ipady=3)

        # Action chips + entries
        for i, val in enumerate(slide.actions):
            tk.Label(self.action_tabs, text=f"Pair {i+1}", bg="#E6D4F5", fg=INK,
                     font=("Segoe UI", 9, "bold"), bd=0, padx=8, pady=2).pack(side="left", padx=(0, 4))
            v = tk.StringVar(value=val); self.action_vars.append(v)
        for v in self.action_vars:
            cell = tk.Frame(self.action_row, bg=BG); cell.pack(side="left", fill="x", expand=True, padx=S2)
            e = tk.Entry(cell, textvariable=v, font=BODY_FONT, bd=1, relief="solid",
                         highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT,
                         background="#FAF8FC", fg=INK, insertbackground=INK)
            e.pack(fill="x", ipady=3)

        # Header +/- buttons — show minus only when 2+ pairs
        for b in (self.subject_plus_btn, self.subject_minus_btn, self.action_plus_btn, self.action_minus_btn):
            b.pack_forget()
        if len(slide.subjects) >= 2:
            self.subject_minus_btn.pack(in_=self.subject_section["header"], side="right", padx=(S1, S1), pady=S1)
            self.action_minus_btn.pack(in_=self.action_section["header"],   side="right", padx=(S1, S1), pady=S1)
        self.subject_plus_btn.pack(in_=self.subject_section["header"], side="right", padx=(S1, S2), pady=S1)
        self.action_plus_btn.pack(in_=self.action_section["header"],   side="right", padx=(S1, S2), pady=S1)

        # Text blocks (stacked, editable)
        for text_content in slide.texts:
            card = tk.Frame(self.text_list, bg=SURFACE, highlightthickness=1, highlightbackground="#555")
            card.pack(fill="x", pady=(S1, S2))
            txt = tk.Text(card, height=8, wrap="word", bd=0, font=BODY_FONT, bg=SURFACE, fg=INK, insertbackground=INK)
            txt.insert("1.0", text_content); txt.pack(fill="both", expand=True, padx=S2, pady=S2)
            self.text_widgets.append(txt)

        # Image / Prompt refresh
        if slide.image:
            self.image_label.config(image=slide.image); self.image_label.image = slide.image
        else:
            self.image_label.config(image=self._blank_photo); self.image_label.image = self._blank_photo

        self.prompt_view.configure(state="normal")
        self.prompt_view.delete("1.0", "end")
        if slide.last_prompt:
            self.prompt_view.insert("1.0", slide.last_prompt)
        self.prompt_view.configure(state="disabled")

    def save_current_slide_data(self):
        """Conservative save: only overwrite sections that have live widgets/vars."""
        if not self.controller.slides:
            return
        slide = self.controller.slides[self.controller.current_slide_index]

        if getattr(self, "subject_vars", None):
            slide.subjects = [v.get() for v in self.subject_vars] or [""]

        if getattr(self, "action_vars", None):
            slide.actions  = [v.get() for v in self.action_vars]  or [""]

        if getattr(self, "text_widgets", None):
            slide.texts    = [t.get("1.0", "end-1c") for t in self.text_widgets] or [""]

    def _blank_image(self, w, h):
        img = Image.new("RGB", (w, h), color=(255, 255, 255))
        return ImageTk.PhotoImage(img)


# ========= RUN =========
if __name__ == "__main__":
    app = StoryBookApp()
    app.mainloop()
