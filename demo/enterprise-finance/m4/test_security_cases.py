import json
import unittest
from pathlib import Path


class SecurityCasesTest(unittest.TestCase):
    def test_attack_set_is_unique_and_covers_required_boundaries(self):
        payload = json.loads(
            (Path(__file__).with_name("security-cases.json")).read_text(encoding="utf-8")
        )
        attacks = payload["attacks"]
        self.assertGreaterEqual(len(attacks), 6)
        self.assertEqual(len(attacks), len({case["id"] for case in attacks}))
        codes = {case["expectedCode"] for case in attacks}
        self.assertTrue(
            {
                "SQL_SECURITY_READ_ONLY",
                "SQL_SECURITY_SINGLE_STATEMENT",
                "SQL_SECURITY_FUNCTION",
                "SQL_SECURITY_TABLE_ALLOWLIST",
                "SQL_SECURITY_COLUMN_ALLOWLIST",
                "SQL_SECURITY_DATA_SCOPE",
                "SQL_HUMAN_REVIEW_REQUIRED",
            }.issubset(codes)
        )


if __name__ == "__main__":
    unittest.main()
