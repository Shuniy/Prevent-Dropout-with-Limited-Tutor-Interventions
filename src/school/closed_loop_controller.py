"""Monthly feedback coordinator; all transitions/accounting stay in CMDPEnvironment."""

from dataclasses import asdict, replace
from hashlib import sha256
import json

from ..intervention.feedback_notes import NoteQuality, SIGNAL_PHRASES, render_note
from ..intervention.observation_extractor import FixtureObservationExtractor, validate_batch
from .constraints import validate_allocation
from .fairness_window import FairnessWindow
from .observation_model import ObservationConfig, SyntheticObservationModel
from .retention_value import estimate_all_student_benefits
from .simulated_withdrawal_risk import SimulatedWithdrawalRiskEstimator
from .state_estimator import StudentStateEstimator


INFORMATION_MODES = ("oracle", "structured", "b_matched", "llm_notes", "noisy_notes")
EXTRACTION_CONTRACTS = ("actionable_monitoring", "legacy_programme_only")


class ClosedLoopCMDPController:
    def __init__(self, environment, policy, *, mode="structured", extractor=None,
                 observation_config=ObservationConfig(), note_quality=NoteQuality(),
                 max_notes_per_month=None, estimator=None, note_quality_by_student=None,
                 max_monitoring_notes_per_month=1, extraction_contract="actionable_monitoring"):
        if mode not in INFORMATION_MODES:
            raise ValueError("unknown information mode")
        if mode in ("llm_notes", "noisy_notes") and extractor is None:
            raise ValueError("note mode requires an explicit real or fixture extractor")
        if max_notes_per_month is not None and (type(max_notes_per_month) is not int or max_notes_per_month < 0):
            raise ValueError("max_notes_per_month must be a non-negative integer or None")
        if extraction_contract not in EXTRACTION_CONTRACTS:
            raise ValueError("unknown extraction contract")
        if max_monitoring_notes_per_month is not None and (
                type(max_monitoring_notes_per_month) is not int or max_monitoring_notes_per_month < 0):
            raise ValueError("max_monitoring_notes_per_month must be a non-negative integer or None")
        self.extraction_contract = extraction_contract
        self.max_monitoring_notes_per_month = max_monitoring_notes_per_month
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
        self.note_selection = []
        self._selection_logged = set()
        self.estimates, self.processed, self.failures = {}, set(), []
        self.decisions, self.snapshots, self.risks, self.fairness_rows = [], [], [], []
        self.decision_diagnostics = []
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
        if self.max_notes_per_month is not None and self.mode not in ("structured", "oracle"):
            # Limit intervention notes, never routine monitoring. Rotating only
            # among programme events prevents unrelated students consuming the cap.
            programmes = [event for event in events if event.programme_id is not None]
            start = (programmes[0].event_month * self.max_notes_per_month) % len(programmes) if programmes else 0
            selected_ids = {event.event_id for event in
                            (programmes[start:] + programmes[:start])[:self.max_notes_per_month]}
            selected = [event for event in events
                        if event.programme_id is None or event.event_id in selected_ids]
            for event in events:
                if event not in selected:
                    self._log_selection(render_note(event, seed=self.environment.config.seed,
                                        quality=self.note_quality_by_student.get(event.student_id, self.note_quality)),
                                        None, False, "programme_source_month_cap")
        self.notes.extend(render_note(event, seed=self.environment.config.seed,
                                     quality=self.note_quality_by_student.get(
                                         event.student_id, self.note_quality)) for event in selected)

    def _log_selection(self, note, month, selected, reason):
        key = (note.note_id, month, reason)
        if key not in self._selection_logged:
            self._selection_logged.add(key)
            self.note_selection.append({"note_id": note.note_id, "student_id": note.student_id,
                "source_event_ids": note.source_event_ids, "event_month": note.event_month,
                "available_from_month": note.available_from_month, "cutoff": month,
                "selected": selected, "reason": reason, "note_type": note.note_type})

    def _select_notes(self, sources, month):
        full = self.mode in ("structured", "oracle")
        legacy = self.extraction_contract == "legacy_programme_only"
        admitted = {sid for row in self.decisions for sid in row["admitted_ids"]}
        registry = {r.student_id: r for r in self.registry
                    if r.event_month == month - 1 and r.available_from_month <= month}
        ready, monitoring = [], []
        for note in sources:
            if note.note_id in self.processed:
                continue
            if note.available_from_month > month or note.event_month >= month:
                self._log_selection(note, month, False, "not_yet_available")
                continue
            if full or legacy or note.note_type == "programme":
                ready.append(note)
                continue
            record = registry.get(note.student_id)
            reason = ("no_remaining_decision" if month > self.environment.config.horizon else
                      "not_actionable" if not record or not record.enrolled or note.student_id in admitted else None)
            if reason:
                self._log_selection(note, month, False, reason)
                self.processed.add(note.note_id)
            else:
                monitoring.append(note)
        # Hash lottery per cutoff: no truth, protected group, condition, or need
        # priority. IDs can correlate with source order, so avoid prefix selection.
        monitoring.sort(key=lambda n: (sha256(json.dumps([
            self.environment.config.seed, month, n.note_id]).encode()).hexdigest(), n.note_id))
        limit = self.max_monitoring_notes_per_month
        ready.extend(monitoring if limit is None else monitoring[:limit])
        for note in ([] if limit is None else monitoring[limit:]):
            self._log_selection(note, month, False, "monitoring_cutoff_cap")
            self.processed.add(note.note_id)  # no later hidden backlog/fallback
        return ready

    def process_new_observations(self, month):
        incoming = {sid: [] for sid in self.estimates}
        # B uses full structured emissions. B-matched contains only note-supported
        # facts, including exactly the same omission/delay/contradiction process.
        sources = ([render_note(event, seed=self.environment.config.seed) for event in self.events]
                   if self.mode in ("structured", "oracle") else self.notes)
        for note in self._select_notes(sources, month):
            if note.note_id in self.processed:
                continue
            self.processed.add(note.note_id)
            extractor = (self.gold_extractor
                         if self.mode in ("structured", "oracle", "b_matched")
                         or (self.extraction_contract == "legacy_programme_only"
                             and note.note_type == "monitoring") else self.extractor)
            self._log_selection(note, month, True, "selected")
            attempt = {"note_id": note.note_id, "student_id": note.student_id,
                "source_event_ids": note.source_event_ids, "event_month": note.event_month,
                "available_from_month": note.available_from_month, "as_of_month": month,
                "note_type": note.note_type, "route": "gold" if extractor is self.gold_extractor else "injected",
                "attempt_id": f"{note.note_id}:extract:{month}", "cache_hit": False}
            calls_before = getattr(extractor, "calls", 0)
            audits_before = len(getattr(extractor, "audit_records", ()))
            try:
                batch = validate_batch(extractor.extract(note, month), note, month)
                incoming.setdefault(note.student_id, []).append(batch)
                self.batches.append(batch)
                attempt.update(status="accepted", evidence_ids=tuple(f.evidence_id for f in batch.facts),
                    result="empty" if not batch.facts else
                    "conflicting" if any(f.assertion_status == "conflicting" for f in batch.facts) else
                    "unknown" if all(f.value == "unknown" for f in batch.facts) else "supported")
            except Exception as exc:
                # Plugin boundary: failures are quarantined, never replaced by gold.
                attempt.update(status="quarantined", reason=str(exc), error_type=type(exc).__name__,
                               evidence_ids=())
                self.failures.append(dict(attempt))
            finally:
                audits = getattr(extractor, "audit_records", ())
                if len(audits) > audits_before:
                    attempt["extractor_audit"] = audits[-1]
                    attempt["cache_hit"] = bool(audits[-1].get("cache_hit"))
                attempt["model_invocations"] = getattr(extractor, "calls", 0) - calls_before
                self.extraction_attempts.append(attempt)
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
        if month != len(self.environment.records) + 1:
            raise ValueError("controller/environment decision cutoff mismatch")
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

    def extraction_diagnostics(self, month=None):
        attempts = [a for a in self.extraction_attempts if a["route"] == "injected"
                    and (month is None or a["as_of_month"] == month)]
        selections = [s for s in self.note_selection if s["selected"]
                      and (month is None or s["cutoff"] == month)]
        eligible = {r.student_id for r in self.registry
                    if r.event_month == (month or len(self.environment.records) + 1) - 1 and r.enrolled}
        admitted = {sid for d in self.decisions if month is None or d["month"] < month
                    for sid in d["admitted_ids"]}
        usable = {sid for sid, e in self.estimates.items() if sid in eligible - admitted
                  and e.last_observation_month is not None}
        new_ids = {eid for a in attempts if a["note_type"] == "monitoring" for eid in a["evidence_ids"]}
        new_usable = {sid for sid, e in self.estimates.items() if sid in eligible - admitted
            and any(f.evidence_id in new_ids and f.evidence in SIGNAL_PHRASES.values()
                    and f not in e.unresolved_observations for f in e.observation_history)}
        return {"extractor_attempts": len(attempts),
            "monitoring_extractor_attempts": sum(a["note_type"] == "monitoring" for a in attempts),
            "actual_model_invocations": sum(a["model_invocations"] for a in attempts),
            "cache_hits": sum(a["cache_hit"] for a in attempts),
            "accepted_extractions": sum(a["status"] == "accepted" for a in attempts),
            "quarantined_extractions": sum(a["status"] == "quarantined" for a in attempts),
            "selected_notes": len(selections),
            "eligible_students_with_usable_evidence": len(usable),
            "eligible_students_with_new_usable_evidence": len(new_usable)}

    def run_episode(self):
        if not self._initialized:
            self.initialize()
        config = self.environment.config
        while not self.environment.done:
            self.run_month()
        # Process terminal evidence/risk at cutoff T+1; there is no 13th allocation.
        self.process_new_observations(config.horizon + 1)
        self.risks.extend(self.risk_estimator.predict(e, 0) for e in self.estimates.values())
        return self

    def run_month(self):
        """Commit one decision; permits common-history pre-decision forks."""
        if not self._initialized:
            self.initialize()
        if self.environment.done:
            raise ValueError("episode has already completed")
        config = self.environment.config
        month = len(self.environment.records) + 1
        snapshot = self.prepare_decision_snapshot(month)
        self.snapshots.append(snapshot)
        self.decision_diagnostics.append({"cutoff": month, **self.extraction_diagnostics(month)})
        if (month - 1) % config.fairness_window == 0:
            self.windows.append(FairnessWindow.initialize(snapshot, window_months=config.fairness_window,
                target=config.fairness_min_access, attribute=config.fairness_grouping_attribute))
        window = self.windows[-1]
        window.update(snapshot)
        allocation = self.allocate(snapshot)
        benefits = estimate_all_student_benefits(snapshot, self.policy.wait_matrix, self.policy.programme_matrix)
        # Independent environment validation precedes all spending/transitions.
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
        return record
