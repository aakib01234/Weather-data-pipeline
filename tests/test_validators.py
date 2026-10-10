import unittest

from src.etl_pipeline import transform
from src.validators import run_quality_checks, validate_record
from tests.helpers import CITY, make_db, raw_payload


class ValidateRecordTests(unittest.TestCase):
    def good(self):
        return transform(raw_payload(), CITY)

    def test_valid_record_has_no_errors(self):
        self.assertEqual(validate_record(self.good()), [])

    def test_missing_required_field(self):
        rec = self.good()
        rec["temperature_c"] = None
        self.assertTrue(any("temperature_c" in e for e in validate_record(rec)))

    def test_out_of_range_values(self):
        rec = self.good()
        rec["humidity"] = 140
        rec["temperature_c"] = 99
        errors = validate_record(rec)
        self.assertEqual(len(errors), 2)

    def test_optional_field_may_be_missing(self):
        rec = self.good()
        rec["pressure_hpa"] = None
        self.assertEqual(validate_record(rec), [])


class QualityCheckTests(unittest.TestCase):
    def test_empty_database(self):
        tmp, db = make_db()
        self.addCleanup(tmp.cleanup)
        result = run_quality_checks(db)
        self.assertEqual(result["total_records"], 0)
        self.assertTrue(result["passed"])


if __name__ == "__main__":
    unittest.main()
