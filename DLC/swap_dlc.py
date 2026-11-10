import sys, os, re, zipfile, json, base64, shutil
import numpy as np

sys.path.append('../Worlds/')

from XMaps.swap_data_nodes import handle_data_node
from XMaps.swap_vertex_buffer_dlc import handle_vertex_buffer_impl, handle_vertex_buffer_impl_remap
from XMaps.swap_index_buffer import handle_index_buffer_impl

def load_tup_from_bytes_cached(package, fileName, cachableName):
    if os.path.exists("./_tupCache/" + cachableName):
        return json.load(open("./_tupCache/" + cachableName))
    if not os.path.exists(os.path.dirname("./_tupCache/" + cachableName)):
        os.makedirs(os.path.dirname("./_tupCache/" + cachableName), exist_ok=True)
    
    tmp = open('temp.oct', 'wb')
    tmp.write(package.read(fileName))
    tmp.close()
    os.system(f'offsetting oct decode temp.oct .\\_tupCache\\{cachableName}')
    os.remove('temp.oct')
    return json.load(open("./_tupCache/" + cachableName))

def compile_tup(path, outPath, repackTextures=False):
    if not os.path.exists(os.path.dirname(outPath)):
        os.makedirs(os.path.dirname(outPath), exist_ok=True)
    if repackTextures:
        os.system('offsetting oct encode -t "' + path + '" "' + outPath + '"')
    else:
        os.system('offsetting oct encode "' + path + '" "' + outPath + '"')

def b64dec(_str):
    return base64.b64decode(_str[7:] + '==')

def b64enc(_str):
    return "base64:" + base64.b64encode(_str).decode().rstrip("=")

def handle_u32array(buf):
    arr = np.frombuffer(buf, dtype=np.uint32)
    swapped = arr.byteswap()
    return swapped.tobytes()

def handle_u16array(buf):
    arr = np.frombuffer(buf, dtype=np.uint16)
    swapped = arr.byteswap()
    return swapped.tobytes()

def ziplistdir(zipFile, dirPath):
    if dirPath and not dirPath.endswith('/'):
        dirPath += '/'
    entries = set()
    for name in zipFile.namelist():
        if not name.startswith(dirPath):
            continue
        rest = name[len(dirPath):]
        if not rest:
            continue
        parts = rest.split('/')
        entries.add(dirPath + parts[0])
    return sorted(entries)

def clear_temp():
    for root, dirs, files in os.walk('temp'):
        for f in files:
            os.unlink(os.path.join(root, f))
        for d in dirs:
            shutil.rmtree(os.path.join(root, d))

def clear_temp_for_frontend(carName):
    os.remove(f"temp/{carName}.bent")
    for folder in os.listdir("temp/characters/"):
        if folder != carName:
            shutil.rmtree(f"temp/characters/{folder}")
    if os.path.exists(f"temp/characters/{carName}/motions/"):
        shutil.rmtree(f"temp/characters/{carName}/motions")

def swap_uuid(guid_str):
    def reverse_bytes(hex_str):
        bytes_ = [hex_str[i:i+2] for i in range(0, len(hex_str), 2)]
        return ''.join(reversed(bytes_))
    parts = guid_str.split('-')
    assert(len(parts) == 5)
    new_parts = [
        reverse_bytes(parts[0]),
        reverse_bytes(parts[1]),
        reverse_bytes(parts[2]),
        parts[3],
        parts[4],
    ]
    return '-'.join(new_parts)

def swap_all_uuids(d):
    if isinstance(d, dict):
        for key in d:
            if key == "Uuid":
                d[key] = swap_uuid(d[key])
            else:
                swap_all_uuids(d[key])
    elif isinstance(d, list):
        for item in d:
            swap_all_uuids(item)

DLC_NAMES = [
    "americanagent",
    "americanagent_undercover",
    "mcqueen_tokyo",
    "matertokyo",
    "holly_undercover",
    "finn_security",
    "materthegreater",
    "mcqueenthegreater",
    "francesco_hotrod",
    "mcqueen_lightyear",
    "queen",
    "flo",
    "sheriff",
    "ramone",
    "chickhicks",
    "wingo",
    "snotrod",
    "boost",
    "dj",
    "uncletopolino",
    "materivan",
    "mater_kabuki",
    "victorhugo",
]

# Every character's `dbl` file is exactly the same.
TEMPLATE_DBL_DATA = bytes([
    0x30, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x47, 0x42, 0x57, 0x49, 0x4E, 0x00, 0x00, 0x00, 
    0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 
])

SRC_FOLDER = "./XDLC/Data/"

SKIP_TEXTURE_DUMPING = True

# characters/NAME/NAME.zip
# - NAME.bent (DONE)
# - characters/ (Ignore car_ and class_)
#   - characters/NAME/
#     - characters/NAME/motions/
#       - characters/NAME/motions/*.oct (DONE)
#     - characters/NAME/NAME.dbl (DONE)
#     - characters/NAME/NAME.oct (DONE)
#     - characters/NAME/NAME_0.ibuf (DONE)
#     - characters/NAME/NAME_0.vbuf (DONE)
# choreographies/disruptor_NAME/disruptor_NAME.zip
# frontend/characters/NAME/NAME.zip

for pack in os.listdir(SRC_FOLDER):
    # Skip the older version of the Classic Cars pack.
    # if pack != "DUMMYPACK":
        # continue
    if pack.upper() == "A6F6329B79B8AE2FA5F159264083491E45E622E642":
        continue
    with open(SRC_FOLDER + pack + "/license.lua", "r") as lic:
        carIds = re.findall(r'name\s*=\s*"(\bCAR_\d+)"', lic.read())
    for carId in carIds:
        carName = DLC_NAMES[int(carId[4:])]
        if "mcqueen" == carName:
            continue
        # Create the needed directories for the output car folder.
        os.makedirs(f"./ArcadeDLC/{carId}/characters/{carName}/", exist_ok=True)
        os.makedirs(f"./ArcadeDLC/{carId}/choreographies/", exist_ok=True)
        os.makedirs(f"./ArcadeDLC/{carId}/frontend/characters/{carName}/", exist_ok=True)
        # Copy over the metadata zip file.
        shutil.copyfile(SRC_FOLDER + pack + f"/{carId}/{carId}.zip", f"./ArcadeDLC/{carId}/{carId}.zip")
        
        print("DLC Pack: " + pack + " Has Character: " + carName)
        with zipfile.ZipFile(SRC_FOLDER + pack + f"/{carId}/characters/{carName}/{carName}.tszip", mode='r') as textureStreamZip:
            textureStreamZip.extractall("temp-tszip")
        with zipfile.ZipFile(SRC_FOLDER + pack + f"/{carId}/characters/{carName}/{carName}.zip", mode='r') as mainZip:
            print("Writing .bent file...")
            bent = load_tup_from_bytes_cached(mainZip, f"{carName}.bent", f"{carName}.bent.json")
            # Collect all animations
            animations = []
            for clipSet in bent["ClipSetPool"]:
                for clip in bent["ClipSetPool"][clipSet]["ClipPool"]:
                    animations.append(bent["ClipSetPool"][clipSet]["ClipPool"][clip]["Filename"])
            animations = list(set(animations))
            # Handle All `BlenderChannelMap`s
            for iface in bent["InterfacePool"]:
                bent["InterfacePool"][iface]["BlenderChannelMap"] = b64enc(handle_u16array(b64dec(bent["InterfacePool"][iface]["BlenderChannelMap"])))
            # If there are `Blender`s present, handle their `DefaultBuffer`.
            if "Blenders" in bent:
                bent["Blenders"]["DefaultBuffer"] = b64enc(handle_u32array(b64dec(bent["Blenders"]["DefaultBuffer"])))
            with open(f"temp.json", "w") as f:
                f.write(json.dumps(bent, indent=2))
            compile_tup(f"temp.json", f"temp/{carName}.bent")
            os.remove(f"temp.json")
            del bent
            
            print("Writing animations...")
            for motionTup in animations:
                if motionTup + ".oct" not in mainZip.namelist():
                    continue
                mot = load_tup_from_bytes_cached(mainZip, f"{motionTup}.oct", f"{carName}/{motionTup}.oct.json")
                for subNetwork in mot["SubNetworkPool"]:
                    for node in mot["SubNetworkPool"][subNetwork]["DataNodePool"]:
                        mot["SubNetworkPool"][subNetwork]["DataNodePool"][node] = handle_data_node(mot["SubNetworkPool"][subNetwork]["DataNodePool"][node])
                with open(f"temp.json", "w") as f:
                    f.write(json.dumps(mot, indent=2))
                compile_tup(f"temp.json", f"temp/{motionTup}.oct")
                os.remove(f"temp.json")
            
            if not os.path.exists(f"temp/characters/{carName}/"):
                os.makedirs(os.path.dirname(f"temp/characters/{carName}/"), exist_ok=True)
            
            print("Writing .dbl...")
            with open(f"temp/characters/{carName}/{carName}.dbl", "wb") as f:
                f.write(TEMPLATE_DBL_DATA)
            
            print("Writing .mer...")
            open(f"temp/characters/{carName}/{carName}.mer", "wb").close()
            # Load the oct and start patching in the metadata from the vertex buffer and whatnot
            oct = load_tup_from_bytes_cached(mainZip, f"characters/{carName}/{carName}.oct", f"characters/{carName}/{carName}.oct.json")
            # Create vertex and index buffers
            print("Writing .vbuf file...")
            with mainZip.open(f"characters/{carName}/{carName}_0.vbuf") as vbuf:
                if "mater" in carName:
                    vertex_metadata, scene_node_to_remap_data_index, remap_datas = handle_vertex_buffer_impl_remap(oct, vbuf, f"temp/characters/{carName}/{carName}_0.vbuf")
                else:
                    vertex_metadata = handle_vertex_buffer_impl(oct, vbuf, f"temp/characters/{carName}/{carName}_0.vbuf")
            
            print("Writing .ibuf file...")
            with mainZip.open(f"characters/{carName}/{carName}_0.ibuf") as ibuf:
                handle_index_buffer_impl(ibuf, f"temp/characters/{carName}/{carName}_0.ibuf")
            
            print("Writing .oct file...")
            # Endian-swap any data nodes with binary blobs.
            for data_node in oct["SubNetworkPool"]["SubNetwork#0"]["DataNodePool"]:
                oct["SubNetworkPool"]["SubNetwork#0"]["DataNodePool"][data_node] = handle_data_node(oct["SubNetworkPool"]["SubNetwork#0"]["DataNodePool"][data_node])
            
            # Patch VertexStreamPool
            oct["VertexStreamPool"] = vertex_metadata
            oct["VertexBufferPool"]["VertexBuffer#0"]["Size"] = os.path.getsize(f"temp/characters/{carName}/{carName}_0.vbuf")
            
            # Patch NetworkBuffer if it exists
            if "NetworkBuffer" in oct["SubNetworkPool"]["SubNetwork#0"]:
                oct["SubNetworkPool"]["SubNetwork#0"]["NetworkBuffer"] = b64enc(handle_u32array(b64dec(oct["SubNetworkPool"]["SubNetwork#0"]["NetworkBuffer"])))
            
            # Patch RestPositionIndices if it exists
            if "RestPositionIndices" in oct["SubNetworkPool"]["SubNetwork#0"]:
                oct["SubNetworkPool"]["SubNetwork#0"]["RestPositionIndices"] = b64enc(handle_u16array(b64dec(oct["SubNetworkPool"]["SubNetwork#0"]["RestPositionIndices"])))
            
            # Patch RestPositionData if it exists
            if "RestPositionData" in oct["SubNetworkPool"]["SubNetwork#0"]:
                oct["SubNetworkPool"]["SubNetwork#0"]["RestPositionData"] = b64enc(handle_u32array(b64dec(oct["SubNetworkPool"]["SubNetwork#0"]["RestPositionData"])))

            # Patch TexturePool
            for item in oct["TexturePool"]:
                path = oct["TexturePool"][item]["SourceFilePath"].replace(".png", ".dds").replace(".hdr", ".dds").replace(".tga", ".dds").replace(".TGA", ".dds")
                del oct["TexturePool"][item]["FileName"]
                oct["TexturePool"][item]["Data"] = "file:" + path
            
            if "mater" not in carName:
                # Generate SkinRemap + Add to SceneComponentPool
                boneIds = []
                for node in oct["SceneTreeNodePool"]:
                    if oct["SceneTreeNodePool"][node]["Type"] == "Bone":
                        boneId = oct["SceneTreeNodePool"][node]["BoneID"]
                        boneIds.append(boneId)
                skinRemap = {
                    "Type": "SkinRemap",
                    "RemapData": boneIds,
                }
                skinRemapComponentIndex = len(oct["SceneComponentPool"])
                oct["SceneComponentPool"]["SceneComponent#" + str(skinRemapComponentIndex)] = skinRemap
                # Add necessary SkinRemap references to SceneTreeNodePool
                for node in oct["SceneTreeNodePool"]:
                    if oct["SceneTreeNodePool"][node]["Type"] == "SubGeometryLit":
                        oct["SceneTreeNodePool"][node]["SceneComponentReferences"] = [skinRemapComponentIndex]
            else:
                # For some reason that doesn't work for mater, so we'll have to *actually* give it a real `RemapData`, and more importantly, *distinct SceneComponentReferences*.
                for index, remap_data in enumerate(remap_datas):
                    sceneComponentNode = { "Type": "SkinRemap", "RemapData": remap_data }
                    oct["SceneComponentPool"][f"SceneComponent#{index + 1}"] = sceneComponentNode # Add one because the first SceneComponent is always CarEyes.
                
                for node in oct["SceneTreeNodePool"]:
                    if oct["SceneTreeNodePool"][node]["Type"] == "SubGeometryLit":
                        sceneComponentIndex = scene_node_to_remap_data_index[node] + 1 # Add one because the first SceneComponent is always CarEyes.
                        oct["SceneTreeNodePool"][node]["SceneComponentReferences"] = [sceneComponentIndex]
            
            # Swap all UUIDs
            swap_all_uuids(oct)
            
            if not SKIP_TEXTURE_DUMPING:
                # Dump the `thb` and `tbb` to disk so we can run `xenon-thb`.
                with open(f"{carName}.thb", "wb") as thb:
                    thb.write(mainZip.read(f"characters/{carName}/{carName}.thb"))
                with open(f"{carName}.tbb", "wb") as tbb:
                    tbb.write(mainZip.read(f"characters/{carName}/{carName}.tbb"))
                # Run `xenon-thb`.
                os.system(f".\\xmaps\\xenon-thb.exe --thb {carName}.thb --tbb {carName}.tbb --tstreams temp-tszip --out temp-dds")
                os.remove(f"{carName}.thb")
                os.remove(f"{carName}.tbb")
                # Rename the textures and place them in `/temp.textures/`
                for item in oct["TexturePool"]:
                    path = oct["TexturePool"][item]["SourceFilePath"].replace(".png", ".dds").replace(".hdr", ".dds").replace(".tga", ".dds").replace(".TGA", ".dds")
                    if os.path.exists(f"temp-dds/{carName}_{item.split('#')[1]}.dds"):
                        os.makedirs(os.path.dirname(".\\temp.textures\\" + path), exist_ok=True)
                        shutil.copyfile(f"temp-dds/{carName}_{item.split('#')[1]}.dds", ".\\temp.textures\\" + path)
            
            with open(f"temp.json", "w") as f:
                f.write(json.dumps(oct, indent=2))
            compile_tup("temp.json", f"temp/characters/{carName}/{carName}.oct", repackTextures=True)
            os.system(f"offsetting why temp ./ArcadeDLC/{carId}/characters/{carName}/{carName}.zip")
            clear_temp_for_frontend(carName)
        with zipfile.ZipFile(SRC_FOLDER + pack + f"/{carId}/frontend/characters/{carName}/{carName}.zip", mode='r') as feZip:
            print("Writing frontend .bent file...")
            bent = load_tup_from_bytes_cached(feZip, f"{carName}.bent", f"{carName}_fe.bent.json")
            # Collect all animations
            animations = []
            for clipSet in bent["ClipSetPool"]:
                for clip in bent["ClipSetPool"][clipSet]["ClipPool"]:
                    animations.append(bent["ClipSetPool"][clipSet]["ClipPool"][clip]["Filename"])
            animations = list(set(animations))
            # Handle All `BlenderChannelMap`s
            for iface in bent["InterfacePool"]:
                bent["InterfacePool"][iface]["BlenderChannelMap"] = b64enc(handle_u16array(b64dec(bent["InterfacePool"][iface]["BlenderChannelMap"])))
            # If there are `Blender`s present, handle their `DefaultBuffer`.
            if "Blenders" in bent:
                if "DefaultBuffer" in bent["Blenders"]:
                    bent["Blenders"]["DefaultBuffer"] = b64enc(handle_u32array(b64dec(bent["Blenders"]["DefaultBuffer"])))
            with open(f"temp.json", "w") as f:
                f.write(json.dumps(bent, indent=2))
            compile_tup(f"temp.json", f"temp/{carName}.bent")
            os.remove(f"temp.json")
            del bent
            
            print("Writing frontend animations...")
            for motionTup in animations:
                if motionTup + ".oct" not in feZip.namelist():
                    continue
                mot = load_tup_from_bytes_cached(feZip, f"{motionTup}.oct", f"{carName}_fe/{motionTup}.oct.json")
                for subNetwork in mot["SubNetworkPool"]:
                    for node in mot["SubNetworkPool"][subNetwork]["DataNodePool"]:
                        mot["SubNetworkPool"][subNetwork]["DataNodePool"][node] = handle_data_node(mot["SubNetworkPool"][subNetwork]["DataNodePool"][node])
                with open(f"temp.json", "w") as f:
                    f.write(json.dumps(mot, indent=2))
                compile_tup(f"temp.json", f"temp/{motionTup}.oct")
                os.remove(f"temp.json")
            
            if not os.path.exists(f"temp/characters/{carName}/"):
                os.makedirs(os.path.dirname(f"temp/characters/{carName}/"), exist_ok=True)
            os.system(f"offsetting why temp ./ArcadeDLC/{carId}/frontend/characters/{carName}/{carName}.zip")
            clear_temp()