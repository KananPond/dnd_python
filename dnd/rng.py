"""确定性随机数发生器（xoshiro256** + splitmix64 播种）。

内核禁止使用 random / time：同一种子 + 同一输入序列必须得到完全一致的结果，
这是回放测试与机器人压测的前提。状态可 JSON 序列化。
"""

from __future__ import annotations

MASK64 = (1 << 64) - 1


def _splitmix64(state: int):
    state = (state + 0x9E3779B97F4A7C15) & MASK64
    z = state
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK64
    return state, z ^ (z >> 31)


def _rotl(x: int, k: int) -> int:
    return ((x << k) | (x >> (64 - k))) & MASK64


class RNG:
    """可序列化的确定性 PRNG（xoshiro256**）。"""

    __slots__ = ("s",)

    def __init__(self, seed: int = 0):
        self.s = self._seed_state(seed)

    @staticmethod
    def _seed_state(seed: int):
        st = seed & MASK64
        out = []
        for _ in range(4):
            st, z = _splitmix64(st)
            out.append(z)
        if all(v == 0 for v in out):
            out[0] = 1
        return out

    # --- 序列化 ---
    def to_json(self):
        return list(self.s)

    @classmethod
    def from_json(cls, data):
        obj = cls(0)
        obj.s = [int(v) & MASK64 for v in data]
        return obj

    # --- 核心 ---
    def next_u64(self) -> int:
        s = self.s
        result = (_rotl((s[1] * 5) & MASK64, 7) * 9) & MASK64
        t = (s[1] << 17) & MASK64
        s[2] ^= s[0]
        s[3] ^= s[1]
        s[1] ^= s[2]
        s[0] ^= s[3]
        s[2] ^= t
        s[3] = _rotl(s[3], 45)
        return result

    def randint(self, lo: int, hi: int) -> int:
        """闭区间 [lo, hi]。"""
        if hi <= lo:
            return lo
        span = hi - lo + 1
        return lo + self.next_u64() % span

    def random(self) -> float:
        return self.next_u64() / float(1 << 64)

    def chance(self, p: float) -> bool:
        return self.random() < p

    def choice(self, seq):
        return seq[self.randint(0, len(seq) - 1)]

    def weighted_choice(self, entries):
        """entries: [(item, weight), ...]"""
        total = sum(max(0.0, float(w)) for _, w in entries)
        if total <= 0:
            return entries[0][0]
        pick = self.random() * total
        acc = 0.0
        for item, w in entries:
            acc += max(0.0, float(w))
            if pick < acc:
                return item
        return entries[-1][0]

    def shuffle(self, seq):
        for i in range(len(seq) - 1, 0, -1):
            j = self.randint(0, i)
            seq[i], seq[j] = seq[j], seq[i]
        return seq
