"""Tile screenshots into one labeled PNG: contact_sheet.py OUT.png IMG... [--cols N]."""
import argparse
from pathlib import Path
from PIL import Image, ImageDraw

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('out', type=Path)
ap.add_argument('images', nargs='+', type=Path)
ap.add_argument('--cols', type=int, default=4)
ap.add_argument('--scale', type=float, default=1.0)
args = ap.parse_args()
imgs = [Image.open(p).convert('RGB') for p in args.images]
w = int(max(i.width for i in imgs) * args.scale)
h = int(max(i.height for i in imgs) * args.scale)
rows = (len(imgs) + args.cols - 1) // args.cols
sheet = Image.new('RGB', (args.cols * w, rows * (h + 12)), (40, 40, 40))
d = ImageDraw.Draw(sheet)
for n, (p, im) in enumerate(zip(args.images, imgs)):
    x, y = (n % args.cols) * w, (n // args.cols) * (h + 12)
    sheet.paste(im.resize((int(im.width * args.scale), int(im.height * args.scale)), Image.NEAREST), (x, y + 12))
    d.text((x + 2, y), p.stem, fill=(255, 255, 0))
sheet.save(args.out)
