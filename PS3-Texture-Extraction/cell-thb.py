import struct, os, sys

if len(sys.argv) < 5:
    print("(PlayStation 3) .THB/.TBB -> .DDS Extractor -Reload-")
    print("Usage: py", sys.argv[0], "<THB_PATH> <TBB_PATH> <TSTREAM_FOLDER> <DDS_FOLDER>")
    print("Note: You'll need `gtf2dds.exe` either added to PATH or in the same folder as this script.")
    exit(-1)

thb_path = sys.argv[1]
tbb_path = sys.argv[2]
tstream_folder = sys.argv[3]
dds_folder = sys.argv[4]
map_name = os.path.splitext(os.path.basename(thb_path))[0]

thb = open(thb_path, "rb")
tbb = open(tbb_path, "rb")

entry_count = struct.unpack(">I", thb.read(4))[0]
entries = []

for i in range(entry_count):
    native_header_offset, body_offset, texture_len = struct.unpack(">III", thb.read(12))
    entries.append((native_header_offset, body_offset, texture_len))

for i in range(entry_count):
    native_header_offset, body_offset, texture_len = entries[i]

    tstream_path = os.path.join(tstream_folder, map_name + "_" + str(i) + ".tstream")
    if os.path.exists(tstream_path):
        tstream = open(tstream_path, "rb")
        texture_data = tstream.read()
        tstream.close()
        tbb.seek(body_offset)
        texture_data += tbb.read(texture_len)
    else:
        tbb.seek(body_offset)
        texture_data = tbb.read(texture_len)
    thb.seek(native_header_offset + 8)
    native_header = thb.read(24)

    gtf_path = os.path.join(dds_folder, map_name + "_" + str(i) + ".gtf")
    dds_path = gtf_path.replace(".gtf", ".dds")
    
    gtf = open(gtf_path, "wb")
    gtf.write(struct.pack(">IIIIII", 0x20200FF, len(texture_data), 1, 0, 48 + 0x50, len(texture_data)) + native_header)
    gtf.write(0x50 * b'P')
    gtf.write(texture_data)
    gtf.close()
    
    os.system("gtf2dds " + gtf_path + " -o " + dds_path)
    os.remove(gtf_path)
    _flags = native_header[15]
    if _flags & 0x7 != 0:
        dds = open(dds_path, "r+b")
        dds.seek(0x74)
        dds.write(b"\x01\x00\x00\x00")
        dds.close()
    if native_header[3] == 1:
        dds = open(dds_path, "r+b")
        dds.seek(0x70)
        dds.write(b"\x00\xFE\x00\x00")
        dds.close()
    print("Extracted Texture (" + str(i) + ") SRGB: " + str(_flags & 0x7 != 0) + " CubeMap: " + str(native_header[3] == 1))
thb.close()
tbb.close()