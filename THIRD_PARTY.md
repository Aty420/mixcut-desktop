# Third-party components

MixCut source code is provided under the MIT license in LICENSE.

Runtime/build dependencies retain their respective licenses:

- Python and Tcl/Tk: https://www.python.org/psf/license/ and https://www.tcl.tk/software/tcltk/license.html
- imageio-ffmpeg 0.6.0 (BSD-2-Clause wrapper): https://github.com/imageio/imageio-ffmpeg
- FFmpeg executable distributed by imageio-ffmpeg: its applicable LGPL/GPL terms depend on the actual build. The Windows build records `ffmpeg -L`, `-version`, and `-buildconf` in `licenses/`; those statements govern the included executable, independently of the wrapper license.
- FFmpeg upstream source: https://ffmpeg.org/download.html ; packaged-binary provenance: https://github.com/imageio/imageio-binaries . Preserve the applicable notices and comply with corresponding-source requirements when redistributing the engine and its bundled codec dependencies.
- PyInstaller build tooling: https://pyinstaller.org/en/stable/license.html . PyInstaller's bootloader distribution exception applies as described by that project.

The build script copies available installed dependency license notices into the portable package. The workflow does not add a code-signing certificate.


## Tabler Icons v3.35.0

界面图标源自 https://github.com/tabler/tabler-icons/tree/v3.35.0 ，按 MIT 许可分发。嵌入的 PNG 只调整了颜色和尺寸，无需联网下载。

```text
MIT License

Copyright (c) 2020-2025 Paweł Kuna

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

```
