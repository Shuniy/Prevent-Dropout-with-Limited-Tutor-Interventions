"""Whole-source-profile bootstrap with evaluator-only lineage (population/v1).

No source identity is attached to StudentSimulation or WeeklyDecisionState.
Generated reset variables are assumptions, never observed school measurements.
"""
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, fields
from hashlib import sha256
import csv
from pathlib import Path

import numpy as np
from scipy.stats import wasserstein_distance

from ..evaluation.provenance import digest
from ..utils.constants import PROJECT_ROOT, BOOLEAN_FIELDS, INTEGER_FIELDS
from .loading import student_from_row
from .student import Student


SOURCE_PATH = PROJECT_ROOT / 'data/processed/students/student_dataset.csv'
SPLIT_PATH = PROJECT_ROOT / 'data/processed/splits/split_manifest.csv'
CONTEXT_FIELDS = tuple(f.name for f in fields(Student) if f.name != 'student_id')
UNKNOWN_FIELDS = ('income_amount', 'income_currency', 'verified_economic_disadvantage',
                  'observed_school_dropout')
GENERATED_FIELDS = ('initial_attendance_fraction_assumed', 'initial_engagement_assumed',
                    'weeks_since_offer', 'support_sessions_completed', 'enrolled_initial_assumed')


@dataclass(frozen=True)
class PopulationGeneratorConfig:
    version: str = 'whole_profile_bootstrap/v1'
    attendance_range: tuple[float, float] = (.55, 1.)
    engagement_range: tuple[float, float] = (.25, 1.)

    def __post_init__(self):
        if self.version != 'whole_profile_bootstrap/v1':
            raise ValueError('unsupported population generator')
        for name in ('attendance_range','engagement_range'):
            bounds=getattr(self,name)
            if len(bounds) != 2 or not 0 <= bounds[0] <= bounds[1] <= 1:
                raise ValueError('generated assumption ranges must be within [0,1]')
            object.__setattr__(self,name,tuple(bounds))


@dataclass(frozen=True)
class SourcePool:
    rows: tuple[tuple[tuple[str, str], ...], ...]
    fingerprint: str
    version: str = 'uci_consolidated_retained/v1'

    def partition(self, split):
        if split not in ('train', 'validation', 'test'):
            raise ValueError('explicit source split required')
        return tuple(dict(row) for row in self.rows if dict(row)['split'] == split)


def load_source_pool(source_path=SOURCE_PATH, split_path=SPLIT_PATH):
    source_path, split_path = Path(source_path), Path(split_path)
    with source_path.open(newline='') as stream:
        rows = tuple(csv.DictReader(stream))
    with split_path.open(newline='') as stream:
        manifest = tuple(csv.DictReader(stream))
    index = {r['student_id']: r for r in manifest}
    if len(index) != len(manifest) or len({r['student_id'] for r in rows}) != len(rows):
        raise ValueError('duplicate source or split identities')
    if {r['student_id'] for r in rows} != set(index):
        raise ValueError('source and split manifests must match exactly')
    groups = {}
    for row in rows:
        sid, group, split = (row[k] for k in ('student_id', 'linkage_group_id', 'split'))
        if not group or split not in ('train', 'validation', 'test'):
            raise ValueError('invalid source lineage')
        if any(row[k] != index[sid][k] for k in ('linkage_group_id', 'split', 'anchor_subject')):
            raise ValueError('source/split assignment mismatch')
        if group in groups and groups[group] != split:
            raise ValueError('source linkage group crosses splits')
        groups[group] = split
        validate_source_row(row)
    return SourcePool(tuple(tuple(sorted(row.items())) for row in rows),
        digest([sha256(p.read_bytes()).hexdigest() for p in (source_path, split_path)]))


def validate_source_row(row):
    # Required context cannot be invented to satisfy the old runtime schema.
    for name in CONTEXT_FIELDS:
        if not row.get(name, '').strip() and name != 'math_grade1_0_20':
            raise ValueError(f'missing required source context: {name}')
    for name in BOOLEAN_FIELDS:
        if row[name] not in ('0', '1'):
            raise ValueError(f'invalid source boolean: {name}')
    bounds = dict(age_years=(10, 30), mother_education_code=(0, 4), father_education_code=(0, 4),
        travel_time_category=(1, 4), study_time_category=(1, 4), past_failures_count=(0, 4),
        family_relationship_rating=(1, 5), health_self_rating=(1, 5),
        anchor_grade1_0_20=(0, 20), math_grade1_0_20=(0, 20))
    for name, (low, high) in bounds.items():
        if row[name].strip() and not low <= int(row[name]) <= high:
            raise ValueError(f'impossible source value: {name}')
    if any(row.get(k, '').strip() for k in UNKNOWN_FIELDS):
        raise ValueError('retained source version expects unknown income/dropout fields')


@dataclass(frozen=True)
class PopulationLineage:
    student_id: str
    source_anchor: str
    linkage_group: str
    source_split: str
    population_seed: int
    generator_version: str
    source_fingerprint: str
    observed_fields: tuple[str, ...] = CONTEXT_FIELDS
    generated_fields: tuple[str, ...] = GENERATED_FIELDS
    unknown_fields: tuple[str, ...] = (*UNKNOWN_FIELDS, 'financial_need_verified')


@dataclass(frozen=True)
class SampledPopulation:
    split: str
    population_seed: int
    source_version: str
    source_fingerprint: str
    generator: PopulationGeneratorConfig
    profiles: tuple[tuple[tuple[str, str], ...], ...]
    lineage: tuple[PopulationLineage, ...]
    source_pool_size: int
    with_replacement: bool

    @property
    def identity(self):
        return digest(asdict(self))

    def students(self):
        return tuple(student_from_row(dict(row)) for row in self.profiles)


def sample_population(split, cohort_size, population_seed, *, source_version='uci_consolidated_retained/v1',
                      generator_config=PopulationGeneratorConfig(), pool=None):
    if type(cohort_size) is not int or cohort_size < 1 or type(population_seed) is not int or population_seed < 0:
        raise ValueError('positive cohort size and nonnegative integer population seed required')
    pool = load_source_pool() if pool is None else pool
    if source_version != pool.version:
        raise ValueError('source version mismatch')
    rows = pool.partition(split)
    if not rows:
        raise ValueError('empty source partition')
    # This RNG is local and cannot advance any transition/observation streams.
    rng = np.random.default_rng(np.random.SeedSequence([population_seed, 5001]))
    replacement = cohort_size > len(rows)
    indices = rng.choice(len(rows), size=cohort_size, replace=replacement)
    profiles, lineage = [], []
    for i, index in enumerate(indices):
        source = rows[int(index)]
        # Synthetic IDs encode neither source split, seed nor source identity.
        sid = f'agent-{i:05d}'
        row = {k: source[k] for k in (*CONTEXT_FIELDS, *UNKNOWN_FIELDS)}
        row.update(student_id=sid,
            initial_attendance_fraction_assumed=str(rng.uniform(*generator_config.attendance_range)),
            initial_engagement_assumed=str(rng.uniform(*generator_config.engagement_range)),
            weeks_since_offer='0', support_sessions_completed='0', enrolled_initial_assumed='1',
            financial_need_verified='')
        student_from_row(row)  # validate compatibility without exposing provenance
        profiles.append(tuple(sorted(row.items())))
        lineage.append(PopulationLineage(sid, source['student_id'], source['linkage_group_id'],
            split, population_seed, generator_config.version, pool.fingerprint))
    return SampledPopulation(split, population_seed, source_version, pool.fingerprint,
        generator_config, tuple(profiles), tuple(lineage), len(rows), replacement)


def population_validation(population, pool=None):
    pool = load_source_pool() if pool is None else pool
    if pool.fingerprint != population.source_fingerprint:
        raise ValueError('source fingerprint mismatch')
    source = pool.partition(population.split)
    generated = [dict(r) for r in population.profiles]
    if (len(generated)!=len(population.lineage) or not generated
            or len({r['student_id'] for r in generated})!=len(generated)
            or tuple(r['student_id'] for r in generated)!=tuple(l.student_id for l in population.lineage)):
        raise ValueError('population profile/lineage identities must match one-to-one')
    anchors = {r['student_id']: r for r in source}
    for row, lineage in zip(generated, population.lineage):
        anchor = anchors[lineage.source_anchor]
        if (lineage.source_split != population.split or lineage.linkage_group != anchor['linkage_group_id']
                or lineage.source_fingerprint!=pool.fingerprint or lineage.population_seed!=population.population_seed
                or lineage.generator_version!=population.generator.version
                or any(row[k] != anchor[k] for k in (*CONTEXT_FIELDS, *UNKNOWN_FIELDS))):
            raise ValueError('descendant changed inherited source context')
    numeric, categorical, missingness = {}, {}, {}
    numeric_fields = set(INTEGER_FIELDS) - {'weeks_since_offer', 'support_sessions_completed'} | {'math_grade1_0_20'}
    for name in CONTEXT_FIELDS:
        a, b = [r[name] for r in source], [r[name] for r in generated]
        missingness[name] = dict(source=sum(not v.strip() for v in a)/len(a),
                                 sampled=sum(not v.strip() for v in b)/len(b))
        if name in numeric_fields:
            a, b = [float(v) for v in a if v.strip()], [float(v) for v in b if v.strip()]
            numeric[name] = dict(source_quantiles=np.quantile(a, [0,.25,.5,.75,1]).tolist() if a else None,
                sampled_quantiles=np.quantile(b, [0,.25,.5,.75,1]).tolist() if b else None,
                wasserstein=wasserstein_distance(a,b) if a and b else None)
        else:
            ca, cb = Counter(a), Counter(b)
            categorical[name] = dict(source={k:v/len(a) for k,v in ca.items()},
                sampled={k:v/len(b) for k,v in cb.items()},
                total_variation=.5*sum(abs(ca[k]/len(a)-cb[k]/len(b)) for k in ca.keys() | cb.keys()))
    def relationships(rows):
        pairs = defaultdict(Counter)
        for row in rows:
            for a,b in (('anchor_grade1_0_20','math_grade1_0_20'),
                        ('mother_education_code','internet_at_home'), ('school_id','sex_source')):
                pairs[a+'|'+b][row[a]+'|'+row[b]] += 1
        return {k:dict(v) for k,v in pairs.items()}
    inherited = [tuple(row[k] for k in CONTEXT_FIELDS) for row in generated]
    groups = {s:{r['linkage_group_id'] for r in pool.partition(s)} for s in ('train','validation','test')}
    return dict(contract='population_validation/v1', population_identity=population.identity,
        cohort_size=len(generated), source_pool_size=len(source),
        unique_source_anchors=len({l.source_anchor for l in population.lineage}),
        unique_linkage_groups=len({l.linkage_group for l in population.lineage}),
        with_replacement=population.with_replacement, duplicate_inherited_profiles=len(inherited)-len(set(inherited)),
        cross_split_group_overlap={a+'|'+b:len(groups[a]&groups[b]) for a,b in
            (('train','validation'),('train','test'),('validation','test'))},
        numeric=numeric, categorical=categorical, missingness=missingness,
        subgroup_proportions={g:dict(n=n,proportion=n/len(generated)) for g,n in
            Counter(str(s.disadvantage_proxy_group) for s in population.students()).items()},
        pairwise_and_conditional_counts=dict(source=relationships(source), sampled=relationships(generated)),
        impossible_combinations=0,
        impossible_definition='invalid source domains, changed inherited joint context, or fabricated unknown fields; no causal plausibility claim',
        assumption_ranges=asdict(population.generator),
        assumption_scope='reset attendance/engagement are generated, never validated as source observations')
