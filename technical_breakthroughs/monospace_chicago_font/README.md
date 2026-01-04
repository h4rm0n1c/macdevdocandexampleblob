This script will allow you to convert ChicagoFLF.ttf into a Mono Compact font suitable for terminal use.

you will need fontforge (apt get install fontforge) to run this.

```
fontforge -lang=py -script /tmp/make_font_mono_compact.py \
  "$HOME/.local/share/fonts/ChicagoFLF.ttf" \
  "/tmp/ChicagoFLF-Mono-Compact.ttf" \
  "ChicagoFLF Mono Compact" \
  "$"

# Install + refresh cache
cp -f "/tmp/ChicagoFLF-Mono-Compact.ttf" "$HOME/.local/share/fonts/"
fc-cache -f -v

# Verify it is tagged monospace
fc-scan --format '%{family} %{style} spacing=%{spacing}\n' "$HOME/.local/share/fonts/ChicagoFLF-Mono-Compact.ttf"
fc-list :spacing=100 | grep -i 'ChicagoFLF Mono Compact' || true
```
