import base64, json, struct, io
import numpy as np

SRC_ENDIAN = '>'
DST_ENDIAN = '<'

def b64dec(_str):
    return base64.b64decode(_str[7:] + '==')

def b64enc(_str):
    return "base64:" + base64.b64encode(_str).decode().rstrip("=")

def handle_clip_data(buf):
    src = io.BytesIO(buf)
    dest = io.BytesIO()
    file_size = len(buf)

    start, end, command_block_count, timeline_count, static_data_offset = struct.unpack(SRC_ENDIAN+"ffhhI", src.read(16))
    dest.write(struct.pack(DST_ENDIAN+"ffhhI", start, end, command_block_count, timeline_count, static_data_offset))

    command_block_offsets = []
    timeline_offsets = []

    for i in range(command_block_count):
        read_num = struct.unpack(SRC_ENDIAN+"I", src.read(4))[0]
        dest.write(struct.pack(DST_ENDIAN+"I", read_num))
        command_block_offsets.append(read_num)

    for i in range(timeline_count):
        read_num = struct.unpack(SRC_ENDIAN+"I", src.read(4))[0]
        dest.write(struct.pack(DST_ENDIAN+"I", read_num))
        timeline_offsets.append(read_num)

    # print("ClipDataBlock: [Start = " + str(start) + ", End = " + str(end) + ", CommandBlockCount = " + str(command_block_count) + ", TimelineCount = " + str(timeline_count) + ", StaticDataOffset = " + hex(static_data_offset) + "]")
    
    command_blocks_end_offset = timeline_offsets[0] if len(timeline_offsets) > 0 else static_data_offset

    for i in range(len(command_block_offsets)):
        next_offset = command_blocks_end_offset if i == len(command_block_offsets) - 1 else command_block_offsets[i + 1]
        command_block_len = next_offset - command_block_offsets[i]
        # print("Reading Command Block...")
        
        computed_value_count, count = struct.unpack(SRC_ENDIAN+"hh", src.read(4))
        dest.write(struct.pack(DST_ENDIAN+"hh", computed_value_count, count))
        
        unk_table = []
        for j in range(count):
            read_num = struct.unpack(SRC_ENDIAN+"h", src.read(2))[0]
            dest.write(struct.pack(DST_ENDIAN+"h", read_num))
            
            unk_table.append(read_num)
            
        unk_remaining = struct.unpack(SRC_ENDIAN+"h", src.read(2))[0]
        dest.write(struct.pack(DST_ENDIAN+"h", unk_remaining))
        
        offset_in_section = 6 + count * 2
        unk_data = []
        unk_data_len = (command_block_len - offset_in_section) / 2
        for j in range(int(round(unk_data_len))):
            read_num = struct.unpack(SRC_ENDIAN+"h", src.read(2))[0]
            dest.write(struct.pack(DST_ENDIAN+"h", read_num))
            
            unk_data.append(read_num)

    for i in range(len(timeline_offsets)):
        next_offset = static_data_offset if i == len(timeline_offsets) - 1 else timeline_offsets[i + 1]
        command_len = next_offset - timeline_offsets[i]
        src.seek(timeline_offsets[i])
        dest.seek(timeline_offsets[i])
        
        flags, first_independent_value, last_independent_value = struct.unpack(SRC_ENDIAN+"Iff", src.read(12))
        dest.write(struct.pack(DST_ENDIAN+"Iff", flags, first_independent_value, last_independent_value))
        # pre infinity, post infinity
        segment_count = (flags & 0xFFF00000) >> 20
        curve_count = (flags & 0xFFC00) >> 10
        curve_type = (flags & 0x3C0) >> 6
        post_infinity_type = (flags & 0x38) >> 3
        pre_infinity_type = (flags & 0x7)
        # print("Reading Timeline", i, ":", segment_count, curve_count, curve_type, post_infinity_type, pre_infinity_type)
        if curve_type == 0:
            unk2 = []
            for j in range(curve_count * 4):
                read_num = struct.unpack(SRC_ENDIAN+"f", src.read(4))[0]
                dest.write(struct.pack(DST_ENDIAN+"f", read_num))
                
                unk2.append(read_num)
            unk3 = []
            for j in range(segment_count):
                read_num = struct.unpack(SRC_ENDIAN+"H", src.read(2))[0]
                dest.write(struct.pack(DST_ENDIAN+"H", read_num))
                
                unk3.append(read_num)
            unk4 = []
            for j in range(segment_count * curve_count * 4):
                read_num = struct.unpack(SRC_ENDIAN+"H", src.read(2))[0]
                dest.write(struct.pack(DST_ENDIAN+"H", read_num))
                
                unk4.append(read_num)
            if src.tell() % 4 != 0:
                src.seek(2, 1)
                dest.write(b"\xEE\xEE")
        elif curve_type == 2:
            unk2 = []
            for j in range(curve_count * 4):
                read_num = struct.unpack(SRC_ENDIAN+"f", src.read(4))[0]
                dest.write(struct.pack(DST_ENDIAN+"f", read_num))
                
                unk2.append(read_num)
            unk3 = []
            for j in range(segment_count):
                read_num = struct.unpack(SRC_ENDIAN+"f", src.read(4))[0]
                dest.write(struct.pack(DST_ENDIAN+"f", read_num))
                
                unk3.append(read_num)
            unk4 = []
            for j in range(segment_count * curve_count * 4):
                read_num = struct.unpack(SRC_ENDIAN+"H", src.read(2))[0]
                dest.write(struct.pack(DST_ENDIAN+"H", read_num))
                
                unk4.append(read_num)
            if src.tell() % 4 != 0:
                src.seek(2, 1)
                dest.write(b"\xEE\xEE")
        elif curve_type == 4:
            unk2 = []
            for j in range(curve_count * 2):
                read_num = struct.unpack(SRC_ENDIAN+"f", src.read(4))[0]
                dest.write(struct.pack(DST_ENDIAN+"f", read_num))
                
                unk2.append(read_num)
            
            unk3 = []
            for j in range(segment_count):
                read_num = struct.unpack(SRC_ENDIAN+"H", src.read(2))[0]
                dest.write(struct.pack(DST_ENDIAN+"H", read_num))
                
                unk3.append(read_num)
            
            if segment_count % 2 != 0:
                src.seek(2, 1)
                dest.seek(2, 1)
            
            unk4 = []
            for j in range(segment_count * curve_count * 4):
                read_num = struct.unpack(SRC_ENDIAN+"f", src.read(4))[0]
                dest.write(struct.pack(DST_ENDIAN+"f", read_num))
                
                unk4.append(read_num)
            
            if src.tell() % 4 != 0:
                src.seek(2, 1)
                dest.write(b"\xEE\xEE")
        else:
            print("Unimplemented timeline of curve type: " + str(curve_type) + ", flags: " + hex(flags) + " ! Please notify author!")
            print("Aborting...")
            exit(-1)
        
        if command_len != 0 and src.tell() - timeline_offsets[i] != command_len:
            print("Failed to parse timeline:", i, "at offset", timeline_offsets[i], "read", src.tell() - timeline_offsets[i], "out of", command_len)
            print("Aborting...")
            exit(-1)
        if command_len == 0 and src.tell() != file_size:
            print("Failed to parse final timeline:", i, "at offset", timeline_offsets[i], "read", src.tell() - timeline_offsets[i], "out of", file_size - timeline_offsets[i])
            print("Aborting...")
            exit(-1)
    size_remaining = file_size - src.tell()
    float_count = size_remaining >> 2
    for j in range(float_count):
        read_num = struct.unpack(SRC_ENDIAN+"f", src.read(4))[0]
        dest.write(struct.pack(DST_ENDIAN+"f", read_num))

    return dest.getvalue()

def handle_relationship_data(buf):
    src = io.BytesIO(buf)
    dest = io.BytesIO()
    file_size = len(buf)

    start, end, phase_offset, command_block_count, timeline_count, static_data_offset = struct.unpack(SRC_ENDIAN+"ffIhhI", src.read(20))
    dest.write(struct.pack(DST_ENDIAN+"ffIhhI", start, end, phase_offset, command_block_count, timeline_count, static_data_offset))

    command_block_offsets = []
    timeline_offsets = []
    
    for i in range(command_block_count):
        read_num = struct.unpack(SRC_ENDIAN+"I", src.read(4))[0]
        dest.write(struct.pack(DST_ENDIAN+"I", read_num))
        command_block_offsets.append(read_num)

    for i in range(timeline_count):
        read_num = struct.unpack(SRC_ENDIAN+"I", src.read(4))[0]
        dest.write(struct.pack(DST_ENDIAN+"I", read_num))
        timeline_offsets.append(read_num)

    # print("RelationshipDataBlock: [Start = " + str(start) + ", End = " + str(end) + ", CommandBlockCount = " + str(command_block_count) + ", TimelineCount = " + str(timeline_count) + ", StaticDataOffset = " + hex(static_data_offset) + "]")

    for i in range(len(command_block_offsets)):
        next_offset = timeline_offsets[0] if i == len(command_block_offsets) - 1 else command_block_offsets[i + 1]
        command_block_len = next_offset - command_block_offsets[i]
        # print("Reading Command Block...")
        
        computed_value_count, count = struct.unpack(SRC_ENDIAN+"hh", src.read(4))
        dest.write(struct.pack(DST_ENDIAN+"hh", computed_value_count, count))
        
        unk_table = []
        for j in range(count):
            read_num = struct.unpack(SRC_ENDIAN+"h", src.read(2))[0]
            dest.write(struct.pack(DST_ENDIAN+"h", read_num))
            
            unk_table.append(read_num)
            
        unk_remaining = struct.unpack(SRC_ENDIAN+"h", src.read(2))[0]
        dest.write(struct.pack(DST_ENDIAN+"h", unk_remaining))
        
        offset_in_section = 6 + count * 2
        unk_data = []
        unk_data_len = (command_block_len - offset_in_section) / 2
        for j in range(int(round(unk_data_len))):
            read_num = struct.unpack(SRC_ENDIAN+"h", src.read(2))[0]
            dest.write(struct.pack(DST_ENDIAN+"h", read_num))
            
            unk_data.append(read_num)
    for i in range(len(timeline_offsets)):
        next_offset = static_data_offset if i == len(timeline_offsets) - 1 else timeline_offsets[i + 1]
        command_len = next_offset - timeline_offsets[i]
        src.seek(timeline_offsets[i])
        dest.seek(timeline_offsets[i])
        
        input_index, flags, first_independent_value, last_independent_value = struct.unpack(SRC_ENDIAN+"IIff", src.read(16))
        dest.write(struct.pack(DST_ENDIAN+"IIff", input_index, flags, first_independent_value, last_independent_value))
        # pre infinity, post infinity
        segment_count = (flags & 0xFFF00000) >> 20
        curve_count = (flags & 0xFFE00) >> 9
        curve_type = (flags & 0x1C0) >> 6
        post_infinity_type = (flags & 0x38) >> 3
        pre_infinity_type = (flags & 0x7)
        if curve_type == 8:
            curve_type = 0
        # print("Reading Timeline", i, ":", segment_count, curve_count, curve_type, post_infinity_type, pre_infinity_type, src.tell())
        if curve_type == 0:
            unk2 = []
            for j in range(curve_count * 4):
                read_num = struct.unpack(SRC_ENDIAN+"f", src.read(4))[0]
                dest.write(struct.pack(DST_ENDIAN+"f", read_num))
                
                unk2.append(read_num)
            unk3 = []
            for j in range(segment_count):
                read_num = struct.unpack(SRC_ENDIAN+"H", src.read(2))[0]
                dest.write(struct.pack(DST_ENDIAN+"H", read_num))
                
                unk3.append(read_num)
            unk4 = []
            for j in range(segment_count * curve_count * 4):
                read_num = struct.unpack(SRC_ENDIAN+"H", src.read(2))[0]
                dest.write(struct.pack(DST_ENDIAN+"H", read_num))
                
                unk4.append(read_num)
            if src.tell() % 4 != 0:
                src.seek(2, 1)
                dest.write(b"\xEE\xEE")
        else:
            print("Unimplemented timeline of curve type: " + str(curve_type) + ", flags: " + hex(flags) + " ! Please notify author!")
            print("Aborting...")
            exit(-1)
        
        if command_len != 0 and src.tell() - timeline_offsets[i] != command_len:
            print("Failed to parse timeline:", i, "at offset", timeline_offsets[i], "read", src.tell() - timeline_offsets[i], "out of", command_len)
            print("Aborting...")
            exit(-1)
        if command_len == 0 and src.tell() != file_size:
            print("Failed to parse final timeline:", i, "at offset", timeline_offsets[i], "read", src.tell() - timeline_offsets[i], "out of", file_size - timeline_offsets[i])
            print("Aborting...")
            exit(-1)
    size_remaining = file_size - src.tell()
    # float_count = size_remaining >> 2
    # for j in range(float_count):
        # read_num = struct.unpack(SRC_ENDIAN+"f", src.read(4))[0]
        # dest.write(struct.pack(DST_ENDIAN+"f", read_num))
    second_block_start_offset = src.tell()
    # We doing this shit again
    start, end, phase_offset, command_block_count, timeline_count, static_data_offset = struct.unpack(SRC_ENDIAN+"ffIhhI", src.read(20))
    dest.write(struct.pack(DST_ENDIAN+"ffIhhI", start, end, phase_offset, command_block_count, timeline_count, static_data_offset))

    command_block_offsets = []
    timeline_offsets = []

    for i in range(command_block_count):
        read_num = struct.unpack(SRC_ENDIAN+"I", src.read(4))[0]
        dest.write(struct.pack(DST_ENDIAN+"I", read_num))
        command_block_offsets.append(read_num)

    for i in range(timeline_count):
        read_num = struct.unpack(SRC_ENDIAN+"I", src.read(4))[0]
        dest.write(struct.pack(DST_ENDIAN+"I", read_num))
        timeline_offsets.append(read_num)

    # print("RelationshipDataBlock: [Start = " + str(start) + ", End = " + str(end) + ", CommandBlockCount = " + str(command_block_count) + ", TimelineCount = " + str(timeline_count) + ", StaticDataOffset = " + hex(static_data_offset) + "]")

    for i in range(len(command_block_offsets)):
        next_offset = timeline_offsets[0] if i == len(command_block_offsets) - 1 else command_block_offsets[i + 1]
        command_block_len = next_offset - command_block_offsets[i]
        # print("Reading Command Block...")
        
        computed_value_count, count = struct.unpack(SRC_ENDIAN+"hh", src.read(4))
        dest.write(struct.pack(DST_ENDIAN+"hh", computed_value_count, count))
        
        unk_table = []
        for j in range(count):
            read_num = struct.unpack(SRC_ENDIAN+"h", src.read(2))[0]
            dest.write(struct.pack(DST_ENDIAN+"h", read_num))
            
            unk_table.append(read_num)
            
        unk_remaining = struct.unpack(SRC_ENDIAN+"h", src.read(2))[0]
        dest.write(struct.pack(DST_ENDIAN+"h", unk_remaining))
        
        offset_in_section = 6 + count * 2
        unk_data = []
        unk_data_len = (command_block_len - offset_in_section) / 2
        for j in range(int(round(unk_data_len))):
            read_num = struct.unpack(SRC_ENDIAN+"h", src.read(2))[0]
            dest.write(struct.pack(DST_ENDIAN+"h", read_num))
            
            unk_data.append(read_num)

    for i in range(len(timeline_offsets)):
        next_offset = static_data_offset if i == len(timeline_offsets) - 1 else timeline_offsets[i + 1]
        command_len = next_offset - timeline_offsets[i]
        src.seek(timeline_offsets[i] + second_block_start_offset)
        dest.seek(timeline_offsets[i] + second_block_start_offset)
        
        input_index, flags, first_independent_value, last_independent_value = struct.unpack(SRC_ENDIAN+"IIff", src.read(16))
        dest.write(struct.pack(DST_ENDIAN+"IIff", input_index, flags, first_independent_value, last_independent_value))
        # pre infinity, post infinity
        segment_count = (flags & 0xFFF00000) >> 20
        curve_count = (flags & 0xFFE00) >> 9
        curve_type = (flags & 0x1C0) >> 6
        post_infinity_type = (flags & 0x38) >> 3
        pre_infinity_type = (flags & 0x7)
        if curve_type == 8:
            curve_type = 0
        # print("Reading Timeline", i, ":", segment_count, curve_count, curve_type, post_infinity_type, pre_infinity_type, src.tell())
        if curve_type == 0:            
            unk2 = []
            for j in range(curve_count * 4):
                read_num = struct.unpack(SRC_ENDIAN+"f", src.read(4))[0]
                dest.write(struct.pack(DST_ENDIAN+"f", read_num))
                
                unk2.append(read_num)
            unk3 = []
            for j in range(segment_count):
                read_num = struct.unpack(SRC_ENDIAN+"H", src.read(2))[0]
                dest.write(struct.pack(DST_ENDIAN+"H", read_num))
                
                unk3.append(read_num)
            unk4 = []
            for j in range(segment_count * curve_count * 4):
                read_num = struct.unpack(SRC_ENDIAN+"H", src.read(2))[0]
                dest.write(struct.pack(DST_ENDIAN+"H", read_num))
                
                unk4.append(read_num)
            if src.tell() % 4 != 0:
                src.seek(2, 1)
                dest.write(b"\xEE\xEE")
        else:
            print("Unimplemented timeline of curve type: " + str(curve_type) + ", flags: " + hex(flags) + " ! Please notify author!")
            print("Aborting...")
            exit(-1)
        
        if command_len != 0 and src.tell() - timeline_offsets[i] - second_block_start_offset != command_len:
            print("Failed to parse timeline:", i, "at offset", timeline_offsets[i], "read", src.tell() - timeline_offsets[i], "out of", command_len)
            print("Aborting...")
            exit(-1)
        if command_len == 0 and src.tell() != file_size:
            print("Failed to parse final timeline:", i, "at offset", timeline_offsets[i], "read", src.tell() - timeline_offsets[i], "out of", file_size - timeline_offsets[i])
            print("Aborting...")
            exit(-1)
    size_remaining = file_size - src.tell()
    float_count = size_remaining >> 2
    for j in range(float_count):
        read_num = struct.unpack(SRC_ENDIAN+"f", src.read(4))[0]
        dest.write(struct.pack(DST_ENDIAN+"f", read_num))
    # print("Done processing RelationshipDataBlock!")
    return dest.getvalue()

def handle_u32array(buf):
    arr = np.frombuffer(buf, dtype=np.uint32)
    swapped = arr.byteswap()
    return swapped.tobytes()

def handle_u16array(buf):
    arr = np.frombuffer(buf, dtype=np.uint16)
    swapped = arr.byteswap()
    return swapped.tobytes()

def handle_data_node(node):
    if node["Type"] == "ClipData":
        node["ClipDataBlock"] = b64enc(handle_clip_data(b64dec(node["ClipDataBlock"])))
    elif node["Type"] == "RelationshipData":
        node["RelationshipDataBlock"] = b64enc(handle_relationship_data(b64dec(node["RelationshipDataBlock"])))
    elif node["Type"] == "UberConstraintData":
        node["UberConstraintDataBlock"] = b64enc(handle_u32array(b64dec(node["UberConstraintDataBlock"])))
    return node