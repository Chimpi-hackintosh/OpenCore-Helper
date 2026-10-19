# Third-party components

## macrecovery

`openhelper/vendor/macrecovery/upstream.py` is an unmodified copy of `Utilities/macrecovery/macrecovery.py` from [acidanthera/OpenCorePkg](https://github.com/acidanthera/OpenCorePkg)

- Commit: `45e7636f24bb4a50b32baeb5170cdfc9f589ea3c`
- File copyright: Copyright (c) 2019, vit9696
- License: BSD 3-Clause, reproduced in [licenses/OpenCorePkg-BSD-3-Clause.txt](licenses/OpenCorePkg-BSD-3-Clause.txt)
- Origin and exact SHA-256: `openhelper/vendor/macrecovery/ORIGIN.json`

The wrapper runs the download action in an isolated child process, gives network operations a timeout and publishes the new output folder only after successful chunklist verification. Assertions must remain enabled; the package is built with optimization level zero

## Python dependencies

CustomTkinter, Pillow, darkdetect, packaging, the Python runtime, Tcl/Tk and the PyInstaller bootloader retain their respective licenses. Dependency license files are collected into the Windows package's `licenses` directory; Python and Tcl/Tk license material included by PyInstaller remains under `lib`

CustomTkinter 6.0.0 declares CC0-1.0; Pillow 13.0.0 declares MIT-CMU; darkdetect declares BSD-3-Clause. Consult the included dependency license texts for authoritative terms

## Optional external tools

[OpenCore Auxiliary Tools](https://github.com/ic005k/OCAuxiliaryTools), OpenCorePkg's ocvalidate and macserial, and [QEMU](https://www.qemu.org/) are optional external programs. They are not bundled or modified by this project. Their own licenses and provenance apply when users download them

The integrated Auxiliary Tools editor is original code for OpenCore Helper, not a port or rebranding of ic005k's Qt application. OpenCore Helper is independent of Apple, Acidanthera, Dortania and ic005k

