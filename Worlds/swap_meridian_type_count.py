import struct

def rw_swap(in_stream, out_stream, fmt):
    if fmt[0] == '>':
        swapped_fmt = '<' + fmt[1:]
    else:
        swapped_fmt = '>' + fmt[1:]
    in_data = struct.unpack(fmt, in_stream.read(struct.calcsize(fmt)))
    out_stream.write(struct.pack(swapped_fmt, *in_data))
    return in_data

def handle_meridian_type_count(in_mtc, out_mtc):
    r_stream = open(in_mtc, "rb")
    w_stream = open(out_mtc, "wb")

    rw_swap(r_stream, w_stream, ">I")
    count_1, count_2 = rw_swap(r_stream, w_stream, ">II")
    for i in range(count_1 + count_2):
        type_count, type_name_offset = rw_swap(r_stream, w_stream, ">II")

    remaining = r_stream.read()
    w_stream.write(remaining)

    r_stream.close()
    w_stream.close()