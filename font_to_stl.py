import os
import glob
import subprocess
from PIL import ImageFont
from fontTools.ttLib import TTFont

# ================= CONFIGURATION =================

# Stamp Dimensions (in mm)
FONT_SIZE_MM = 5     # The visual size of the letter (EM square)
BASE_HEIGHT = 2       # The height of the handle/block (Z-axis base)
RELIEF_HEIGHT = 2     # How far the letter sticks out (Z-axis relief)
SIDE_PADDING = 1      # Extra space on left/right of the letter

# Margins for the Holder/Rails (Y-axis)
MARGIN_TOP = 0
MARGIN_BOTTOM = 0

# Initial Block Depth. Script will increase this if needed.
MIN_BLOCK_DEPTH = 5  

OUTPUT_DIR = "stl_output"
CHARS_TO_GENERATE = "AÄBCDEFGHIJKLMNOÖPQRSTUÜVWXYZaäbcdefghijklmnoöpqrsßtuüvwxyz0123456789.:,;!?&/-"

OPENSCAD_EXEC = "openscad"

# =================================================

def get_font_info(font_path):
    """ Extracts internal Family and Style for OpenSCAD. """
    font = TTFont(font_path)
    family = ""
    style = ""
    for record in font['name'].names:
        if record.platformID == 3 and record.platEncID == 1 and record.langID == 0x409:
            if record.nameID == 1: family = record.toUnicode()
            elif record.nameID == 2: style = record.toUnicode()
    
    if not family:
        for record in font['name'].names:
            if record.nameID == 1: family = record.toUnicode(); break
    if not style:
         for record in font['name'].names:
            if record.nameID == 2: style = record.toUnicode(); break
                
    return family, style

def get_font_design_metrics(font_path):
    """
    Instead of scanning pixels (which can miss accents), we ask the font
    for its designated 'Ascent' and 'Descent'. This covers the tallest 
    possible character in the font.
    """
    dummy_size = 100
    try:
        font = ImageFont.truetype(font_path, dummy_size)
    except OSError:
        print(f"Error: PIL could not load font file: {font_path}")
        return 0, 0

    # getmetrics returns (ascent, descent) in pixels for the entire font
    # ascent is distance from baseline to top-most ink
    # descent is distance from baseline to bottom-most ink
    ascent_px, descent_px = font.getmetrics()
    
    # Calculate scale factor
    scale_factor = FONT_SIZE_MM / dummy_size
    
    # We add a small safety buffer (10%) because OpenSCAD and PIL 
    # handle rounding slightly differently.
    safety_buffer = 1.10
    
    abs_ascent_mm = (ascent_px * scale_factor) * safety_buffer
    abs_descent_mm = (descent_px * scale_factor) * safety_buffer
    
    return abs_ascent_mm, abs_descent_mm

def get_char_width_mm(char, font_path):
    """ Returns the physical width of a character in mm. """
    dummy_size = 100
    font = ImageFont.truetype(font_path, dummy_size)
    length = font.getlength(char)
    return (length / dummy_size) * FONT_SIZE_MM

def generate_scad_string(char, block_width, block_depth, baseline_y_pos, family, style):
    family_safe = family.replace('"', '\\"').replace('-', '\\\\-')
    style_safe = style.replace('"', '\\"').replace('-', '\\\\-')

    scad_code = f"""
    $fn = 60;
    union() {{
        // Base Block
        translate([- {block_width}/2, -{block_depth}/2, 0])
            cube([{block_width}, {block_depth}, {BASE_HEIGHT}]);
            
        // Letter
        // baseline_y_pos is where the baseline sits relative to the CENTER (0,0)
        translate([0, {baseline_y_pos}, {BASE_HEIGHT}])
            mirror([1, 0, 0]) 
            linear_extrude({RELIEF_HEIGHT})
                text("{char}", 
                     size={FONT_SIZE_MM}, 
                     font="{family_safe}:style={style_safe}", 
                     halign="center", 
                     valign="baseline");
    }}
    """
    return scad_code

def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    # 1. Font Setup
    font_files = glob.glob("*.ttf") + glob.glob("*.otf")
    if not font_files:
        print("Error: No .ttf or .otf files found.")
        return
    font_path = font_files[0]
    
    try:
        family_name, style_name = get_font_info(font_path)
        print(f"Using Font: '{family_name}' Style: '{style_name}'")
    except Exception as e:
        print(f"Error reading font metadata: {e}")
        return

    # 2. METRIC CALCULATION
    # We use the font's Global Design Metrics now.
    # This guarantees the block is tall enough for ANY character in the set.
    design_ascent, design_descent = get_font_design_metrics(font_path)
    
    print(f"Font Metrics (Design): Ascent={design_ascent:.2f}mm, Descent={design_descent:.2f}mm")

    # Height needed for the text itself
    text_height_needed = design_ascent + design_descent
    
    # Total Block Height needed (Text + Top Margin + Bottom Margin)
    total_depth_needed = text_height_needed + MARGIN_TOP + MARGIN_BOTTOM
    
    # Set final depth
    final_block_depth = max(MIN_BLOCK_DEPTH, total_depth_needed)
    
    print(f"Block Height calculated: {final_block_depth:.2f}mm")

    # 3. Calculate Baseline Position
    # OpenSCAD Y=0 is the center of the block.
    # The TOP edge of the block is at Y = final_block_depth / 2
    # We want the highest point of the font (Ascent) to be 'MARGIN_TOP' away from the edge.
    # So: Baseline_Y + Ascent = Top_Edge - Margin_Top
    # Baseline_Y = (Top_Edge - Margin_Top) - Ascent
    
    block_top_edge = final_block_depth / 2
    baseline_y_pos = (block_top_edge - MARGIN_TOP) - design_ascent

    print(f"Baseline Offset: {baseline_y_pos:.2f}mm (from center)")
    print(f"Generating stamps...")

    for char in CHARS_TO_GENERATE:
        # Width calculation is still per-character to keep blocks compact horizontally
        char_width = get_char_width_mm(char, font_path)
        block_width = max(char_width + (SIDE_PADDING * 2), 5.0)

        scad_content = generate_scad_string(char, block_width, final_block_depth, baseline_y_pos, family_name, style_name)
        
        safe_char_name = "dot" if char == "." else "colon" if char == ":" else char
        if not safe_char_name.isalnum(): safe_char_name = f"symbol_{ord(char)}"
        
        stl_filename = os.path.join(OUTPUT_DIR, f"{safe_char_name}.stl")
        scad_filename = os.path.join(OUTPUT_DIR, "temp.scad")
        
        with open(scad_filename, "w") as f:
            f.write(scad_content)

        print(f"  Rendering '{char}'")
        
        try:
            subprocess.run(
                [OPENSCAD_EXEC, "-o", stl_filename, scad_filename],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except subprocess.CalledProcessError:
            print(f"Error: OpenSCAD failed on '{char}'.")

    if os.path.exists(os.path.join(OUTPUT_DIR, "temp.scad")):
        os.remove(os.path.join(OUTPUT_DIR, "temp.scad"))

    print(f"\nSuccess! All stamps generated.")

if __name__ == "__main__":
    main()