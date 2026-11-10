import json, struct, os, sys

# py dump_wii_textures.py vanilla-wii/italy/italy.thb vanilla-wii/italy/italy.tbb wii-converted/italy.oct.json vanilla-wii/italy-tszip wii-converted/textures

if len(sys.argv) < 6:
    print("Usage: py", sys.argv[0], "<THB_PATH> <TBB_PATH> <OCT_JSON_PATH> <TSTREAM_FOLDER> <TEX0_FOLDER>")
    exit(-1)

thb_path = sys.argv[1]
tbb_path = sys.argv[2]
oct_path = sys.argv[3]
tstream_folder = sys.argv[4]
tex0_folder = sys.argv[5]
map_name = os.path.splitext(os.path.basename(thb_path))[0]

def get_path_from_tup(tip, i):
    return tup["TexturePool"]["Texture#" + str(i)]["SourceFilePath"]

def dump_tex0(path, image_size, has_palette, width, height, image_format, num_images, data, name):
    version_number = 1
    brres_offset = 0
    section_offset = 0x40
    string_offset = image_size + 0x40
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as tex0:
        tex0.write(b"TEX0")
        tex0.write(struct.pack(">IIIIIIHHII", image_size + 0x40 + len(name) + 1, version_number, brres_offset, section_offset, string_offset, 0 if has_palette == 0 else 1, width, height, image_format, num_images))
        tex0.seek(0x40)
        tex0.write(data)
        tex0.seek(image_size + 0x40)
        tex0.write(name.encode() + b'\x00')

tup = json.load(open(oct_path))

thb = open(thb_path, "rb")
tbb = open(tbb_path, "rb")
entry_count = struct.unpack(">I", thb.read(4))[0]
entries = []
native_headers = []
for i in range(entry_count):
    native_header_offset, body_offset, texture_len = struct.unpack(">III", thb.read(12))
    entries.append((native_header_offset, body_offset, texture_len))
for i in range(entry_count):
    image_size, alpha_offset, wrap_mode_u, wrap_mode_v, fill2, fill3, width, height, _format, mip_levels, alpha_width, alpha_height, alpha_format, alpha_mip_levels, stream_data_bitfield = struct.unpack(">IIBBBBHHHHHHHHI", thb.read(32))
    native_headers.append((native_header_offset, body_offset, texture_len))
    
    path = os.path.join(tex0_folder, get_path_from_tup(tup, i).replace(".png", ".tex0").replace(".tga", ".tex0"))
    _, body_offset, texture_len = entries[i]
    tbb.seek(body_offset)
    data = tbb.read(texture_len)
    
    tstream_path = os.path.join(tstream_folder, map_name + "_" + str(i) + ".tstream")
    if os.path.exists(tstream_path):
        tstream = open(tstream_path, "rb")
        tstream_data = tstream.read()
        tstream.close()
        data += tstream_data
        # data = tstream_data + data
    if _format in [8, 9, 10]:
        print("Texture has palette! " + str(i))
    dump_tex0(path, image_size, False, width, height, _format, mip_levels, data, path[path.rfind("\\") + 1:].replace(".tex0", ""))
    os.system('wimgt DECODE --no-mipmaps "' + path + '" --dest "' + path.replace(".tex0", ".png") + '"')
    os.system('texconv -dx9 -y "' + path.replace(".tex0", ".png") + '" -o "' + os.path.dirname(path) + '"')
    os.remove(path)
    os.remove(path.replace(".tex0", ".png"))
    outDds = open(path.replace(".tex0", ".dds"), "r+b")
    outDds.seek(0x74)
    outDds.write(struct.pack("<I", 1))
    outDds.close()
tbb.close()
thb.close()