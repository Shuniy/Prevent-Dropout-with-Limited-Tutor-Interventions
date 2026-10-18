"""Checks for direct dataset consumption, lineage and feature separation."""
import csv
from dataclasses import fields
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import pandas as pd

from src.data.access import PolicyStore, ContextStore, EnvironmentStore, EvaluatorStore, model_features
from src.data.dataset import (DATA_DIR, read_rows, read_table, context_record,
                              population_rows, population_table)


class DatasetTests(unittest.TestCase):
    def test_dataframe_preserves_source_text_and_blanks(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'student_dataset.csv'
            path.write_text('student_id,label,unknown\n001,NA,\n002,"a,b",\n')
            table = read_table('student_dataset', directory)
            self.assertIsInstance(table, pd.DataFrame)
            self.assertEqual(table['student_id'].tolist(), ['001', '002'])
            self.assertEqual(table['label'].tolist(), ['NA', 'a,b'])
            self.assertEqual(table['unknown'].tolist(), ['', ''])

    def test_dataframe_rejects_malformed_csv(self):
        cases = ['', 'student_id,student_id\na,b\n',
                 'student_id,\na,b\n', 'student_id,label\na\n',
                 'student_id,label\na,b,c\n', 'label\na\n',
                 'student_id,label\n,b\n']
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'student_dataset.csv'
            for content in cases:
                with self.subTest(content=content):
                    path.write_text(content)
                    with self.assertRaises(ValueError):
                        read_table('student_dataset', directory)

    def test_dataframe_cohort_filter_and_copy(self):
        students = population_table('train', 'primary')
        self.assertEqual(len(students), 388)
        self.assertTrue(students['anchor_subject'].eq('portuguese').all())
        self.assertTrue(students['split'].eq('train').all())
        students.loc[:, 'split'] = 'changed'
        self.assertTrue(population_table('train', 'primary')['split'].eq('train').all())

    def test_population_and_split_counts(self):
        for split, count in [('train', 1200), ('validation', 400), ('test', 400)]:
            self.assertEqual(len(ContextStore().load(split)), count)
        self.assertEqual(sum(len(ContextStore().load(s, 'primary'))
                             for s in ('train', 'validation', 'test')), 649)

    def test_fixture_inherits_anchor_fields_and_split(self):
        anchors = {row['student_id']: row for row in read_rows('student_dataset')}
        for row in read_rows('synthetic_student_population'):
            anchor = anchors[row['source_anchor_student_id']]
            for key, value in anchor.items():
                if key not in ('student_id', 'record_provenance'):
                    self.assertEqual(row[key], value, (row['student_id'], key))

    def test_policy_reads_only_population_and_writes_nothing(self):
        original = Path.open
        opened = []
        def read_only(path, mode='r', *args, **kwargs):
            self.assertEqual(mode, 'r')
            self.assertEqual(path.name, 'synthetic_student_population.csv')
            opened.append(path)
            return original(path, mode, *args, **kwargs)
        with patch.object(Path, 'open', read_only):
            records = PolicyStore().load_reset('test')
        self.assertEqual(len(opened), 1)
        self.assertEqual(len(records), 400)
        self.assertEqual(set(model_features(records[0])),
                         {'anchor_grade1_0_20', 'past_failures_count', 'study_time_category'})
        for name in ('sex_source', 'student_id', 'G3', 'response_tendency_assumed'):
            with self.assertRaises(ValueError):
                model_features(records[0], (name,))
        self.assertTrue(all(o.value is None and o.status == 'withheld' for o in
                            records[0].observations if o.field == 'attendance'))

    def test_environment_excludes_future_draw_and_hazard(self):
        states = EnvironmentStore().load_fixture('train')
        self.assertEqual(len(states), 1200)
        self.assertFalse({'constant_weekly_hazard_assumed',
                          'dropout_draw_at_static_annual_hazard_assumed'} &
                         {f.name for f in fields(states[0])})

    def test_evaluator_preserves_supplied_values(self):
        self.assertEqual(len(EvaluatorStore().load_subject_references()), 1044)
        self.assertEqual(list(EvaluatorStore().load_historical_outcomes()),
                         read_rows('student_outcomes_reference'))

    def test_nulls_and_invalid_values(self):
        row = read_rows('synthetic_student_population')[0]
        self.assertTrue(all(v is None for v in context_record(row).unknown.to_dict().values()))
        for key, value in [('income_amount', '0'), ('age_years', 'bad'),
                           ('internet_at_home', '2')]:
            with self.assertRaises((ValueError, TypeError)):
                context_record({**row, key: value})

    def test_invalid_selection_rejected(self):
        for split, cohort in [('other', 'fixture'), ('train', '../hidden')]:
            with self.assertRaises(ValueError):
                population_rows(split, cohort)
        with self.assertRaises(ValueError):
            read_rows('../simulator_hidden_truth')

    def test_corrupt_ids_and_split_crossings_rejected(self):
        rows = read_rows('synthetic_student_population')[:2]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'synthetic_student_population.csv'
            def save(values):
                with path.open('w', newline='') as stream:
                    writer = csv.DictWriter(stream, fieldnames=values[0])
                    writer.writeheader()
                    writer.writerows(values)
            save([rows[0], rows[0]])
            with self.assertRaises(ValueError):
                read_rows('synthetic_student_population', directory)
            save([rows[0], {**rows[1], 'linkage_group_id': rows[0]['linkage_group_id'],
                           'split': 'test' if rows[0]['split'] != 'test' else 'train'}])
            with self.assertRaises(ValueError):
                population_rows('train', directory=directory)


if __name__ == '__main__':
    unittest.main()
