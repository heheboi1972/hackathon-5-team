"""상대 값이 응답 투영에서 제거되는 최소 계약 테스트."""

import unittest

from app.services.projection import project_pair


class ProjectionTest(unittest.TestCase):
    def test_only_couple_and_mine_are_returned(self) -> None:
        projected = project_pair({"couple": 0.4, "a": 0.2, "b": 0.6}, "a")
        self.assertEqual(projected, {"couple": 0.4, "mine": 0.2})
        self.assertNotIn("a", projected)
        self.assertNotIn("b", projected)


if __name__ == "__main__":
    unittest.main()

