import struct, sys, os
from PIL import Image

if len(sys.argv) < 3:
    print("Usage: py", sys.argv[0], "<INPUT_DDS_FILE> <OUTPUT_PNG_FILE>")
    exit(-1)

input_image = sys.argv[1]
output_image = sys.argv[2]

img = Image.open(input_image).convert("RGBA")
r, g, b, a = img.split()

r.paste(255, (0, 0, r.size[0], r.size[1]))
b.paste(255, (0, 0, b.size[0], b.size[1]))

result = Image.merge('RGBA', (g, a, r, b))
result.save(output_image)