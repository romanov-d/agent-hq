#!/bin/sh
# Renders the animated README header: docs/banner.gif (needs Google Chrome and ffmpeg).
set -e
cd "$(dirname "$0")"
CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
python3 gen.py --frames 36
for f in frames/f*.html; do
  "$CHROME" --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=2 \
    --window-size=1280,400 --screenshot="${f%.html}.png" "file://$PWD/$f" 2>/dev/null
done
ffmpeg -y -loglevel error -framerate 12 -i frames/f%02d.png \
  -vf "scale=1600:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128:stats_mode=full[p];[b][p]paletteuse=dither=none" \
  -loop 0 ../banner.gif
rm -rf frames
ls -la ../banner.gif
