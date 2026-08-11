#!/usr/bin/env python

from PIL import Image

def process_app_assets(
    source_path="assets/src_icon.png",
    icon_out="assets/custom_icon.png",
    bg_color=(127, 127, 127) # White background (R, G, B)
):
    # Load source artwork and convert to RGBA
    img = Image.open(source_path).convert("RGBA")
    
    # 2. Generate Opaque App Icon for TestFlight (1024x1024 RGB)
    # Create a solid canvas with no alpha channel
    background = Image.new("RGB", (1920, 1920), bg_color)
    
    # Resize artwork
    resized_art = img.resize((1920, 1920), Image.Resampling.LANCZOS)
    
    # Composite artwork onto background using the artwork's alpha channel as a mask
    background.paste(resized_art, (0, 0), mask=resized_art.split()[3])
    
    # Save as non-transparent PNG
    background.save(icon_out, format="PNG")
    print(f" Saved opaque 1920x1920 app icon to {icon_out}")

if __name__ == "__main__":
    process_app_assets()

