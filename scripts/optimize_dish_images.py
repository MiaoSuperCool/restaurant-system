"""把菜品配图压成适合当卡片背景的 WebP

用法：原图丢进 web-staff/public/dishes/，然后

    .venv/Scripts/python.exe scripts/optimize_dish_images.py     # Windows
    .venv/bin/python scripts/optimize_dish_images.py             # Linux/macOS

做完把 `dish.image` 指到产出的 `.webp` 上（演示数据在 `backend/app/demo.py`
的 `DISH_IMAGES` 里配）。

--------------------------------------------------------------------------
两件事，都是「不做也能跑，但会后悔」
--------------------------------------------------------------------------

**一、缩到长边 800px。** 菜单卡片才 200px 宽，2 倍屏也就 400px——800 已经
是留足余量了。原图动辄 2000+ px，存进 git 纯属浪费。

**二、存成 WebP，不是 PNG。** 卡片背景本来就要 blur 过，像素级细节根本看不出来，
但 PNG 的无损存法在这种图上一点不省：

    同一张牛肉面，2496×1664
      PNG  optimize=True   480 KB
      WebP q=90             59 KB     ← 差 8 倍

需要 Pillow（`pip install Pillow`）。它只是压图用的工具，没写进 requirements——
应用跑起来不需要它。
"""
import os
import sys

try:
    from PIL import Image
except ImportError:
    sys.exit('需要 Pillow：pip install Pillow')

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET_DIR = os.path.join(REPO_ROOT, 'web-staff', 'public', 'dishes')

MAX_EDGE = 800
QUALITY = 90

# 已经是产出格式的就不动了
SOURCE_EXTS = ('.png', '.jpg', '.jpeg')


def main():
    if not os.path.isdir(TARGET_DIR):
        sys.exit(f'目录不存在：{TARGET_DIR}')

    sources = [f for f in sorted(os.listdir(TARGET_DIR))
               if f.lower().endswith(SOURCE_EXTS)]
    if not sources:
        print(f'{TARGET_DIR} 里没有待处理的图（只找 {"/".join(SOURCE_EXTS)}）')
        return

    for filename in sources:
        src = os.path.join(TARGET_DIR, filename)
        dst = os.path.join(TARGET_DIR, os.path.splitext(filename)[0] + '.webp')
        before = os.path.getsize(src)

        with Image.open(src) as im:
            im = im.convert('RGB')          # 带透明通道的先压平，WebP 那边也支持但没必要
            im.thumbnail((MAX_EDGE, MAX_EDGE), Image.LANCZOS)
            im.save(dst, 'WEBP', quality=QUALITY, method=6)
            size = im.size

        after = os.path.getsize(dst)
        os.remove(src)                      # 原图别留，不然它才是进 git 的那个

        print(f'{filename}  →  {os.path.basename(dst)}')
        print(f'  {size[0]}×{size[1]}   {before / 1024:.0f} KB → {after / 1024:.0f} KB'
              f'   （压掉 {100 - after / before * 100:.0f}%）')

    print('\n记得把 dish.image 指到 .webp 上（演示数据在 backend/app/demo.py 的 DISH_IMAGES）')


if __name__ == '__main__':
    main()