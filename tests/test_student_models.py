import unittest
from dataclasses import fields, replace

from src.school.student import Student
from src.utils.constants import DEFAULT_STUDENT_DATA_PATH
from src.school.loading import load_students


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

    def test_need_properties_reject_invalid_optional_fractions(self):
        for field_name in ("initial_attendance_fraction_assumed", "initial_engagement_assumed"):
            for value in (-0.1, 1.1, float("nan")):
                with self.subTest(field=field_name, value=value):
                    with self.assertRaises(ValueError):
                        replace(self.low_need_student(), **{field_name: value}).need_profile

    def test_learning_gap_uses_available_grades(self):
        student = self.low_need_student()
        self.assertEqual(replace(student, anchor_grade1_0_20=2).learning_gap, 0.8)
        self.assertEqual(replace(student, anchor_grade1_0_20=2, math_grade1_0_20=10).learning_gap, 0.4)
        self.assertEqual(replace(student, anchor_grade1_0_20=18).learning_gap, 0)

    def test_access_properties_reflect_source_values(self):
        student = replace(self.low_need_student(), mother_education_code=2,
                          father_education_code=1, internet_at_home=False, travel_time_category=3)
        self.assertTrue(student.both_parents_education_at_most_2)
        self.assertTrue(student.no_home_internet)
        self.assertTrue(student.travel_over_30min)
        self.assertEqual(student.disadvantage_proxy_count, 3)
        self.assertTrue(student.disadvantage_proxy_group)
        self.assertFalse(replace(student, father_education_code=3,
                                 internet_at_home=True).disadvantage_proxy_group)

    def test_support_rules_select_the_expected_support(self):
        cases = [
            ({"enrolled_initial_assumed": False}, "reentry_support"),
            ({"past_failures_count": 1}, "tutoring"),
            ({"initial_attendance_fraction_assumed": 0.7}, "attendance_planning"),
            ({"internet_at_home": False}, "device_access"),
            ({"travel_time_category": 3}, "transport_assessment"),
            ({"study_time_category": 1}, "homework_support"),
            ({"family_relationship_rating": 2}, "family_liaison"),
            ({"health_self_rating": 2}, "wellbeing_checkin"),
            ({"initial_engagement_assumed": 0.5}, "peer_support"),
            ({"financial_need_verified": True}, "family_finances"),
        ]
        for changes, support in cases:
            with self.subTest(support=support):
                student = replace(self.low_need_student(), **changes)
                self.assertEqual(student.primary_support_type, support)
                self.assertGreater(student.need_score, 0)


if __name__ == "__main__":
    unittest.main()
