import struct, json

def handle_index_buffer(source_ibuf, dest_ibuf):
    ibuf = open(source_ibuf, "rb")
    handle_index_buffer_impl(ibuf, dest_ibuf)
    ibuf.close()

def handle_index_buffer_impl(r_stream, dest_ibuf):
    w_stream = open(dest_ibuf, "wb")

    size = r_stream.seek(0,2) // 2
    r_stream.seek(0)

    buffer = []

    for i in range(size):
        buffer.append(struct.unpack('>h', r_stream.read(2))[0])

    for i in range(size):
        w_stream.write(struct.pack('<h', buffer[i]))
    
    w_stream.close()