import tkinter as tk
from tkinter import ttk
from tkinter import font as tkfont
from PIL import Image, ImageTk, ImageDraw, ImageFont

# --- Data Structure for a Slide ---
class Slide:
    """A simple class to hold the data for a single slide."""
    def __init__(self, text=""):
        self.subjects = [""]
        self.actions = [""]
        self.texts = [text]
        self.image = None # This will hold the PhotoImage object for the GUI

# --- Main Application Class ---
class StoryBookApp(tk.Tk):
    """The main application window that manages frames and data."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # --- Basic Window Setup ---
        self.title("StoryBook")
        self.geometry("1000x700")
        self.configure(bg="#FADFF2") # Light pink background

        # --- Style Configuration ---
        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        self.style.configure("TButton",
                             background="#8A2BE2",
                             foreground="white",
                             font=("Helvetica", 12, "bold"),
                             bordercolor="#8A2BE2",
                             lightcolor="#8A2BE2",
                             darkcolor="#8A2BE2")
        self.style.map("TButton",
                       background=[("active", "#6A1EAD")]) # Darker purple on hover/click

        # --- Data Storage ---
        self.slides = []
        self.current_slide_index = 0

        # --- Frame Management ---
        # A container to hold all our frames (screens)
        container = tk.Frame(self, bg="#FADFF2")
        container.pack(side="top", fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.frames = {}
        # We create instances of our two main screens
        for F in (StartFrame, SlideFrame):
            page_name = F.__name__
            frame = F(parent=container, controller=self)
            self.frames[page_name] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.show_frame("StartFrame")

    def show_frame(self, page_name):
        """Show a frame for the given page name."""
        frame = self.frames[page_name]
        frame.tkraise()

    def process_initial_story(self, story_text):
        """
        Takes the full story, splits it into slides, and switches to the editor.
        """
        # A simple way to split the story is by sentences (ending with a period).
        sentences = [s.strip() for s in story_text.split('.') if s.strip()]

        if not sentences: # If no text, create one blank slide
            self.slides = [Slide()]
        else:
            self.slides = [Slide(text=sentence + ".") for sentence in sentences]

        # Switch to the slide editor view and update it with the first slide's data
        self.show_frame("SlideFrame")
        self.frames["SlideFrame"].update_display()
        self.illustrate_current_slide() # Generate the first image

# --- Start Screen ---
class StartFrame(tk.Frame):
    """The first screen the user sees."""
    def __init__(self, parent, controller):
        super().__init__(parent, bg="#FADFF2")
        self.controller = controller

        # --- Title ---
        title_font = tkfont.Font(family="Brush Script MT", size=48, weight="bold")
        title_label = tk.Label(self, text="StoryBook", font=title_font, bg="#FADFF2", fg="#4B0082")
        title_label.pack(pady=(50, 20))

        # --- Text Input Box ---
        text_frame = tk.Frame(self, bg="white", bd=2, relief="solid", highlightbackground="#8A2BE2", highlightthickness=2)
        self.story_text = tk.Text(text_frame, wrap="word", height=15, width=80, font=("Helvetica", 12), bd=0)
        self.story_text.pack(padx=10, pady=10)
        text_frame.pack(pady=20)

        # --- Illustrate Button ---
        illustrate_button = ttk.Button(
            self,
            text="Illustrate",
            command=lambda: self.controller.process_initial_story(self.story_text.get("1.0", "end-1c"))
        )
        illustrate_button.pack(pady=20, ipadx=20, ipady=10)

# --- Slide Editor Screen ---
class SlideFrame(tk.Frame):
    """The main editor screen for creating and viewing slides."""
    def __init__(self, parent, controller):
        super().__init__(parent, bg="#FADFF2")
        self.controller = controller

        # --- Main Layout Frames ---
        self.top_bar = tk.Frame(self, bg="#FADFF2")
        self.top_bar.pack(fill="x", pady=10)
        
        self.main_content = tk.Frame(self, bg="#FADFF2")
        self.main_content.pack(fill="both", expand=True, padx=20, pady=10)
        self.main_content.grid_columnconfigure(0, weight=1) # Left panel
        self.main_content.grid_columnconfigure(1, weight=1) # Right panel
        self.main_content.grid_rowconfigure(0, weight=1)

        # --- Top Bar Widgets ---
        self.slide_title_font = tkfont.Font(family="Brush Script MT", size=36, weight="bold")
        self.slide_title = tk.Label(self.top_bar, text="Slide 1", font=self.slide_title_font, bg="#FADFF2", fg="#4B0082")
        
        self.nav_font = tkfont.Font(family="Helvetica", size=30, weight="bold")
        self.back_arrow = tk.Label(self.top_bar, text="ᐊ", font=self.nav_font, bg="#FADFF2", fg="#8A2BE2", cursor="hand2")
        self.add_button = tk.Label(self.top_bar, text="+", font=self.nav_font, bg="#FADFF2", fg="#8A2BE2", cursor="hand2")
        self.forward_arrow = tk.Label(self.top_bar, text="ᐅ", font=self.nav_font, bg="#FADFF2", fg="#8A2BE2", cursor="hand2")

        self.back_arrow.pack(side="left", padx=20)
        self.slide_title.pack(side="left", expand=True)
        self.add_button.pack(side="left", padx=10)
        self.forward_arrow.pack(side="left", padx=20)

        # --- Bind Navigation Events ---
        self.back_arrow.bind("<Button-1>", lambda e: self.controller.navigate(-1))
        self.forward_arrow.bind("<Button-1>", lambda e: self.controller.navigate(1))
        self.add_button.bind("<Button-1>", lambda e: self.controller.add_new_slide())

        # --- Left Panel for Text Inputs ---
        self.left_panel = tk.Frame(self.main_content, bg="#FADFF2")
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 20))

        # --- Right Panel for Image ---
        self.right_panel = tk.Frame(self.main_content, bg="#FADFF2")
        self.right_panel.grid(row=0, column=1, sticky="nsew")
        
        self.image_container = tk.Frame(self.right_panel, bd=2, relief="solid", highlightbackground="#8A2BE2", highlightthickness=2)
        self.image_label = tk.Label(self.image_container, bg="white")
        self.image_label.pack(fill="both", expand=True)
        self.image_container.pack(fill="both", expand=True, pady=(0, 20))

        self.illustrate_button = ttk.Button(self.right_panel, text="Illustrate", command=self.controller.illustrate_current_slide)
        self.illustrate_button.pack(ipadx=20, ipady=10)

        # Placeholder for dynamically created widgets
        self.input_widgets = []

    def update_display(self):
        """Clears and redraws the widgets based on the current slide data."""
        # Clear old widgets
        for widget in self.input_widgets:
            widget.destroy()
        self.input_widgets = []

        if not self.controller.slides:
            return

        current_slide = self.controller.slides[self.controller.current_slide_index]
        
        # Update Slide Title
        self.slide_title.config(text=f"Slide {self.controller.current_slide_index + 1}")

        # Update Navigation Arrows
        self.back_arrow.config(fg="#8A2BE2" if self.controller.current_slide_index > 0 else "#D3D3D3")
        self.forward_arrow.config(fg="#8A2BE2" if self.controller.current_slide_index < len(self.controller.slides) - 1 else "#D3D3D3")

        # Dynamically create input sections (Subject, Action, Text)
        self._create_input_section("Subject", current_slide.subjects)
        self._create_input_section("Action", current_slide.actions)
        self._create_input_section("Text", current_slide.texts, is_large_text=True)

        # Update the image
        if current_slide.image:
            self.image_label.config(image=current_slide.image)
        else:
            # If no image, show a placeholder
            placeholder = self.create_placeholder_image(400, 300, f"Illustration for Slide {self.controller.current_slide_index + 1} will appear here.")
            self.image_label.config(image=placeholder)
            self.image_label.image = placeholder # Keep a reference!
            
    def _create_input_section(self, name, data_list, is_large_text=False):
        """Helper to create a section like 'Subject' or 'Action'."""
        section_frame = tk.Frame(self.left_panel, bg="#FADFF2")
        section_frame.pack(fill="x", pady=5)
        self.input_widgets.append(section_frame)

        # Header with Title and Add button
        header_frame = tk.Frame(section_frame, bg="#8A2BE2")
        header_frame.pack(fill="x")
        
        label = tk.Label(header_frame, text=name, fg="white", bg="#8A2BE2", font=("Helvetica", 10, "bold"))
        label.pack(side="left", padx=5, pady=2)
        
        add_btn = tk.Label(header_frame, text="+", fg="white", bg="#8A2BE2", font=("Helvetica", 12, "bold"), cursor="hand2")
        add_btn.pack(side="right", padx=5)
        
        # Bind add button to the correct function
        if name == "Subject":
            add_btn.bind("<Button-1>", lambda e: self.controller.add_field("subjects"))
        elif name == "Action":
            add_btn.bind("<Button-1>", lambda e: self.controller.add_field("actions"))
        elif name == "Text":
            add_btn.bind("<Button-1>", lambda e: self.controller.add_field("texts"))

        # Create entry/text widgets for each item in the data list
        for i, text_content in enumerate(data_list):
            if is_large_text:
                widget = tk.Text(section_frame, height=8, wrap="word", font=("Helvetica", 11))
            else:
                widget = tk.Entry(section_frame, font=("Helvetica", 11))
            
            widget.insert("1.0" if is_large_text else "0", text_content)
            widget.pack(fill="x", pady=(2, 5), padx=5)
            self.input_widgets.append(widget) # Add to list for later access/clearing

    def save_current_slide_data(self):
        """Reads data from widgets and saves it to the current slide object."""
        if not self.controller.slides:
            return

        current_slide = self.controller.slides[self.controller.current_slide_index]
        current_slide.subjects = []
        current_slide.actions = []
        current_slide.texts = []

        # This is a simple but effective way to find the widgets.
        # It relies on the creation order in update_display().
        widget_iter = iter(w for w in self.input_widgets if isinstance(w, (tk.Entry, tk.Text)))
        
        try:
            # Assumes one subject section, then one action, then one text section.
            num_subjects = len(self.controller.slides[self.controller.current_slide_index].subjects)
            num_actions = len(self.controller.slides[self.controller.current_slide_index].actions)
            num_texts = len(self.controller.slides[self.controller.current_slide_index].texts)
            
            for _ in range(num_subjects):
                current_slide.subjects.append(next(widget_iter).get())
            for _ in range(num_actions):
                current_slide.actions.append(next(widget_iter).get())
            for _ in range(num_texts):
                current_slide.texts.append(next(widget_iter).get("1.0", "end-1c"))

        except StopIteration:
            print("Warning: Mismatch between widgets and data structure during save.")

    def create_placeholder_image(self, width, height, text):
        """Creates a placeholder image with text."""
        img = Image.new('RGB', (width, height), color = (255, 255, 255))
        d = ImageDraw.Draw(img)
        try:
            fnt = ImageFont.truetype("arial.ttf", 15)
        except IOError:
            fnt = ImageFont.load_default()
        
        # Simple text wrapping
        lines = text.split()
        wrapped_lines = []
        current_line = ""
        for word in lines:
            if d.textlength(current_line + word, font=fnt) < width - 20:
                current_line += word + " "
            else:
                wrapped_lines.append(current_line)
                current_line = word + " "
        wrapped_lines.append(current_line)

        y_text = (height - len(wrapped_lines) * 20) / 2
        for line in wrapped_lines:
            text_width = d.textlength(line, font=fnt)
            d.text(((width-text_width)/2, y_text), line, font=fnt, fill=(150, 150, 150))
            y_text += 20
        
        return ImageTk.PhotoImage(img)

# --- Add Controller Methods to the Main App ---
def navigate(self, direction):
    """Navigate between slides."""
    if not self.slides: return
    
    # Save the data from the current slide before moving
    self.frames["SlideFrame"].save_current_slide_data()
    
    new_index = self.current_slide_index + direction
    if 0 <= new_index < len(self.slides):
        self.current_slide_index = new_index
        self.frames["SlideFrame"].update_display()

def add_new_slide(self):
    """Adds a new blank slide after the current one."""
    self.frames["SlideFrame"].save_current_slide_data()
    
    new_slide = Slide()
    new_index = self.current_slide_index + 1
    self.slides.insert(new_index, new_slide)
    self.current_slide_index = new_index
    self.frames["SlideFrame"].update_display()

def add_field(self, field_type):
    """Adds a new entry box for a subject, action, or text."""
    self.frames["SlideFrame"].save_current_slide_data()
    
    current_slide = self.slides[self.current_slide_index]
    if field_type == "subjects":
        current_slide.subjects.append("")
    elif field_type == "actions":
        current_slide.actions.append("")
    elif field_type == "texts":
        current_slide.texts.append("")
        
    self.frames["SlideFrame"].update_display()
    
def illustrate_current_slide(self):
    """
    Placeholder for your Stable Diffusion model.
    Generates a prompt and creates a placeholder image.
    """
    self.frames["SlideFrame"].save_current_slide_data()
    current_slide = self.slides[self.current_slide_index]
    
    # --- THIS IS WHERE YOU INTEGRATE YOUR AI MODEL ---
    # 1. Combine the text fields to create your prompt
    prompt_parts = current_slide.subjects + current_slide.actions + current_slide.texts
    final_prompt = ", ".join(part for part in prompt_parts if part) # Join all non-empty parts
    
    print(f"--- Generating Image for Slide {self.current_slide_index + 1} ---")
    print(f"PROMPT: {final_prompt}")
    
    # 2. Call your Stable Diffusion function with the final_prompt
    # generated_image = your_stable_diffusion_function(final_prompt)
    # For now, we'll just create a placeholder image.
    
    # 3. Display the new image
    # For this example, we'll just update the placeholder with the prompt.
    new_image = self.frames["SlideFrame"].create_placeholder_image(400, 300, f"PROMPT:\n{final_prompt}")
    current_slide.image = new_image
    self.frames["SlideFrame"].update_display()
    print("--------------------------------------------------")


# Add the new methods to the controller class
StoryBookApp.navigate = navigate
StoryBookApp.add_new_slide = add_new_slide
StoryBookApp.add_field = add_field
StoryBookApp.illustrate_current_slide = illustrate_current_slide


# --- Run the Application ---
if __name__ == "__main__":
    app = StoryBookApp()
    app.mainloop()

