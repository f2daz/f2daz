"""Erzeugt das ASCII-Porträt für update_profile.py aus einem Bild.

Benötigt Pillow:  pip install pillow

Beispiele:
  python tools/make_ascii.py avatar.jpg                  # nur ausgeben
  python tools/make_ascii.py avatar.jpg --update         # ART in update_profile.py ersetzen
  python tools/make_ascii.py avatar.jpg --crop 80 0 390 400 --cols 42 --rows 30

Avatar herunterladen:
  curl -sL "https://avatars.githubusercontent.com/f2daz?s=460" -o avatar.jpg
"""
import argparse
import re
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps

RAMP = " .:-=+*#%@"  # dunkel -> hell (für dunklen Hintergrund: hell = dichtes Zeichen)
SCRIPT = Path(__file__).resolve().parent.parent / "update_profile.py"


def to_ascii(path, crop, cols, rows, threshold, blend):
    src = Image.open(path).convert("L")
    if crop:
        src = src.crop(tuple(crop))
    # Autokontrast + Histogramm-Ausgleich mischen: hebt Schattenseiten an, ohne
    # den Hintergrund ganz aufzuhellen; Unschärfemaske hält Kanten (Brille) sichtbar.
    img = Image.blend(ImageOps.autocontrast(src, cutoff=1), ImageOps.equalize(src), blend)
    img = img.filter(ImageFilter.UnsharpMask(2, 120, 2)).resize((cols, rows), Image.LANCZOS)
    lines = []
    for y in range(rows):
        row = ""
        for x in range(cols):
            v = img.getpixel((x, y)) / 255
            row += " " if v < threshold else RAMP[min(int(v * len(RAMP)), len(RAMP) - 1)]
        lines.append(row.rstrip())
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image")
    ap.add_argument("--crop", type=int, nargs=4, metavar=("L", "O", "R", "U"), default=[80, 0, 390, 400],
                    help="Ausschnitt in Pixeln (links oben rechts unten), passend für 460px-Avatar")
    ap.add_argument("--cols", type=int, default=42, help="Breite in Zeichen")
    ap.add_argument("--rows", type=int, default=30, help="Höhe in Zeilen (Zeichen sind ~2x so hoch wie breit)")
    ap.add_argument("--threshold", type=float, default=0.22, help="Helligkeit darunter wird Leerzeichen (0-1)")
    ap.add_argument("--blend", type=float, default=0.5, help="Anteil Histogramm-Ausgleich (0-1)")
    ap.add_argument("--update", action="store_true", help="ART-Block in update_profile.py ersetzen")
    a = ap.parse_args()

    art = to_ascii(a.image, a.crop, a.cols, a.rows, a.threshold, a.blend)
    print(art)
    if a.update:
        text = SCRIPT.read_text(encoding="utf-8")
        new, n = re.subn(r'ART = r""".*?"""', lambda _: f'ART = r"""\n{art}\n"""', text, count=1, flags=re.S)
        if n != 1:
            raise SystemExit("ART-Block in update_profile.py nicht gefunden")
        SCRIPT.write_text(new, encoding="utf-8")
        print(f"\n-> {SCRIPT.name} aktualisiert")


if __name__ == "__main__":
    main()
