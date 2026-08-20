import os
import shutil
from PIL import Image

def main():
    # Source generated image path
    source_png = r"C:\Users\Naqqash\.gemini\antigravity\brain\142b8083-6277-4e0e-847d-4d1ba71df08e\netvision_logo_1787156776483.png"
    
    # Destination directories
    assets_dir = r"c:\Users\Naqqash\Downloads\Projects\NetworkProject\desktop\assets"
    os.makedirs(assets_dir, exist_ok=True)
    
    dest_png = os.path.join(assets_dir, "netvision_logo.png")
    dest_ico = os.path.join(assets_dir, "netvision.ico")
    root_ico = r"c:\Users\Naqqash\Downloads\Projects\NetworkProject\desktop\netvision.ico"
    
    print(f"Copying source PNG to {dest_png}...")
    shutil.copy2(source_png, dest_png)
    
    print("Generating multi-resolution ICO file...")
    img = Image.open(dest_png)
    
    # Standard Windows icon sizes
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    
    # Save as ICO with all resolutions
    img.save(dest_ico, format="ICO", sizes=sizes)
    print(f"ICO saved to {dest_ico}")
    
    # Also copy to desktop\netvision.ico for easy root reference if needed
    shutil.copy2(dest_ico, root_ico)
    print(f"ICO copied to {root_ico}")
    
    print("Icon creation completed successfully!")

if __name__ == "__main__":
    main()
