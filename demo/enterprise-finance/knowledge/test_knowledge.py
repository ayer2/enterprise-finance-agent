import json
import re
import unittest
from pathlib import Path


KNOWLEDGE_DIR = Path(__file__).resolve().parent
DEMO_DIR = KNOWLEDGE_DIR.parent


def load_json(name: str):
    return json.loads((KNOWLEDGE_DIR / name).read_text(encoding="utf-8"))


class KnowledgeAssetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        schema = (DEMO_DIR / "sql" / "01_schema.sql").read_text(encoding="utf-8")
        cls.schema_columns = {}
        for table_name, body in re.findall(
            r"CREATE TABLE\s+(\w+)\s*\((.*?)\)\s*COMMENT=",
            schema,
            flags=re.DOTALL | re.IGNORECASE,
        ):
            cls.schema_columns[table_name] = {
                match.group(1)
                for line in body.splitlines()
                if (match := re.match(r"\s*([a-z][a-z0-9_]*)\s+[A-Z]", line))
            }

    def test_semantic_models_reference_real_columns(self):
        models = load_json("semantic-models.json")
        self.assertGreaterEqual(len(models), 50)
        keys = set()
        for model in models:
            key = (model["tableName"], model["columnName"])
            self.assertNotIn(key, keys)
            keys.add(key)
            self.assertIn(model["tableName"], self.schema_columns)
            self.assertIn(model["columnName"], self.schema_columns[model["tableName"]])
            for required in ("businessName", "businessDescription", "dataType"):
                self.assertTrue(model[required].strip())

    def test_core_metrics_have_business_knowledge(self):
        knowledge = load_json("business-knowledge.json")
        terms = {item["businessTerm"] for item in knowledge}
        self.assertTrue({"销售额", "回款率", "预算执行率", "逾期应收", "KPI完成率"} <= terms)
        for item in knowledge:
            self.assertTrue(item["description"].strip())
            self.assertTrue(item["synonyms"].strip())

    def test_standard_questions_are_natural_and_read_only(self):
        questions = load_json("标准问答.json")
        self.assertGreaterEqual(len(questions), 15)
        self.assertEqual(len(questions), len({item["id"] for item in questions}))
        self.assertEqual(len(questions), len({item["question"] for item in questions}))
        for item in questions:
            sql = item["sql"].strip()
            self.assertRegex(sql.upper(), r"^(SELECT|WITH)\b")
            self.assertEqual(sql.count(";"), 1)
            self.assertTrue(sql.endswith(";"))
            self.assertNotRegex(sql.upper(), r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE)\b")
            self.assertTrue(item["question"].endswith("？"))
            self.assertTrue(item["expectedColumns"])


if __name__ == "__main__":
    unittest.main()
