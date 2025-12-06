"""
image_processor.py - Robust image processing with better font handling
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from typing import Tuple, Optional, Union, List
import os
import logging
from pathlib import Path
import sys

logger = logging.getLogger(__name__)

class ImageProcessor:
    """Handles image processing and text overlay operations"""
    
    def __init__(self, output_dir: Union[str, Path] = "generated_images"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Font handling - use system fonts with fallback
        self.font_cache = {}
        self.default_font_size = 24
        self._init_fonts()
        
        # Default text style (configurable via params in methods)
        self.text_color = (255, 255, 255)  # White
        self.outline_color = (0, 0, 0)     # Black
        self.background_color = (0, 0, 0, 180)  # Semi-transparent black
    
    def _init_fonts(self):
        """Initialize fonts with comprehensive fallback chain"""
        self.font_paths = []
        
        # Windows fonts
        if sys.platform == 'win32':
            font_dirs = [
                "C:/Windows/Fonts",
                os.path.expanduser("~/AppData/Local/Microsoft/Windows/Fonts")
            ]
            for font_dir in font_dirs:
                if os.path.exists(font_dir):
                    for file in os.listdir(font_dir):
                        if file.lower().endswith(('.ttf', '.otf')):
                            self.font_paths.append(os.path.join(font_dir, file))
        
        # Linux fonts
        elif sys.platform.startswith('linux'):
            font_dirs = [
                "/usr/share/fonts/truetype",
                "/usr/share/fonts/opentype",
                "/usr/local/share/fonts",
                os.path.expanduser("~/.fonts")
            ]
            for font_dir in font_dirs:
                if os.path.exists(font_dir):
                    for root, dirs, files in os.walk(font_dir):
                        for file in files:
                            if file.lower().endswith(('.ttf', '.otf')):
                                self.font_paths.append(os.path.join(root, file))
        
        # macOS fonts
        elif sys.platform == 'darwin':
            font_dirs = [
                "/System/Library/Fonts",
                "/Library/Fonts",
                os.path.expanduser("~/Library/Fonts")
            ]
            for font_dir in font_dirs:
                if os.path.exists(font_dir):
                    for file in os.listdir(font_dir):
                        if file.lower().endswith(('.ttf', '.otf', '.ttc')):
                            self.font_paths.append(os.path.join(font_dir, file))
        
        # Add some common specific fonts
        common_fonts = [
            "arial.ttf", "arialbd.ttf", "times.ttf", "verdana.ttf",
            "tahoma.ttf", "georgia.ttf", "cour.ttf", "comic.ttf"
        ]
        
        # Try to load a default font
        self.default_font = self._load_default_font()
        
        if not self.default_font:
            logger.warning("No suitable font found, using PIL default")
            try:
                self.default_font = ImageFont.load_default()
            except:
                self.default_font = None
    
    def _load_default_font(self, size: int = None) -> Optional[ImageFont.FreeTypeFont]:
        """Load a default font from available system fonts"""
        if size is None:
            size = self.default_font_size
            
        # Try common readable fonts first (expanded list for better fallback)
        preferred_fonts = [
            "arial.ttf", "verdana.ttf", "tahoma.ttf", 
            "georgia.ttf", "times.ttf", "dejavusans.ttf",
            "liberationsans-regular.ttf", "calibri.ttf"
        ]
        
        # Check preferred fonts
        for font_name in preferred_fonts:
            for font_path in self.font_paths:
                if font_name.lower() in font_path.lower():
                    try:
                        return ImageFont.truetype(font_path, size)
                    except Exception as e:
                        logger.warning(f"Failed to load font {font_path}: {e}")
                        continue
        
        # Try any available font
        for font_path in self.font_paths[:20]:  # Try first 20
            try:
                return ImageFont.truetype(font_path, size)
            except Exception as e:
                logger.warning(f"Failed to load font {font_path}: {e}")
                continue
        
        return None
    
    def get_font(self, size: int = None) -> Optional[ImageFont.FreeTypeFont]:
        """Get a font of specified size, using cache"""
        if size is None:
            size = self.default_font_size
            
        # Check cache
        if size in self.font_cache:
            return self.font_cache[size]
        
        # Try to load font
        font = self._load_default_font(size)
        if font:
            self.font_cache[size] = font
        else:
            # Last resort: default font
            try:
                font = ImageFont.load_default()
                self.font_cache[size] = font
            except Exception as e:
                logger.error(f"Failed to load any font: {e}")
                font = None
        
        return font
    
    def overlay_text(self, 
                    base_image_path: str, 
                    text: str,
                    position: str = "bottom",
                    margin: int = 20,
                    max_width_ratio: float = 0.8,
                    font_size: int = None,
                    text_color: Tuple[int, int, int] = None,
                    outline_color: Tuple[int, int, int] = None,
                    background_color: Tuple[int, int, int, int] = None,
                    slide_index: int = 0) -> Path:
        """
        Overlay text on base image and save as new file (for publish only).
        Returns path to overlaid image; logs errors.
        """
        if not text or not text.strip():
            logger.info("No text to overlay; returning base path")
            return Path(base_image_path)
        
        try:
            image = Image.open(base_image_path)
        except Exception as e:
            logger.error(f"Failed to open base image {base_image_path}: {e}")
            raise
        
        # Use params or defaults
        if font_size is None:
            font_size = self.default_font_size
        if text_color is None:
            text_color = self.text_color
        if outline_color is None:
            outline_color = self.outline_color
        if background_color is None:
            background_color = self.background_color
        
        # Get font
        font = self.get_font(font_size)
        if not font:
            logger.error("No font available; skipping overlay")
            return Path(base_image_path)
        
        # Create working copy
        result = image.copy()
        draw = ImageDraw.Draw(result, 'RGBA')
        
        # Calculate text dimensions
        img_width, img_height = result.size
        actual_max_width = int(img_width * max_width_ratio)
        
        # Wrap text
        lines = self._wrap_text(draw, text, font, actual_max_width)
        
        # Calculate total text height
        line_height = draw.textbbox((0, 0), "Ay", font=font)[3]  # Approximate line height
        total_height = len(lines) * line_height + (len(lines) - 1) * 5  # With spacing
        bg_height = total_height + 2 * margin
        
        # Determine position
        if position == "bottom":
            bg_y = img_height - bg_height
        elif position == "top":
            bg_y = 0
        else:
            bg_y = (img_height - bg_height) // 2  # Center fallback
        
        # Draw semi-transparent background
        draw.rectangle(
            (0, bg_y, img_width, bg_y + bg_height),
            fill=background_color
        )
        
        # Draw text with outline
        x = margin
        y = bg_y + margin
        for line in lines:
            # Outline
            for dx, dy in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
                draw.text((x + dx, y + dy), line, font=font, fill=outline_color)
            # Main text
            draw.text((x, y), line, font=font, fill=text_color)
            y += line_height + 5
        
        # Save overlaid version
        if 'slide_index' not in locals():
            slide_index = 0
        overlaid_path = self.save_image(result, slide_index=slide_index, prefix="overlaid")
        logger.info(f"Overlaid image saved: {overlaid_path}")
        return overlaid_path
    
    def _wrap_text(self, draw: ImageDraw.Draw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> List[str]:
        """Wrap text to fit within max_width, handling long words"""
        words = text.split()
        lines = []
        current_line = []
        
        for word in words:
            test_line = ' '.join(current_line + [word]) if current_line else word
            bbox = draw.textbbox((0, 0), test_line, font=font)
            line_width = bbox[2] - bbox[0]
            
            if line_width <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                
                # Handle single word too long
                if draw.textbbox((0, 0), word, font=font)[2] > max_width:
                    # Hyphenate or truncate long word
                    broken_word = []
                    current_chars = []
                    for char in word:
                        current_chars.append(char)
                        test = ''.join(current_chars)
                        if draw.textbbox((0, 0), test, font=font)[2] > max_width:
                            lines.append(''.join(broken_word) + '-')
                            broken_word = [char]
                            current_chars = [char]
                        else:
                            broken_word.append(char)
                    if broken_word:
                        lines.append(''.join(broken_word))
                else:
                    current_line = [word]
        
        if current_line:
            lines.append(' '.join(current_line))
        
        return lines
    
    def resize_for_display(self, 
                          image_path: str, 
                          target_size: Tuple[int, int] = (420, 300)) -> Image.Image:
        """Resize image for display while maintaining aspect ratio (raw or overlaid)"""
        try:
            image = Image.open(image_path)
        except Exception as e:
            logger.error(f"Failed to open image for resize: {image_path}: {e}")
            raise
        
        img_width, img_height = image.size
        target_width, target_height = target_size
        
        # If smaller, pad
        if img_width < target_width or img_height < target_height:
            result = Image.new('RGB', target_size, (240, 240, 240))
            paste_x = (target_width - img_width) // 2
            paste_y = (target_height - img_height) // 2
            result.paste(image, (paste_x, paste_y))
            return result
        
        # Calculate ratios
        img_ratio = img_width / img_height
        target_ratio = target_width / target_height
        
        if img_ratio > target_ratio:
            new_width = target_width
            new_height = int(target_width / img_ratio)
        else:
            new_height = target_height
            new_width = int(target_height * img_ratio)
        
        # Resize
        resized = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Pad to target
        result = Image.new('RGB', target_size, (240, 240, 240))
        paste_x = (target_width - new_width) // 2
        paste_y = (target_height - new_height) // 2
        result.paste(resized, (paste_x, paste_y))
        
        return result
    
    def save_base_image(self, image: Image.Image, slide_index: int) -> Path:
        """Save raw generated image (post-Forge, pre-overlay)"""
        return self.save_image(image, slide_index, prefix="base_slide")
    
    def save_image(self, 
                  image: Image.Image, 
                  slide_index: int,
                  prefix: str = "slide") -> Path:
        """Save image with organized naming; distinguish base/overlaid"""
        import time
        timestamp = int(time.time())
        filename = f"{prefix}_{slide_index:03d}_{timestamp}.png"
        filepath = self.output_dir / filename
        
        try:
            image.save(
                filepath,
                format='PNG',
                optimize=True,
                quality=95
            )
            logger.info(f"Image saved: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Failed to save image {filename}: {e}")
            raise
    
    def apply_enhancements(self, image: Image.Image) -> Image.Image:
        """Apply subtle enhancements to generated images"""
        try:
            result = image.copy()
            
            # Slight sharpening
            result = result.filter(ImageFilter.UnsharpMask(radius=1, percent=50, threshold=0))
            
            # Slight contrast
            enhancer = ImageEnhance.Contrast(result)
            result = enhancer.enhance(1.05)
            
            # Slight saturation
            enhancer = ImageEnhance.Color(result)
            result = enhancer.enhance(1.02)
            
            return result
        except Exception as e:
            logger.error(f"Error applying enhancements: {e}")
            return image  # Return original on failure

# Singleton instance with thread safety
import threading
_image_processor = None
_image_processor_lock = threading.Lock()

def get_image_processor() -> ImageProcessor:
    """Get or create ImageProcessor singleton with thread safety"""
    global _image_processor
    if _image_processor is None:
        with _image_processor_lock:
            if _image_processor is None:  # Double-check locking
                _image_processor = ImageProcessor()
    return _image_processor