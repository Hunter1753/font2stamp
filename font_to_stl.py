import os
import glob
import subprocess
from PIL import ImageFont
from fontTools.ttLib import TTFont

# ================= CONFIGURATION =================

# Stamp Dimensions (in mm)
FONT_SIZE_MM = 5     # The visual size of the letter
BASE_DEPTH = 2      # The height of the handle/block (Z-axis base)
RELIEF_DEPTH = 2    # How far the letter sticks out (Z-axis relief)
SIDE_PADDING = 1     # Extra space on left/right of the letter

# Margins for the Holder/Rails (Y-axis)
# These create empty space at top and bottom for sliding into a rail
MARGIN_TOP = 1.5
MARGIN_BOTTOM = 1.5

# Initial Block height (Y-axis). 
# The script will INCREASE this automatically if the letters + margins don't fit.
MIN_BLOCK_HEIGHT = 5

OUTPUT_DIR = "stl_output"
CHARS_TO_GENERATE = "AÄBCDEFGHIJKLMNOÖPQRSTUÜVWXYZaäbcdefghijklmnoöpqrsßtuüvwxyz0123456789.:,;!?&/-"

# OpenSCAD Path
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

def get_vertical_metrics(chars, font_path):
    """
    Scans ALL characters to find the maximum Ascent (height above baseline)
    and Descent (depth below baseline). 
    Returns: (max_ascent_mm, max_descent_mm)
    """
    dummy_size = 100
    try:
        font = ImageFont.truetype(font_path, dummy_size)
    except OSError:
        print(f"Error: PIL could not load font file: {font_path}")
        return 0, 0

    max_asc_px = 0
    max_desc_px = 0

    for char in chars:
        # anchor='ls' means Left, Baseline. 
        # bbox returns (left, top, right, bottom) relative to baseline.
        # Top is usually negative (up), Bottom is positive (down).
        try:
            bbox = font.getbbox(char, anchor='ls')
        except ValueError:
            # Fallback for older Pillow versions
            bbox = font.getbbox(char)
        
        # Calculate height above baseline (negative Y in bbox means up)
        ascent = -bbox[1]
        descent = bbox[3]

        if ascent > max_asc_px: max_asc_px = ascent
        if descent > max_desc_px: max_desc_px = descent

    # Convert pixels to MM ratio
    scale_factor = FONT_SIZE_MM / dummy_size
    return max_asc_px * scale_factor, max_desc_px * scale_factor

def get_char_width_mm(char, font_path):
    """ Returns the physical width of a character in mm. """
    dummy_size = 100
    font = ImageFont.truetype(font_path, dummy_size)
    length = font.getlength(char) # More accurate than bbox for width spacing
    return (length / dummy_size) * FONT_SIZE_MM

def generate_scad_string(char, block_width, block_depth, y_offset, family, style):
    """
    Generates OpenSCAD code.
    y_offset: The Y position of the baseline relative to the center of the block.
    """
    family_safe = family.replace('"', '\\"').replace('-', '\\\\-')
    style_safe = style.replace('"', '\\"').replace('-', '\\\\-')

    scad_code = f"""
    $fn = 60;
    union() {{
        // The Base Block
        translate([- {block_width}/2, -{block_depth}/2, 0])
            cube([{block_width}, {block_depth}, {BASE_DEPTH}]);
            
        // The Letter
        // We translate the baseline to the calculated y_offset
        translate([0, {y_offset}, {BASE_DEPTH}])
            mirror([1, 0, 0]) // Stamps must be mirrored
            linear_extrude({RELIEF_DEPTH})
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

    # 2. PRE-CALCULATION: Determine Metrics for the Holder
    print("Analyzing font metrics to fit umlauts and margins...")
    max_ascent, max_descent = get_vertical_metrics(CHARS_TO_GENERATE, font_path)
    
    print(f"  Max Ascent (e.g. Ä): {max_ascent:.2f}mm")
    print(f"  Max Descent (e.g. g): {max_descent:.2f}mm")

    # Calculate required height for text only
    text_height_needed = max_ascent + max_descent
    
    # Calculate total block heihgt needed
    total_height_needed = text_height_needed + MARGIN_TOP + MARGIN_BOTTOM
    
    # Determine final Block Height (use MIN unless we need more)
    final_block_height = max(MIN_BLOCK_HEIGHT, total_height_needed)
    
    print(f"  Block Height set to: {final_block_height:.2f}mm (Margins: {MARGIN_TOP}mm top, {MARGIN_BOTTOM}mm bottom)")

    # 3. Calculate Baseline Position
    # We want the text to sit in the 'printable area' between margins.
    # To align 'A' and 'g' correctly, the baseline must be fixed relative to the block.
    # OpenSCAD Y=0 is the center of the block.
    # Top of block = final_block_depth / 2
    # Top of Tallest Letter = Top of block - MARGIN_TOP
    # Baseline Position = (Top of Tallest Letter) - Max_Ascent
    
    baseline_y_pos = (final_block_height / 2) - MARGIN_TOP - max_ascent

    print(f"Generating stamps...")

    for char in CHARS_TO_GENERATE:
        # Calculate width specific to this char
        char_width = get_char_width_mm(char, font_path)
        block_width = max(char_width + (SIDE_PADDING * 2), 5.0)

        scad_content = generate_scad_string(char, block_width, final_block_height, baseline_y_pos, family_name, style_name)
        
        # Clean filename
        safe_char_name = "dot" if char == "." else "colon" if char == ":" else char
        if not safe_char_name.isalnum(): safe_char_name = f"symbol_{ord(char)}"
        
        stl_filename = os.path.join(OUTPUT_DIR, f"{safe_char_name}.stl")
        scad_filename = os.path.join(OUTPUT_DIR, "temp.scad")
        
        with open(scad_filename, "w") as f:
            f.write(scad_content)

        print(f"  Rendering '{char}' -> Width: {block_width:.1f}mm")
        
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

    print(f"\nSuccess! All stamps generated with height {final_block_height:.2f}mm.")

if __name__ == "__main__":
    main()