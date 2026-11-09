"""Hand-calculated weekly delivery invariants, independent of policy scores."""
from dataclasses import replace
import unittest

from src.school.delivery_config import DeliveryConfig
from src.school.delivery_contracts import DeliveryAction, SupportOffer, StudentProfile
from src.school.delivery_environment import WeeklyDeliveryEnvironment
from src.school.delivery_resources import audit_delivery_events
from src.school.mentor import Mentor
from src.school.mentor_availability import MentorAvailability
from src.school.student_condition import StudentCondition


def world(*, count=3, mentors=2, **overrides):
    identity = tuple(tuple(float(i == j) for j in range(4)) for i in range(4))
    overrides.setdefault('weekly_wait_matrix', identity)
    overrides.setdefault('weekly_tutoring_matrix', identity)
    config = DeliveryConfig(num_students=count, num_mentors=mentors, horizon_weeks=8, acceptance_probability=1,
        attendance_probability=1, delivery_probability=1, cancellation_probability=0,
        **overrides)
    profiles = tuple(StudentProfile(f's{i}', 'tutoring', .5, bool(i % 2), 'F')
                     for i in range(count))
    staff = tuple(Mentor(f'm{i}', ['tutoring'], config.max_concurrent_students,
        availability_by_step=[MentorAvailability(w, config.weekly_mentor_hours,
            config.weekly_session_capacity) for w in range(1, config.horizon_weeks + 1)],
        cost_units_per_session=config.cost_per_session) for i in range(mentors))
    return WeeklyDeliveryEnvironment(profiles, staff, config,
        initial_conditions=tuple((p.student_id, StudentCondition.VULNERABLE) for p in profiles))


class LifecycleTests(unittest.TestCase):
    def test_five_sessions_are_delivered_across_five_weeks(self):
        env = world(cost_per_session=.1, administrative_offer_cost=.2, budget=2)
        env.step(DeliveryAction((SupportOffer('s0', 'm0', 1),)))
        programme = env.programmes[0]
        self.assertEqual(programme.status, 'ACTIVE')
        self.assertEqual(programme.delivered_sessions, 1)
        self.assertEqual(tuple(s.week for s in programme.sessions), (1, 2, 3, 4, 5))
        self.assertEqual(env.ledger.spent, '0.3')
        self.assertEqual(env.ledger.reserved, '0.4')
        for _ in range(4):
            env.step(DeliveryAction())
        self.assertEqual(env.programmes[0].status, 'COMPLETED')
        self.assertEqual(env.ledger.spent, '0.7')
        self.assertEqual(env.ledger.reserved, '0.0')

    def test_refusal_counts_as_offer_and_releases_service(self):
        env = world()
        env.step(DeliveryAction((SupportOffer('s0', 'm0', 1),)),
                 outcomes={('s0', 'acceptance', 1): False})
        self.assertEqual(env.programmes[0].status, 'REFUSED')
        self.assertEqual(env.programmes[0].delivered_sessions, 0)
        self.assertEqual(float(env.ledger.reserved), 0)
        self.assertTrue(any(e.kind == 'offer_refused' for e in env.events))

    def test_miss_is_partial_and_no_automatic_rescheduling(self):
        env = world()
        env.step(DeliveryAction((SupportOffer('s0', 'm0', 1),)),
                 outcomes={('s0', 'attendance', 1): False})
        for _ in range(4):
            env.step(DeliveryAction())
        self.assertEqual(env.programmes[0].status, 'INCOMPLETE')
        self.assertEqual(env.programmes[0].delivered_sessions, 4)
        self.assertEqual(len(env.programmes[0].sessions), 5)

    def test_cancel_releases_only_unused_reservations(self):
        env = world(cost_per_session=1, administrative_offer_cost=0)
        env.step(DeliveryAction((SupportOffer('s0', 'm0', 1),)))
        pid = env.programmes[0].programme_id
        env.step(DeliveryAction(cancel_programme_ids=(pid,)))
        self.assertEqual(env.programmes[0].status, 'CANCELLED')
        self.assertEqual(float(env.ledger.spent), 1)
        self.assertEqual(float(env.ledger.reserved), 0)
        self.assertEqual(float(env.ledger.released), 4)

    def test_capacity_hours_caseload_and_horizon(self):
        env = world(weekly_mentor_hours=1, weekly_session_capacity=2)
        with self.assertRaises(ValueError):
            env.step(DeliveryAction((SupportOffer('s0', 'm0', 1), SupportOffer('s1', 'm0', 1))))
        self.assertFalse(env.events)
        for _ in range(4):
            env.step(DeliveryAction())
        with self.assertRaises(ValueError):
            env.step(DeliveryAction((SupportOffer('s0', 'm0', 5),)))

    def test_auditor_rejects_altered_session_schedule(self):
        env = world()
        env.step(DeliveryAction((SupportOffer('s0', 'm0', 1),)))
        events = list(env.events)
        index = next(i for i, e in enumerate(events) if e.kind == 'session_reserved')
        events[index] = replace(events[index], scheduled_week=99)
        with self.assertRaises(ValueError):
            audit_delivery_events(env.config, env.mentors, tuple(events))


if __name__ == '__main__':
    unittest.main()
