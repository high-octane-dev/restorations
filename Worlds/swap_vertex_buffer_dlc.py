import struct, json, binascii
import numpy as np

FLOAT_2 = "ff" # 1
FLOAT_3 = "fff" # 2
U8_4 = 'BBBB' # 24
U8_4_NORMALIZED = 'BBBB' # 25
S10_10_10_NORMALIZED = 'I' # 31
S11_11_10_NORMALIZED = 'I' # 39
FLOAT16_2 = 'HH' # 44
FLOAT16_4 = 'HHHH' # 45
S1_6_3 = 'bbb' # 46

ID_FLOAT_2 = 1
ID_FLOAT_3 = 2
ID_U8_4 = 24
ID_U8_4_NORMALIZED = 25
ID_S10_10_10_NORMALIZED = 31
ID_S11_11_10_NORMALIZED = 39
ID_FLOAT16_2 = 44
ID_FLOAT16_4 = 45
ID_S1_6_3 = 46

def sign_extend(value, bits):
    signBit = 1 << (bits - 1)
    return (value & (signBit - 1)) - (value & signBit)

def to_floats_s10(int_value):
    raw1 = (int_value >> 0) & 0x3FF
    raw2 = (int_value >> 10) & 0x3FF
    raw3 = (int_value >> 20) & 0x3FF
    sv1 = sign_extend(raw1, 10) / 511
    sv2 = sign_extend(raw2, 10) / 511
    sv3 = sign_extend(raw3, 10) / 511
    return sv1, sv2, sv3

def to_floats_s11_11_10(int_value):
    raw1 = (int_value >>  0) & 0x7FF
    raw2 = (int_value >> 11) & 0x7FF
    raw3 = (int_value >> 22) & 0x3FF
    sv1 = sign_extend(raw1, 11) / 1023
    sv2 = sign_extend(raw2, 11) / 1023
    sv3 = sign_extend(raw3, 10) / 511
    return sv1, sv2, sv3

def to_floats_s1_6_3(int_values):
    x, y, z = int_values
    return x / 64.0, y / 64.0, z / 64.0

def f32_to_f16(float32):
    F16_EXPONENT_BITS = 0x1F
    F16_EXPONENT_SHIFT = 10
    F16_EXPONENT_BIAS = 15
    F16_MANTISSA_BITS = 0x3ff
    F16_MANTISSA_SHIFT =  (23 - F16_EXPONENT_SHIFT)
    F16_MAX_EXPONENT =  (F16_EXPONENT_BITS << F16_EXPONENT_SHIFT)
    a = struct.pack('>f',float32)
    b = binascii.hexlify(a)
    f32 = int(b,16)
    f16 = 0
    sign = (f32 >> 16) & 0x8000
    exponent = ((f32 >> 23) & 0xff) - 127
    mantissa = f32 & 0x007fffff
    if exponent == 128:
        f16 = sign | F16_MAX_EXPONENT
        if mantissa:
            f16 |= (mantissa & F16_MANTISSA_BITS)
    elif exponent > 15:
        f16 = sign | F16_MAX_EXPONENT
    elif exponent > -15:
        exponent += F16_EXPONENT_BIAS
        mantissa >>= F16_MANTISSA_SHIFT
        f16 = sign | exponent << F16_EXPONENT_SHIFT | mantissa
    else:
        f16 = sign
    return f16

def compute_remap_datas(tup, srcVBuf):
    remapDatas = []
    for node in tup["SceneTreeNodePool"]:
        if tup["SceneTreeNodePool"][node]["Type"] == "SubGeometryLit":
            remapData = []
            remapDataSet = set()
            
            vStreamRefs = tup["SceneTreeNodePool"][node]["VertexStreamReferences"]
            vStream0 = tup["VertexStreamPool"][f"VertexStream#{vStreamRefs[0]}"]
            boneIndicesElement = vStream0["Elements"]["Element#1"]
            
            for i in range(vStream0["Length"]):
                srcVBuf.seek(vStream0["VertexBufferOffset"] + i * vStream0["Width"] + boneIndicesElement["Offset"])
                values = struct.unpack('>' + U8_4, srcVBuf.read(4))
                for idx in values:
                    if idx not in remapDataSet:
                        remapDataSet.add(idx)
                        remapData.append(idx)
            remapDatas.append(remapData)
    srcVBuf.seek(0)
    return remapDatas

def create_vstream0_meta(vertexCount: int, vBufOffset: int):
    return {
        "Length": vertexCount,
        "Width": 24,
        "ExtraStride": 0,
        "VertexBufferReference": 0,
        "VertexBufferOffset": vBufOffset,
        "Elements": {
            "Element#0": { "Type": 2, "Name": "Position", "Offset": 0 },
            "Element#1": { "Type": 24, "Name": "BoneIndices", "Offset": 12 },
            "Element#2": { "Type": 25, "Name": "BlendWeights", "Offset": 16 },
            "Element#3": { "Type": 44, "Name": "Uv1", "Offset": 20 }
        }
    }

def create_vstream1_meta(vertexCount: int, vBufOffset: int, hasTangent: bool):
    if hasTangent:
        return {
            "Length": vertexCount,
            "Width": 24,
            "ExtraStride": 0,
            "VertexBufferReference": 0,
            "VertexBufferOffset": vBufOffset,
            "Elements": {
                "Element#0": { "Type": 45, "Name": "Tangent", "Offset": 0 },
                "Element#1": { "Type": 45, "Name": "Normal", "Offset": 8 },
                "Element#2": { "Type": 45, "Name": "Binormal", "Offset": 16 }
            }
        }
    else:
        return {
            "Length": vertexCount,
            "Width": 8,
            "ExtraStride": 0,
            "VertexBufferReference": 0,
            "VertexBufferOffset": vBufOffset,
            "Elements": {
                "Element#0": { "Type": 45, "Name": "Normal", "Offset": 0 }
            }
        }

def swizzle_meshes(tup, srcVBuf, dstVBuf, remapBones=False):
    if remapBones:
        remapDatas = compute_remap_datas(tup, srcVBuf)
    
    outStreamPool = { "VertexStreamPool": {} }
    
    currentMeshIndex = 0
    for node in tup["SceneTreeNodePool"]:
        if tup["SceneTreeNodePool"][node]["Type"] == "SubGeometryLit":
            vStreamRefs = tup["SceneTreeNodePool"][node]["VertexStreamReferences"]
            vStream0 = tup["VertexStreamPool"][f"VertexStream#{vStreamRefs[0]}"]
            vStream1 = tup["VertexStreamPool"][f"VertexStream#{vStreamRefs[1]}"]
            hasTangent = len(vStream0["Elements"]) == 6
            vertexCount = vStream0["Length"]
            
            outVStream0 = b""
            outVStream1 = b""
            
            if hasTangent:
                for i in range(vertexCount):
                    srcVBuf.seek(vStream0["VertexBufferOffset"] + i * vStream0["Width"])
                    
                    position = struct.unpack('>' + FLOAT_3, srcVBuf.read(12))
                    boneIndices = struct.unpack('>' + U8_4, srcVBuf.read(4))
                    blendWeights = struct.unpack('>' + U8_4_NORMALIZED, srcVBuf.read(4))
                    tangent = to_floats_s10(struct.unpack('>' + S10_10_10_NORMALIZED, srcVBuf.read(4))[0])
                    normal = to_floats_s10(struct.unpack('>' + S10_10_10_NORMALIZED, srcVBuf.read(4))[0])
                    binormal = to_floats_s10(struct.unpack('>' + S10_10_10_NORMALIZED, srcVBuf.read(4))[0])
                    
                    srcVBuf.seek(vStream1["VertexBufferOffset"] + i * vStream1["Width"])
                    uv1 = struct.unpack('>' + FLOAT16_2, srcVBuf.read(4))
                    
                    if remapBones:
                        remapData = remapDatas[currentMeshIndex]
                        boneIndices = remapData.index(boneIndices[0]), remapData.index(boneIndices[1]), remapData.index(boneIndices[2]), remapData.index(boneIndices[3])
                    
                    outVStream0 += struct.pack('<' + FLOAT_3, *position)
                    outVStream0 += struct.pack('<' + U8_4, *boneIndices)
                    outVStream0 += struct.pack('<' + U8_4_NORMALIZED, *blendWeights)
                    outVStream0 += struct.pack('<' + FLOAT16_2, *uv1)
                    outVStream1 += struct.pack('<' + FLOAT16_4, f32_to_f16(tangent[0]), f32_to_f16(tangent[1]), f32_to_f16(tangent[2]), 0)
                    outVStream1 += struct.pack('<' + FLOAT16_4, f32_to_f16(normal[0]), f32_to_f16(normal[1]), f32_to_f16(normal[2]), 0)
                    outVStream1 += struct.pack('<' + FLOAT16_4, f32_to_f16(binormal[0]), f32_to_f16(binormal[1]), f32_to_f16(binormal[2]), 0)          
            else:
                for i in range(vertexCount):
                    srcVBuf.seek(vStream0["VertexBufferOffset"] + i * vStream0["Width"])
                    
                    position = struct.unpack('>' + FLOAT_3, srcVBuf.read(12))
                    boneIndices = struct.unpack('>' + U8_4, srcVBuf.read(4))
                    blendWeights = struct.unpack('>' + U8_4_NORMALIZED, srcVBuf.read(4))
                    normal = to_floats_s10(struct.unpack('>' + S10_10_10_NORMALIZED, srcVBuf.read(4))[0])
                    
                    srcVBuf.seek(vStream1["VertexBufferOffset"] + i * vStream1["Width"])
                    uv1 = struct.unpack('>' + FLOAT16_2, srcVBuf.read(4))
                    
                    if remapBones:
                        remapData = remapDatas[currentMeshIndex]
                        boneIndices = remapData.index(boneIndices[0]), remapData.index(boneIndices[1]), remapData.index(boneIndices[2]), remapData.index(boneIndices[3])
                    
                    outVStream0 += struct.pack('<' + FLOAT_3, *position)
                    outVStream0 += struct.pack('<' + U8_4, *boneIndices)
                    outVStream0 += struct.pack('<' + U8_4_NORMALIZED, *blendWeights)
                    outVStream0 += struct.pack('<' + FLOAT16_2, *uv1)
                    outVStream1 += struct.pack('<' + FLOAT16_4, f32_to_f16(normal[0]), f32_to_f16(normal[1]), f32_to_f16(normal[2]), 0)
            
            outStreamPool["VertexStreamPool"][f"VertexStream#{vStreamRefs[0]}"] = create_vstream0_meta(vertexCount, dstVBuf.tell())
            dstVBuf.write(outVStream0)
            outStreamPool["VertexStreamPool"][f"VertexStream#{vStreamRefs[1]}"] = create_vstream1_meta(vertexCount, dstVBuf.tell(), hasTangent)
            dstVBuf.write(outVStream1)
            
            currentMeshIndex += 1
    
    if remapBones:
        return outStreamPool, remapDatas
    else:
        return outStreamPool, None

def handle_vertex_buffer_impl_remap(tup, r_stream, dest_vbuf):
    w_stream = open(dest_vbuf, "wb")
    vertex_stream_pool, remap_datas = swizzle_meshes(tup, r_stream, w_stream, remapBones=True)
    w_stream.close()
    
    scene_node_to_remap_data_index = {}
    current_mesh_index = 0
    for node in tup["SceneTreeNodePool"]:
        if tup["SceneTreeNodePool"][node]["Type"] == "SubGeometryLit":
            scene_node_to_remap_data_index[node] = current_mesh_index
            current_mesh_index += 1
    
    return vertex_stream_pool["VertexStreamPool"], scene_node_to_remap_data_index, remap_datas

def handle_vertex_buffer_impl(tup, r_stream, dest_vbuf):
    w_stream = open(dest_vbuf, "wb")
    vertex_stream_pool, _ = swizzle_meshes(tup, r_stream, w_stream, remapBones=False)
    w_stream.close()
    return vertex_stream_pool["VertexStreamPool"]

# def assert_vertex_stream_format(tup):
    # for node in tup["SceneTreeNodePool"]:
        # if tup["SceneTreeNodePool"][node]["Type"] == "SubGeometryLit":
            # vStreamRefs = tup["SceneTreeNodePool"][node]["VertexStreamReferences"]
            # assert(len(vStreamRefs) == 2)
            
            # vStream0 = tup["VertexStreamPool"][f"VertexStream#{vStreamRefs[0]}"]
            # vStream1 = tup["VertexStreamPool"][f"VertexStream#{vStreamRefs[1]}"]
            
            # assert(len(vStream0["Elements"]) == 4 or len(vStream0["Elements"]) == 6)
            # hasTangent = len(vStream0["Elements"]) == 6
            
            # assert(vStream0["Elements"]["Element#0"]["Name"] == "Position")
            # assert(vStream0["Elements"]["Element#1"]["Name"] == "BoneIndices")
            # assert(vStream0["Elements"]["Element#2"]["Name"] == "BlendWeights")
            
            # if hasTangent:
                # assert(vStream0["Elements"]["Element#3"]["Name"] == "Tangent")
                # assert(vStream0["Elements"]["Element#4"]["Name"] == "Normal")
                # assert(vStream0["Elements"]["Element#5"]["Name"] == "Binormal")
            # else:
                # assert(vStream0["Elements"]["Element#3"]["Name"] == "Normal")
            
            # assert(len(vStream1["Elements"]) == 1)
            # assert(vStream1["Elements"]["Element#0"]["Name"] == "Uv1")