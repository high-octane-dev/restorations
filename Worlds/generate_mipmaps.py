import struct, os

for name in os.listdir("./xbox-converted/textures/"):
    if name.endswith(".dds"):
        inDds = open("./xbox-converted/textures/" + name, "rb")
        inDds.seek(0x74)
        isSrgb = struct.unpack("<I", inDds.read(4))[0] == 1
        inDds.close()
        os.system("texconv -y ./xbox-converted/textures/" + name + " -o ./xbox-converted/textures/")
        if isSrgb:
            outDds = open("./xbox-converted/textures/" + name, "r+b")
            outDds.seek(0x74)
            outDds.write(struct.pack("<I", 1))
            outDds.close()