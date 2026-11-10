import struct

def handle_bullet_metadata(source_btm, dest_btm):
    r_stream = open(source_btm, "rb")
    w_stream = open(dest_btm, "wb")

    r_stream.seek(4)
    w_stream.write(struct.pack("<I", 0xC001D00D))
    instance_count = struct.unpack(">I", r_stream.read(4))[0]
    w_stream.write(struct.pack("<I", instance_count))
    for i in range(instance_count):
        instance_offset, alignment, instance_type = struct.unpack(">IHH", r_stream.read(8))
        w_stream.write(struct.pack("<IHH", instance_offset, alignment, instance_type))
    r_stream.close()
    w_stream.close()