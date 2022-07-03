"""
Implementation of decoder and encoder of the xcursor file format.
Reference: https://man.archlinux.org/man/Xcursor.3
"""


import io
import struct
from typing import Union

from PIL import Image
import numpy as np

from .cursor import *


__all__ = ['open_xcursor', 'save_xcursor']

def open_xcursor(file: Union[io.BufferedReader, str], debug=False) -> Cursor:
    """load a xcursor file"""
    if isinstance(file, str):
        f = open(file, 'rb')
    else:
        f = file

    # load header
    # check magic string
    magic_str = f.read(4)
    if debug:
        print(f'magic string = {magic_str}')
    assert magic_str == b'Xcur', IOError(
        'Unrecognized file format, check the file')

    # header size
    header_size = struct.unpack('<I', f.read(4))[0]
    if debug:
        print(f'header size: {header_size}')

    # disregard the header size given. should always be 16 anyway
    header = f
    # header = io.BytesIO(file.read(header_size))

    fv0, fv1, fv2, fv3, n_entry = struct.unpack('<BBBBI', header.read(8))
    if debug:
        print(f'file version: {fv0}.{fv1}.{fv2}.{fv3}')
    if debug:
        print(f'header entries: {n_entry}')

    # load table of content
    chunks = []
    for i in range(n_entry):
        chunk_type, chunk_subtype, chunk_position = struct.unpack(
            '<III', header.read(12))

        # chunk type
        if chunk_type == 0xfffe0001:
            chunk_type = 'comment'
        elif chunk_type == 0xfffd0002:
            chunk_type = 'image'
        else:
            # unknown chunk type, warn and skip the chunk
            if debug:
                print(f'\tunknown chunk type {hex(chunk_type)}, skipping')
            continue

        # subtype represent type of info for comment chunk, side length of image chunk
        # not really needed, the same info is in the chunk header as well
        if debug:
            print(f'\t{i}: {chunk_type}, {chunk_subtype} chunk at {chunk_position}')

        chunks.append((chunk_type, chunk_position))

    # load the chunks
    cursor_frames = []
    if debug:
        print('loading chunks...')
    for i, chunk in enumerate(chunks):
        chunk_type, chunk_position = chunk
        f.seek(chunk_position)
        header_size, actual_type = struct.unpack('<II', f.read(8))

        # check chunk type again
        if actual_type == 0xfffe0001:
            actual_type = 'comment'
        elif actual_type == 0xfffd0002:
            actual_type = 'image'
        else:
            # unknown chunk type, warn and skip the chunk
            if debug:
                print(
                    f'\tchunk {i}: unknown chunk type {hex(actual_type)}, skipping')
            continue
        if chunk_type != actual_type:
            if debug:
                print(
                    f'\tchunk {i}: TOC type and actual type not match, using actual type')

        # read chunk
        # disregard header size
        if actual_type == 'image':
            subtype, version,\
                w, h, xhot, yhot, delay = struct.unpack(
                    '<IIIIIII', f.read(7 * 4))
            # unsure what subtype means, but that doesn't matter

            # read pixels
            pixel_data = f.read(w * h * 4)
            pixel_array = np.frombuffer(pixel_data, np.ubyte)
            pixel_array: np.ndarray
            pixel_array = pixel_array.reshape((w, h, 4))
            pixel_array = np.stack(
                (pixel_array[:, :, 2],
                 pixel_array[:, :, 1],
                 pixel_array[:, :, 0],
                 pixel_array[:, :, 3]),
                axis=2)
            frame_img = Image.fromarray(pixel_array, 'RGBA')
            cursor_frame = CursorFrame(frame_img, (xhot, yhot), delay)
            cursor_frames.append(cursor_frame)

        elif actual_type == 'comment':
            pass
        else:
            continue

    
    # make the cursor object and return
    cursor_obj = Cursor(cursor_frames)
    return cursor_obj


def save_xcursor(cursor: Cursor, file: Union[io.BufferedWriter, str], debug=False):
    if isinstance(file, str):
        f = open(file, 'wb')
    else:
        f = file

    # write magic string
    f.write(b'Xcur')

    header_size = 16  # header size is always 16
    header_size = struct.pack('<I', header_size)
    version = struct.pack('<BBBB', 0, 0, 1, 0)
    ntoc = struct.pack('<I', len(cursor.frames))
    f.write(header_size + version + ntoc)

    # write TOC
    # just leave enough space for now, fill in contents later
    toc_pointer = f.tell()
    spacer = bytes(len(cursor.frames) * 4*3)
    f.write(spacer)

    # write in the actual chunks
    for i, frame in enumerate(cursor.frames):
        # first fill in the TOC
        chunk_start = f.tell()
        f.seek(toc_pointer)
        chunk_type = 0xfffd0002  # image chunk
        chunk_subtype = frame.image.width
        chunk_position = chunk_start
        f.write(struct.pack('<III', chunk_type, chunk_subtype, chunk_position))
        toc_pointer = f.tell()
        f.seek(chunk_start)

        # write the chunk header
        header_size = 36
        chunk_version = 1
        header = struct.pack('<IIIIIIIII',
            header_size,
            chunk_type,
            chunk_subtype,
            chunk_version,
            
            frame.image.width,
            frame.image.height,
            frame.hot_spot[0],
            frame.hot_spot[1],
            frame.duration,
            )
        f.write(header)

        # write pixel data
        img_array = np.asarray(frame.image, dtype=np.ubyte)
        # convert RGBA to BGRA
        img_array = np.stack(
            (img_array[:,:,2],
            img_array[:,:,1],
            img_array[:,:,0],
            img_array[:,:,3]),
            2
        )
        img_bytes = bytes(img_array.reshape(-1))
        f.write(img_bytes)


    # TODO: write comment chunk as well