"""视野：递归阴影投射（recursive shadowcasting）。

原版 PLATO 地牢游戏如何在单屏内表现"看得见/看不见"已不可考（见 docs/research-dossier.md C 类），
此处采用现代 roguelike 的通行做法，属于 L2 现代化层。
"""

from __future__ import annotations

# 4 行 × 8 个八分圆（Björn Bergström 的经典递归阴影投射表）
# 第 k 个八分圆的 (xx, xy, yx, yy) = (MULT[0][k], MULT[1][k], MULT[2][k], MULT[3][k])
MULT = (
    (1, 0, 0, -1, -1, 0, 0, 1),
    (0, 1, -1, 0, 0, -1, 1, 0),
    (0, 1, 1, 0, 0, -1, -1, 0),
    (1, 0, 0, 1, -1, 0, 0, -1),
)


def _cast(level, cx, cy, row, start, end, radius, xx, xy, yx, yy, lit):
    if start < end:
        return
    radius2 = radius * radius
    for j in range(row, radius + 1):
        dx, dy = -j - 1, -j
        blocked = False
        new_start = start
        while dx <= 0:
            dx += 1
            x = cx + dx * xx + dy * xy
            y = cy + dx * yx + dy * yy
            l_slope = (dx - 0.5) / (dy + 0.5)
            r_slope = (dx + 0.5) / (dy - 0.5)
            if start < r_slope:
                continue
            if end > l_slope:
                break
            if dx * dx + dy * dy <= radius2:
                lit.add((x, y))
            if blocked:
                if level.blocks_sight(x, y):
                    new_start = r_slope
                    continue
                blocked = False
                start = new_start
            else:
                if level.blocks_sight(x, y) and j < radius:
                    blocked = True
                    _cast(level, cx, cy, j + 1, start, l_slope, radius, xx, xy, yx, yy, lit)
                    new_start = r_slope
        if blocked:
            break


def compute(level, cx: int, cy: int, radius: int = 9) -> set:
    lit = {(cx, cy)}
    for k in range(8):
        _cast(level, cx, cy, 1, 1.0, 0.0, radius,
              MULT[0][k], MULT[1][k], MULT[2][k], MULT[3][k], lit)
    return {(x, y) for (x, y) in lit if level.in_bounds(x, y)}
