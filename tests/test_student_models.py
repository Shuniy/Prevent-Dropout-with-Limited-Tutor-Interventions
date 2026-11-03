import csv
import unittest
from dataclasses import fields
from pathlib import Path

from src.models.student import Student, StudentSimulation


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DERIVED_FIELDS = {
    "both_parents_education_at_most_2",
    "no_home_internet",
    "travel_over_30min",
    "disadvantage_proxy_count",
    "disadvantage_proxy_group",
    "learning_gap_initial_assumed",
}


class StudentModelTests(unittest.TestCase):
    def test_student_params_exclude_derived_dataset_fields(self) -> None:
        path = PROJECT_ROOT / "data/processed/students/student_dataset.csv"
        with path.open(newline="", encoding="utf-8") as source:
            columns = set(next(csv.reader(source)))

        model_fields = {field.name for field in fields(Student)}
        self.assertTrue(model_fields <= columns)
        self.assertTrue(model_fields.isdisjoint(DERIVED_FIELDS))

    def test_synthetic_params_exclude_derived_dataset_fields(self) -> None:
        path = PROJECT_ROOT / "data/synthetic/populations/synthetic_student_population.csv"
        with path.open(newline="", encoding="utf-8") as source:
            columns = set(next(csv.reader(source)))

        model_fields = {field.name for field in fields(StudentSimulation)}
        self.assertTrue(model_fields <= columns)
        self.assertTrue(model_fields.isdisjoint(DERIVED_FIELDS))

    def test_properties_reproduce_dataset_derivations(self) -> None:
        path = PROJECT_ROOT / "data/processed/students/student_dataset.csv"
        model_fields = {field.name for field in fields(Student)}

        with path.open(newline="", encoding="utf-8") as source:
            for row in csv.DictReader(source):
                params = {name: row[name] for name in model_fields}
                params["internet_at_home"] = row["internet_at_home"] == "1"
                params["travel_time_category"] = int(row["travel_time_category"])
                params["mother_education_code"] = int(row["mother_education_code"])
                params["father_education_code"] = int(row["father_education_code"])
                params["anchor_grade1_0_20"] = int(row["anchor_grade1_0_20"])
                params["math_grade1_0_20"] = int(row["math_grade1_0_20"]) if row["math_grade1_0_20"] else None
                student = Student(**params)

                self.assertEqual(student.no_home_internet, row["no_home_internet"] == "1")
                self.assertEqual(student.travel_over_30min, row["travel_over_30min"] == "1")
                self.assertEqual(student.disadvantage_proxy_count, int(row["disadvantage_proxy_count"]))
                self.assertEqual(student.disadvantage_proxy_group, row["disadvantage_proxy_group"] == "1")
                grades = [params["anchor_grade1_0_20"]]
                if params["math_grade1_0_20"] is not None:
                    grades.append(params["math_grade1_0_20"])
                expected_gap = max(0.0, (10 - sum(grades) / len(grades)) / 10)
                self.assertAlmostEqual(student.learning_gap, expected_gap)


if __name__ == "__main__":
    unittest.main()
