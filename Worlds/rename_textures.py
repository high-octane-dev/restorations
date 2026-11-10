import os, shutil, json, sys

if len(sys.argv) < 2:
    print("Usage: py", sys.argv[0], "<SCENE_NAME>")
    exit(-1)

scene_name = sys.argv[1]
DUMPED_TEXTURES = ".\\xbox-converted\\textures\\"

oct = json.load(open(f"./xbox-converted/{scene_name}.oct.json"))
for item in oct["TexturePool"]:
    if oct["TexturePool"][item]["Type"] != "2d":
        print(oct["TexturePool"][item]["SourceFilePath"])
    
    path = oct["TexturePool"][item]["SourceFilePath"].replace(".png", ".dds").replace(".hdr", ".dds").replace(".tga", ".dds").replace(".TGA", ".dds")
    fileName = oct["TexturePool"][item]["FileName"].replace(".tbuf", ".dds")
    if os.path.exists(DUMPED_TEXTURES + fileName):
        os.makedirs(os.path.dirname(".\\output.oct.textures\\" + path), exist_ok=True)
        shutil.copyfile(DUMPED_TEXTURES + fileName, ".\\output.oct.textures\\" + path)