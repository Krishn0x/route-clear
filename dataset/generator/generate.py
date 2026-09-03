import os
import json
import random
import uuid
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import numpy as np

# Fonts
try:
    FONT_PRINT_LARGE = ImageFont.truetype("C:\\Windows\\Fonts\\arialbd.ttf", 36)
    FONT_PRINT = ImageFont.truetype("C:\\Windows\\Fonts\\arial.ttf", 24)
    FONT_PRINT_SMALL = ImageFont.truetype("C:\\Windows\\Fonts\\arial.ttf", 18)
    FONT_HAND = ImageFont.truetype("C:\\Windows\\Fonts\\segoepr.ttf", 32)
    FONT_STAMP = ImageFont.truetype("C:\\Windows\\Fonts\\arialbd.ttf", 48)
except:
    FONT_PRINT_LARGE = ImageFont.load_default()
    FONT_PRINT = ImageFont.load_default()
    FONT_PRINT_SMALL = ImageFont.load_default()
    FONT_HAND = ImageFont.load_default()
    FONT_STAMP = ImageFont.load_default()

def draw_scribble(d: ImageDraw.Draw, x, y, w, h):
    # draw a scribble line to act as a cross-out
    points = []
    for _ in range(5):
        points.append((x + random.randint(0, w), y + random.randint(0, h)))
    d.line(points, fill="blue", width=3)

def draw_stamp(img: Image.Image, text: str, x: int, y: int, color: str = "red"):
    stamp = Image.new("RGBA", (300, 150), (255, 255, 255, 0))
    sd = ImageDraw.Draw(stamp)
    sd.ellipse([10, 10, 290, 140], outline=color, width=5)
    sd.ellipse([20, 20, 280, 130], outline=color, width=2)
    sd.text((50, 50), text, fill=color, font=FONT_STAMP)
    stamp = stamp.rotate(random.uniform(-30, 30), expand=True)
    img.paste(stamp, (x, y), stamp)

def add_shadows(img: Image.Image) -> Image.Image:
    w, h = img.size
    shadow = Image.new('L', (w, h))
    sd = ImageDraw.Draw(shadow)
    if random.random() > 0.5:
        for y in range(h):
            val = int(255 - (y / h) * 100)
            sd.line([(0, y), (w, y)], fill=val)
    else:
        cx, cy = w/2, h/2
        for r in range(max(w, h)):
            val = max(100, 255 - int(r / 3))
            sd.ellipse([cx-r, cy-r, cx+r, cy+r], outline=val)
    shadow = shadow.convert("RGB")
    return Image.blend(img, shadow, alpha=0.3)

def add_perspective(img: Image.Image) -> Image.Image:
    w, h = img.size
    if random.random() > 0.5:
        x1, y1 = random.randint(0, 50), random.randint(0, 50)
        x2, y2 = w - random.randint(0, 50), random.randint(0, 50)
        x3, y3 = w, h
        x4, y4 = 0, h
    else:
        x1, y1 = 0, 0
        x2, y2 = w, 0
        x3, y3 = w - random.randint(0, 100), h - random.randint(0, 100)
        x4, y4 = random.randint(0, 100), h - random.randint(0, 100)
        
    coeffs = find_coeffs([(x1, y1), (x2, y2), (x3, y3), (x4, y4)], [(0, 0), (w, 0), (w, h), (0, h)])
    return img.transform((w, h), Image.PERSPECTIVE, coeffs, Image.BICUBIC, fillcolor="white")

def find_coeffs(pa, pb):
    matrix = []
    for p1, p2 in zip(pa, pb):
        matrix.append([p1[0], p1[1], 1, 0, 0, 0, -p2[0]*p1[0], -p2[0]*p1[1]])
        matrix.append([0, 0, 0, p1[0], p1[1], 1, -p2[1]*p1[0], -p2[1]*p1[1]])
    A = np.matrix(matrix, dtype=np.float32)
    B = np.array(pb).reshape(8)
    res = np.dot(np.linalg.inv(A.T * A) * A.T, B)
    return np.array(res).reshape(8)

def render_document(record: dict, output_dir: str):
    gt = record["ground_truth"]
    scenario = record["scenario"]
    filename = record["filename"]
    
    img = Image.new('RGB', (1000, 1400), color='white')
    d = ImageDraw.Draw(img)
    
    d.rectangle([50, 50, 950, 150], outline="black", width=2)
    d.text((300, 70), "DELIVERY CHALLAN", font=FONT_PRINT_LARGE, fill="black")
    d.text((320, 110), "XYZ Logistics Pvt Ltd", font=FONT_PRINT, fill="black")
    
    d.text((60, 180), f"Date: 2026-09-03", font=FONT_PRINT, fill="black")
    d.text((600, 180), f"Challan No: {uuid.uuid4().hex[:8].upper()}", font=FONT_PRINT, fill="black")
    
    d.rectangle([50, 220, 480, 320], outline="black")
    d.text((60, 230), "Shipper:", font=FONT_PRINT_SMALL, fill="black")
    d.text((60, 260), "MegaCorp Industries", font=FONT_PRINT, fill="black")
    
    d.rectangle([520, 220, 950, 320], outline="black")
    d.text((530, 230), "Consignee:", font=FONT_PRINT_SMALL, fill="black")
    d.text((530, 260), "Acme Retail Store", font=FONT_PRINT, fill="black")
    
    table_y = 360
    d.rectangle([50, table_y, 950, table_y+50], outline="black", fill="#e0e0e0")
    d.text((60, table_y+10), "Item Description", font=FONT_PRINT, fill="black")
    d.text((500, table_y+10), "Ordered", font=FONT_PRINT, fill="black")
    d.text((650, table_y+10), "Unit", font=FONT_PRINT, fill="black")
    
    d.rectangle([50, table_y+50, 950, table_y+120], outline="black")
    d.text((60, table_y+80), "Premium Widget v2.0", font=FONT_PRINT, fill="black")
    d.text((510, table_y+80), str(gt["ordered_quantity"]), font=FONT_PRINT, fill="black")
    d.text((650, table_y+80), "PCS", font=FONT_PRINT, fill="black")
    
    f_y = 550
    d.rectangle([50, f_y, 950, f_y+200], outline="black")
    d.text((60, f_y+10), "FULFILLMENT CONFIRMATION", font=FONT_PRINT, fill="black")
    
    d.text((100, f_y+60), "Accepted Qty:", font=FONT_PRINT, fill="black")
    d.text((100, f_y+110), "Damaged Qty:", font=FONT_PRINT, fill="black")
    d.text((100, f_y+160), "Rejected Qty:", font=FONT_PRINT, fill="black")
    
    if not (scenario == "missing_qty" and random.random() > 0.3):
        if random.random() > 0.8: # 20% chance of a corrected mistake
            # Draw a crossed out value
            mistake = gt["accepted_quantity"] + random.randint(10, 50)
            d.text((350, f_y+50), str(mistake), font=FONT_PRINT, fill="black")
            draw_scribble(d, 350, f_y+65, 50, 10)
            # Write correct value next to it
            d.text((420, f_y+50), str(gt["accepted_quantity"]), font=FONT_HAND, fill="blue")
        else:
            d.text((350, f_y+50), str(gt["accepted_quantity"]), font=FONT_HAND, fill="blue")
    
    if gt["damaged_quantity"] > 0 or random.random() > 0.5:
        d.text((350, f_y+100), str(gt["damaged_quantity"]), font=FONT_HAND, fill="blue")
    if gt["rejected_quantity"] > 0 or random.random() > 0.5:
        d.text((350, f_y+150), str(gt["rejected_quantity"]), font=FONT_HAND, fill="blue")
        
    if scenario == "arithmetic_contradiction":
        d.text((600, f_y+60), "Total Received:", font=FONT_PRINT, fill="black")
        d.text((800, f_y+60), str(gt["accepted_quantity"]), font=FONT_HAND, fill="red")
        
    if scenario == "full_reject":
        draw_stamp(img, "REJECTED", 400, 500, "red")
        
    s_y = 850
    d.text((100, s_y), "Authorized Signatory (Shipper)", font=FONT_PRINT, fill="black")
    d.text((120, s_y+50), "John Doe", font=FONT_HAND, fill="black")
    
    d.text((600, s_y), "Receiver Signature / Stamp", font=FONT_PRINT, fill="black")
    if gt["signature_present"]:
        draw_scribble(d, 620, s_y+40, 150, 50)
        if random.random() > 0.5:
            draw_stamp(img, "RECEIVED", 600, s_y+80, "blue")
            
    r = random.random()
    if r < 0.3:
        difficulty = "easy"
        if random.random() > 0.5:
            img = img.filter(ImageFilter.GaussianBlur(radius=0.5))
    elif r < 0.8:
        difficulty = "moderate"
        img = add_shadows(img)
        img = img.rotate(random.uniform(-1.5, 1.5), expand=False, fillcolor="white")
        img = img.filter(ImageFilter.GaussianBlur(radius=1.0))
    else:
        difficulty = "difficult"
        img = add_perspective(img)
        img = add_shadows(img)
        img = img.rotate(random.uniform(-3, 3), expand=False, fillcolor="white")
        img = img.filter(ImageFilter.GaussianBlur(radius=1.5))
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(0.7)
        
    img.save(os.path.join(output_dir, filename), "PNG")
    return difficulty

def generate_from_existing_ground_truth(dataset_dir: str):
    gt_file = os.path.join(dataset_dir, "ground_truth.json")
    with open(gt_file, "r") as f:
        metadata = json.load(f)
        
    random.seed(42)
    diff_counts = {"easy": 0, "moderate": 0, "difficult": 0}
    
    for record in metadata:
        diff = render_document(record, dataset_dir)
        diff_counts[diff] += 1
        record["difficulty"] = diff
        
    print(f"Generated {len(metadata)} images.")
    print(f"Difficulty split: {diff_counts}")
    
    with open("difficulties.json", "w") as f:
        json.dump([{"filename": r["filename"], "difficulty": r["difficulty"]} for r in metadata], f, indent=2)

if __name__ == "__main__":
    generate_from_existing_ground_truth("../images")
