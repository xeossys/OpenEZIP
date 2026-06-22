# SiFli EZIP Reversing Tool & Decoder 🛠️ (ALPHA)

An open-source research initiative and Python GUI tool aimed at reverse-engineering the SiFli EZIP `.bin` image format used in various smartwatches and embedded displays.

**⚠️ PROJECT STATUS: ALPHA / WORK-IN-PROGRESS** Currently, this tool can successfully parse EZIP block structures and decompress the hidden PNG data, but **the color rendering is off (images appear reddish/purplish)**. 

This repository is being released to the community so developers can collaborate, fix the color decoding matrix, and ultimately achieve our main goal: **compiling modified `.bin` files that the watch hardware will accept.**

## 🎯 The End Goal / Roadmap

1. **[WIP] Perfect the Decoder:** Fix the RGB/BGR byte-swapping and RGB565 rendering issues so extracted `.png` files have 100% accurate colors.
2. **[TODO] Re-Encoder/Compiler:** Build out the compression logic to turn standard `.png` files *back* into SiFli EZIP `.bin` files with the correct LVGL/EZIP headers.
3. **[TODO] Hardware Flashing:** Successfully flash modded UI elements and custom watch faces back onto the smartwatch.

## 🐛 Known Issues (Help Wanted!)

* **Color Channel Misalignment:** Decompressed images currently output with a reddish/purple tint. This is likely due to the hardware using a specific `BGR;16` or `RGB565` byte layout that our current PIL implementation isn't perfectly aligning with after the LZ77 decompression.
* **Filter Types:** PNG filter un-filtering works for standard blocks, but some hardware-specific filter flags might still be misread.

## ✨ Current Working Features

* **GUI Live Preview:** Fast, responsive UI built in PyQt6 for loading `.bin` files.
* **Header Parsing:** Successfully reads the custom SiFli LVGL (4-byte) and EZIP (16-byte) headers.
* **Block Extraction:** Maps the block offset table and dynamically extracts chunked streams.
* **Deflate/Huffman Decoding:** Handles both "Modded Stream" (standard zlib deflate) and "Factory Stream" (Custom Shared Huffman Tree) extraction.

## 🛠️ Requirements & Setup

* Python 3.8+
* `PyQt6` (For the GUI)
* `Pillow` (For image handling)

```bash
git clone [https://github.com/yourusername/sifli-ezip-reversing.git](https://github.com/yourusername/sifli-ezip-reversing.git)
cd sifli-ezip-reversing
pip install -r requirements.txt
python main.py
