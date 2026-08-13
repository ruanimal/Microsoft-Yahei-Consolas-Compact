#!/usr/bin/env python3
"""
生成 compare_lineheight.png
策略: 4 个字体两两分组 (Compact/Original, Hybrid/Consolas),
      每组内并排, 各自的行高真实渲染, 画出行框 + baseline.
      这样行高差异、字符在行框内的密度差异一目了然.
"""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

DEMO = Path(__file__).with_name("demo.txt").read_text(encoding="utf-8")
OUT = Path(__file__).with_name("compare_lineheight.png")

FONT_SIZE = 34
LABEL_SIZE = 22
INFO_SIZE = 16        # 基线信息字号
LABEL_MIN = 12        # 标签字号下限 (一行放不下时缩小)
MARGIN_X = 40
MARGIN_Y = 40
COL_GAP = 80          # 组内两个字体之间
GROUP_GAP = 100       # 两组之间
LINE_PAD = 8

# 每组 2 个字体
FONT_PAIRS = [
    [
        ("Microsoft YaHei Consolas Compact",
         "/Users/ruan/Library/Fonts/Microsoft YaHei Consolas Compact.ttf"),
        ("Microsoft YaHei Consolas",
         "/Users/ruan/Library/Fonts/Microsoft YaHei Consolas Regular.ttf"),
    ],
    [
        ("Microsoft YaHei Mono",
         "/Users/ruan/Library/Fonts/Microsoft-YaHei-Mono.ttf"),
        ("YaHei Consolas Hybrid",
         "/Users/ruan/Library/Fonts/YaHei Consolas Hybrid 1.12.ttf"),
    ],
]

# 行框 / baseline 颜色
BOX_TOP_COLOR = "#888888"        # 行框上沿
BOX_BOTTOM_COLOR = "#444444"     # 行框下沿 (深色, 表示 descent 边界)
BOX_LEFT_COLOR = "#bbbbbb"
BASELINE_COLOR = "#dd3333"       # baseline 用红色


def load_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception as e:
        raise RuntimeError(f"无法加载字体 {path}: {e}")


def line_metrics(font, text):
    """返回 (宽度, 行高, ascent, descent) 列表"""
    ascent, descent = font.getmetrics()
    line_h = ascent + descent
    lines = text.splitlines()
    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    widths = [draw.textbbox((0, 0), line, font=font)[2] for line in lines]
    return max(widths), line_h, ascent, descent, widths


def header_height(path_a, path_b):
    """标题行 (字体标签 + 基线信息) 的高度"""
    heights = []
    for p in (path_a, path_b):
        a, d = load_font(p, LABEL_SIZE).getmetrics()
        heights.append(a + d)
    a, d = load_font(path_a, INFO_SIZE).getmetrics()
    heights.append(a + d)
    return max(heights)


def fit_label_size(draw, name, path, ascent, descent, box_w):
    """返回 (标签字号, 基线信息文本, info 字体): 一行放不下时缩小标签"""
    info = f"  ascent={ascent}  descent={descent}  line_h={ascent + descent}"
    info_font = load_font(path, INFO_SIZE)
    size = LABEL_SIZE
    while size > LABEL_MIN:
        label_font = load_font(path, size)
        total_w = draw.textlength(name, font=label_font) + draw.textlength(info, font=info_font)
        if total_w <= box_w:
            break
        size -= 2
    return size, info, info_font


def render_group(draw, x, y, font_a, name_a, font_b, name_b, lines, path_a, path_b):
    """
    在 (x, y) 起始处, 并排画两个字体各自渲染的 demo.
    每个字体用自己的 line_h 排列行, 画出行框.
    返回: (结束 y, 最大宽度)
    """
    wa, ha, aa, da, widths_a = line_metrics(font_a, DEMO)
    wb, hb, ab, db, widths_b = line_metrics(font_b, DEMO)
    box_w = max(wa, wb) + 20

    # 标题行: 字体标签 + 基线信息 同一行, baseline 对齐
    for col_x, name, path, ascent, descent in [
        (x, name_a, path_a, aa, da),
        (x + box_w + COL_GAP, name_b, path_b, ab, db),
    ]:
        size, info, info_font = fit_label_size(draw, name, path, ascent, descent, box_w)
        label_font = load_font(path, size)
        dy = label_font.getmetrics()[0] - info_font.getmetrics()[0]
        draw.text((col_x, y), name, fill="black", font=label_font)
        name_w = draw.textlength(name, font=label_font)
        draw.text((col_x + name_w, y + dy), info, fill="#666666", font=info_font)
    y += header_height(path_a, path_b) + 4

    # 画两列
    y0 = y
    for col_x, font, ascent, descent, line_h, widths in [
        (x, font_a, aa, da, ha, widths_a),
        (x + box_w + COL_GAP, font_b, ab, db, hb, widths_b),
    ]:
        cur_y = y0
        for i, line in enumerate(lines):
            baseline = cur_y + ascent
            # 行框
            col_w = widths[i]
            draw.line([(col_x, baseline - ascent), (col_x + col_w, baseline - ascent)], fill=BOX_TOP_COLOR, width=1)
            draw.line([(col_x, baseline + descent), (col_x + col_w, baseline + descent)], fill=BOX_BOTTOM_COLOR, width=1)
            draw.line([(col_x, baseline - ascent), (col_x, baseline + descent)], fill=BOX_LEFT_COLOR, width=1)
            # baseline 红线
            draw.line([(col_x, baseline), (col_x + col_w, baseline)], fill=BASELINE_COLOR, width=1)
            # 字符
            draw.text((col_x, cur_y), line, fill="black", font=font)
            cur_y += line_h
    end_y = max(y0 + ha * len(lines), y0 + hb * len(lines))
    return end_y, box_w * 2 + COL_GAP


def main():
    # 加载字体
    loaded = []
    for group in FONT_PAIRS:
        loaded.append([
            (load_font(p, FONT_SIZE), name, p)
            for name, p in group
        ])

    # 先量总宽高
    lines = DEMO.splitlines()
    sample_block_w = 0
    total_h = MARGIN_Y
    for group in loaded:
        wa = line_metrics(group[0][0], DEMO)[0]
        wb = line_metrics(group[1][0], DEMO)[0]
        box_w = max(wa, wb) + 20
        group_w = box_w * 2 + COL_GAP
        sample_block_w = max(sample_block_w, group_w)
        ha = group[0][0].getmetrics()[0] + group[0][0].getmetrics()[1]
        hb = group[1][0].getmetrics()[0] + group[1][0].getmetrics()[1]
        group_h = header_height(group[0][2], group[1][2]) + 4 + len(lines) * max(ha, hb) + 20
        total_h += group_h + GROUP_GAP
    total_h = total_h - GROUP_GAP + MARGIN_Y

    img_w = MARGIN_X * 2 + sample_block_w
    img_h = total_h
    img = Image.new("RGB", (img_w, img_h), "white")
    draw = ImageDraw.Draw(img)

    y = MARGIN_Y
    for group in loaded:
        end_y, _ = render_group(
            draw, MARGIN_X, y,
            group[0][0], group[0][1], group[1][0], group[1][1],
            lines,
            group[0][2], group[1][2],
        )
        y = end_y + GROUP_GAP

    img.save(OUT)
    print(f"已保存: {OUT} ({img_w}x{img_h})")


if __name__ == "__main__":
    main()
