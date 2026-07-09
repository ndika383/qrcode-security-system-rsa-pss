"""
create_code_screenshots.py - Membuat screenshot kode untuk evidensi visual
Menggunakan syntax highlighting dan export ke PNG
"""

from PIL import Image, ImageDraw, ImageFont
import os
from pathlib import Path

# Configuration
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / 'evidensi'
os.makedirs(OUTPUT_DIR, exist_ok=True)

print("=" * 70)
print("MEMBUAT SCREENSHOT KODE UNTUK EVIDENSI VISUAL")
print("=" * 70)

# Read app.py
with open(BASE_DIR / 'app.py', 'r', encoding='utf-8') as f:
    all_lines = f.readlines()

def create_code_screenshot(filename, title, code_lines, line_numbers):
    """Create a code screenshot with syntax highlighting"""
    
    # Settings
    font_size = 13
    line_height = 18
    padding = 30
    char_width = 8  # Approximate width per character for monospace
    
    # Calculate dimensions
    max_line_len = max(len(line.rstrip()) for line in code_lines) if code_lines else 50
    img_width = padding * 2 + max_line_len * char_width + 50
    img_height = padding * 2 + 70 + len(code_lines) * line_height  # 70 for title
    
    # Create image
    img = Image.new('RGB', (img_width, img_height), color='#1e1e1e')
    draw = ImageDraw.Draw(img)
    
    # Try to use a monospace font
    try:
        font = ImageFont.truetype("consola.ttf", font_size)
        title_font = ImageFont.truetype("consola.ttf", font_size + 2)
    except:
        try:
            font = ImageFont.truetype("DejaVuSansMono.ttf", font_size)
            title_font = ImageFont.truetype("DejaVuSansMono.ttf", font_size + 2)
        except:
            font = ImageFont.load_default()
            title_font = ImageFont.load_default()
    
    # Draw title
    draw.text((padding, 15), title, fill='#4ec9b0', font=title_font)
    
    # Draw file reference
    draw.text((padding, 42), filename, fill='#858585', font=font)
    
    # Draw code lines
    y_offset = 70
    for i, (line, line_num) in enumerate(zip(code_lines, line_numbers)):
        line_text = line.rstrip()
        
        # Line number
        draw.text((padding, y_offset), f"{line_num:5d} ", fill='#858585', font=font)
        
        # Simple syntax highlighting
        x = padding + 50
        
        # Check for keywords
        if 'def ' in line_text:
            draw.text((x, y_offset), line_text, fill='#dcdcaa', font=font)
        elif 'class ' in line_text:
            draw.text((x, y_offset), line_text, fill='#4ec9b0', font=font)
        elif line_text.strip().startswith('#') or line_text.strip().startswith('//'):
            draw.text((x, y_offset), line_text, fill='#6a9955', font=font)
        elif 'import ' in line_text or 'from ' in line_text:
            draw.text((x, y_offset), line_text, fill='#c586c0', font=font)
        elif '=' in line_text and '==' not in line_text:
            # Variable assignment
            parts = line_text.split('=', 1)
            draw.text((x, y_offset), parts[0], fill='#9cdcfe', font=font)
            draw.text((x + len(parts[0]) * char_width, y_offset), '=', fill='#d4d4d4', font=font)
            if len(parts) > 1:
                draw.text((x + (len(parts[0]) + 1) * char_width, y_offset), parts[1], fill='#ce9178', font=font)
        else:
            draw.text((x, y_offset), line_text, fill='#d4d4d4', font=font)
        
        y_offset += line_height
    
    # Save
    output_path = os.path.join(OUTPUT_DIR, filename.replace('.py', '').replace('/', '_') + '.png')
    img.save(output_path, 'PNG', optimize=True)
    print(f"  ✅ Saved: {output_path} ({img_width}x{img_height})")
    return output_path

# ============================================================
# SCREENSHOT 1: RSA-PSS Salt 8-Byte (Signing)
# ============================================================
print("\n[1/9] RSA-PSS Signing with 8-byte salt...")
create_code_screenshot(
    'app_line_1166',
    'Evidence 1: RSA-PSS Signing with Modified Salt (8 bytes)',
    [all_lines[1163], all_lines[1164], all_lines[1165], all_lines[1166], all_lines[1167], all_lines[1168], all_lines[1169], all_lines[1170]],
    [1164, 1165, 1166, 1167, 1168, 1169, 1170, 1171]
)

# ============================================================
# SCREENSHOT 2: RSA-PSS Verification
# ============================================================
print("\n[2/9] RSA-PSS Verification with 8-byte salt...")
create_code_screenshot(
    'app_line_1369',
    'Evidence 2: RSA-PSS Verification (Consistent 8-byte salt)',
    [all_lines[1366], all_lines[1367], all_lines[1368], all_lines[1369], all_lines[1370], all_lines[1371], all_lines[1372]],
    [1367, 1368, 1369, 1370, 1371, 1372, 1373]
)

# ============================================================
# SCREENSHOT 3: DigiSig Envelope Structure
# ============================================================
print("\n[3/9] DigiSig Envelope (ISO/IEC 20248:2022)...")
create_code_screenshot(
    'app_line_1179',
    'Evidence 3: DigiSig Envelope Structure (ISO/IEC 20248:2022)',
    [all_lines[1176], all_lines[1177], all_lines[1178], all_lines[1179], all_lines[1180], 
     all_lines[1181], all_lines[1182], all_lines[1183], all_lines[1184], all_lines[1185], all_lines[1186]],
    [1177, 1178, 1179, 1180, 1181, 1182, 1183, 1184, 1185, 1186, 1187]
)

# ============================================================
# SCREENSHOT 4: Nonce + Timestamp Generation
# ============================================================
print("\n[4/9] Nonce + Timestamp Generation...")
create_code_screenshot(
    'app_line_1151',
    'Evidence 4: Nonce (4-byte) + Timestamp (ISO 8601, WIB) Generation',
    [all_lines[1148], all_lines[1149], all_lines[1150], all_lines[1151], all_lines[1152], all_lines[1153], all_lines[1154]],
    [1149, 1150, 1151, 1152, 1153, 1154, 1155]
)

# ============================================================
# SCREENSHOT 5: Dual-Layer Verification
# ============================================================
print("\n[5/9] Dual-Layer Security Verification...")
create_code_screenshot(
    'app_line_1396',
    'Evidence 5: Dual-Layer Verification (Nonce + Timestamp + Signature)',
    [all_lines[1396], all_lines[1397], all_lines[1398], all_lines[1399], all_lines[1400],
     all_lines[1401], all_lines[1402], all_lines[1403], all_lines[1404], all_lines[1405],
     all_lines[1406], all_lines[1407], all_lines[1408], all_lines[1409], all_lines[1410],
     all_lines[1411], all_lines[1412], all_lines[1413], all_lines[1414], all_lines[1415]],
    [1397, 1398, 1399, 1400, 1401, 1402, 1403, 1404, 1405, 1406,
     1407, 1408, 1409, 1410, 1411, 1412, 1413, 1414, 1415, 1416]
)

# ============================================================
# SCREENSHOT 6: Nonce Checking Function
# ============================================================
print("\n[6/9] Nonce Checking Function...")
create_code_screenshot(
    'app_line_428',
    'Evidence 6: is_nonce_used() Function with File Locking',
    [all_lines[428], all_lines[429], all_lines[430], all_lines[431], all_lines[432],
     all_lines[433], all_lines[434], all_lines[435], all_lines[436], all_lines[437],
     all_lines[438], all_lines[439], all_lines[440], all_lines[441], all_lines[442]],
    [429, 430, 431, 432, 433, 434, 435, 436, 437, 438, 439, 440, 441, 442, 443]
)

# ============================================================
# SCREENSHOT 7: Temporal Decomposition (6 Timers)
# ============================================================
print("\n[7/9] Temporal Decomposition (6 Timers)...")
create_code_screenshot(
    'app_line_1207',
    'Evidence 7: Temporal Decomposition (6 Separate Timers)',
    [all_lines[1204], all_lines[1205], all_lines[1206], all_lines[1207], all_lines[1208],
     all_lines[1209], all_lines[1210], all_lines[1211], all_lines[1212], all_lines[1213],
     all_lines[1214], all_lines[1215], all_lines[1216], all_lines[1217], all_lines[1218]],
    [1205, 1206, 1207, 1208, 1209, 1210, 1211, 1212, 1213, 1214, 1215, 1216, 1217, 1218, 1219]
)

# ============================================================
# SCREENSHOT 8: CSV Logging (14 Columns)
# ============================================================
print("\n[8/9] CSV Logging (14 Columns, Microsecond Precision)...")
create_code_screenshot(
    'app_line_1227',
    'Evidence 8: Comprehensive CSV Logging (14 Columns, Microsecond Precision)',
    [all_lines[1224], all_lines[1225], all_lines[1226], all_lines[1227], all_lines[1228],
     all_lines[1229], all_lines[1230], all_lines[1231], all_lines[1232], all_lines[1233],
     all_lines[1234], all_lines[1235], all_lines[1236], all_lines[1237]],
    [1225, 1226, 1227, 1228, 1229, 1230, 1231, 1232, 1233, 1234, 1235, 1236, 1237, 1238]
)

# ============================================================
# SCREENSHOT 9: Rate Limiting with Redis
# ============================================================
print("\n[9/9] Rate Limiting with Redis...")
create_code_screenshot(
    'app_line_79',
    'Evidence 9: Production-Ready Rate Limiting with Redis Backend',
    [all_lines[79], all_lines[80], all_lines[81], all_lines[82], all_lines[83],
     all_lines[84], all_lines[85], all_lines[86], all_lines[87], all_lines[88],
     all_lines[89], all_lines[90], all_lines[91], all_lines[92]],
    [80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93]
)

# ============================================================
# SCREENSHOT 10: Multi-Scenario Benchmarks
# ============================================================
print("\n[10/10] Multi-Scenario Benchmarks...")
with open(BASE_DIR / 'modules' / 'realistic_performance.py', 'r', encoding='utf-8') as f:
    perf_lines = f.readlines()

create_code_screenshot(
    'realistic_performance_line_12',
    'Evidence 10: Multi-Scenario Benchmarks (Calibrated from IEEE/ACM/NIST)',
    [perf_lines[9], perf_lines[10], perf_lines[11], perf_lines[12], perf_lines[13],
     perf_lines[14], perf_lines[15], perf_lines[16], perf_lines[17], perf_lines[18],
     perf_lines[19], perf_lines[20], perf_lines[21]],
    [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22]
)

print("\n" + "=" * 70)
print("SEMUA SCREENSHOT BERHASIL DIBUAT!")
print("=" * 70)

# List all files
for f in os.listdir(OUTPUT_DIR):
    if f.endswith('.png'):
        path = os.path.join(OUTPUT_DIR, f)
        size_kb = os.path.getsize(path) / 1024
        print(f"  📷 {f}: {size_kb:.1f} KB")

print(f"\nLokasi: {OUTPUT_DIR}")
print("Screenshot siap dilampirkan sebagai evidensi visual di paper.")
