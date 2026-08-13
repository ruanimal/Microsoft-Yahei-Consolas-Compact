#!/usr/bin/env python3
"""
build_compact_font.py — 从 "Microsoft YaHei Consolas Regular.ttf" 生成
"Microsoft YaHei Consolas Compact.ttf" 的可复现构建脚本。

修改内容：
1. 等比缩放全部全角（雅黑）字形并横向居中（advance 保持 2048，1:2 宽度不变）
2. 垂直度量改回原版 Consolas（行高 2398 = 1.171em）
3. 删除失效的 TrueType hinting（fpgm/prep/cvt + 全部字形指令）与竖排表（vhea/vmtx）
4. 重命名 family 为 "Microsoft YaHei Consolas Compact"

依赖：fontTools >= 4.x   （pip install fonttools）
用法：python3 build_compact_font.py
"""
import sys
from fontTools.ttLib import TTFont
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import DecomposingRecordingPen

SRC = "Microsoft YaHei Consolas Regular.ttf"
DST = "Microsoft YaHei Consolas Compact.ttf"

# ---- 目标度量（原版 Consolas consola.ttf）----
WIN_ASCENT = 1884          # usWinAscent
WIN_DESCENT = -514         # usWinDescent（负值表示基线下方）
TYP_ASCENT = 1521          # hhea/OS2 sTypoAscender
TYP_DESCENT = -527         # hhea/OS2 sTypoDescender
LINE_GAP = 350             # hhea/OS2 sTypoLineGap
NEW_FAMILY = "Microsoft YaHei Consolas Compact"
NEW_PS_NAME = "MicrosoftYaHeiConsolasCompact"


def main():
    if len(sys.argv) > 1:
        out = sys.argv[1]
    else:
        out = DST

    font = TTFont(SRC)
    glyf = font['glyf']
    hmtx = font['hmtx']
    head = font['head']
    hhea = font['hhea']
    os2 = font['OS/2']
    all_glyphs = font.getGlyphOrder()

    # ---- 1. 分组：advance == 2048 的全角（雅黑）字形 ----
    to_scale = set(gn for gn in all_glyphs if hmtx[gn][0] == 2048)
    print(f"缩放字形数: {len(to_scale)} / 总字形 {len(all_glyphs)}")

    # ---- 2. 全局垂直变换参数：把 [yMin,yMax] 线性映射到 [WIN_DESCENT, WIN_ASCENT] ----
    ys = [glyf[gn].yMin for gn in to_scale if glyf[gn].numberOfContours != 0]
    ye = [glyf[gn].yMax for gn in to_scale if glyf[gn].numberOfContours != 0]
    y_min_all, y_max_all = min(ys), max(ye)
    s = (WIN_ASCENT - WIN_DESCENT) / (y_max_all - y_min_all)
    dy = WIN_DESCENT - s * y_min_all
    print(f"全角字形 y 范围: [{y_min_all}, {y_max_all}] -> s={s:.6f}, dy={dy:.3f}")

    # ---- 3. 先展平所有复合字形为简单字形（消除组件/复合的处理顺序依赖）----
    gs = font.getGlyphSet()  # draw(pen) 单参数包装，正确解析复合字形
    n_composite = 0
    for gn in all_glyphs:
        g = glyf[gn]
        if g.isComposite():
            rec = DecomposingRecordingPen(gs)  # 递归展开组件为纯轮廓点
            gs[gn].draw(rec)
            ttpen = TTGlyphPen(gs)
            rec.replay(ttpen)
            glyf[gn] = ttpen.glyph()
            n_composite += 1
    if n_composite:
        print(f"展平复合字形: {n_composite}")

    # ---- 4. 逐字形变换（此时全部为简单字形），数学方式记录新边界 ----
    new_bounds = {}
    n_scaled = 0
    for gn in to_scale:
        g = glyf[gn]
        if g.numberOfContours == 0 and not g.isComposite():
            continue  # 空字形（.null 等）
        bp = BoundsPen(gs)
        gs[gn].draw(bp)
        if bp.bounds is None:
            continue
        x_min, y_min, x_max, y_max = bp.bounds
        cx = (x_min + x_max) / 2.0
        dx = 1024.0 - s * cx  # 横向居中到全角格 [0, 2048]
        ttpen = TTGlyphPen(gs)
        tpen = TransformPen(ttpen, (s, 0, 0, s, dx, dy))
        gs[gn].draw(tpen)
        glyf[gn] = ttpen.glyph()
        # 新边界 = 线性映射端点（xMin/xMax 单调）
        nx_min, nx_max = round(s * x_min + dx), round(s * x_max + dx)
        ny_min, ny_max = round(s * y_min + dy), round(s * y_max + dy)
        new_bounds[gn] = (nx_min, ny_min, nx_max, ny_max)
        hmtx[gn] = (hmtx[gn][0], nx_min)  # 更新 lsb，advance 保持 2048
        n_scaled += 1
    print(f"实际缩放字形: {n_scaled}")

    # ---- 5. 让全部字形可计算边界（TTGlyphPen 产物为懒加载状态，maxp.recalc 需要）----
    for gn in all_glyphs:
        g = glyf[gn]
        if g.numberOfContours != 0:
            g.recalcBounds(glyf)

    # ---- 6. 重算 head 全局边界（统一用 BoundsPen，兼容懒加载字形）----
    x_mins, x_maxs, y_mins, y_maxs = [], [], [], []
    for gn in all_glyphs:
        g = glyf[gn]
        if g.numberOfContours == 0:
            continue
        bp = BoundsPen(gs)
        gs[gn].draw(bp)
        if bp.bounds is None:
            continue
        x_min, y_min, x_max, y_max = bp.bounds
        x_mins.append(x_min); x_maxs.append(x_max)
        y_mins.append(y_min); y_maxs.append(y_max)
    head.xMin, head.xMax = min(x_mins), max(x_maxs)
    head.yMin, head.yMax = min(y_mins), max(y_maxs)
    print(f"head 边界: x[{head.xMin},{head.xMax}] y[{head.yMin},{head.yMax}]")

    # ---- 7. 垂直度量改回原版 Consolas ----
    hhea.ascent, hhea.descent, hhea.lineGap = TYP_ASCENT, TYP_DESCENT, LINE_GAP
    os2.sTypoAscender, os2.sTypoDescender, os2.sTypoLineGap = TYP_ASCENT, TYP_DESCENT, LINE_GAP
    os2.usWinAscent, os2.usWinDescent = WIN_ASCENT, -WIN_DESCENT
    line_h = TYP_ASCENT - TYP_DESCENT + LINE_GAP
    print(f"行高 = {line_h} ({line_h / head.unitsPerEm:.3f}em)")

    # ---- 8. 删除失效/无用表 ----
    for t in ('fpgm', 'prep', 'cvt ', 'vhea', 'vmtx'):
        if t in font:
            del font[t]

    # ---- 9. 清除全部字形 hinting 指令（含未缩放半角字形残留）----
    removed = 0
    for gn in all_glyphs:
        g = glyf[gn]
        if g.numberOfContours == 0:
            continue
        prog = getattr(g, 'program', None)
        if prog and len(prog.getBytecode()):
            g.removeHinting()
            removed += 1
    print(f"清除 hinting 指令字形: {removed}")

    # ---- 10. maxp 重新计算 ----
    font['maxp'].recalc(font)

    # ---- 11. 重命名 family，避免与已安装同名字体冲突 ----
    name = font['name']
    for nid in (1, 2, 4, 6, 16, 17):
        name.removeNames(nameID=nid)
    name.setName(NEW_FAMILY, 1, 3, 1, 0x409)
    name.setName("Regular", 2, 3, 1, 0x409)
    name.setName(NEW_FAMILY + " Regular", 4, 3, 1, 0x409)
    name.setName(NEW_PS_NAME, 6, 3, 1, 0x409)
    name.setName(NEW_FAMILY, 16, 3, 1, 0x409)
    name.setName("Regular", 17, 3, 1, 0x409)

    font.save(out)
    print(f"已保存: {out}")


if __name__ == "__main__":
    main()
