import json, os, base64, sys
from swap_vertex_buffer import handle_vertex_buffer
from swap_index_buffer import handle_index_buffer
from swap_data_nodes import handle_data_node
from swap_meridian_type_count import handle_meridian_type_count
from swap_bullet_metadata import handle_bullet_metadata
from swap_bullet_data import handle_bullet_data
from swap_database import handle_database

def b64dec(_str):
    return base64.b64decode(_str[7:] + '==')

def b64enc(_str):
    return "base64:" + base64.b64encode(_str).decode().rstrip("=")

def normalize_uuid(test):
    return "-".join([test[:8], test[8:12], test[12:16], test[16:20], test[20:]])

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

def handle_network_buffer(buf):
    swapped = bytearray()
    for i in range(0, len(buf), 4):
        swapped += buf[i+3:i+4] + buf[i+2:i+3] + buf[i+1:i+2] + buf[i:i+1]
    return bytes(swapped)

if len(sys.argv) < 2:
    print("Usage: py", sys.argv[0], "<CHOREO_NAME>")
    exit(-1)

choreography_name = sys.argv[1]

source_oct_json = f"./xbox-converted/{choreography_name}.oct.json"
# source_mer_json = f"./xbox-converted/{choreography_name}.mer.json"
source_vbuf = f"./vanilla-xbox/{choreography_name}/{choreography_name}_0.vbuf"
source_ibuf = f"./vanilla-xbox/{choreography_name}/{choreography_name}_0.ibuf"
# source_mtc = f"./vanilla-xbox/{choreography_name}/{choreography_name}.mtc"
# source_dbl = f"./vanilla-xbox/{choreography_name}/{choreography_name}.dbl"
dest_oct_json = "output.oct.json"
dest_oct = fr"C:\Projects\OctaneEngine\C2A\assets\choreographies\{choreography_name}\{choreography_name}.oct"
# dest_mer_json = "output.mer.json"
# dest_mer = fr"C:\Projects\OctaneEngine\C2A\assets\worlds\{choreography_name}\{choreography_name}.mer"
dest_vbuf = fr"C:\Projects\OctaneEngine\C2A\assets\choreographies\{choreography_name}\{choreography_name}_0.vbuf"
dest_ibuf = fr"C:\Projects\OctaneEngine\C2A\assets\choreographies\{choreography_name}\{choreography_name}_0.ibuf"
# dest_mtc = fr"C:\Projects\OctaneEngine\C2A\assets\worlds\{choreography_name}\{choreography_name}.mtc"
# dest_dbl = fr"C:\Projects\OctaneEngine\C2A\assets\worlds\{choreography_name}\{choreography_name}.dbl"

# # Handle .dbl file
# print("Writing .dbl file...")
# handle_database(source_dbl, dest_dbl)

# # Handle .mer file
# print("Writing .mer file...")
# mer = json.load(open(source_mer_json, "r"))
# # Swap all UUIDs
# swap_all_uuids(mer)
# # Make sure all `ConsoleType` checks resolve correctly; we want the `DX` test case to return 1 if the `Xbox360` case returns 1.
# for node in mer["MeridianNodePool"]:
    # if mer["MeridianNodePool"][node]["Type"] == "ConsoleType":
        # if mer["MeridianNodePool"][node]["Xbox360"] == 1:
            # mer["MeridianNodePool"][node]["DX"] = 1
# # Write to .mer file
# data = json.dumps(mer, indent=2)
# with open(dest_mer_json, "w") as out:
    # out.write(data)
# os.system('offsetting oct encode "' + dest_mer_json + '" "' + dest_mer + '"')

# # Handle .mtc file
# print("Writing .mtc file...")
# handle_meridian_type_count(source_mtc, dest_mtc)

# Create vertex and index buffers
print("Writing .vbuf file...")
vertex_metadata = handle_vertex_buffer(source_oct_json, source_vbuf, dest_vbuf)
print("Writing .ibuf file...")
handle_index_buffer(source_ibuf, dest_ibuf)

# Load the oct and start patching in the metadata from the vertex buffer and whatnot
print("Writing .oct file...")
oct = json.load(open(source_oct_json, "r"))

# Endian-swap any data nodes with binary blobs.
for data_node in oct["SubNetworkPool"]["SubNetwork#0"]["DataNodePool"]:
    oct["SubNetworkPool"]["SubNetwork#0"]["DataNodePool"][data_node] = handle_data_node(oct["SubNetworkPool"]["SubNetwork#0"]["DataNodePool"][data_node])

# Patch VertexStreamPool
oct["VertexStreamPool"] = vertex_metadata
oct["VertexBufferPool"]["VertexBuffer#0"]["Size"] = os.path.getsize(dest_vbuf)

# Patch NetworkBuffer if it exists
if "NetworkBuffer" in oct["SubNetworkPool"]["SubNetwork#0"]:
    oct["SubNetworkPool"]["SubNetwork#0"]["NetworkBuffer"] = b64enc(handle_network_buffer(b64dec(oct["SubNetworkPool"]["SubNetwork#0"]["NetworkBuffer"])))

# Patch TexturePool
for item in oct["TexturePool"]:
    path = oct["TexturePool"][item]["SourceFilePath"].replace(".png", ".dds").replace(".hdr", ".dds").replace(".tga", ".dds").replace(".TGA", ".dds")
    del oct["TexturePool"][item]["FileName"]
    oct["TexturePool"][item]["Data"] = "file:" + path

# Swap all UUIDs
swap_all_uuids(oct)

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
if "SceneComponentPool" in oct:
    skinRemapComponentIndex = len(oct["SceneComponentPool"])
    oct["SceneComponentPool"]["SceneComponent#" + str(skinRemapComponentIndex)] = skinRemap
else:
    skinRemapComponentIndex = 0
    oct["SceneComponentPool"] = { "SceneComponent#0": skinRemap }

# Add necessary SkinRemap references to SceneTreeNodePool
for node in oct["SceneTreeNodePool"]:
    if oct["SceneTreeNodePool"][node]["Type"] in ["SubGeometryLit", "SubGeometry"]:
        oct["SceneTreeNodePool"][node]["SceneComponentReferences"] = [skinRemapComponentIndex]

data = json.dumps(oct, indent=2)
with open(dest_oct_json, "w") as out:
    out.write(data)
os.system('offsetting oct encode -t "' + dest_oct_json + '" "' + dest_oct + '"')