import sys
import os
import struct
import zlib
from PyQt6.QtWidgets import (QApplication, QMainWindow, QPushButton, QLabel, 
                             QVBoxLayout, QHBoxLayout, QWidget, QFileDialog, QTextEdit, QFrame, QComboBox, QGroupBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap
from PIL import Image

# STANDARD DEFLATE CONSTANTS
LENGTHBASE = [3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31, 35, 43, 51, 59, 67, 83, 99, 115, 131, 163, 195, 227, 258]
LENGTHEXTRA = [0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 0]
DISTANCEBASE = [1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193, 257, 385, 513, 769, 1025, 1537, 2049, 3073, 4097, 6145, 8193, 12289, 16385, 24577]
DISTANCEEXTRA = [0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 13, 13]
CLCL_ORDER = [16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15]

# SIFLI CUSTOM DECOMPRESSOR 
class BitStream:
    def __init__(self, data):
        self.data = data
        self.bp = 0
        self.length = len(data) * 8

    def read_bit(self):
        if self.bp >= self.length:
            raise EOFError("End of stream reached")
        bit = (self.data[self.bp >> 3] >> (self.bp & 7)) & 1
        self.bp += 1
        return bit

    def read_bits(self, numbits):
        val = 0
        for i in range(numbits):
            val |= (self.read_bit() << i)
        return val

    def align_4bytes(self):
        byte_idx = (self.bp + 7) >> 3
        byte_idx = (byte_idx + 3) & ~3
        self.bp = byte_idx * 8

def make_huffman_tree(lengths):
    max_len = max(lengths) if lengths else 0
    bl_count = [0] * (max_len + 1)
    for l in lengths:
        if l != 0:
            bl_count[l] += 1

    next_code = [0] * (max_len + 1)
    code = 0
    for bits in range(1, max_len + 1):
        code = (code + bl_count[bits - 1]) << 1
        next_code[bits] = code

    tree = {}
    for i, l in enumerate(lengths):
        if l != 0:
            tree[(l, next_code[l])] = i
            next_code[l] += 1
    return tree

def decode_symbol(stream, tree):
    code = 0
    length = 0
    while True:
        code = (code << 1) | stream.read_bit()
        length += 1
        if (length, code) in tree:
            return tree[(length, code)]
        if length > 15:
            raise Exception("Invalid Huffman sequence")

def decode_sifli_ezip(data, row_size):
    stream = BitStream(data)
    
    hlit = stream.read_bits(5) + 257
    hdist = stream.read_bits(5) + 1
    hclen = stream.read_bits(4) + 4

    code_length_lengths = [0] * 19
    for i in range(hclen):
        code_length_lengths[CLCL_ORDER[i]] = stream.read_bits(3)

    cl_tree = make_huffman_tree(code_length_lengths)

    lengths = []
    while len(lengths) < hlit + hdist:
        sym = decode_symbol(stream, cl_tree)
        if sym <= 15:
            lengths.append(sym)
        elif sym == 16:
            rep = stream.read_bits(2) + 3
            lengths.extend([lengths[-1]] * rep)
        elif sym == 17:
            rep = stream.read_bits(3) + 3
            lengths.extend([0] * rep)
        elif sym == 18:
            rep = stream.read_bits(7) + 11
            lengths.extend([0] * rep)

    tree_ll = make_huffman_tree(lengths[:hlit])
    tree_d = make_huffman_tree(lengths[hlit:])

    stream.align_4bytes()
    out_data = bytearray()

    while True:
        bfinal = stream.read_bit()
        btype = stream.read_bits(2)

        if btype == 0:
            stream.bp = (stream.bp + 7) & ~7 
            byte_idx = stream.bp >> 3
            length = stream.data[byte_idx] | (stream.data[byte_idx+1] << 8)
            byte_idx += 4
            out_data.extend(stream.data[byte_idx : byte_idx + length])
            stream.bp = (byte_idx + length) * 8
        elif btype in (1, 2):
            while True:
                sym = decode_symbol(stream, tree_ll)
                if sym < 256:
                    out_data.append(sym)
                elif sym == 256:
                    break
                else:
                    idx = sym - 257
                    length = LENGTHBASE[idx] + stream.read_bits(LENGTHEXTRA[idx])
                    dist_sym = decode_symbol(stream, tree_d)
                    dist = DISTANCEBASE[dist_sym] + stream.read_bits(DISTANCEEXTRA[dist_sym])

                    for _ in range(length):
                        out_data.append(out_data[-dist])
        else:
            raise Exception("Invalid Block Type")

        stream.align_4bytes()
        if bfinal:
            break

    return out_data

def unfilter_png_blocks(data, width, height, bpp, block_row_size, has_filters):
    out = bytearray(width * height * bpp)
    stride = width * bpp
    
    if not has_filters:
        return bytearray(data[:len(out)])

    row_len = stride + 1

    def paeth(a, b, c):
        p = a + b - c
        pa = abs(p - a)
        pb = abs(p - b)
        pc = abs(p - c)
        if pa <= pb and pa <= pc: return a
        if pb <= pc: return b
        return c

    for y in range(height):
        in_row_start = y * row_len
        if in_row_start >= len(data): break
        filter_type = data[in_row_start]
        in_row = data[in_row_start + 1 : in_row_start + 1 + stride]
        
        is_first_row_in_block = (y % block_row_size == 0)

        for x in range(stride):
            if x >= len(in_row): break
            raw = in_row[x]
            left = out[y * stride + x - bpp] if x >= bpp else 0
            up = 0 if is_first_row_in_block else out[(y - 1) * stride + x]
            up_left = 0 if (is_first_row_in_block or x < bpp) else out[(y - 1) * stride + x - bpp]

            if filter_type == 0: val = raw
            elif filter_type == 1: val = (raw + left) & 0xFF
            elif filter_type == 2: val = (raw + up) & 0xFF
            elif filter_type == 3: val = (raw + (left + up) // 2) & 0xFF
            elif filter_type == 4: val = (raw + paeth(left, up, up_left)) & 0xFF
            else: val = raw

            out[y * stride + x] = val

    return out

# DECODER THREAD 
class DecoderThread(QThread):
    log_signal = pyqtSignal(str)
    image_ready_signal = pyqtSignal(str, dict)
    error_signal = pyqtSignal(str)

    def __init__(self, bin_filepath, color_override):
        super().__init__()
        self.bin_filepath = bin_filepath
        self.color_override = color_override

    def run(self):
        try:
            self.log_signal.emit(f"Opening {os.path.basename(self.bin_filepath)}...")
            with open(self.bin_filepath, 'rb') as f:
                data = f.read()

            header_val = struct.unpack("<I", data[:4])[0]
            color_format = header_val & 0x1F
            width = (header_val >> 10) & 0x7FF
            height = (header_val >> 21) & 0x7FF

            comp_data = data[20:]
            row_size = struct.unpack(">H", comp_data[0:2])[0]
            num_blocks = struct.unpack(">H", comp_data[2:4])[0]
            
            ctrl = data[8]
            filterless_flag = data[4 + 12] & 0x0F
            has_filters = (filterless_flag != 1)
            one_huffcode = ((ctrl >> 4) > 2) and ((ctrl >> 4) != 5)

            meta = {
                'w': width, 'h': height, 'row_size': row_size, 
                'ctrl': ctrl, 'num_blocks': num_blocks,
                'has_filters': has_filters, 'one_huffcode': one_huffcode,
                'color_format': color_format, 'file_size': len(data)
            }

            self.log_signal.emit(f"[EZIP] Block Rows: {row_size}, Blocks: {num_blocks}")
            
            table_size = 4 * (num_blocks + 1)
            raw_stream = comp_data[table_size:]

            if one_huffcode:
                self.log_signal.emit("Decompressing Factory Stream (Shared Huffman)...")
                lz77_filtered = decode_sifli_ezip(raw_stream, row_size)
            else:
                self.log_signal.emit("Decompressing Modded Stream (Standard Blocks)...")
                offsets = []
                for i in range(num_blocks):
                    off = struct.unpack(">I", comp_data[4 + i*4 : 8 + i*4])[0]
                    if i == 0: off &= 0x00FFFFFF
                    offsets.append(off)
                offsets.append(len(raw_stream) + table_size + 16)
                
                lz77_filtered = bytearray()
                for i in range(num_blocks):
                    start = offsets[i] - 16 - table_size
                    end = offsets[i+1] - 16 - table_size
                    lz77_filtered.extend(zlib.decompress(raw_stream[start:end], -15))

            bpp = (len(lz77_filtered) - height) // (width * height) if has_filters else len(lz77_filtered) // (width * height)
            meta['bpp'] = bpp
            
            raw_pixels = unfilter_png_blocks(lz77_filtered, width, height, bpp, row_size, has_filters)

            # COLOR SPACE DEBUGGER LOGIC 
            img = None
            if self.color_override == "Auto (Default)":
                if bpp == 2: decode_format = "BGR;16"
                elif bpp == 3: decode_format = "RGB"
                else: decode_format = "RGBA"
            else:
                decode_format = self.color_override.split(": ")[-1] # Extracts "RGB;16", "BGR", etc.

            self.log_signal.emit(f"Rendering frame using PIL format: [{decode_format}]")

            try:
                if bpp == 2 or "16" in decode_format:
                    img = Image.frombytes("RGB", (width, height), bytes(raw_pixels), "raw", decode_format)
                elif bpp == 3 or decode_format in ["RGB", "BGR"]:
                    img = Image.frombytes("RGB", (width, height), bytes(raw_pixels), "raw", decode_format)
                else:
                    img = Image.frombytes("RGBA", (width, height), bytes(raw_pixels), "raw", decode_format)
            except ValueError as ve:
                self.error_signal.emit(f"Color Mode Mismatch: File has {bpp} BPP, but you forced {decode_format}.")
                return

            output_path = os.path.splitext(self.bin_filepath)[0] + ".png"
            img.save(output_path)
            
            self.log_signal.emit(" Decoded Successfully! Preview rendered.")
            self.image_ready_signal.emit(output_path, meta)

        except Exception as e:
            self.error_signal.emit(f"Critical Error: {str(e)}")


# MAIN GUI 
class BinToPngApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SiFli EZIP Reversing Tool (Alpha)")
        self.setFixedSize(950, 680)
        self.current_bin_path = None
        self.meta = None
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # Toolbar
        toolbar = QHBoxLayout()
        self.btn_select = QPushButton("Load & Extract .bin File")
        self.btn_select.clicked.connect(self.select_file)
        self.btn_select.setFixedHeight(45)
        self.btn_select.setStyleSheet("font-size: 14px; font-weight: bold; background-color: #2b4c3b; color: white;")
        toolbar.addWidget(self.btn_select)

        main_layout.addLayout(toolbar)

        # Middle Section (Canvas + Specs)
        middle_layout = QHBoxLayout()
        
        # Image Preview
        self.img_preview = QLabel("Waiting for .bin extraction...")
        self.img_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.img_preview.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Sunken)
        self.img_preview.setMinimumSize(400, 400)
        self.img_preview.setStyleSheet("background-color: #1e1e1e; color: #666666;")
        middle_layout.addWidget(self.img_preview, stretch=2)

        # Right Specs Panel
        right_panel = QVBoxLayout()
        
        # Color Debugger Group
        color_group = QGroupBox(" Color Space Debugger")
        color_group.setStyleSheet("font-weight: bold; color: #ffcc00;")
        color_layout = QVBoxLayout()
        
        color_layout.addWidget(QLabel("Change the color space accordingly", styleSheet="color: #cccccc; font-weight: normal; font-size: 11px;"))
        self.color_mode_combo = QComboBox()
        self.color_mode_combo.addItems([
            "Auto (Default)",
            "16-bit: BGR;16",
            "16-bit: RGB;16",
            "16-bit: BGR;16B (Big Endian)",
            "24-bit: RGB",
            "24-bit: BGR",
            "32-bit: RGBA",
            "32-bit: BGRA"
        ])
        self.color_mode_combo.setStyleSheet("font-weight: normal; color: black; background-color: white;")
        color_layout.addWidget(self.color_mode_combo)
        color_group.setLayout(color_layout)
        right_panel.addWidget(color_group)

        # Specs Box
        specs_label = QLabel("📊 EZIP Specifications")
        specs_label.setStyleSheet("font-weight: bold; font-size: 14px; margin-top: 10px;")
        
        self.specs_box = QTextEdit()
        self.specs_box.setReadOnly(True)
        self.specs_box.setStyleSheet("background-color: #0b0c10; color: #00ff99; font-family: Consolas; font-size: 13px; font-weight: normal;")
        self.specs_box.setMaximumWidth(280)
        self.specs_box.setText("Load a file to see properties...")
        
        right_panel.addWidget(specs_label)
        right_panel.addWidget(self.specs_box)
        
        middle_layout.addLayout(right_panel, stretch=1)
        main_layout.addLayout(middle_layout)

        # Log Panel
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setStyleSheet("background-color: #0d0d0d; color: #00ffcc; font-family: Consolas; font-size: 12px;")
        self.log_box.setMaximumHeight(150)
        main_layout.addWidget(self.log_box)

    def select_file(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Select SiFli Bin", "", "Bin Files (*.bin)")
        if filepath:
            self.current_bin_path = filepath
            
            # Temporarily disable button to prevent thread collision
            self.btn_select.setEnabled(False)
            self.btn_select.setText("Extracting...")
            
            # Clear previous UI states
            self.log_box.clear()
            self.specs_box.clear()
            self.img_preview.clear()
            self.img_preview.setText("Extracting hardware specs...")
            self.specs_box.setText("Processing...")
            self.log_box.append(f"> Loading {filepath}...")
            
            selected_color = self.color_mode_combo.currentText()

            # Safe thread startup
            self.decoder = DecoderThread(filepath, selected_color)
            self.decoder.log_signal.connect(self.log_box.append)
            self.decoder.image_ready_signal.connect(self.image_loaded)
            self.decoder.error_signal.connect(self.error_handled)
            self.decoder.start()

    def image_loaded(self, path, meta):
        self.meta = meta
        
        # Render the newly generated PNG to the preview canvas
        pixmap = QPixmap(path)
        pixmap = pixmap.scaled(self.img_preview.width(), self.img_preview.height(), 
                               Qt.AspectRatioMode.KeepAspectRatio, 
                               Qt.TransformationMode.SmoothTransformation)
        self.img_preview.setPixmap(pixmap)
        
        # Populate the Specifications Panel
        specs_text = (
            f"FILE PROPERTIES\n"
            f"{'-'*25}\n"
            f"Width         : {meta['w']} px\n"
            f"Height        : {meta['h']} px\n"
            f"Color Format  : {meta['color_format']}\n"
            f"Bytes/Pixel   : {meta['bpp']}\n"
            f"File Size     : {meta['file_size'] / 1024:.2f} KB\n\n"
            f"EZIP HARDWARE SPECS\n"
            f"{'-'*25}\n"
            f"Total Blocks  : {meta['num_blocks']}\n"
            f"Row Per Block : {meta['row_size']}\n"
            f"Control Byte  : 0x{meta['ctrl']:02X}\n"
            f"Shared Huffman: {'Yes' if meta['one_huffcode'] else 'No'}\n"
            f"Filters Active: {'Yes' if meta['has_filters'] else 'No'}\n"
        )
        self.specs_box.setText(specs_text)
        
        # Reset Load Button
        self.btn_select.setEnabled(True)
        self.btn_select.setText("Load & Extract .bin File")

    def error_handled(self, error_msg):
        self.log_box.append(f"\n❌ {error_msg}")
        self.specs_box.setText("Extraction Failed.\nSee logs for details.")
        self.img_preview.setText("Error loading preview.")
        
        # Reset Load Button so the user can try again
        self.btn_select.setEnabled(True)
        self.btn_select.setText("Load & Extract .bin File")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = BinToPngApp()
    window.show()
    sys.exit(app.exec())
