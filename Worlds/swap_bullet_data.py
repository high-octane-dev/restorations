import struct

def handle_bullet_data(source_btm, source_btd, dest_btd):
    # Parse metadata from BTM
    btm = open(source_btm, "rb")
    btm.seek(4)
    instance_count = struct.unpack(">I", btm.read(4))[0]
    instance_meta = []
    for i in range(instance_count):
        instance_offset, alignment, instance_type = struct.unpack(">IHH", btm.read(8))
        entry = {}
        entry["Offset"] = instance_offset
        entry["Align"] = alignment
        entry["Type"] = instance_type # Always TRI_LIST_SHAPE
        assert(instance_type == 1)
        instance_meta.append(entry)
    btm.close()

    r_stream = open(source_btd, "rb")
    w_stream = open(dest_btd, "wb")

    for meta in instance_meta:
        r_stream.seek(meta["Offset"])
        w_stream.seek(meta["Offset"])
        
        # print("Start:", meta["Offset"])
        bounding_volume_hierarchy_offset, bounding_volume_hierarchy_size, positions_offset, position_count, position_indices_offset, face_count, face_attributes_offset, face_attributes_count, attribute_indices_offset, attribute_indices_count, vertex_stride, triangle_vertex_stride, index_size, flags = struct.unpack(">IIIIIIIIIIHHHH", r_stream.read(0x30))
        
        # print("BoundingVolumeHierarchyOffset:", bounding_volume_hierarchy_offset)
        # print("BoundingVolumeHierarchySize:", bounding_volume_hierarchy_size)
        # print("PositionsOffset:", positions_offset)
        # print("PositionCount:", position_count)
        # print("PositionIndicesOffset:", position_indices_offset)
        # print("FaceCount:", face_count)
        # print("FaceAttributesOffset:", face_attributes_offset)
        # print("FaceAttributesCount:", face_attributes_count)
        # print("AttributeIndicesOffset:", attribute_indices_offset)
        # print("AttributeIndicesCount:", attribute_indices_count)
        # print("VertexStride:", vertex_stride)
        # print("TriangleVertexStride:", triangle_vertex_stride)
        # print("IndexSize:", index_size)
        # print("Flags:", flags)
        w_stream.write(struct.pack("<IIIIIIIIIIHHHH", bounding_volume_hierarchy_offset, bounding_volume_hierarchy_size, positions_offset, position_count, position_indices_offset, face_count, face_attributes_offset, face_attributes_count, attribute_indices_offset, attribute_indices_count, vertex_stride, triangle_vertex_stride, index_size, flags))
        
        # Handle btQuantizedBvh
        r_stream.seek(meta["Offset"] + bounding_volume_hierarchy_offset)
        w_stream.seek(meta["Offset"] + bounding_volume_hierarchy_offset)
        unknown = struct.unpack(">ixxxxxxxxxxxx", r_stream.read(16))[0]
        w_stream.write(struct.pack("<ixxxxxxxxxxxx", unknown))
        aabb_min_x, aabb_min_y, aabb_min_z = struct.unpack(">fffxxxx", r_stream.read(16))
        w_stream.write(struct.pack("<fffxxxx", aabb_min_x, aabb_min_y, aabb_min_z))
        aabb_max_x, aabb_max_y, aabb_max_z = struct.unpack(">fffxxxx", r_stream.read(16))
        w_stream.write(struct.pack("<fffxxxx", aabb_max_x, aabb_max_y, aabb_max_z))
        quantization_x, quantization_y, quantization_z = struct.unpack(">fffxxxx", r_stream.read(16))
        w_stream.write(struct.pack("<fffxxxx", quantization_x, quantization_y, quantization_z))
        
        bullet_version, current_node_index, use_quantization, traversal_mode = struct.unpack(">iibxxxi", r_stream.read(16))
        w_stream.write(struct.pack("<iibxxxi", bullet_version, current_node_index, use_quantization, traversal_mode))
        
        assert(use_quantization == 1)
        
        unknown2 = r_stream.read(0x64)
        w_stream.write(unknown2)
        
        subtree_header_count = struct.unpack(">I", r_stream.read(4))[0]
        w_stream.write(struct.pack("<I", subtree_header_count))
        r_stream.seek(8, 1)
        w_stream.seek(8, 1)
        
        i = 0
        while i < current_node_index:
            r_stream.seek(12, 1)
            escape_index_or_triangle_index_hi, escape_index_or_triangle_index_lo = struct.unpack(">HH", r_stream.read(4))
            r_stream.seek(-16, 1)
            
            is_bounding_leaf_node = (escape_index_or_triangle_index_hi & (1 << 14)) != 0
            
            if not is_bounding_leaf_node:
                aabb_min_x, aabb_min_y, aabb_min_z, aabb_max_x, aabb_max_y, aabb_max_z, escape_index_or_triangle_index = struct.unpack(">hhhhhhi", r_stream.read(16))
                w_stream.write(struct.pack("<hhhhhhi", aabb_min_x, aabb_min_y, aabb_min_z, aabb_max_x, aabb_max_y, aabb_max_z, escape_index_or_triangle_index))
            else:
                has_tri_index_node = ((((escape_index_or_triangle_index_hi & (1 << 14)) << 1) & (escape_index_or_triangle_index_hi & (1 << 15))) != 0)
                if has_tri_index_node:
                    packed_aab_and_triangle_index = struct.unpack(">bbbbbbbbbbbbi", r_stream.read(16))
                    w_stream.write(struct.pack("<bbbbbbbbbbbbi", *packed_aab_and_triangle_index))
                    i += 1
                    triangle_indices = struct.unpack(">hhhhhhhh", r_stream.read(16))
                    w_stream.write(struct.pack("<hhhhhhhh", *triangle_indices))
                else:
                    packed_aab_and_triangle_index = struct.unpack(">bbbbbbbbbbbbi", r_stream.read(16))
                    w_stream.write(struct.pack("<bbbbbbbbbbbbi", *packed_aab_and_triangle_index))
            i += 1
        for i in range(subtree_header_count):
            aabb_min_x, aabb_min_y, aabb_min_z, aabb_max_x, aabb_max_y, aabb_max_z, root_node_index, subtree_size = struct.unpack(">hhhhhhiixxxxxxxxxxxx", r_stream.read(32))
            w_stream.write(struct.pack(">hhhhhhiixxxxxxxxxxxx", aabb_min_x, aabb_min_y, aabb_min_z, aabb_max_x, aabb_max_y, aabb_max_z, root_node_index, subtree_size))
        # Finished handling btQuantizedBvh
        
        # Handle Positions
        r_stream.seek(meta["Offset"] + positions_offset)
        w_stream.seek(meta["Offset"] + positions_offset)
        for i in range(position_count):
            x, y, z = struct.unpack(">fff", r_stream.read(12))
            w_stream.write(struct.pack("<fff", x, y, z))
        # Handle Indices
        r_stream.seek(meta["Offset"] + position_indices_offset)
        w_stream.seek(meta["Offset"] + position_indices_offset)
        for i in range(face_count * 3):
            index = struct.unpack(">H", r_stream.read(2))[0]
            w_stream.write(struct.pack("<H", index))
        # Handle Face Attributes
        r_stream.seek(meta["Offset"] + face_attributes_offset)
        w_stream.seek(meta["Offset"] + face_attributes_offset)
        for i in range(face_attributes_count):
            surface_type, color = struct.unpack(">II", r_stream.read(8))
            w_stream.write(struct.pack("<II", surface_type, color))
        # Handle Attribute Indices
        r_stream.seek(meta["Offset"] + attribute_indices_offset)
        w_stream.seek(meta["Offset"] + attribute_indices_offset)
        for i in range(attribute_indices_count):
            index = struct.unpack(">I", r_stream.read(4))[0]
            w_stream.write(struct.pack("<I", index))
        r_stream.seek(0 if r_stream.tell() % entry["Align"] == 0 else entry["Align"] - (r_stream.tell() % entry["Align"]), 1)
        w_stream.seek(0 if w_stream.tell() % entry["Align"] == 0 else entry["Align"] - (w_stream.tell() % entry["Align"]), 1)
    r_stream.close()
    w_stream.close()