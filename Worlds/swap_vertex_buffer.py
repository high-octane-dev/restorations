import struct, json
import numpy as np

# PLEASE READ ME:
# U8_4 is used for both bone indices and vertex coloring. For maps I had to replace the struct format with I so it would "endian swap" colors correctly, but for characters since those have rigs those should just be BBBB. I know that makes no fucking sense but that is what worked so /shrug

FLOAT_2 = ">ff" # 1
FLOAT_3 = ">fff" # 2
U8_4 = '>BBBB' # 24
U8_4_NORMALIZED = '>BBBB' # 25
S10_10_10_NORMALIZED = '>I' # 31
S11_11_10_NORMALIZED = '>I' # 39
FLOAT16_2 = '>HH' # 44
FLOAT16_4 = '>HHHH' # 45
S1_6_3 = '>bbb' # 46

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
    sign_bit = 1 << (bits - 1)
    return (value & (sign_bit - 1)) - (value & sign_bit)

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

def rw_swap(in_stream, out_stream, fmt):
    if fmt[0] == '>':
        swapped_fmt = '<' + fmt[1:]
    else:
        swapped_fmt = '>' + fmt[1:]
    in_data = struct.unpack(fmt, in_stream.read(struct.calcsize(fmt)))
    out_stream.write(struct.pack(swapped_fmt, *in_data))

def handle_vertex_buffer(source_oct_json, source_vbuf, dest_vbuf_path):
    with open(source_oct_json, "r") as src_oct:
        oct = json.load(src_oct)
    vbuf = open(source_vbuf, "rb")
    meta = handle_vertex_buffer_impl(oct, vbuf, dest_vbuf_path)
    vbuf.close()
    return meta

def handle_vertex_buffer_impl_remap(oct, r_stream, ibuf_data, dest_vbuf):
    
    scene_node_to_remap_data_index = {}
    
    remap_datas = []
    vertex_stream_index_to_remap_data_index = {}
    for node in oct["SceneTreeNodePool"]:
        if oct["SceneTreeNodePool"][node]["Type"] == "SubGeometryLit":
            
            mesh_influences_list = []
            mesh_influences_set = set()
            vertex_stream_refs = oct["SceneTreeNodePool"][node]["VertexStreamReferences"]
            
            index_stream = oct["IndexStreamPool"][f"IndexStream#{oct["SceneTreeNodePool"][node]["IndexStreamReference"]}"]
            
            assert(index_stream["IndexBufferReference"] == 0)
            
            for stream_index in vertex_stream_refs:
                bone_indices_element_index = ""
                for element in oct["VertexStreamPool"][f"VertexStream#{stream_index}"]["Elements"]:
                    if oct["VertexStreamPool"][f"VertexStream#{stream_index}"]["Elements"][element]["Name"] == "BoneIndices":
                        bone_indices_element_index = element
                if bone_indices_element_index == "":
                    continue
                
                ibuf_offset = index_stream["IndexBufferOffset"]
                ibuf_len = index_stream["Length"] * 2
                
                vertex_indices_data = ibuf_data[ibuf_offset : ibuf_offset + ibuf_len]
                for face_index in range(0, len(vertex_indices_data) // 2, 3):
                    for face_vert in [0, 1, 2]:
                        i = face_index + face_vert
                        vertex_index = int.from_bytes(vertex_indices_data[i * 2 : (i + 1) * 2], "big")
                        
                        vertex_offset = oct["VertexStreamPool"][f"VertexStream#{stream_index}"]["VertexBufferOffset"] + vertex_index * oct["VertexStreamPool"][f"VertexStream#{stream_index}"]["Width"]
                        element_offset = oct["VertexStreamPool"][f"VertexStream#{stream_index}"]["Elements"][bone_indices_element_index]["Offset"]
                        
                        r_stream.seek(vertex_offset + element_offset)
                        values = struct.unpack(U8_4, r_stream.read(4))
                        for idx in values:
                            if idx not in mesh_influences_set:
                                mesh_influences_set.add(idx)
                                mesh_influences_list.append(idx)
            scene_node_to_remap_data_index[node] = len(remap_datas)
            for stream_index in vertex_stream_refs:
                vertex_stream_index_to_remap_data_index[stream_index] = len(remap_datas)
            remap_datas.append(mesh_influences_list)
    
    w_stream = open(dest_vbuf, "wb")
    current_output_dct = {}
    for stream_name in oct["VertexStreamPool"]:
        stream_index = int(stream_name.split("#")[1])
        elems = oct["VertexStreamPool"][stream_name]["Elements"]
        _len = oct["VertexStreamPool"][stream_name]["Length"]
        _width = oct["VertexStreamPool"][stream_name]["Width"]
        offset = oct["VertexStreamPool"][stream_name]["VertexBufferOffset"]
        
        output_vertex_buffer_offset = w_stream.tell()
        r_stream.seek(offset)
        
        current_output_width = 0
        current_output_elements = []
        for elem in elems:
            raw_type = oct["VertexStreamPool"][stream_name]["Elements"][elem]["Type"]
            name = oct["VertexStreamPool"][stream_name]["Elements"][elem]["Name"]
            if raw_type == ID_FLOAT_2:
                output_elem = {
                    'Type': ID_FLOAT_2,
                    'Name': name,
                    'Offset': current_output_width
                }
                current_output_width+=8
            elif raw_type == ID_FLOAT_3:
                output_elem = {
                    'Type': ID_FLOAT_3,
                    'Name': name,
                    'Offset': current_output_width
                }
                current_output_width+=12
            elif raw_type == ID_U8_4:
                output_elem = {
                    'Type': ID_U8_4,
                    'Name': name,
                    'Offset': current_output_width
                }
                current_output_width+=4
            elif raw_type == ID_U8_4_NORMALIZED:
                output_elem = {
                    'Type': ID_U8_4_NORMALIZED,
                    'Name': name,
                    'Offset': current_output_width
                }
                current_output_width+=4
            elif raw_type == ID_S10_10_10_NORMALIZED:
                output_elem = {
                    'Type': ID_FLOAT_3,
                    'Name': name,
                    'Offset': current_output_width
                }
                current_output_width+=12
            elif raw_type == ID_S11_11_10_NORMALIZED:
                output_elem = {
                    'Type': ID_FLOAT_3,
                    'Name': name,
                    'Offset': current_output_width
                }
                current_output_width+=12
            elif raw_type == ID_FLOAT16_2:
                output_elem = {
                    'Type': ID_FLOAT16_2,
                    'Name': name,
                    'Offset': current_output_width
                }
                current_output_width+=4
            elif raw_type == ID_FLOAT16_4:
                output_elem = {
                    'Type': ID_FLOAT16_4,
                    'Name': name,
                    'Offset': current_output_width
                }
                current_output_width+=8
            elif raw_type == ID_S1_6_3:
                output_elem = {
                    'Type': ID_FLOAT_3,
                    'Name': name,
                    'Offset': current_output_width
                }
                current_output_width+=12
            else:
                print("Unimplemented type! " + str(raw_type))
            current_output_elements.append(output_elem)
        
        current_output_dct[stream_name] = {}
        current_output_dct[stream_name]["Length"] = _len
        current_output_dct[stream_name]["Width"] = current_output_width
        current_output_dct[stream_name]["ExtraStride"] = 0
        current_output_dct[stream_name]["VertexBufferReference"] = 0
        current_output_dct[stream_name]["VertexBufferOffset"] = output_vertex_buffer_offset
        current_output_dct[stream_name]["Elements"] = {}
        for i, output_elem in enumerate(current_output_elements):
            current_output_dct[stream_name]["Elements"]["Element#" + str(i)] = output_elem
        
        for i in range(_len):
            for elem in elems:
                raw_type = oct["VertexStreamPool"][stream_name]["Elements"][elem]["Type"]
                name = oct["VertexStreamPool"][stream_name]["Elements"][elem]["Name"]
                if raw_type == ID_FLOAT_2:
                    rw_swap(r_stream, w_stream, FLOAT_2)
                elif raw_type == ID_FLOAT_3:
                    rw_swap(r_stream, w_stream, FLOAT_3)
                elif raw_type == ID_U8_4:
                    if 'BoneIndices' == name:
                        old_indices = struct.unpack(U8_4, r_stream.read(4))
                        remap_data = remap_datas[vertex_stream_index_to_remap_data_index[stream_index]]
                        remapped_indices = struct.pack(U8_4, remap_data.index(old_indices[0]), remap_data.index(old_indices[1]), remap_data.index(old_indices[2]), remap_data.index(old_indices[3]))
                        w_stream.write(remapped_indices)
                    else:
                        rw_swap(r_stream, w_stream, U8_4)
                elif raw_type == ID_U8_4_NORMALIZED:
                    rw_swap(r_stream, w_stream, U8_4_NORMALIZED)
                elif raw_type == ID_S10_10_10_NORMALIZED:
                    w_stream.write(struct.pack("<fff", *to_floats_s10(struct.unpack(S10_10_10_NORMALIZED, r_stream.read(4))[0])))
                elif raw_type == ID_S11_11_10_NORMALIZED:
                    w_stream.write(struct.pack("<fff", *to_floats_s11_11_10(struct.unpack(S11_11_10_NORMALIZED, r_stream.read(4))[0])))
                elif raw_type == ID_FLOAT16_2:
                    rw_swap(r_stream, w_stream, FLOAT16_2)
                elif raw_type == ID_FLOAT16_4:
                    rw_swap(r_stream, w_stream, FLOAT16_4)
                elif raw_type == ID_S1_6_3:
                    w_stream.write(struct.pack("<fff", *to_floats_s1_6_3(struct.unpack(S1_6_3, r_stream.read(3)))))
    w_stream.close()
    
    return current_output_dct, scene_node_to_remap_data_index, remap_datas

def handle_vertex_buffer_impl(oct, r_stream, dest_vbuf):
    w_stream = open(dest_vbuf, "wb")
    current_output_dct = {}
    for stream_name in oct["VertexStreamPool"]:
        elems = oct["VertexStreamPool"][stream_name]["Elements"]
        _len = oct["VertexStreamPool"][stream_name]["Length"]
        _width = oct["VertexStreamPool"][stream_name]["Width"]
        offset = oct["VertexStreamPool"][stream_name]["VertexBufferOffset"]
        
        output_vertex_buffer_offset = w_stream.tell()
        r_stream.seek(offset)
        
        current_output_width = 0
        current_output_elements = []
        for elem in elems:
            raw_type = oct["VertexStreamPool"][stream_name]["Elements"][elem]["Type"]
            name = oct["VertexStreamPool"][stream_name]["Elements"][elem]["Name"]
            if raw_type == ID_FLOAT_2:
                output_elem = {
                    'Type': ID_FLOAT_2,
                    'Name': name,
                    'Offset': current_output_width
                }
                current_output_width+=8
            elif raw_type == ID_FLOAT_3:
                output_elem = {
                    'Type': ID_FLOAT_3,
                    'Name': name,
                    'Offset': current_output_width
                }
                current_output_width+=12
            elif raw_type == ID_U8_4:
                output_elem = {
                    'Type': ID_U8_4,
                    'Name': name,
                    'Offset': current_output_width
                }
                current_output_width+=4
            elif raw_type == ID_U8_4_NORMALIZED:
                output_elem = {
                    'Type': ID_U8_4_NORMALIZED,
                    'Name': name,
                    'Offset': current_output_width
                }
                current_output_width+=4
            elif raw_type == ID_S10_10_10_NORMALIZED:
                output_elem = {
                    'Type': ID_FLOAT_3,
                    'Name': name,
                    'Offset': current_output_width
                }
                current_output_width+=12
            elif raw_type == ID_S11_11_10_NORMALIZED:
                output_elem = {
                    'Type': ID_FLOAT_3,
                    'Name': name,
                    'Offset': current_output_width
                }
                current_output_width+=12
            elif raw_type == ID_FLOAT16_2:
                output_elem = {
                    'Type': ID_FLOAT16_2,
                    'Name': name,
                    'Offset': current_output_width
                }
                current_output_width+=4
            elif raw_type == ID_FLOAT16_4:
                output_elem = {
                    'Type': ID_FLOAT16_4,
                    'Name': name,
                    'Offset': current_output_width
                }
                current_output_width+=8
            elif raw_type == ID_S1_6_3:
                output_elem = {
                    'Type': ID_FLOAT_3,
                    'Name': name,
                    'Offset': current_output_width
                }
                current_output_width+=12
            else:
                print("Unimplemented type! " + str(raw_type))
            current_output_elements.append(output_elem)
        
        current_output_dct[stream_name] = {}
        current_output_dct[stream_name]["Length"] = _len
        current_output_dct[stream_name]["Width"] = current_output_width
        current_output_dct[stream_name]["ExtraStride"] = 0
        current_output_dct[stream_name]["VertexBufferReference"] = 0
        current_output_dct[stream_name]["VertexBufferOffset"] = output_vertex_buffer_offset
        current_output_dct[stream_name]["Elements"] = {}
        for i, output_elem in enumerate(current_output_elements):
            current_output_dct[stream_name]["Elements"]["Element#" + str(i)] = output_elem
        
        for i in range(_len):
            for elem in elems:
                raw_type = oct["VertexStreamPool"][stream_name]["Elements"][elem]["Type"]
                name = oct["VertexStreamPool"][stream_name]["Elements"][elem]["Name"]
                if raw_type == ID_FLOAT_2:
                    rw_swap(r_stream, w_stream, FLOAT_2)
                elif raw_type == ID_FLOAT_3:
                    rw_swap(r_stream, w_stream, FLOAT_3)
                elif raw_type == ID_U8_4:
                    rw_swap(r_stream, w_stream, U8_4)
                elif raw_type == ID_U8_4_NORMALIZED:
                    rw_swap(r_stream, w_stream, U8_4_NORMALIZED)
                elif raw_type == ID_S10_10_10_NORMALIZED:
                    w_stream.write(struct.pack("<fff", *to_floats_s10(struct.unpack(S10_10_10_NORMALIZED, r_stream.read(4))[0])))
                elif raw_type == ID_S11_11_10_NORMALIZED:
                    w_stream.write(struct.pack("<fff", *to_floats_s11_11_10(struct.unpack(S11_11_10_NORMALIZED, r_stream.read(4))[0])))
                elif raw_type == ID_FLOAT16_2:
                    rw_swap(r_stream, w_stream, FLOAT16_2)
                elif raw_type == ID_FLOAT16_4:
                    rw_swap(r_stream, w_stream, FLOAT16_4)
                elif raw_type == ID_S1_6_3:
                    w_stream.write(struct.pack("<fff", *to_floats_s1_6_3(struct.unpack(S1_6_3, r_stream.read(3)))))
    w_stream.close()
    return current_output_dct
