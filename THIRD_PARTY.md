# Third-party components

MixCut source code is provided under the MIT license in LICENSE.

Runtime/build dependencies retain their respective licenses:

- Python and Tcl/Tk: https://www.python.org/psf/license/ and https://www.tcl.tk/software/tcltk/license.html
- imageio-ffmpeg 0.6.0 (BSD-2-Clause wrapper): https://github.com/imageio/imageio-ffmpeg
- FFmpeg executable distributed by imageio-ffmpeg: its applicable LGPL/GPL terms depend on the actual build. The Windows build records `ffmpeg -L`, `-version`, and `-buildconf` in `licenses/`; those statements govern the included executable, independently of the wrapper license.
- FFmpeg upstream source: https://ffmpeg.org/download.html ; packaged-binary provenance: https://github.com/imageio/imageio-binaries . Preserve the applicable notices and comply with corresponding-source requirements when redistributing the engine and its bundled codec dependencies.
- PyInstaller build tooling: https://pyinstaller.org/en/stable/license.html . PyInstaller's bootloader distribution exception applies as described by that project.

The build script copies available installed dependency license notices into the portable package. The workflow does not add a code-signing certificate.
