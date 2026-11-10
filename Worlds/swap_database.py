import struct, json

def handle_database(src_dbl, dst_dbl):
    r_stream = open(src_dbl, 'rb')
    w_stream = open(dst_dbl, 'wb')
    
    c_skip_count = r_stream.read(8)
    w_stream.write(c_skip_count)
    r_stream.seek(8, 1)
    w_stream.write(b"GBWIN\x00\x00\x00")
    
    version, fileFlags, chunks, maxChunkSize = struct.unpack(">IIII", r_stream.read(16))
    w_stream.write(struct.pack("<IIII", version, fileFlags, chunks, maxChunkSize))
    
    for i in range(chunks):
        chunkType, flags, size, version = struct.unpack(">HHIH", r_stream.read(10))
        w_stream.write(struct.pack("<HHIH", chunkType, flags, size, version))
        chunkName = r_stream.read(54) # actually a char[32] + 22 bytes of padding but who gaf
        w_stream.write(chunkName)
        
        chunkStartOffset = r_stream.tell()
        
        # ChunkType::Paths
        if chunkType == 0x203:
            # Handle Record List
            recordCount, recordListFlags = struct.unpack(">HH", r_stream.read(4))
            w_stream.write(struct.pack("<HH", recordCount, recordListFlags))            
            for j in range(recordCount):
                offset = struct.unpack(">I", r_stream.read(4))[0]
                w_stream.write(struct.pack("<I", offset))
            # Handle Paths
            for j in range(recordCount):
                pathName = r_stream.read(64)
                w_stream.write(pathName)
                vertexCount, pathFlags = struct.unpack(">II", r_stream.read(8))
                w_stream.write(struct.pack("<II", vertexCount, pathFlags))
                for k in range(vertexCount):
                    x, y, z = struct.unpack(">fff", r_stream.read(12))
                    w_stream.write(struct.pack("<fff", x, y, z))
            currentlyRead = r_stream.tell() - chunkStartOffset
            remaining = r_stream.read(size - currentlyRead)
            w_stream.write(remaining)
        # ChunkType::Curves
        elif chunkType == 0x210:
            # Handle Record List
            recordCount, recordListFlags = struct.unpack(">HH", r_stream.read(4))
            w_stream.write(struct.pack("<HH", recordCount, recordListFlags))
            recordOffsets = []
            for j in range(recordCount):
                offset = struct.unpack(">I", r_stream.read(4))[0]
                recordOffsets.append(offset)
                w_stream.write(struct.pack("<I", offset))
            # Handle Curves
            for j in range(recordCount):
                splineFlags, pointCount, knotCount, reserved0, reserved1, reserved2, reserved3, reserved4 = struct.unpack(">IIIIIIII", r_stream.read(32))
                w_stream.write(struct.pack("<IIIIIIII", splineFlags, pointCount, knotCount, reserved0, reserved1, reserved2, reserved3, reserved4))
                for k in range(pointCount):
                    x, y, z = struct.unpack(">fff", r_stream.read(12))
                    w_stream.write(struct.pack("<fff", x, y, z))
                for k in range(knotCount):
                    knot = struct.unpack(">f", r_stream.read(4))[0]
                    w_stream.write(struct.pack("<f", knot))
                if j < recordCount - 1:
                    splineNameSize = (recordOffsets[j + 1] + chunkStartOffset) - r_stream.tell()
                    remaining = r_stream.read(splineNameSize)
                    w_stream.write(remaining)
                else:
                    splineNameSize = (chunkStartOffset + size) - r_stream.tell()
                    remaining = r_stream.read(splineNameSize)
                    w_stream.write(remaining)
        # ChunkType::TerrainList
        elif chunkType == 0x83:
            # Handle Record List
            recordCount, recordListFlags = struct.unpack(">HH", r_stream.read(4))
            w_stream.write(struct.pack("<HH", recordCount, recordListFlags))
            for j in range(recordCount):
                offset = struct.unpack(">I", r_stream.read(4))[0]
                w_stream.write(struct.pack("<I", offset))
            currentlyRead = r_stream.tell() - chunkStartOffset
            remaining = r_stream.read(size - currentlyRead)
            w_stream.write(remaining)
        else:
            print("Unknown Chunk Type! " + str(chunkType))
            exit(-1)
    r_stream.close()
    w_stream.close()
# handle_database("./tokyo_a/tokyo_a.dbl", "./tokyo_a/tokyo_a_le.dbl")