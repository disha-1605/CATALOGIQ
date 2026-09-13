"""Generate realistic, photographic e-commerce catalog image variations for CatalogIQ."""

import os
import glob
import numpy as np
import pandas as pd
from PIL import Image, ImageEnhance, ImageOps, ImageFilter

ARTIFACTS_DIR = "/Users/disha/.gemini/antigravity-ide/brain/8200b367-a5af-46ff-9b59-422a4a3048b9"
OUTPUT_BASE = "frontend/assets/products"

# Master source photo mappings
SOURCE_PHOTOS = {
    "cargo-pants": glob.glob(f"{ARTIFACTS_DIR}/cargo_pants_black_*.jpg")[0],
    "dress": glob.glob(f"{ARTIFACTS_DIR}/dress_white_relaxed_*.jpg")[0],
    "handbag": glob.glob(f"{ARTIFACTS_DIR}/handbag_black_leather_*.jpg")[0],
    "jacket": glob.glob(f"{ARTIFACTS_DIR}/jacket_black_studio_*.jpg")[0],
    "jeans": glob.glob(f"{ARTIFACTS_DIR}/jeans_grey_straight_*.jpg")[0],
    "kurta": glob.glob(f"{ARTIFACTS_DIR}/kurta_beige_studio_*.jpg")[0],
    "kurta_black": glob.glob(f"{ARTIFACTS_DIR}/mens_kurta_product_*.jpg")[0],
    "running-shoes": glob.glob(f"{ARTIFACTS_DIR}/running_shoes_blue_*.jpg")[0],
    "shirt": glob.glob(f"{ARTIFACTS_DIR}/shirt_black_slim_*.jpg")[0],
    "sneakers": glob.glob(f"{ARTIFACTS_DIR}/sneakers_navy_studio_*.jpg")[0],
    "trousers": glob.glob(f"{ARTIFACTS_DIR}/trousers_olive_relaxed_*.jpg")[0],
    "t-shirt": glob.glob(f"{ARTIFACTS_DIR}/folded_tshirt_hero_*.jpg")[0],
}


def apply_color_grade(img: Image.Image, color_theme: str, brightness: float = 1.0, contrast: float = 1.0) -> Image.Image:
    """Apply realistic photographic color grading to a studio garment image."""
    img = img.convert("RGB")
    
    # Separate into luminance / lightness
    np_img = np.array(img, dtype=np.float32) / 255.0
    r, g, b = np_img[:, :, 0], np_img[:, :, 1], np_img[:, :, 2]
    
    # Compute luminance
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    
    # Background mask: areas where luminance is very high (> 0.92) and saturation is low
    sat = np.max(np_img, axis=2) - np.min(np_img, axis=2)
    bg_mask = (lum > 0.90) & (sat < 0.12)
    # Smooth background mask
    mask_img = Image.fromarray((bg_mask * 255).astype(np.uint8))
    mask_img = mask_img.filter(ImageFilter.GaussianBlur(radius=2))
    smooth_bg_mask = np.array(mask_img, dtype=np.float32) / 255.0
    
    # Garment mask
    garment_mask = 1.0 - smooth_bg_mask
    garment_mask = np.clip(garment_mask[:, :, np.newaxis], 0.0, 1.0)

    # Color tone curves
    color_map = {
        "black": (0.22, 0.22, 0.24),
        "white": (0.95, 0.95, 0.96),
        "blue": (0.28, 0.48, 0.72),
        "navy": (0.16, 0.24, 0.40),
        "beige": (0.78, 0.72, 0.62),
        "olive": (0.42, 0.48, 0.32),
        "grey": (0.50, 0.50, 0.52),
        "red": (0.76, 0.22, 0.24),
        "pink": (0.84, 0.60, 0.68),
        "green": (0.26, 0.55, 0.38),
        "brown": (0.48, 0.34, 0.24),
        "yellow": (0.88, 0.76, 0.30),
    }

    tint_r, tint_g, tint_b = color_map.get(color_theme, (0.5, 0.5, 0.5))
    
    if color_theme == "black":
        # Darken garment while preserving shadow detail
        graded_r = np.clip(lum * 0.45 + (r - lum) * 0.2, 0, 1)
        graded_g = np.clip(lum * 0.45 + (g - lum) * 0.2, 0, 1)
        graded_b = np.clip(lum * 0.48 + (b - lum) * 0.2, 0, 1)
    elif color_theme == "white":
        # Brighten garment while preserving texture
        graded_r = np.clip(lum * 0.70 + 0.28, 0, 1)
        graded_g = np.clip(lum * 0.70 + 0.28, 0, 1)
        graded_b = np.clip(lum * 0.70 + 0.29, 0, 1)
    elif color_theme == "original":
        graded_r, graded_g, graded_b = r, g, b
    else:
        # Tint garment with target hue proportional to luminance
        graded_r = np.clip(lum * tint_r * 1.5 + (r - lum) * 0.1, 0, 1)
        graded_g = np.clip(lum * tint_g * 1.5 + (g - lum) * 0.1, 0, 1)
        graded_b = np.clip(lum * tint_b * 1.5 + (b - lum) * 0.1, 0, 1)

    graded_stack = np.stack([graded_r, graded_g, graded_b], axis=2)
    
    # Composite: keep clean off-white background (#FAFAFA / #F8F6F4), blend graded garment
    clean_bg = np.array(img, dtype=np.float32) / 255.0
    final_np = clean_bg * (1.0 - garment_mask) + graded_stack * garment_mask
    final_np = np.clip(final_np * 255.0, 0, 255).astype(np.uint8)
    
    result = Image.fromarray(final_np)
    
    # Fine-tune brightness and contrast
    if brightness != 1.0:
        result = ImageEnhance.Brightness(result).enhance(brightness)
    if contrast != 1.0:
        result = ImageEnhance.Contrast(result).enhance(contrast)
        
    return result


def generate_all_catalog_images():
    """Generate realistic photography for all 11 categories."""
    # Color assignments per category index
    COLOR_ROTATIONS = {
        "cargo-pants": ["black", "olive", "beige", "grey", "navy", "black", "beige", "olive", "grey", "black", "navy", "beige"],
        "dress": ["white", "red", "pink", "blue", "beige", "white", "red", "green", "pink", "blue", "white", "beige"],
        "handbag": ["black", "brown", "beige", "red", "black", "brown", "beige", "pink", "black", "brown", "red", "beige"],
        "jacket": ["black", "olive", "navy", "brown", "grey", "black", "olive", "navy", "black", "brown", "grey", "olive"],
        "jeans": ["grey", "blue", "navy", "black", "blue", "grey", "blue", "navy", "black", "grey", "blue", "navy"],
        "kurta": ["beige", "white", "black", "navy", "olive", "beige", "white", "red", "navy", "black", "beige", "olive"],
        "running-shoes": ["blue", "black", "white", "grey", "red", "blue", "black", "white", "grey", "red", "blue", "black"],
        "shirt": ["black", "white", "blue", "beige", "black", "white", "blue", "olive", "grey", "blue", "black", "white"],
        "sneakers": ["navy", "white", "grey", "black", "pink", "navy", "white", "grey", "black", "pink", "navy", "white"],
        "t-shirt": ["blue", "black", "white", "grey", "navy", "green", "red", "black", "white", "grey", "navy", "blue"],
        "trousers": ["olive", "beige", "grey", "black", "navy", "olive", "white", "beige", "grey", "black", "olive", "navy"],
    }

    count = 0
    for cat_slug, colors in COLOR_ROTATIONS.items():
        src_key = cat_slug
        src_path = SOURCE_PHOTOS[src_key]
        base_img = Image.open(src_path)
        
        out_dir = os.path.join(OUTPUT_BASE, cat_slug)
        os.makedirs(out_dir, exist_ok=True)
        
        for i in range(1, 13):
            color = colors[i - 1]
            out_file = os.path.join(out_dir, f"{cat_slug}-{i:02d}.webp")
            
            # Special case for Kurta: alternate between beige studio and black studio
            if cat_slug == "kurta" and color in ["black", "navy"]:
                kurta_src = SOURCE_PHOTOS["kurta_black"]
                cur_base = Image.open(kurta_src)
                graded = apply_color_grade(cur_base, color, brightness=1.05, contrast=1.05)
            else:
                graded = apply_color_grade(base_img, color, brightness=1.0, contrast=1.05)
                
            # Resize / crop to clean 800x800 square
            w, h = graded.size
            min_dim = min(w, h)
            left = (w - min_dim) // 2
            top = (h - min_dim) // 2
            cropped = graded.crop((left, top, left + min_dim, top + min_dim))
            resized = cropped.resize((800, 800), Image.Resampling.LANCZOS)
            
            resized.save(out_file, "WEBP", quality=94)
            count += 1
            
    print(f"Successfully generated {count} photorealistic catalog images across all 11 categories!")


if __name__ == "__main__":
    generate_all_catalog_images()
