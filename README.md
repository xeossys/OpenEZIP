
# OpenEZIP: SiFli Reversing Tool & Decoder 🛠️ (ALPHA)

An open-source research initiative and Python GUI tool aimed at reverse-engineering the SiFli EZIP `.bin` image format used in various smartwatches and embedded displays. 

**Target Hardware:** This tool was initiated for the **HK8 Pro Max** smartwatch, but it is designed to work with the same lineup of smartwatches utilizing **SiFli chipsets**.

**⚠️ PROJECT STATUS: ALPHA / WORK-IN-PROGRESS** The decoder supports the current
SiFli raw-DEFLATE stream layout and the documented little-endian RGB565,
RGB888, RGB565 with alpha, and ARGB8888 pixel layouts. Legacy shared-Huffman
streams still need broader fixture coverage.

This repository is being released to the community so developers can broaden
format support and ultimately achieve our main goal: **compiling modified
`.bin` files that the watch hardware will accept.**

## 🎯 The End Goal / Roadmap

1. **[WIP] Perfect the Decoder:** Add fixture coverage for more firmware and legacy shared-Huffman stream variants.
2. **[WIP] Re-Encoder/Compiler:** `ezip_encoder.py` now provides a verified bridge to a user-supplied official SiFli encoder. A fully open reimplementation of SiFli compression remains TODO.
3. **[TODO] Hardware Flashing:** Successfully flash modded UI elements and custom watch faces back onto the smartwatch.

## 🐛 Known Issues (Help Wanted!)

* **Legacy Streams:** The shared-Huffman decoder is retained for older assets but
  does not yet have an authoritative public fixture. Current raw-DEFLATE eZIP
  streams are checksum-validated and tested against SiFli's published output.
* **Firmware Variants:** Assets from additional watches may use header or stream
  variants that are not represented by the available fixtures yet.

## ✨ Current Working Features

* **GUI Live Preview:** Fast, responsive UI built in PyQt6 for loading `.bin` files.
* **Header Parsing:** Successfully reads the custom SiFli LVGL (4-byte) and EZIP (16-byte) headers.
* **Block Extraction:** Maps the block offset table and dynamically extracts chunked streams.
* **Stream Decoding:** Handles current raw-DEFLATE streams with Adler-32
  verification and retains legacy block-DEFLATE/shared-Huffman fallbacks.
* **Color Space Debugger:** Dropdown selection tool to force-override the byte decoding pattern during analysis.

## Decoder pixel formats

The resource header distinguishes eZIP data with and without alpha. Combined
with the decoded bit depth, the automatic decoder selects these layouts:

| Resource format | Bytes per pixel | SiFli byte layout | PNG output |
|---|---:|---|---|
| eZIP | 2 | little-endian RGB565 | RGB |
| eZIP | 3 | B, G, R | RGB |
| eZIP with alpha | 3 | RGB565 low byte, high byte, alpha | RGBA |
| eZIP with alpha | 4 | B, G, R, A | RGBA |

The format definitions follow SiFli's
[EZIP Image Conversion Tool documentation](https://github.com/OpenSiFli/SiFli-SDK/blob/main/docs/source/en/app_note/ezip_tool_usage.md).

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

Run the encoder and decoder tests with:

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
