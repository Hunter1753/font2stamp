import os
import glob
import subprocess
from PIL import ImageFont
from fontTools.ttLib import TTFont

# ================= CONFIGURATION =================

# Stamp Dimensions (in mm)
FONT_SIZE_MM = 20     
BASE_HEIGHT = 20      
RELIEF_HEIGHT = 2     
BLOCK_DEPTH = 25      
SIDE_PADDING = 2      

OUTPUT_DIR = "stl_output"
CHARS_TO_GENERATE = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,!?"

# OpenSCAD Path (default "openscad" assumes it's in PATH)
OPENSCAD_EXEC = "openscad" 

# =================================================

def get_font_info(font_path):
    """
    Extracts the internal Family Name and Style from the font file.
    OpenSCAD needs the internal name (e.g. "Arial"), not the filename.
    """
    font = TTFont(font_path)
    family = ""
    style = ""

    # Iterate through the naming table
    # Name ID 1 = Font Family
    # Name ID 2 = Font Subfamily (Style)
    for record in font['name'].names:
        if record.platformID == 3 and record.platEncID == 1 and record.langID == 0x409:
            if record.nameID == 1:
                family = record.toUnicode()
            elif record.nameID == 2:
                style = record.toUnicode()
    
    # Fallback if US English not found, try any record
    if not family:
        for record in font['name'].names:
            if record.nameID == 1:
                family = record.toUnicode()
                break
    if not style:
         for record in font['name'].names:
            if record.nameID == 2:
                style = record.toUnicode()
                break
                
    return family, style

def get_char_width_ratio(char, font_path):
    """
    Uses PIL to measure width. We pass the FILE PATH directly to PIL
    to ensure we measure the exact file we are using.
    """
    dummy_font_size = 100
    try:
        font = ImageFont.truetype(font_path, dummy_font_size)
    except OSError:
        print(f"Error: PIL could not load font file: {font_path}")
        return 0.5

    bbox = font.getbbox(char) 
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    
    if height == 0: return 0.5
    return width / dummy_font_size

def generate_scad_string(char, block_width, family, style):
    """
    Generates OpenSCAD code using the detected family and style.
    """
    baseline_offset = -FONT_SIZE_MM * 0.3
    
    # Escape quote marks in case font name has them
    family_safe = family.replace('"', '\\"')
    style_safe = style.replace('"', '\\"')

    scad_code = f"""
    $fn = 60;
    union() {{
        translate([- {block_width}/2, -{BLOCK_DEPTH}/2, 0])
            cube([{block_width}, {BLOCK_DEPTH}, {BASE_HEIGHT}]);
            
        translate([0, {baseline_offset}, {BASE_HEIGHT}])
            mirror([1, 0, 0])
            linear_extrude({RELIEF_HEIGHT})
                text("{char}", 
                     size={FONT_SIZE_MM}, 
                     font="{family_safe}:{style_safe}", 
                     halign="center", 
                     valign="baseline");
    }}
    """
    return scad_code

def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    # 1. Auto-detect Font File
    font_files = glob.glob("*.ttf") + glob.glob("*.otf")
    if not font_files:
        print("Error: No .ttf or .otf files found in the current directory.")
        return
    
    font_path = font_files[0] # Use the first one found
    print(f"Found font file: {font_path}")

    # 2. Extract Internal Name
    try:
        family_name, style_name = get_font_info(font_path)
        print(f"Detected internal font name: '{family_name}' Style: '{style_name}'")
    except Exception as e:
        print(f"Error reading font metadata: {e}")
        return

    print(f"Generating stamps...")

    for char in CHARS_TO_GENERATE:
        # Calculate width using the file path (accurate)
        ratio = get_char_width_ratio(char, font_path)
        char_phys_width = FONT_SIZE_MM * ratio
        block_width = max(char_phys_width + (SIDE_PADDING * 2), 5.0)

        # Write SCAD using the internal name (required for OpenSCAD to find the installed font)
        scad_content = generate_scad_string(char, block_width, family_name, style_name)
        scad_filename = os.path.join(OUTPUT_DIR, "temp.scad")
        
        with open(scad_filename, "w") as f:
            f.write(scad_content)

        # Handle file naming
        safe_char_name = char if char.isalnum() else f"symbol_{ord(char)}"
        stl_filename = os.path.join(OUTPUT_DIR, f"{safe_char_name}.stl")

        print(f"Rendering '{char}' -> {stl_filename}")
        
        try:
            subprocess.run(
                [OPENSCAD_EXEC, "-o", stl_filename, scad_filename],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except subprocess.CalledProcessError:
            print(f"Error: OpenSCAD failed on '{char}'.")

    # Cleanup
    if os.path.exists(os.path.join(OUTPUT_DIR, "temp.scad")):
        os.remove(os.path.join(OUTPUT_DIR, "temp.scad"))

    print(f"\nSuccess! STLs are in '{OUTPUT_DIR}'")

if __name__ == "__main__":
    main()