"""Console-first, paired single-world comparison of baseline and feedback runs."""

from dataclasses import asdict, replace
from datetime import datetime
import json
from pathlib import Path
from time import perf_counter
import tomllib

from .allocation_policies import POLICY_NAMES, make_policy
from .cmdp_experiments import run_policy
from .cmdp_scenarios import build_school
from .feedback_experiments import save_episode, write_csv, write_jsonl
from .feedback_validation import validate_feedback_episode
from .observation_model import ObservationConfig
from .scenario_config import ScenarioConfig
from src.intervention.feedback_notes import NoteQuality
from src.intervention.observation_extractor import FixtureObservationExtractor, LLMObservationExtractor
from src.intervention.ollama_client import OllamaClient


CAVEAT = (
    "All runs share the scenario, population seed, transition assumptions and resource limits. "
    "Baselines and oracle see true state; structured sees full observations; b_matched and "
    "llm_notes use the same note feature schema and note-quality settings. noisy_notes deliberately "
    "changes note quality. Realized trajectories may diverge after different allocations. "
    "Fixture extraction is an offline wiring control, not an LLM result. "
    "This is a single-seed synthetic comparison, not a statistical effectiveness claim. "
    "Times cover school construction and simulation (including extraction), excluding report I/O."
)


def run_comparison(args):
    if any(getattr(args, key) is not None for key in
           ("suite", "stage", "development_seeds", "evaluation_seeds")) or args.print_monthly:
        raise ValueError("sweep, stage, seed-count and monthly options require --runner baselines")
    path = args.config or Path(__file__).resolve().parents[2] / "configs/cmdp_llm_feedback.toml"
    with path.open("rb") as stream:
        values = tomllib.load(stream)
    config = (ScenarioConfig(**values["scenario"]) if "scenario" in values
              else ScenarioConfig.load(path))
    fields = {"students": "num_students", "mentors": "num_mentors", "months": "horizon",
              "sessions": "appointments_per_programme", "capacity": "monthly_admissions",
              "budget": "budget", "seed": "seed", "effect_strength": "effect_strength"}
    config = replace(config, **{field: getattr(args, key) for key, field in fields.items()
                                if getattr(args, key) is not None})
    policies = tuple(args.policies if args.policies is not None else POLICY_NAMES)
    for names, allowed in ((policies, POLICY_NAMES), (args.feedback_policies, ("resource", "fairness"))):
        if not names or len(set(names)) != len(names) or any(name not in allowed for name in names):
            raise ValueError("policies must contain distinct supported names")
    if len(set(args.modes)) != len(args.modes):
        raise ValueError("modes must be distinct")
    if args.timeout <= 0 or (args.max_notes_per_month is not None and args.max_notes_per_month < 0):
        raise ValueError("timeout must be positive and max-notes-per-month non-negative")
    observation_values = dict(values.get("observation", {}))
    if "emissions" in observation_values:
        observation_values["emissions"] = tuple(tuple(row) for row in observation_values["emissions"])
    observation = ObservationConfig(**observation_values)
    quality = NoteQuality(**values.get("notes", {}))
    noisy = NoteQuality(**values.get("noisy_notes", {}))
    output = args.output or Path("results/simulation_comparison") / datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    output = Path(output)
    if output.exists():
        raise FileExistsError(f"Output already exists: {output}")
    rows, artifacts = [], []
    print("Shared scenario: " + json.dumps(asdict(config), sort_keys=True), flush=True)
    print(CAVEAT, flush=True)

    def record(name, mode, seconds, enrolled, programmes, spent, failures=0, calls=0, extractor="none"):
        row = dict(policy=name, mode=mode, seed=config.seed, students=config.num_students,
                   months=config.horizon, terminal_enrolled=enrolled, programmes=programmes,
                   spent_budget=spent, seconds=seconds, quarantined_extractions=failures,
                   real_llm_calls=calls, extractor=extractor)
        rows.append(row)
        print(f"{name}/{mode}: enrolled={enrolled}/{config.num_students}, programmes={programmes}, "
              f"spent={spent:.2f}, time={seconds:.3f}s, quarantined={failures}, LLM calls={calls}", flush=True)

    for name in policies:
        print(f"Running baseline/{name} ...", flush=True)
        start = perf_counter()
        metrics, trajectory = run_policy(config, name)
        elapsed = perf_counter() - start
        record(name, "baseline_oracle", elapsed, metrics["terminal_enrolled"], metrics["programmes"], metrics["spending"])
        artifacts.append((f"baseline_{name}", (metrics, trajectory)))
    for name in args.feedback_policies:
        for mode in args.modes:
            print(f"Running {name}/{mode} ({args.extractor}) ...", flush=True)
            # Fresh extractor and school prevent mutable state leaking between runs.
            extractor = (FixtureObservationExtractor() if args.extractor == "fixture" else
                         LLMObservationExtractor(OllamaClient(args.model, timeout=args.timeout, num_ctx=8192)))
            policy = make_policy("terminal_value" if name == "resource" else name, config)
            start = perf_counter()
            controller = build_school(config).run_cmdp_feedback(
                policy, config=config, mode=mode, extractor=extractor,
                observation_config=observation, note_quality=noisy if mode == "noisy_notes" else quality,
                max_notes_per_month=args.max_notes_per_month)
            elapsed = perf_counter() - start
            validate_feedback_episode(controller)
            record(name, mode, elapsed, controller.environment.terminal_reward(),
                   sum(len(row["admitted_ids"]) for row in controller.decisions),
                   config.budget - controller.environment.records[-1].remaining_budget,
                   len(controller.failures), getattr(extractor, "calls", 0),
                   type(extractor).__name__ if mode in ("llm_notes", "noisy_notes") else "structured_gold")
            artifacts.append((f"{name}_{mode}", controller))

    lines = ["# Simulation comparison", "", CAVEAT, "",
             f"Note extractor: {args.extractor}; model: {args.model if args.extractor == 'ollama' else 'none (fixture control)'}. ", "",
             "| Policy | Information mode | Enrolled | Programmes | Spent | Seconds | Quarantined |",
             "|---|---|---:|---:|---:|---:|---:|"]
    for row in rows:
        lines.append(f"| {row['policy']} | {row['mode']} | {row['terminal_enrolled']} | "
                     f"{row['programmes']} | {row['spent_budget']:.2f} | {row['seconds']:.3f} | "
                     f"{row['quarantined_extractions']} |")
    lines += ["", "## Shared configuration", "", "```json", json.dumps(asdict(config), indent=2), "```", ""]
    report = "\n".join(lines)
    print("\n" + report, flush=True)
    # No report or trace files are written until all results have been shown.
    output.mkdir(parents=True, exist_ok=False)
    manifest = dict(scenario=asdict(config), observation=asdict(observation), notes=asdict(quality),
                    noisy_notes=asdict(noisy), max_notes_per_month=args.max_notes_per_month,
                    extractor=args.extractor, model=args.model, timeout=args.timeout,
                    num_ctx=8192, temperature=0, policies=policies,
                    feedback_policies=args.feedback_policies, modes=args.modes, caveat=CAVEAT)
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    write_csv(output / "comparison.csv", rows)
    (output / "comparison.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    (output / "report.md").write_text(report, encoding="utf-8")
    for name, artifact in artifacts:
        if isinstance(artifact, tuple):
            destination = output / name
            destination.mkdir()
            metrics, trajectory = artifact
            (destination / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
            write_jsonl(destination / "trajectory.jsonl", trajectory)
        else:
            save_episode(artifact, output / name)
    return output
