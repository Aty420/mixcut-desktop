"""Exact distance-1/2 codebooks for unequal group sizes, without cartesian expansion."""
from __future__ import annotations

import itertools
import math
import random
from collections.abc import Iterable, Iterator, Sequence


def minimum_distance(group_count: int) -> int:
    if group_count < 2:
        raise ValueError("至少需要2个素材子文件夹")
    return 1 if group_count <= 3 else 2


def capacity(sizes: Sequence[int], distance: int) -> int:
    if len(sizes) < 2 or any(s <= 0 for s in sizes):
        raise ValueError("每个素材组至少需要1条有效视频")
    if distance not in (1, 2):
        raise ValueError("仅支持至少1段或2段不同")
    count = math.prod(sizes)
    return count if distance == 1 else count // max(sizes)


def decode(index: int, sizes: Sequence[int]) -> list[int]:
    digits = []
    for size in reversed(sizes):
        index, digit = divmod(index, size)
        digits.append(digit)
    return list(reversed(digits))


def codebook(sizes: Sequence[int], distance: int, seed: int = 17) -> Iterator[tuple[int, ...]]:
    """Maximum-size code for a fresh catalog; random traversal without replacement.

    For d=2 use the largest alphabet q as a checksum coordinate. Every
    other coordinate is <q, so changing just one coordinate changes the
    checksum mod q. Deleting the largest coordinate gives the matching
    upper bound product(sizes)/q. An affine permutation avoids materializing
    the cartesian product, even when it contains billions of combinations.
    """
    total = capacity(sizes, distance)
    rng = random.Random(seed)
    start = rng.randrange(total)
    step = rng.randrange(1, total + 1)
    while math.gcd(step, total) != 1:
        step = step % total + 1
    pivot = max(range(len(sizes)), key=lambda i: sizes[i])
    reduced = list(sizes) if distance == 1 else [s for i, s in enumerate(sizes) if i != pivot]
    offset = seed % sizes[pivot]
    for k in range(total):
        row = decode((start + k * step) % total, reduced)
        if distance == 2:
            row.insert(pivot, (sum(row) + offset) % sizes[pivot])
        yield tuple(row)


class DistanceIndex:
    """O(n) membership checks per candidate; protects against ALL historic rows."""

    def __init__(self, width: int, distance: int, rows: Iterable[Sequence[str]] = ()):
        self.width = width
        self.distance = distance
        self.keys: set[tuple] = set()
        for row in rows:
            self.add(row)

    def signatures(self, row: Sequence[str]) -> Iterator[tuple]:
        if len(row) != self.width:
            raise ValueError("历史记录与当前素材组数量不一致")
        if self.distance == 1:
            yield tuple(row)
        else:
            for omit in range(self.width):
                yield (omit, *row[:omit], *row[omit + 1:])

    def allows(self, row: Sequence[str]) -> bool:
        return not any(key in self.keys for key in self.signatures(row))

    def add(self, row: Sequence[str]) -> None:
        self.keys.update(self.signatures(row))


def assert_distance(rows: Sequence[Sequence], distance: int) -> None:
    for left, right in itertools.combinations(rows, 2):
        if sum(a != b for a, b in zip(left, right)) < distance:
            raise AssertionError(f"组合差异不足: {left}, {right}")
