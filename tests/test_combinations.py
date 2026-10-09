import itertools
import unittest

from mixcut.combinations import DistanceIndex, assert_distance, capacity, codebook, minimum_distance


class CombinationTests(unittest.TestCase):
    def test_user_rules(self):
        self.assertEqual([minimum_distance(n) for n in (2, 3, 4, 5)], [1, 1, 2, 2])

    def test_unequal_alphabets_exhaustively(self):
        for n in (2, 3, 4):
            for sizes in itertools.product(range(1, 4), repeat=n):
                distance = minimum_distance(n)
                rows = list(codebook(sizes, distance))
                self.assertEqual(len(rows), capacity(sizes, distance), sizes)
                self.assertEqual(len(rows), len(set(rows)))
                for row in rows:
                    self.assertTrue(all(0 <= pos < size for pos, size in zip(row, sizes)))
                assert_distance(rows, distance)

    def test_four_groups_maximum(self):
        for sizes in ((3, 3, 3, 3), (3, 4, 2, 5), (1, 1, 1, 7), (7, 2, 3, 4), (2, 3, 2, 3, 2)):
            rows = list(codebook(sizes, 2))
            self.assertEqual(len(rows), capacity(sizes, 2))
            assert_distance(rows, 2)

    def test_not_just_adjacent(self):
        index = DistanceIndex(4, 2, [("a", "b", "c", "d"), ("w", "x", "y", "z")])
        self.assertFalse(index.allows(("a", "b", "c", "z")))
        self.assertFalse(index.allows(("a", "b", "c", "d")))
        self.assertTrue(index.allows(("a", "x", "c", "z")))

    def test_huge_catalog_is_lazy(self):
        rows = list(itertools.islice(codebook([10000] * 4, 2), 100))
        self.assertEqual(len(rows), 100)
        assert_distance(rows, 2)

    def test_invalid_input(self):
        with self.assertRaises(ValueError):
            minimum_distance(1)
        with self.assertRaises(ValueError):
            capacity([0, 1], 1)


if __name__ == "__main__":
    unittest.main()
