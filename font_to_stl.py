import os
import glob
import subprocess
from fontTools.ttLib import TTFont

# ================= CONFIGURATION =================

# Stamp Dimensions (in mm)
FONT_SIZE_MM = 5    # The visual size of the letter (EM square)
BASE_HEIGHT = 1.5     # The height of the handle/block (Z-axis base)
RELIEF_HEIGHT = 2   # How far the letter sticks out (Z-axis relief)

RIGHT_SAFETY = 0.5    # Extra space on the right (mirrored because of stamp) as a safety margin for misbehaving fonts
LEFT_SAFETY = 0.5    # Extra space on the left (mirrored because of stamp) as a safety margin for misbehaving fonts
TOP_SAFETY = 2      # Extra space on top as a safety margin for misbehaving fonts
                    # use this if your umlauts of e.g. Ä are invading your margin

# Margins for the Holder/Rails (Y-axis)
MARGIN_TOP = 2
MARGIN_BOTTOM = 2

# --- Handle / Rail Configuration ---
GENERATE_HANDLE = True
HANDLE_LENGTH = 80        # Length of the handle in mm
HANDLE_WALL = 2.0         # Thickness of the handle walls
HANDLE_LIP = 1            # How far the rail overlaps the stamp (must be < MARGINS!)
HANDLE_TOLERANCE = 0.3    # Extra gap for smooth sliding
HANDLE_BASE_THICKNESS = 3 # Thickness of the handle body behind the stamps

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

def generate_scad_string(char, family, style):
    family_safe = family.replace('"', '\\"').replace('-', '\\\\-')
    style_safe = style.replace('"', '\\"').replace('-', '\\\\-')

    scad_code = f"""
    $fn = 60;
    met = textmetrics(text="{char}", 
                     size={FONT_SIZE_MM}, 
                     font="{family_safe}:style={style_safe}", 
                     halign="center", 
                     valign="baseline");
    fnt = fontmetrics({FONT_SIZE_MM}, "{family_safe}:style={style_safe}");
    union() {{
        // Base Block
        translate([- (max(met.advance.x, met.size.x))/2 - {RIGHT_SAFETY}, (-(fnt.max.ascent-fnt.max.descent)/2)-{MARGIN_BOTTOM}, 0])
            cube([({RIGHT_SAFETY} + max(met.advance.x, met.size.x)) + {LEFT_SAFETY}, {MARGIN_BOTTOM} + (fnt.max.ascent-fnt.max.descent)+{TOP_SAFETY}+{MARGIN_TOP}, {BASE_HEIGHT}]);
            
        // Letter
        translate([0, fnt.max.descent, {BASE_HEIGHT}])
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

def generate_handle_scad(family, style):
    family_safe = family.replace('"', '\\"').replace('-', '\\\\-')
    style_safe = style.replace('"', '\\"').replace('-', '\\\\-')

    scad_code = f"""
    $fn = 60;
    fnt = fontmetrics({FONT_SIZE_MM}, "{family_safe}:style={style_safe}");
    stamp_h = (fnt.max.ascent - fnt.max.descent) + {TOP_SAFETY} + {MARGIN_BOTTOM} + {MARGIN_TOP};
    
    // Handle Parameters
    h_len = {HANDLE_LENGTH};
    tol = {HANDLE_TOLERANCE};
    wall = {HANDLE_WALL};
    lip = {HANDLE_LIP};
    lip_thick = 1;
    base_thick = {HANDLE_BASE_THICKNESS};
    stamp_base_z = {BASE_HEIGHT};
    slide_relief = base_thick/8;

    // Derived Dimensions
    slot_width_y = stamp_h + tol;
    slot_depth_z = stamp_base_z + tol;
    
    outer_width_y = slot_width_y + 2*wall;
    outer_height_z = slot_depth_z + base_thick + tol + lip_thick;

    difference() {{
        // 1. The Main Handle Body
        translate([0, 0, 0])
            cube([h_len + wall, outer_width_y, outer_height_z]);

        // 2. The Slot Channel (Horizontal Cut)
        translate([-1, wall, base_thick]) 
            cube([h_len - wall + 1, slot_width_y, slot_depth_z]);

        // 3. The Top Opening (Vertical Cut through the rails) + relief for easy sliding
        // We leave 'lip' material on the sides to hold the stamp
        translate([-1, wall + lip, base_thick - slide_relief])
            cube([h_len - wall + 1, slot_width_y - 2*lip, outer_height_z]);
    }}
    """
    return scad_code

def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

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

    print(f"Generating stamps...")

    for char in CHARS_TO_GENERATE:
        scad_content = generate_scad_string(char, family_name, style_name)
        
        safe_char_name = char
        if not safe_char_name.isalnum(): safe_char_name = f"symbol_{ord(char)}"
        
        stl_filename = os.path.join(OUTPUT_DIR, f"{safe_char_name}.stl")
        scad_filename = os.path.join(OUTPUT_DIR, "temp.scad") # set this to f"{safe_char_name}.scad" to view generated scad code
        
        with open(scad_filename, "w") as f:
            f.write(scad_content)

        print(f"  Rendering '{char}'")
        
        try:
            subprocess.run(
                [OPENSCAD_EXEC, "--enable", "textmetrics", "-o", stl_filename, scad_filename],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except subprocess.CalledProcessError:
            print(f"Error: OpenSCAD failed on '{char}'.")

    # --- Generate Handle ---
    if GENERATE_HANDLE:
        print(f"Generating Handle...")
        handle_scad = generate_handle_scad(family_name, style_name)
        handle_stl = os.path.join(OUTPUT_DIR, "handle.stl")
        handle_scad_file = os.path.join(OUTPUT_DIR, "handle_temp.scad")
        
        with open(handle_scad_file, "w") as f:
            f.write(handle_scad)
            
        try:
            subprocess.run(
                [OPENSCAD_EXEC, "--enable", "textmetrics", "-o", handle_stl, handle_scad_file],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            print("  Handle generated successfully.")
        except subprocess.CalledProcessError:
            print("  Error: OpenSCAD failed on handle.")
        
        if os.path.exists(handle_scad_file): os.remove(handle_scad_file)

    if os.path.exists(os.path.join(OUTPUT_DIR, "temp.scad")):
        os.remove(os.path.join(OUTPUT_DIR, "temp.scad"))

    print(f"\nSuccess! All stamps generated.")

if __name__ == "__main__":
    main()