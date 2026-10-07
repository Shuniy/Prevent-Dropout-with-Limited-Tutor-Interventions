"""Stage 1 CLI: validated ingestion, immutable contracts, separated versioned outputs."""
import argparse
import csv
import json
import platform
from pathlib import Path, PurePosixPath
import shutil
import tempfile

from .contracts import VERSION, json_schemas
from .access import (reset_observations, DEFAULT_FEATURES, CONSUMER_ALLOWLISTS,
                     PolicyStore, ContextStore, EnvironmentStore, EvaluatorStore)
from .ingestion import sha, read_csv, require, validate_and_adapt
from .provenance import provenance_register, source_mapping, GENERATOR_ASSUMPTIONS

PROJECT = Path(__file__).resolve().parents[2]
INPUT_PATHS = {
    'raw_portuguese':'student+performance/student/student-por.csv',
    'raw_math':'student+performance/student/student-mat.csv',
    **{n:f'results/stage0-v1/data/{n}.csv' for n in ('student_dataset','synthetic_student_population',
        'split_manifest','subject_records_reference','student_outcomes_reference','simulator_hidden_truth')},
    'historical_provenance':'docs/references/audit_v1/provenance_register.csv',
    'school_codebook':'student+performance/student/student.txt'}


def dump(path, value):
    Path(path).write_text(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n')


def write_lines(path, rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w') as f:
        for row in rows:
            value=row.to_dict() if hasattr(row,'to_dict') else row
            f.write(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n')


def write_csv(path, rows):
    with path.open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def preflight(source_root, manifest, output=None):
    root=Path(source_root).resolve(strict=True)
    config_path=Path(manifest).resolve(strict=True)
    cfg=json.loads(config_path.read_text())
    require(cfg['schema_version']==VERSION and cfg['adapter_version']=='stage1-v1', 'Unsupported ingestion configuration')
    entries=cfg['inputs']; require(len(entries)==len(INPUT_PATHS), 'Unexpected input count')
    require({e['name']:e['relative_path'] for e in entries}==INPUT_PATHS, 'Input paths do not match the Stage 1 allowlist')
    require(len({e['name'] for e in entries})==len(entries), 'Duplicate input')
    require(set(cfg['reset_features'])<=set(CONSUMER_ALLOWLISTS['policy']['reset_fields'])
            and len(set(cfg['reset_features']))==len(cfg['reset_features']), 'Forbidden reset feature')
    paths={}
    for entry in entries:
        rel=PurePosixPath(entry['relative_path'])
        require(not rel.is_absolute() and '..' not in rel.parts, 'Invalid relative input')
        p=root/rel
        require(not any((root/Path(*rel.parts[:i])).is_symlink() for i in range(1,len(rel.parts)+1)), 'Symlink input forbidden')
        require(p.is_file() and p.resolve().is_relative_to(root), f'Missing/escaped input: {rel}')
        require(sha(p)==entry['sha256'] and p.stat().st_size==entry['bytes'], f'Input identity mismatch: {rel}')
        paths[entry['name']]=p
    if output is not None:
        out=Path(output).absolute()
        require(not out.exists() and not out.is_symlink(), f'Output already exists: {out}')
        require(not out.resolve().is_relative_to(root/'student_cmdp_study'), 'Preserved baseline cannot receive outputs')
        require(not out.resolve().is_relative_to(root/'results/stage0-v1'), 'Completed Stage 0 cannot receive outputs')
        for p in [*paths.values(),config_path]:
            require(not p.is_relative_to(out.resolve()) and not out.resolve().is_relative_to(p.parent), 'Output overlaps an input directory')
    return cfg,paths


def load_tables(paths):
    return {name:read_csv(p,';' if name.startswith('raw_') else ',')
            for name,p in paths.items() if name not in ('school_codebook','historical_provenance')}


def build(source_root, manifest, output):
    config,paths=preflight(source_root,manifest,output)
    before={str(p):sha(p) for p in [*paths.values(),Path(manifest)]}
    tables=load_tables(paths)
    contexts,fixture_contexts,states,outcomes,report=validate_and_adapt(tables)
    out=Path(output).absolute(); out.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix='.stage1-',dir=out.parent))
    try:
        features=tuple(config['reset_features'])
        cohorts={'primary':[c for c in contexts if c.lineage.anchor_subject=='portuguese'],
                 'sensitivity':contexts,'fixture':fixture_contexts}
        for cohort,records in cohorts.items():
            for split in ('train','validation','test'):
                selected=[c for c in records if c.lineage.split==split]
                write_lines(stage/'data/context'/f'{cohort}_{split}.jsonl',selected)
                write_lines(stage/'data/policy'/f'{cohort}_{split}.jsonl',[reset_observations(c,features) for c in selected])
        fixture_splits={c.lineage.student_id:c.lineage.split for c in fixture_contexts}
        for split in ('train','validation','test'):
            write_lines(stage/'data/environment'/f'fixture_{split}.jsonl',[s for s in states if fixture_splits[s.student_id]==split])
        write_lines(stage/'data/evaluator/subject_records_reference.jsonl',tables['subject_records_reference'])
        write_lines(stage/'data/evaluator/student_outcomes_reference.jsonl',outcomes)
        write_lines(stage/'data/evaluator/static_fixture_diagnostics.jsonl',tables['simulator_hidden_truth'])
        write_csv(stage/'data/split_manifest.csv',tables['split_manifest'])
        dump(stage/'contracts.v2.json',json_schemas())
        dump(stage/'consumer_allowlists.json',CONSUMER_ALLOWLISTS)
        dump(stage/'fixture_assumptions.json',GENERATOR_ASSUMPTIONS)
        dump(stage/'input_manifest.json',config)
        registry=provenance_register(tables,read_csv(paths['historical_provenance']),features)
        write_csv(stage/'provenance_register.v2.csv',registry)
        write_csv(stage/'source_field_mapping.v2.csv',source_mapping())
        # Read back the actual consumer products before publication.
        for cohort in cohorts:
            for split in ('train','validation','test'):
                p=PolicyStore(stage).load_reset(split,cohort); c=ContextStore(stage).load(split,cohort)
                require(tuple(x.student_id for x in p)==tuple(x.lineage.student_id for x in c), 'Policy/context readback mismatch')
        require(sum(len(EnvironmentStore(stage).load_fixture(s)) for s in ('train','validation','test'))==2000,'Environment readback mismatch')
        require(len(EvaluatorStore(stage).load_subject_references())==1044, 'Reference readback mismatch')
        require(before=={p:sha(p) for p in before}, 'Inputs changed during ingestion')
        report.update({'consumer_readback_passed':True,'input_hashes_unchanged':True,
                       'provenance_rows':len(registry),'reset_features':list(features)})
        dump(stage/'validation.json',report)
        code={f'src/data/{n}':sha(Path(__file__).parent/n) for n in
              ('stage1.py','contracts.py','ingestion.py','access.py','provenance.py')}
        dump(stage/'run_manifest.json',{'adapter_version':'stage1-v1','schema_version':VERSION,
            'python':platform.python_version(),'configuration_sha256':sha(manifest),
            'code_sha256':code,'random_generation':'none; audited fixed fixtures retained',
            'seeds':{'inherited_fixture_seed':20261006},'source_splits':['train','validation','test']})
        # Only this staging tree is inventoried; never recursively scan mixed source roots.
        artifacts=[{'relative_path':str(p.relative_to(stage)),'sha256':sha(p),'bytes':p.stat().st_size}
                   for p in sorted(stage.rglob('*')) if p.is_file()]
        dump(stage/'COMPLETED.json',{'stage':1,'schema_version':VERSION,'artifacts':artifacts})
        require(not out.exists(), 'Output appeared during build')
        stage.rename(out)
    except BaseException:
        shutil.rmtree(stage)
        raise
    return report


def verify(output):
    root=Path(output).resolve(strict=True)
    ledger=json.loads((root/'COMPLETED.json').read_text())
    require(ledger['stage']==1 and ledger['schema_version']==VERSION,'Wrong completed version')
    seen=set()
    for row in ledger['artifacts']:
        rel=PurePosixPath(row['relative_path'])
        require(not rel.is_absolute() and '..' not in rel.parts and row['relative_path'] not in seen,'Invalid artifact path')
        seen.add(row['relative_path']); p=root/rel
        require(not any((root/Path(*rel.parts[:i])).is_symlink() for i in range(1,len(rel.parts)+1)), 'Symlink artifact forbidden')
        require(p.is_file() and sha(p)==row['sha256'] and p.stat().st_size==row['bytes'],f'Artifact mismatch: {rel}')
    return {'artifacts_verified':len(seen),'validation':json.loads((root/'validation.json').read_text())}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root',type=Path,default=PROJECT)
    parser.add_argument('--manifest',type=Path,default=PROJECT/'configs/stage1_inputs.v1.json')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--verify',action='store_true')
    args=parser.parse_args()
    print(json.dumps(verify(args.output) if args.verify else build(args.source_root,args.manifest,args.output),indent=2))


if __name__=='__main__':
    main()
