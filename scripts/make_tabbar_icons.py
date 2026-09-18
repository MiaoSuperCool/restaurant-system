"""生成顾客端底部 tabBar 的图标

**为什么要写个脚本而不是直接放几张 PNG**：图标是「画出来的」这件事得留个记录——
后面要调整颜色、线宽、或者加第五个 tab 时，能改一行重跑，
而不是去翻哪个网站下载的、或者拿画图软件重描一遍。

（和 `optimize_dish_images.py` 一个路子：凡是对图片做过的处理，都留得下痕迹。）

小程序 tabBar 的图标有硬要求：
- **必须是本地图片**（不支持网络图片，也不支持字体图标）
- 建议 81×81，PNG
- 所以这里按 4 倍尺寸画（324×324）再缩到 81——直接画 81 的话线条全是锯齿

用法：
    python scripts/make_tabbar_icons.py
产物写到 mp-customer/src/static/tabbar/ 下，每个图标两套颜色（未选中/选中）。
"""
import os

from PIL import Image, ImageDraw

# 输出目录
OUT_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..',
    'mp-customer', 'src', 'static', 'tabbar',
)

SIZE = 81          # 最终尺寸（小程序建议 81×81）
SCALE = 4          # 先按 4 倍画再缩，等于手工做了一遍抗锯齿
CANVAS = SIZE * SCALE

# 两套颜色：和 App 里其他地方一致（未选中灰、选中近黑）
COLORS = {'': '#999999', '-on': '#1f1f1f'}

# 线宽（按最终尺寸算，画的时候乘 SCALE）
STROKE = 2


def px(value):
    """0~1 的相对坐标 → 画布上的像素"""
    return value * CANVAS


def box(left, top, right, bottom):
    return [px(left), px(top), px(right), px(bottom)]


def point(x, y):
    return (px(x), px(y))


def draw_home(d, color):
    """首页：一间房子"""
    # 屋顶 + 两面墙 + 地面，一笔画成（闭合多边形）
    d.line([point(0.50, 0.12), point(0.90, 0.46), point(0.90, 0.88),
            point(0.10, 0.88), point(0.10, 0.46), point(0.50, 0.12)],
           fill=color, width=STROKE * SCALE, joint='curve')


def draw_menu(d, color):
    """点餐：一只碗（横线 + 下半圆），比刀叉更贴中餐"""
    w = STROKE * SCALE
    # 碗口
    d.line([point(0.14, 0.42), point(0.86, 0.42)], fill=color, width=w)
    # 碗身：下半圆
    d.arc(box(0.14, 0.42, 0.86, 0.90), start=0, end=180, fill=color, width=w)
    # 碗底一小段，不然看着像个半圆而不是碗
    d.line([point(0.40, 0.90), point(0.60, 0.90)], fill=color, width=w)


def draw_orders(d, color):
    """订单：一张单据"""
    w = STROKE * SCALE
    d.rounded_rectangle(box(0.22, 0.10, 0.78, 0.90), radius=px(0.08),
                        outline=color, width=w)
    for y in (0.32, 0.50, 0.68):
        d.line([point(0.36, y), point(0.64, y)], fill=color, width=w)


def draw_mine(d, color):
    """个人中心：一个人（头 + 肩）"""
    w = STROKE * SCALE
    d.ellipse(box(0.34, 0.12, 0.66, 0.44), outline=color, width=w)
    # 肩膀：上半圆。PIL 的角度是从 3 点钟方向顺时针算的，180~360 正好是上半圆
    d.arc(box(0.16, 0.54, 0.84, 1.10), start=180, end=360, fill=color, width=w)


ICONS = [
    ('home', draw_home),
    ('menu', draw_menu),
    ('orders', draw_orders),
    ('mine', draw_mine),
]


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    for name, draw in ICONS:
        for suffix, color in COLORS.items():
            # 透明底：tabBar 的背景色由 pages.json 定，图标不该自带白底
            image = Image.new('RGBA', (CANVAS, CANVAS), (0, 0, 0, 0))
            canvas = ImageDraw.Draw(image)
            draw(canvas, color)
            image = image.resize((SIZE, SIZE), Image.LANCZOS)

            path = os.path.join(OUT_DIR, f'{name}{suffix}.png')
            image.save(path)
            print(f'@@ {os.path.relpath(path)}')


if __name__ == '__main__':
    main()