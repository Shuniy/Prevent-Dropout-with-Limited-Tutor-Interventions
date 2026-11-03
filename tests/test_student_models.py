import csv
import unittest
from dataclasses import fields, replace
from pathlib import Path

from src.models.student import Student, StudentSimulation
from src.utils.school import DEFAULT_STUDENT_DATA_PATH, load_students


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
    def low_need_student(self):
        return replace(
            load_students(DEFAULT_STUDENT_DATA_PATH, 1)[0],
            anchor_grade1_0_20=10, math_grade1_0_20=None,
            past_failures_count=0, internet_at_home=True, travel_time_category=2,
            study_time_category=2, family_relationship_rating=3, health_self_rating=3,
            initial_attendance_fraction_assumed=0.85, initial_engagement_assumed=0.6,
            enrolled_initial_assumed=True, financial_need_verified=None,
        )

    def test_need_properties_respect_thresholds_and_unknowns(self):
        student = self.low_need_student()
        self.assertEqual(student.need_score, 0)
        self.assertEqual(student.primary_support_type, "tutoring")
        self.assertEqual(len(student.need_profile), 1)
        basic = Student(**{item.name: getattr(student, item.name) for item in fields(Student)})
        self.assertIsNone(basic.initial_scores["attendance_fraction_assumed"])
        self.assertIsNone(basic.initial_scores["engagement_assumed"])
        self.assertIsNone(basic.initial_scores["school_dropout_risk"])
        self.assertNotIn("family_finances", [need["support_type"] for need in basic.need_profile])
        self.assertEqual(replace(student, financial_need_verified=True).need_score, 0.75)

    def test_need_profile_recomputes_without_mutating_source(self):
        student = self.low_need_student()
        profile = student.need_profile
        profile[0]["severity"] = 1
        self.assertEqual(student.need_score, 0)
        student.internet_at_home = False
        self.assertEqual(student.primary_support_type, "device_access")
        self.assertEqual(student.need_score, 0.5)
        student.travel_time_category = 4
        self.assertEqual(student.primary_support_type, "transport_assessment")
        self.assertEqual(student.need_score, 1)
        self.assertNotIn("need_profile", {item.name for item in fields(student)})

    def test_need_properties_reject_invalid_optional_fractions(self):
        for field_name in ("initial_attendance_fraction_assumed", "initial_engagement_assumed"):
            for value in (-0.1, 1.1, float("nan")):
                with self.subTest(field=field_name, value=value):
                    with self.assertRaises(ValueError):
                        replace(self.low_need_student(), **{field_name: value}).need_profile

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
