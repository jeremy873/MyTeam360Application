#!/bin/bash
# MyTeam360 — Icon Generator
# Usage: ./scripts/generate-icons.sh [source.png]
# If no source provided, generates a placeholder icon.

set -e

ICONS_DIR="src-tauri/icons"
mkdir -p "$ICONS_DIR"

SOURCE="${1:-}"

if [ -z "$SOURCE" ]; then
    echo "No source icon provided. Generating placeholder..."

    # Check for sips (macOS) or ImageMagick
    if command -v python3 &>/dev/null; then
        python3 << 'PYEOF'
import struct, zlib, os

def create_png(width, height, r, g, b):
    """Create a minimal solid-color PNG."""
    def chunk(ctype, data):
        c = ctype + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)

    header = b'\x89PNG\r\n\x1a\n'
    ihdr = chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))

    raw = b''
    for y in range(height):
        raw += b'\x00'  # filter byte
        for x in range(width):
            # Simple gradient + centered circle
            cx, cy = width/2, height/2
            dx, dy = x - cx, y - cy
            dist = (dx*dx + dy*dy) ** 0.5
            radius = min(width, height) * 0.38

            if dist < radius:
                # Inner: lighter accent
                raw += bytes([min(255, r+40), min(255, g+40), min(255, b+40)])
            elif dist < radius + 2:
                # Border
                raw += bytes([255, 255, 255])
            else:
                # Background
                raw += bytes([r, g, b])

    idat = chunk(b'IDAT', zlib.compress(raw))
    iend = chunk(b'IEND', b'')
    return header + ihdr + idat + iend

sizes = {
    '32x32.png': 32,
    '128x128.png': 128,
    '128x128@2x.png': 256,
    'icon.png': 512,
}

icons_dir = 'src-tauri/icons'
for name, size in sizes.items():
    data = create_png(size, size, 124, 92, 252)  # #7c5cfc accent
    path = os.path.join(icons_dir, name)
    with open(path, 'wb') as f:
        f.write(data)
    print(f"  Created {path} ({size}x{size})")

print("\nPlaceholder icons generated.")
print("For production, replace with your actual icon and re-run:")
print("  ./scripts/generate-icons.sh your-icon-1024.png")
PYEOF
    else
        echo "ERROR: python3 required for icon generation"
        exit 1
    fi
else
    echo "Generating icons from: $SOURCE"

    if command -v sips &>/dev/null; then
        # macOS native
        sips -z 32 32     "$SOURCE" --out "$ICONS_DIR/32x32.png"
        sips -z 128 128   "$SOURCE" --out "$ICONS_DIR/128x128.png"
        sips -z 256 256   "$SOURCE" --out "$ICONS_DIR/128x128@2x.png"
        sips -z 512 512   "$SOURCE" --out "$ICONS_DIR/icon.png"

        # Generate .icns
        ICONSET="$ICONS_DIR/icon.iconset"
        mkdir -p "$ICONSET"
        sips -z 16 16     "$SOURCE" --out "$ICONSET/icon_16x16.png"
        sips -z 32 32     "$SOURCE" --out "$ICONSET/icon_16x16@2x.png"
        sips -z 32 32     "$SOURCE" --out "$ICONSET/icon_32x32.png"
        sips -z 64 64     "$SOURCE" --out "$ICONSET/icon_32x32@2x.png"
        sips -z 128 128   "$SOURCE" --out "$ICONSET/icon_128x128.png"
        sips -z 256 256   "$SOURCE" --out "$ICONSET/icon_128x128@2x.png"
        sips -z 256 256   "$SOURCE" --out "$ICONSET/icon_256x256.png"
        sips -z 512 512   "$SOURCE" --out "$ICONSET/icon_256x256@2x.png"
        sips -z 512 512   "$SOURCE" --out "$ICONSET/icon_512x512.png"
        sips -z 1024 1024 "$SOURCE" --out "$ICONSET/icon_512x512@2x.png"
        iconutil -c icns "$ICONSET" -o "$ICONS_DIR/icon.icns"
        rm -rf "$ICONSET"
        echo "  Created icon.icns"

    elif command -v convert &>/dev/null; then
        # ImageMagick
        convert "$SOURCE" -resize 32x32     "$ICONS_DIR/32x32.png"
        convert "$SOURCE" -resize 128x128   "$ICONS_DIR/128x128.png"
        convert "$SOURCE" -resize 256x256   "$ICONS_DIR/128x128@2x.png"
        convert "$SOURCE" -resize 512x512   "$ICONS_DIR/icon.png"
        echo "  Note: .icns generation requires macOS sips/iconutil"
    else
        echo "ERROR: Needs either macOS (sips) or ImageMagick (convert)"
        exit 1
    fi

    echo "Icons generated successfully."
fi
