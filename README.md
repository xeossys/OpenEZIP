
# OpenEZIP: SiFli Reversing Tool & Decoder 🛠️ (ALPHA)

An open-source research initiative and Python GUI tool aimed at reverse-engineering the SiFli EZIP `.bin` image format used in various smartwatches and embedded displays. 

**Target Hardware:** This tool was initiated for the **HK8 Pro Max** smartwatch, but it is designed to work with the same lineup of smartwatches utilizing **SiFli chipsets**.

**⚠️ PROJECT STATUS: ALPHA / WORK-IN-PROGRESS** Currently, this tool can successfully parse EZIP block structures and decompress the hidden PNG data, but **the color rendering is off (images appear reddish/purplish)**. 

This repository is being released to the community so developers can collaborate, fix the color decoding matrix, and ultimately achieve our main goal: **compiling modified `.bin` files that the watch hardware will accept.**

## 🎯 The End Goal / Roadmap

1. **[WIP] Perfect the Decoder:** Fix the RGB/BGR byte-swapping and RGB565 rendering issues so extracted `.png` files have 100% accurate colors.
2. **[WIP] Re-Encoder/Compiler:** `ezip_encoder.py` now provides a verified bridge to a user-supplied official SiFli encoder. A fully open reimplementation of SiFli compression remains TODO.
3. **[TODO] Hardware Flashing:** Successfully flash modded UI elements and custom watch faces back onto the smartwatch.

## 🐛 Known Issues (Help Wanted!)

* **Color Channel Misalignment:** Decompressed images currently output with a reddish/purple tint. This is likely due to the hardware using a specific `BGR;16` or `RGB565` byte layout that our current PIL implementation isn't perfectly aligning with after the LZ77 decompression.
* **Filter Types:** PNG filter un-filtering works for standard blocks, but some hardware-specific filter flags might still be misread.

## ✨ Current Working Features

* **GUI Live Preview:** Fast, responsive UI built in PyQt6 for loading `.bin` files.
* **Header Parsing:** Successfully reads the custom SiFli LVGL (4-byte) and EZIP (16-byte) headers.
* **Block Extraction:** Maps the block offset table and dynamically extracts chunked streams.
* **Deflate/Huffman Decoding:** Handles both "Modded Stream" (standard zlib deflate) and "Factory Stream" (Custom Shared Huffman Tree) extraction.
* **Color Space Debugger:** Dropdown selection tool to force-override the byte decoding pattern during analysis.

## ✅ Official encoder bridge (verified)

OpenEZIP does **not** redistribute SiFli's encoder or its runtime DLLs. Instead,
`ezip_encoder.py` invokes a copy of `eZIP.exe` that the user obtained from the
official SiFli GraphicsTool, then validates the generated SiFli header and PNG
dimensions. This is the tested path for producing eZip assets accepted by an
HK8 PRO MAX equipment-6167 watchface package.

Windows:

```bash
python ezip_encoder.py face.png --encoder "C:\\SiFli\\video_tool\\eZIP.exe" --outdir build --format rgb565a
```

Linux with Wine:

```bash
python ezip_encoder.py face.png \
  --encoder /opt/sifli/video_tool/eZIP.exe \
  --outdir build \
  --format rgb565a \
  --wine
```

The output is `build/face.bin`. The script checks the four-byte SiFli header
and fails if its width or height differs from the source PNG. `rgb565a` is the
verified setting for alpha-capable eZip backgrounds; `rgb565` and `rgb888` are
also exposed for investigation.

This creates an image resource only. A complete store watchface still requires
the matching stock package structure, resource paths and native watchface
module for the target firmware. Do not assume a valid `.bin` is portable
between HK8 revisions or SiFli watches.

Run the bridge tests with:

```bash
python -m unittest discover -s tests -v
```

## 🛠️ Requirements & Setup

* Python 3.8+
* `PyQt6` (For the GUI)
* `Pillow` (For image handling)

```bash
git clone [https://github.com/xeossys/OpenEZIP.git](https://github.com/xeossys/OpenEZIP.git)
cd OpenEZIP
pip install -r requirements.txt
python main.py
```
## How to Use for Reverse Engineering
Launch the application and click "Load & Extract .bin File".
Choose your target smartwatch asset .bin file.
Observe the extracted specifications in the EZIP Hardware Specs panel (check block counts, flags, and if it uses shared Huffman strings).
If the colors on the preview look broken (red/purple), select a different raw decoder target layout from the 🧪 Color Space Debugger dropdown panel.
Reload the file. Keep testing combinations until the colors align perfectly!

🤝 Contributing
We actively need your help! If you have experience reverse-engineering firmware, working with embedded displays, dealing with packed pixel arrays (RGB565/BGR), or parsing custom zlib/deflate structures, please get involved! 
