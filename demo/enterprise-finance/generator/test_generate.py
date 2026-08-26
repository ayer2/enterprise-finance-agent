import tempfile
import unittest
from pathlib import Path

from generate import build_manifest, generate_dataset, load_config, write_sql


class GenerateDatasetTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.demo_dir = Path(__file__).resolve().parent.parent
        cls.config = load_config(cls.demo_dir / "config.json")
        cls.dataset = generate_dataset(cls.config)

    def test_expected_row_and_anomaly_counts(self) -> None:
        self.assertEqual(20_000, len(self.dataset.orders))
        self.assertEqual(50_000, len(self.dataset.order_items))
        self.assertEqual(18_050, len(self.dataset.receivables))
        self.assertGreaterEqual(len(self.dataset.payments), 20_000)
        self.assertLessEqual(len(self.dataset.payments), 30_000)
        self.assertEqual(
            {"A01": 1, "A02": 1, "A03": 950, "A04": 120, "A05": 20, "A06": 50},
            {row[0]: row[1] for row in self.dataset.expectations},
        )

    def test_primary_and_business_numbers_are_unique(self) -> None:
        self.assertEqual(len(self.dataset.orders), len({row[0] for row in self.dataset.orders}))
        self.assertEqual(len(self.dataset.orders), len({row[1] for row in self.dataset.orders}))
        self.assertEqual(len(self.dataset.receivables), len({row[1] for row in self.dataset.receivables}))
        self.assertEqual(len(self.dataset.payments), len({row[1] for row in self.dataset.payments}))

    def test_same_seed_produces_identical_sql(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_a = Path(directory) / "a.sql"
            output_b = Path(directory) / "b.sql"
            hash_a = write_sql(output_a, self.dataset)
            second_dataset = generate_dataset(self.config)
            hash_b = write_sql(output_b, second_dataset)
            self.assertEqual(hash_a, hash_b)
            self.assertEqual(output_a.read_bytes(), output_b.read_bytes())
            manifest = build_manifest(self.config, second_dataset, hash_b)
            self.assertEqual(20_000, manifest["row_counts"]["sales_order"])

    def test_generated_sql_declares_utf8mb4_client_encoding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "generated.sql"
            write_sql(output, self.dataset)

            self.assertIn("SET NAMES utf8mb4;", output.read_text(encoding="utf-8").splitlines()[:3])


if __name__ == "__main__":
    unittest.main()
