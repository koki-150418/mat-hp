#!/usr/bin/env python3
"""MAT blog eyecatch generator (logo navy + teal palette).
Usage:
  python3 tools/make_eyecatch.py "タイトル｜サブ" "カテゴリ" out.jpg
  python3 tools/make_eyecatch.py --all   # regenerate every blog/*/eyecatch.jpg from post-meta
"""
import json, os, re, sys, glob
from PIL import Image, ImageDraw, ImageFont

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERIF = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc"
SANS = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
NAVY = "#02254e"
TEAL = "#0e8fa1"
FRAME = "#0a4a6e"
MUTED = "#b8dce3"
_idx = {}

def _jp_index(path=SERIF):
    if path in _idx:
        return _idx[path]
    for i in range(10):
        try:
            f = ImageFont.truetype(path, 20, index=i)
            if "JP" in f.getname()[0]:
                _idx[path] = i
                return i
        except Exception:
            break
    _idx[path] = 0
    return 0

def wrap(draw, text, font, maxw):
    lines, cur = [], ""
    for ch in text:
        if draw.textlength(cur + ch, font=font) > maxw:
            if ch in "、。」）｜！？ー・":
                cur += ch
                lines.append(cur)
                cur = ""
                continue
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines

def eyecatch(title, cat, out):
    W, H = 1200, 630
    im = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 18, H], fill=TEAL)
    d.rectangle([60, 60, W - 60, H - 60], outline=FRAME, width=2)
    y = 540
    pts = [(100, y), (300, y), (318, y - 22), (336, y + 18), (354, y - 34), (372, y), (1100, y)]
    d.line(pts, fill=TEAL, width=4)
    # light teal pulse tip accent
    d.line([(318, y - 22), (336, y + 18), (354, y - 34)], fill="#5fd3e0", width=3)
    fc = ImageFont.truetype(SANS, 30, index=_jp_index(SANS))
    tw = d.textlength(cat, font=fc)
    d.rounded_rectangle([100, 100, 100 + tw + 40, 152], 8, fill=TEAL)
    d.text((120, 105), cat, font=fc, fill="white")
    main = title.split("｜")[0]
    sub = title.split("｜", 1)[1] if "｜" in title else ""
    for size in (64, 58, 52, 48):
        f = ImageFont.truetype(SERIF, size, index=_jp_index())
        ls = wrap(d, main, f, 1000)
        if len(ls) <= 3:
            break
    yy = 190
    for l in ls:
        d.text((100, yy), l, font=f, fill="white")
        yy += int(size * 1.35)
    if sub:
        fs = ImageFont.truetype(SANS, 30, index=_jp_index(SANS))
        sl = wrap(d, sub, fs, 1000)[:2]
        yy += 10
        for l in sl:
            d.text((100, yy), l, font=fs, fill=MUTED)
            yy += 44
    fl = ImageFont.truetype(SANS, 26, index=_jp_index(SANS))
    d.text((100, 560), "MEDI-AI TEAM  |  医療職のためのAI実践チーム", font=fl, fill=MUTED)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    im.save(out, "JPEG", quality=88)

def regen_all():
    n = 0
    for fp in sorted(glob.glob(f"{REPO}/blog/*/index.html")):
        slug = os.path.basename(os.path.dirname(fp))
        t = open(fp).read()
        m = re.search(r'id="post-meta">(.*?)</script>', t, re.S)
        if not m:
            print("skip (no meta)", slug)
            continue
        meta = json.loads(m.group(1))
        out = f"{REPO}/blog/{slug}/eyecatch.jpg"
        eyecatch(meta["title"], meta.get("category", "ブログ"), out)
        n += 1
        print(n, slug)
    # defaults / template
    eyecatch("MEDI-AI TEAM ブログ", "ブログ", f"{REPO}/img/blog-default.jpg")
    print("+ img/blog-default.jpg")
    eyecatch("【サンプル記事】記事ページのレイアウト見本", "サンプル", f"{REPO}/tools/post-template/eyecatch.jpg")
    print("+ tools/post-template/eyecatch.jpg")
    return n

if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "--all":
        print("regenerated", regen_all(), "post eyecatches")
    elif len(sys.argv) >= 4:
        eyecatch(sys.argv[1], sys.argv[2], sys.argv[3])
    else:
        print(__doc__)
        sys.exit(1)
