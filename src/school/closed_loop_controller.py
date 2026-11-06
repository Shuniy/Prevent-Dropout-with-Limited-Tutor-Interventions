"""Monthly feedback coordinator; all transitions/accounting stay in CMDPEnvironment."""

from dataclasses import asdict, replace

from ..intervention.feedback_notes import NoteQuality, render_note
from ..intervention.observation_extractor import FixtureObservationExtractor
from .constraints import validate_allocation
from .fairness_window import FairnessWindow
from .observation_model import ObservationConfig, SyntheticObservationModel
from .retention_value import estimate_all_student_benefits
from .simulated_withdrawal_risk import SimulatedWithdrawalRiskEstimator
from .state_estimator import StudentStateEstimator


INFORMATION_MODES = ("oracle", "structured", "b_matched", "llm_notes", "noisy_notes")


class ClosedLoopCMDPController:
    def __init__(self, environment, policy, *, mode="structured", extractor=None,
                 observation_config=ObservationConfig(), note_quality=NoteQuality(),
                 max_notes_per_month=None, estimator=None, note_quality_by_student=None):
        if mode not in INFORMATION_MODES:
            raise ValueError("unknown information mode")
        if mode in ("llm_notes", "noisy_notes") and extractor is None:
            raise ValueError("note mode requires an explicit real or fixture extractor")
        if max_notes_per_month is not None and (type(max_notes_per_month) is not int or max_notes_per_month < 0):
            raise ValueError("max_notes_per_month must be a non-negative integer or None")
        self.environment, self.policy, self.mode = environment, policy, mode
        self.extractor = extractor
        self.gold_extractor = FixtureObservationExtractor()
        self.observation_model = SyntheticObservationModel(observation_config)
        self.note_quality, self.max_notes_per_month = note_quality, max_notes_per_month
        # Synthetic information-quality experiments may assign an authorized
        # source group a different note channel. Only the renderer sees these
        # declared qualities; no hidden conditions or audit groups enter prompts.
        self.note_quality_by_student = dict(note_quality_by_student or {})
        if any(not isinstance(quality, NoteQuality)
               for quality in self.note_quality_by_student.values()):
            raise ValueError("student note qualities must be NoteQuality records")
        # Assumed controller matrices come from the planner, recorded separately
        # from the environment parameters for future misspecification studies.
        self.estimator = estimator or StudentStateEstimator(
            observation_config=observation_config, wait_matrix=policy.wait_matrix,
            treatment_matrix=policy.programme_matrix)
        self.risk_estimator = SimulatedWithdrawalRiskEstimator(self.estimator.wait)
        self.events, self.registry, self.notes, self.batches = [], [], [], []
        self.extraction_attempts = []
        self.estimates, self.processed, self.failures = {}, set(), []
        self.decisions, self.snapshots, self.risks, self.fairness_rows = [], [], [], []
        self.evaluator_truth, self.windows = [], []
        self._initialized = False

    def initialize(self):
        if self._initialized or self.environment.records:
            raise ValueError("closed-loop initialization requires a fresh episode")
        self._initialized = True
        # Initial truth is evaluator-only. Ordinary decision construction below
        # never calls the legacy exact-enrollment observe() interface.
        oracle = self.environment.observe()
        self.evaluator_truth.append({"month": 0, "conditions": tuple(
            (s.student_id, s.condition) for s in oracle.students)})
        self._generate_observations()

    def _generate_observations(self):
        events, registry = self.environment.generate_observable_records(self.observation_model)
        self.events.extend(events)
        self.registry.extend(registry)
        selected = events
        if self.max_notes_per_month is not None:
            # Limit intervention notes, never routine monitoring. Rotating only
            # among programme events prevents unrelated students consuming the cap.
            programmes = [event for event in events if event.programme_id is not None]
            start = (programmes[0].event_month * self.max_notes_per_month) % len(programmes) if programmes else 0
            selected_ids = {event.event_id for event in
                            (programmes[start:] + programmes[:start])[:self.max_notes_per_month]}
            selected = [event for event in events
                        if event.programme_id is None or event.event_id in selected_ids]
        self.notes.extend(render_note(event, seed=self.environment.config.seed,
                                     quality=self.note_quality_by_student.get(
                                         event.student_id, self.note_quality)) for event in selected)

    def process_new_observations(self, month):
        incoming = {sid: [] for sid in self.estimates}
        # B uses full structured emissions. B-matched contains only note-supported
        # facts, including exactly the same omission/delay/contradiction process.
        sources = ([render_note(event, seed=self.environment.config.seed) for event in self.events]
                   if self.mode in ("structured", "oracle") else self.notes)
        for note in sources:
            if note.note_id in self.processed or note.available_from_month > month:
                continue
            self.processed.add(note.note_id)
            # Routine monitoring uses the declared synthetic grammar, with no
            # LLM call. Only delivered programme notes use the injected extractor.
            # Both paths keep the note's omissions, conflicts and availability.
            extractor = (self.gold_extractor
                         if self.mode in ("structured", "oracle", "b_matched")
                         or note.note_type == "monitoring" else self.extractor)
            try:
                batch = extractor.extract(note, month)
                incoming.setdefault(note.student_id, []).append(batch)
                self.batches.append(batch)
            except (ValueError, RuntimeError, OSError, KeyError, TypeError) as exc:
                self.failures.append({"note_id": note.note_id, "as_of_month": month, "reason": str(exc)})
            finally:
                if hasattr(extractor, "audit_records") and extractor.audit_records:
                    self.extraction_attempts.append(extractor.audit_records[-1])
        current_registry = tuple(r for r in self.registry if r.event_month == month - 1)
        history = self.decisions
        for record in current_registry:
            sid = record.student_id
            actions = tuple(row["month"] for row in history if sid in row["admitted_ids"])
            records = tuple(r for r in self.registry if r.student_id == sid and r.available_from_month <= month)
            previous = self.estimates.get(sid)
            self.estimates[sid] = (self.estimator.update(previous, incoming.get(sid, ()), actions,
                as_of_month=month, registry=records) if previous else
                self.estimator.initialize(sid, incoming.get(sid, ()), registry=records, as_of_month=month))
        return current_registry

    def prepare_decision_snapshot(self, month):
        registry = self.process_new_observations(month)
        estimates = tuple(self.estimates.values())
        horizon = self.environment.config.horizon - month + 1
        risks = tuple(self.risk_estimator.predict(estimate, horizon) for estimate in estimates)
        self.risks.extend(risks)
        snapshot = (self.environment.observe() if self.mode == "oracle" else
                    self.environment.operational_snapshot(registry, estimates=estimates, risks=risks))
        if snapshot.month != month:
            raise ValueError("controller/environment decision cutoff mismatch")
        return snapshot

    def allocate(self, decision_input):
        allocation = self.policy.plan(decision_input)
        validate_allocation(decision_input, allocation.assignments)
        return allocation

    def run_episode(self):
        if not self._initialized:
            self.initialize()
        config = self.environment.config
        while not self.environment.done:
            month = len(self.environment.records) + 1
            snapshot = self.prepare_decision_snapshot(month)
            self.snapshots.append(snapshot)
            if (month - 1) % config.fairness_window == 0:
                window = FairnessWindow.initialize(snapshot, window_months=config.fairness_window,
                    target=config.fairness_min_access, attribute=config.fairness_grouping_attribute)
                self.windows.append(window)
            window.update(snapshot)
            allocation = self.allocate(snapshot)
            benefits = estimate_all_student_benefits(snapshot, self.policy.wait_matrix, self.policy.programme_matrix)
            # Environment independently checks exact feasibility and executes
            # delivery and transitions with its existing keyed random stream.
            record = self.environment.step(allocation)
            admitted = tuple(a.student_id for a in allocation.assignments)
            histories = tuple(replace(s, programme_months=(*s.programme_months, month))
                              if s.student_id in admitted else s for s in snapshot.students)
            window.update(replace(snapshot, students=histories))
            self.fairness_rows.extend({**row, "decision_month": month} for row in window.rows())
            self.decisions.append({"month": month, "cutoff": month, "seed": config.seed,
                "admitted_ids": admitted, "allocation": asdict(allocation),
                "benefits": benefits, "remaining_budget_before": snapshot.remaining_budget,
                "remaining_budget_after": record.remaining_budget,
                "spending": snapshot.remaining_budget - record.remaining_budget,
                "fairness_window_start": window.start, "fairness_window_end": window.end})
            self.evaluator_truth.append({"month": month, "conditions": record.conditions})
            self._generate_observations()
        # Process terminal evidence/risk at cutoff T+1; there is no 13th allocation.
        self.process_new_observations(config.horizon + 1)
        self.risks.extend(self.risk_estimator.predict(e, 0) for e in self.estimates.values())
        return self
