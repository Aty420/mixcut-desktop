"""Record the precise bundled engine build and preserve dependency licenses."""
import importlib.metadata
import shutil
import subprocess
from pathlib import Path

import imageio_ffmpeg

out = Path("dist/MixCut/licenses")
out.mkdir(parents=True, exist_ok=True)
for arg, filename in [("-L", "FFmpeg-license.txt"), ("-version", "FFmpeg-version.txt"),
                      ("-buildconf", "FFmpeg-build-configuration.txt")]:
    result = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), arg], capture_output=True, check=True)
    (out / filename).write_bytes(result.stdout + result.stderr)
for package in ("imageio-ffmpeg",):
    distribution = importlib.metadata.distribution(package)
    for entry in distribution.files or []:
        if "license" in entry.name.lower() or "copying" in entry.name.lower():
            source = distribution.locate_file(entry)
            if source.is_file():
                shutil.copyfile(source, out / f"{package}-{entry.name}")
