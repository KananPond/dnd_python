"""dnd —— PLATO(1975) 同名地牢爬行游戏的现代 Python 复刻。

设计原则见 docs/reimplementation-plan.md：
  L1 忠实层：单屏字符地牢、俯视、逐层下潜、掷骰战斗、角色持久化、永久死亡
  L2 现代化层：键位/帮助/存档导入导出/信息面板
  L3 自由发挥层：职业/法术/怪物/数值（原版数据不可得，见 data/*.json 的 _meta）
"""

__version__ = "0.1.0"
