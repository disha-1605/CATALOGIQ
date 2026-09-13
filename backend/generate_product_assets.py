"""Generate high-quality category-specific fashion product images for CatalogIQ."""

import os
from PIL import Image, ImageDraw

OUTPUT_BASE = "frontend/assets/products"

CATEGORIES = {
    "cargo-pants": {
        "title": "Cargo Pants",
        "tag": "BOTTOMWEAR • UTILITY",
        "colors": [
            ("#2B2D2F", "#1A1B1C", "Charcoal Black"),
            ("#4A5340", "#363D2E", "Military Olive"),
            ("#C2B280", "#A89765", "Desert Beige"),
            ("#3E424B", "#2A2D35", "Gunmetal Grey"),
            ("#1B263B", "#0D1B2A", "Deep Navy"),
            ("#6B705C", "#4A4E3D", "Sage Green"),
            ("#8C7A6B", "#6E5D4F", "Muted Khaki"),
            ("#212529", "#111315", "Stealth Black"),
            ("#7F7F7F", "#595959", "Stone Grey"),
            ("#3D312A", "#261E1A", "Earth Brown"),
            ("#5B6770", "#414C53", "Slate Blue"),
            ("#343A40", "#212529", "Urban Camo"),
        ],
        "shape": "pants_cargo"
    },
    "dress": {
        "title": "Editorial Dress",
        "tag": "WOMEN • DRESSES",
        "colors": [
            ("#E76F51", "#D15637", "Terracotta Red"),
            ("#E9D8A6", "#D3BD82", "Champagne Gold"),
            ("#2A9D8F", "#1D756B", "Emerald Green"),
            ("#F4A261", "#DB8440", "Warm Peach"),
            ("#264653", "#182F38", "Ocean Teal"),
            ("#E07A5F", "#C45B3E", "Rose Bloom"),
            ("#F2CC8F", "#DCB069", "Soft Vanilla"),
            ("#8338EC", "#631BC9", "Electric Violet"),
            ("#FFB703", "#D99800", "Marigold Yellow"),
            ("#3D405B", "#292B3E", "Midnight Navy"),
            ("#E83E4F", "#C72535", "Crimson Coral"),
            ("#DDA15E", "#B87E3B", "Caramel Tan"),
        ],
        "shape": "dress"
    },
    "handbag": {
        "title": "Leather Handbag",
        "tag": "ACCESSORIES • LEATHER",
        "colors": [
            ("#8D5B4C", "#6E4235", "Cognac Leather"),
            ("#1E1E1E", "#0D0D0D", "Onyx Black"),
            ("#D4A373", "#B58455", "Tuscan Tan"),
            ("#CCD5AE", "#A3AF7F", "Pistachio Leather"),
            ("#582F0E", "#3A1E08", "Espresso Brown"),
            ("#7F4F24", "#523214", "Chestnut Saddle"),
            ("#936639", "#674421", "Caramel Suede"),
            ("#B6AD90", "#8F8569", "Ivory Cream"),
            ("#A68A56", "#7C6337", "Burnished Gold"),
            ("#6C584C", "#4B3B31", "Mocha Pebble"),
            ("#DDA15E", "#BA7E3C", "Honey Tan"),
            ("#283618", "#17200E", "Forest Olive"),
        ],
        "shape": "handbag"
    },
    "jacket": {
        "title": "Tailored Jacket",
        "tag": "OUTERWEAR • JACKET",
        "colors": [
            ("#1F2421", "#0D110E", "Obsidian Black"),
            ("#335C67", "#1E3C45", "Alpine Teal"),
            ("#6B705C", "#4B503E", "Field Green"),
            ("#540B0E", "#380608", "Burgundy Wine"),
            ("#9E2A2B", "#741B1C", "Rust Corduroy"),
            ("#283618", "#161F0D", "Hunter Olive"),
            ("#3A5A40", "#233927", "Pine Forest"),
            ("#22333B", "#121E24", "Deep Slate"),
            ("#5E503F", "#403528", "Waxed Tan"),
            ("#495057", "#2D3238", "Granite Grey"),
            ("#0B090A", "#000000", "Biker Leather"),
            ("#4A5759", "#313B3D", "Storm Grey"),
        ],
        "shape": "jacket"
    },
    "jeans": {
        "title": "Denim Jeans",
        "tag": "DENIM • JEANS",
        "colors": [
            ("#1F3B64", "#122543", "Indigo Raw Denim"),
            ("#416788", "#2B4764", "Medium Stone Wash"),
            ("#7698B3", "#52748F", "Vintage Light Blue"),
            ("#202426", "#111314", "Washed Black"),
            ("#3A4A58", "#232F3A", "Dark Steel Blue"),
            ("#5B7082", "#3D4F5E", "Acid Wash Denim"),
            ("#182C4A", "#0D1A2E", "Midnight Rinse"),
            ("#647A8F", "#485A6C", "Cloud Blue Wash"),
            ("#303841", "#1E232A", "Charcoal Denim"),
            ("#8BA0B2", "#667B8D", "Bleach Light Wash"),
            ("#1B3B5F", "#0F253F", "Classic Selvedge"),
            ("#4C566A", "#333A48", "Nordic Blue Grey"),
        ],
        "shape": "jeans"
    },
    "kurta": {
        "title": "Ethnic Kurta",
        "tag": "TRADITIONAL • KURTA",
        "colors": [
            ("#D4AF37", "#A6861D", "Royal Gold Brocade"),
            ("#101827", "#05080E", "Midnight Black"),
            ("#800020", "#520014", "Deep Maroon Silk"),
            ("#F5F5DC", "#DCDCB8", "Beige Raw Silk"),
            ("#004225", "#002414", "British Racing Green"),
            ("#002366", "#001238", "Navy Embroidered"),
            ("#E83E4F", "#B51A29", "Sindhoori Red"),
            ("#E5D4C0", "#C7B29A", "Off-White Linen"),
            ("#705335", "#4B3620", "Chanderi Ochre"),
            ("#4A0E4E", "#2B062E", "Royal Purple Silk"),
            ("#E97451", "#C24E2B", "Burnt Saffron"),
            ("#2E4057", "#1A2636", "Indigo Kalamkari"),
        ],
        "shape": "kurta"
    },
    "running-shoes": {
        "title": "Performance Runner",
        "tag": "FOOTWEAR • RUNNING",
        "colors": [
            ("#E63946", "#BA1E2A", "Speed Crimson"),
            ("#1D3557", "#0F1E33", "Aero Navy"),
            ("#457B9D", "#2C546D", "Hydro Blue"),
            ("#A8DADC", "#7EA9AB", "Ice Mint"),
            ("#2B2D42", "#181926", "Stealth Carbon"),
            ("#8D99AE", "#636E82", "Alloy Silver"),
            ("#FF6B6B", "#D94141", "Neon Coral"),
            ("#4ECDC4", "#2E9991", "Volt Turquoise"),
            ("#FFE66D", "#D4BB33", "Solar Yellow"),
            ("#2F3E46", "#1B2429", "Obsidian Mesh"),
            ("#354F52", "#203032", "Deep Forest Run"),
            ("#52796F", "#355049", "Sage Cushion"),
        ],
        "shape": "shoe_running"
    },
    "shirt": {
        "title": "Button-Down Shirt",
        "tag": "TOPS • FORMAL & CASUAL",
        "colors": [
            ("#FFFFFF", "#E0E0E0", "Crisp Oxford White"),
            ("#A3CEF1", "#78A6CC", "Sky Blue Poplin"),
            ("#274C77", "#17304E", "Regatta Navy"),
            ("#606C38", "#414924", "Olive Linen"),
            ("#DDA15E", "#B87E3B", "Safari Beige"),
            ("#BC6C25", "#8A4E17", "Terracotta Weave"),
            ("#2B2D42", "#171824", "Onyx Twill"),
            ("#E0AAFF", "#B56BE6", "Soft Lilac Chambray"),
            ("#C5D3E8", "#98ABC5", "Glacier Blue"),
            ("#D8E2DC", "#B0BEB7", "Sage Cotton"),
            ("#FFE5D9", "#D9B4A4", "Blush Peach"),
            ("#FFCAD4", "#D899A6", "Rose Fine Stripe"),
        ],
        "shape": "shirt"
    },
    "sneakers": {
        "title": "Streetwear Sneaker",
        "tag": "FOOTWEAR • SNEAKERS",
        "colors": [
            ("#F8F9FA", "#DEE2E6", "Triple White Classic"),
            ("#212529", "#0D0E10", "Triple Black Leather"),
            ("#E83E4F", "#B51A29", "Varsity Red / White"),
            ("#3A86FF", "#1858BF", "Royal Blue Court"),
            ("#8338EC", "#591AB5", "Hyper Violet Retro"),
            ("#FFBE0B", "#C99100", "Dunk Gold Ochre"),
            ("#FB5607", "#C43C00", "Sunset Orange"),
            ("#2EC4B6", "#1B877D", "Tiffany Aqua"),
            ("#ADB5BD", "#7D858D", "Cement Grey Suede"),
            ("#E7C6FF", "#B88EE6", "Pastel Lavender"),
            ("#B8F2E6", "#7BC7B7", "Pistachio Mint"),
            ("#DDA15E", "#B0793A", "Gum Sole Wheat"),
        ],
        "shape": "shoe_sneaker"
    },
    "t-shirt": {
        "title": "Oversized Tee",
        "tag": "TOPS • T-SHIRTS",
        "colors": [
            ("#1A1A1A", "#000000", "Vintage Washed Black"),
            ("#F5F5F5", "#D8D8D8", "Heavyweight White"),
            ("#4A5568", "#2D3748", "Slate Charcoal"),
            ("#E53E3E", "#A62020", "Bold Crimson"),
            ("#DD6B20", "#9C430B", "Amber Orange"),
            ("#319795", "#1D6462", "Muted Pine"),
            ("#3182CE", "#1B528A", "Cobalt Blue"),
            ("#805AD5", "#513196", "Grape Purple"),
            ("#D69E2E", "#946B18", "Mustard Gold"),
            ("#E2E8F0", "#CBD5E1", "Heather Ash"),
            ("#C6F6D5", "#92D8A8", "Mint Sorbet"),
            ("#FEB2B2", "#E87878", "Coral Blossom"),
        ],
        "shape": "tshirt"
    },
    "trousers": {
        "title": "Relaxed Trousers",
        "tag": "BOTTOMWEAR • TROUSERS",
        "colors": [
            ("#2D3748", "#1A202C", "Charcoal Tailored"),
            ("#D69E2E", "#976C18", "Camel Wool"),
            ("#4A5568", "#2B333F", "Graphite Grey"),
            ("#718096", "#475263", "Silver Pebble"),
            ("#1A202C", "#0D1117", "Formal Jet Black"),
            ("#A0AEC0", "#718096", "Heather Khaki"),
            ("#319795", "#1E6563", "Deep Spruce"),
            ("#805AD5", "#533396", "Plum Fine Weave"),
            ("#C05621", "#87350F", "Burnt Rust"),
            ("#E2E8F0", "#CBD5E1", "Ecru Linen"),
            ("#2C5282", "#1A365D", "Savile Row Navy"),
            ("#744210", "#4B2807", "Mocha Herringbone"),
        ],
        "shape": "pants_formal"
    }
}


def draw_fashion_visual(category_key: str, index: int, output_path: str):
    """Render a clean, high-resolution fashion studio product image."""
    cat_info = CATEGORIES[category_key]
    color_info = cat_info["colors"][(index - 1) % len(cat_info["colors"])]
    primary_color, dark_shade, color_name = color_info
    
    width, height = 600, 800
    
    # Soft warm studio gradient background
    bg = Image.new("RGB", (width, height), "#F8F5F2")
    draw = ImageDraw.Draw(bg)
    
    # Studio ambient back lighting
    for radius in range(350, 50, -30):
        draw.ellipse([width//2 - radius, height//2 - 60 - radius, width//2 + radius, height//2 - 60 + radius], fill="#FCFBF9")

    # Studio Floor shadow
    shadow_y = 620
    draw.ellipse([width//2 - 180, shadow_y - 25, width//2 + 180, shadow_y + 25], fill="#E5DFD7")
    draw.ellipse([width//2 - 130, shadow_y - 15, width//2 + 130, shadow_y + 15], fill="#D6CEC4")

    # Center coordinates
    cx, cy = width // 2, height // 2 - 20
    shape = cat_info["shape"]
    
    if shape == "kurta":
        draw.polygon([(cx - 70, cy - 200), (cx + 70, cy - 200), (cx + 110, cy + 180), (cx - 110, cy + 180)], fill=primary_color)
        draw.polygon([(cx - 70, cy - 200), (cx - 160, cy - 60), (cx - 120, cy - 40), (cx - 60, cy - 130)], fill=dark_shade)
        draw.polygon([(cx + 70, cy - 200), (cx + 160, cy - 60), (cx + 120, cy - 40), (cx + 60, cy - 130)], fill=dark_shade)
        draw.rectangle([cx - 12, cy - 190, cx + 12, cy - 70], fill="#D4AF37" if "Gold" in color_name else "#FFFFFF")
        draw.ellipse([cx - 30, cy - 220, cx + 30, cy - 180], fill="#F8F5F2")
        for by in range(cy - 170, cy - 70, 25):
            draw.ellipse([cx - 4, by, cx + 4, by + 8], fill="#111827")
        draw.rectangle([cx - 110, cy + 165, cx + 110, cy + 180], fill=dark_shade)
        
    elif shape == "shirt":
        draw.polygon([(cx - 85, cy - 180), (cx + 85, cy - 180), (cx + 105, cy + 160), (cx - 105, cy + 160)], fill=primary_color)
        draw.polygon([(cx - 85, cy - 180), (cx - 170, cy - 30), (cx - 125, cy - 10), (cx - 75, cy - 100)], fill=dark_shade)
        draw.polygon([(cx + 85, cy - 180), (cx + 170, cy - 30), (cx + 125, cy - 10), (cx + 75, cy - 100)], fill=dark_shade)
        draw.polygon([(cx, cy - 175), (cx - 45, cy - 150), (cx - 20, cy - 200)], fill=dark_shade)
        draw.polygon([(cx, cy - 175), (cx + 45, cy - 150), (cx + 20, cy - 200)], fill=dark_shade)
        draw.rectangle([cx - 10, cy - 175, cx + 10, cy + 160], fill=dark_shade)
        for by in range(cy - 140, cy + 150, 45):
            draw.ellipse([cx - 4, by, cx + 4, by + 8], fill="#FFFFFF" if primary_color != "#FFFFFF" else "#9CA3AF")
        draw.rectangle([cx - 70, cy - 100, cx - 35, cy - 50], outline=dark_shade, width=2)
        
    elif shape == "tshirt":
        draw.polygon([(cx - 95, cy - 180), (cx + 95, cy - 180), (cx + 115, cy + 160), (cx - 115, cy + 160)], fill=primary_color)
        draw.polygon([(cx - 95, cy - 180), (cx - 175, cy - 80), (cx - 135, cy - 40), (cx - 85, cy - 100)], fill=dark_shade)
        draw.polygon([(cx + 95, cy - 180), (cx + 175, cy - 80), (cx + 135, cy - 40), (cx + 85, cy - 100)], fill=dark_shade)
        draw.ellipse([cx - 40, cy - 205, cx + 40, cy - 165], fill="#F8F5F2", outline=dark_shade, width=4)
        draw.rectangle([cx - 40, cy - 90, cx + 40, cy - 60], fill=dark_shade)
        draw.rectangle([cx - 35, cy - 85, cx + 35, cy - 65], fill="#F8F5F2")
        
    elif shape == "jacket":
        draw.polygon([(cx - 95, cy - 190), (cx + 95, cy - 190), (cx + 120, cy + 160), (cx - 120, cy + 160)], fill=primary_color)
        draw.polygon([(cx - 95, cy - 190), (cx - 180, cy + 30), (cx - 135, cy + 50), (cx - 80, cy - 90)], fill=dark_shade)
        draw.polygon([(cx + 95, cy - 190), (cx + 180, cy + 30), (cx + 135, cy + 50), (cx + 80, cy - 90)], fill=dark_shade)
        draw.polygon([(cx - 30, cy - 200), (cx - 65, cy - 120), (cx - 10, cy - 80)], fill=dark_shade)
        draw.polygon([(cx + 30, cy - 200), (cx + 65, cy - 120), (cx + 10, cy - 80)], fill=dark_shade)
        draw.rectangle([cx - 4, cy - 80, cx + 4, cy + 160], fill="#E5E7EB")
        draw.rectangle([cx - 100, cy + 40, cx - 40, cy + 100], fill=dark_shade)
        draw.rectangle([cx + 40, cy + 40, cx + 100, cy + 100], fill=dark_shade)
        
    elif shape == "dress":
        draw.polygon([(cx - 50, cy - 190), (cx + 50, cy - 190), (cx + 45, cy - 60), (cx - 45, cy - 60)], fill=dark_shade)
        draw.ellipse([cx - 35, cy - 210, cx + 35, cy - 175], fill="#F8F5F2")
        draw.polygon([(cx - 45, cy - 60), (cx + 45, cy - 60), (cx + 150, cy + 190), (cx - 150, cy + 190)], fill=primary_color)
        draw.rectangle([cx - 50, cy - 65, cx + 50, cy - 50], fill="#111827")
        for px in [-80, -30, 30, 80]:
            draw.line([(cx + px//3, cy - 50), (cx + px, cy + 190)], fill=dark_shade, width=2)
            
    elif shape in ["jeans", "pants_cargo", "pants_formal"]:
        waist_w = 80
        draw.rectangle([cx - waist_w, cy - 190, cx + waist_w, cy - 155], fill=dark_shade)
        crotch_y = cy - 40
        draw.polygon([(cx - waist_w, cy - 155), (cx + waist_w, cy - 155), (cx + 90, crotch_y), (cx - 90, crotch_y)], fill=primary_color)
        draw.polygon([(cx - 90, crotch_y), (cx - 10, crotch_y), (cx - 30, cy + 190), (cx - 95, cy + 190)], fill=primary_color)
        draw.polygon([(cx + 10, crotch_y), (cx + 90, crotch_y), (cx + 95, cy + 190), (cx + 30, cy + 190)], fill=primary_color)
        draw.line([(cx, crotch_y), (cx - 30, cy + 190)], fill=dark_shade, width=2)
        draw.line([(cx, crotch_y), (cx + 30, cy + 190)], fill=dark_shade, width=2)
        
        if shape == "pants_cargo":
            draw.rectangle([cx - 110, cy + 10, cx - 65, cy + 80], fill=dark_shade)
            draw.rectangle([cx + 65, cy + 10, cx + 110, cy + 80], fill=dark_shade)
            draw.rectangle([cx - 112, cy + 10, cx - 63, cy + 25], fill="#111827")
            draw.rectangle([cx + 63, cy + 10, cx + 112, cy + 25], fill="#111827")
        elif shape == "jeans":
            draw.arc([cx - 75, cy - 155, cx - 25, cy - 95], 0, 90, fill="#E5E7EB", width=2)
            draw.arc([cx + 25, cy - 155, cx + 75, cy - 95], 90, 180, fill="#E5E7EB", width=2)
            draw.ellipse([cx - 6, cy - 175, cx + 6, cy - 163], fill="#C084FC" if "Purple" in color_name else "#D4AF37")
            
    elif shape == "handbag":
        draw.arc([cx - 60, cy - 190, cx + 60, cy - 70], 180, 360, fill=dark_shade, width=12)
        draw.polygon([(cx - 110, cy - 70), (cx + 110, cy - 70), (cx + 130, cy + 140), (cx - 130, cy + 140)], fill=primary_color)
        draw.rectangle([cx - 110, cy - 70, cx + 110, cy - 40], fill=dark_shade)
        draw.rectangle([cx - 16, cy - 15, cx + 16, cy + 15], fill="#D4AF37")
        draw.ellipse([cx - 8, cy - 8, cx + 8, cy + 8], fill="#854D0E")
        draw.rectangle([cx - 100, cy - 30, cx + 100, cy + 130], outline=dark_shade, width=2)
        
    elif shape in ["shoe_sneaker", "shoe_running"]:
        sy = cy + 20
        draw.polygon([(cx - 160, sy + 70), (cx + 150, sy + 70), (cx + 170, sy + 35), (cx + 140, sy + 30), (cx - 150, sy + 35)], fill="#FFFFFF" if primary_color != "#F8F9FA" else "#1F2937")
        draw.rectangle([cx - 160, sy + 65, cx + 150, sy + 75], fill="#111827")
        draw.polygon([(cx - 150, sy + 35), (cx - 120, sy - 40), (cx - 40, sy - 80), (cx + 40, sy - 80), (cx + 100, sy - 20), (cx + 150, sy + 30)], fill=primary_color)
        draw.polygon([(cx - 120, sy - 40), (cx - 80, sy - 110), (cx - 20, sy - 70), (cx - 40, sy - 80)], fill=dark_shade)
        draw.polygon([(cx - 20, sy - 70), (cx + 40, sy - 80), (cx + 60, sy - 30), (cx, sy - 20)], fill="#FFFFFF")
        for lx in range(0, 50, 12):
            draw.line([(cx + lx - 10, sy - 65 + lx//2), (cx + lx + 10, sy - 50 + lx//2)], fill="#111827", width=2)
        draw.polygon([(cx - 80, sy + 10), (cx + 20, sy - 30), (cx + 80, sy + 15), (cx - 30, sy + 25)], fill=dark_shade)

    # Category badge top-left
    draw.rectangle([40, 40, 240, 68], fill="#111827")
    draw.text((52, 48), cat_info["tag"], fill="#FFFFFF")
    
    # Bottom product badge
    draw.rectangle([40, height - 90, width - 40, height - 40], fill="#FFFFFF", outline="#E5E7EB", width=1)
    draw.text((55, height - 80), f"{cat_info['title']} #{index:02d}", fill="#111827")
    draw.text((55, height - 60), f"Colorway: {color_name}", fill="#6B7280")
    draw.text((width - 120, height - 70), "CatalogIQ", fill="#E83E4F")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    bg.save(output_path, "WEBP", quality=92)


def generate_all_images():
    count = 0
    for cat_slug, info in CATEGORIES.items():
        dir_path = os.path.join(OUTPUT_BASE, cat_slug)
        for i in range(1, 13):
            file_name = f"{cat_slug}-{i:02d}.webp"
            out_file = os.path.join(dir_path, file_name)
            draw_fashion_visual(cat_slug, i, out_file)
            count += 1
    print(f"Generated {count} category-specific images!")


if __name__ == "__main__":
    generate_all_images()
