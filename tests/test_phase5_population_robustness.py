"""Population/world dependence and immutable acceptance completeness gates."""
from copy import deepcopy
from dataclasses import replace
import unittest

from src.evaluation.phase5_followup import load_config,population_summary,cohort_metadata
from src.school.delivery_config import DeliveryConfig


class RobustnessTests(unittest.TestCase):
    def rows(self):
        rows=[]
        for population,differences in ((1,(0.,1.)),(2,(-1.,0.)),(3,(.5,.5))):
            for world,difference in enumerate(differences):
                for mode in ('fair_point','fair_robust'):
                    value=difference if mode=='fair_robust' else 0.
                    rows.append(dict(population_seed=population,seed=100*population+world,policy=mode,
                        retention_rate=value,worst_group_retention=value,access_gap=0.,normalized_shortfall=0.,
                        actual_support_offers=1,compatibility_audit=dict(exercised_design=True),solver_failures=0,incomplete_stages=0))
        return rows

    def test_population_means_are_clusters_not_student_or_world_rows(self):
        report=population_summary(self.rows(),[])
        retention=report['outcomes']['retention_rate']
        self.assertEqual(retention['population_clusters']['n'],3)
        self.assertEqual(report['episodes'],12)
        self.assertAlmostEqual(retention['population_clusters']['mean'],1/6)
        self.assertGreater(retention['within_population_world_variance_mean'],0)
        self.assertGreater(retention['observed_population_mean_variance'],0)
        self.assertEqual(report['outcomes']['normalized_shortfall']['population_clusters']['mean'],0)

    def test_missing_or_duplicate_policy_pairs_rejected(self):
        rows=self.rows()
        for bad in (rows[:-1],[*rows,rows[0]]):
            with self.assertRaisesRegex(ValueError,'incomplete|duplicate'):
                population_summary(bad,[])

    def test_unavailable_fairness_is_not_fabricated_as_zero(self):
        rows=self.rows();rows[0]['access_gap']=None
        report=population_summary(rows,[])['outcomes']['access_gap']
        self.assertEqual(report['unavailable_populations'],[1])
        self.assertEqual(report['population_clusters']['n'],2)

    def test_nested_world_and_source_partitions_are_explicit(self):
        config=load_config();p=config['followup']
        worlds=[w for ws in p['population_world_seeds'] for w in ws]
        self.assertEqual(len(worlds),len(set(worlds)))
        self.assertFalse(set(worlds)&set(p['training_world_seeds']+p['validation_world_seeds']+p['test_world_seeds']))
        acceptance=load_config(acceptance=True)
        self.assertEqual(acceptance['delivery']['sessions_required'],5)
        self.assertEqual(acceptance['delivery']['horizon_weeks'],6)

    def test_reused_ancestry_and_support_feasibility_are_reported(self):
        cfg=DeliveryConfig(num_students=200,horizon_weeks=6,sessions_required=5,fairness_grouping_attribute='sex_source')
        a,b=cohort_metadata(cfg,55000),cohort_metadata(cfg,55001)
        self.assertTrue(a['with_replacement'])
        self.assertGreater(a['repeated_anchor_descendants'],0)
        self.assertGreater(a['compatibility']['feasible_students'],0)
        report=population_summary(self.rows(),[a,b])
        self.assertGreater(report['ancestry_overlap']['55000|55001']['shared_source_anchors'],0)
        self.assertIn('tutoring',a['eligible_support_types'])
        self.assertEqual(sum(a['eligible_audited_groups'].values()),200)


if __name__=='__main__':
    unittest.main()
