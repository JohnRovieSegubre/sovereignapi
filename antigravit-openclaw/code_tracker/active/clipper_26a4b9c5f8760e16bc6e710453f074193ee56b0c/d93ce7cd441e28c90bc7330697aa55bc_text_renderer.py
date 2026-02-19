¥*from PIL import Image, ImageDraw, ImageFont, ImageColor
import textwrap
import os
import sys

class TextOverlayGenerator:
    def __init__(self, width: int = 1080, height: int = 1920):
        self.width = width
        self.height = height
        self.font = None
        self._load_font()

    def _load_font(self):
        """Try to load a nice looking BOLD font (TikTok Style)."""
        # Common bold fonts
        candidates = [
            "arialbd.ttf",       # Arial Bold
            "seguisb.ttf",       # Segoe UI SemiBold
            "segoeuib.ttf",      # Segoe UI Bold
            "calibrib.ttf",      # Calibri Bold
            "robotobold.ttf",
            "C:\\Windows\\Fonts\\arialbd.ttf",
            "C:\\Windows\\Fonts\\seguisb.ttf"
        ]
        
        # We start with a default size just to test loading
        for font_name in candidates:
            try:
                self.font_name = font_name
                ImageFont.truetype(font_name, 40)
                return
            except OSError:
                continue
        
        self.font_name = None # Fallback to default if needed (ugly)

    def generate(self, 
                 text: str, 
                 output_path: str, 
                 bg_color: str = "#333333", 
                 text_color: str = "white", 
                 font_size: int = 65, # Slightly larger
                 padding: int = 25,   # Tighter padding
                 max_width_ratio: float = 0.85):
        """
        Generates a transparent PNG with a rounded text box centered on screen.
        Mimics TikTok 'Classic' or 'Background' style.
        """
        # Create transparent base
        img = Image.new('RGBA', (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Load font with correct size
        try:
            font = ImageFont.truetype(self.font_name, font_size) if self.font_name else ImageFont.load_default()
        except:
            font = ImageFont.load_default()

        # Wrap text
        # Approx chars per line
        max_width_px = self.width * max_width_ratio
        # Heuristic: Bold fonts are wider
        avg_char_width = font_size * 0.55 
        chars_per_line = int(max_width_px / avg_char_width)
        
        wrapper = textwrap.TextWrapper(width=chars_per_line, break_long_words=False, replace_whitespace=False)
        lines = []
        for line in text.splitlines():
            lines.extend(wrapper.wrap(line))
        
        if not lines:
            lines = ["..."]

        # Calculate text dimensions
        line_heights = []
        line_widths = []
        
        # Stroke width for text measurement (important!)
        stroke_width = 4
        
        for line in lines:
            bbox = font.getbbox(line) # (left, top, right, bottom)
            w = bbox[2] - bbox[0] + (stroke_width * 2)
            h = bbox[3] - bbox[1]
            line_widths.append(w)
            # Add some leading (line spacing)
            line_heights.append(h + (font_size * 0.2)) 

        text_block_h = sum(line_heights)
        text_block_w = max(line_widths) if line_widths else 0
        
        # Box dimensions with strict padding
        box_w = text_block_w + (padding * 2)
        box_h = text_block_h + (padding * 2)
        
        # Center the box
        box_x = (self.width - box_w) // 2
        bg_y_offset = -150 # Move text up slightly from exact center for better visibility? 
                           # Or keep centered. Let's keep centered for now.
        box_y = (self.height - box_h) // 2 
        
        # Adjust hex color to include alpha if not present
        if bg_color.startswith('#'):
            rgb = ImageColor.getrgb(bg_color)
            # Add 85% opacity (approx 216) -> TikTok is usually solid if background is used.
            # But let's stick to slight transparency 216/255
            bg_rgba = (*rgb, 230) # More opaque for TikTok style
        else:
            bg_rgba = (50, 50, 50, 230)

        # Draw rounded rectangle (Chat Bubble)
        radius = 20 # Smaller radius for tighter look
        draw.rounded_rectangle(
            (box_x, box_y, box_x + box_w, box_y + box_h),
            radius=radius,
            fill=bg_rgba,
            outline=None
        )
        
        # Draw text
        current_y = box_y + padding
        for i, line in enumerate(lines):
            # Center text within the box
            line_w = line_widths[i]
            # Adjust X for centering based on pure text width (ignoring strict bbox stroke drift)
            # Simplified centering
            w_text = font.getlength(line)
            line_x = box_x + (box_w - w_text) // 2
            
            # Draw with Strong Outline (TikTok Style)
            # stroke_width should be ~3-5px for size 65
            draw.text(
                (line_x, current_y), 
                line, 
                font=font, 
                fill=text_color,
                stroke_width=stroke_width,
                stroke_fill="black"
            )
            
            current_y += line_heights[i]

        # Save
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        img.save(output_path, "PNG")
        return output_path
ò *cascade08òÍ(*cascade08Í(¥* *cascade08"(26a4b9c5f8760e16bc6e710453f074193ee56b0c2Pfile:///c:/Users/rovie%20segubre/clipper/src/clipper/processing/text_renderer.py:(file:///c:/Users/rovie%20segubre/clipper