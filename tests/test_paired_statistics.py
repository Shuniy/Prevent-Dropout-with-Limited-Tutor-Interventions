import math
import unittest

from scipy.stats import t

from src.evaluation.paired_statistics import paired_comparison, summarize


class PairedStatisticsTests(unittest.TestCase):
    def test_pairs_world_seeds_and_uses_sample_sd_and_t_interval(self):
        rows = [{"seed": 3, "retention": 8}, {"seed": 1, "retention": 7},
                {"seed": 2, "retention": 6}]
        reference = [{"seed": 1, "retention": 6}, {"seed": 2, "retention": 3},
                     {"seed": 3, "retention": 3}]
        result = paired_comparison(rows, reference, "retention")
        # Differences [1, 3, 5], not the unpaired cells' standard errors.
        margin = t.ppf(.975, 2) * 2 / math.sqrt(3)
        self.assertEqual(result["mean"], 3)
        self.assertEqual(result["cell_mean"], 7)
        self.assertEqual(result["reference_mean"], 4)
        self.assertNotIn("mean_difference_pp", result)
        self.assertEqual(result["sample_sd"], 2)
        self.assertAlmostEqual(result["ci95_low"], 3 - margin)
        self.assertAlmostEqual(result["ci95_high"], 3 + margin)
        self.assertEqual(result["seeds"], [1, 2, 3])

    def test_rejects_duplicates_missing_worlds_and_invalid_metrics(self):
        valid = [{"seed": 1, "value": 1}]
        for selected, reference in ((valid * 2, valid), (valid, []),
                                    (valid, [{"seed": 2, "value": 1}]),
                                    ([{"seed": 1}], valid),
                                    ([{"value": 1}], valid),
                                    ([{"seed": 1, "value": math.nan}], valid)):
            with self.subTest(selected=selected, reference=reference):
                with self.assertRaises(ValueError):
                    paired_comparison(selected, reference, "value")

    def test_one_world_does_not_claim_sampling_uncertainty(self):
        result = paired_comparison([{"seed": 1, "value": 3}],
                                   [{"seed": 1, "value": 1}], "value")
        self.assertEqual(result["mean"], 2)
        self.assertEqual(result["status"], "insufficient_replicates")
        self.assertIsNone(result["sample_sd"])
        self.assertIsNone(result["ci95_low"])
        self.assertIsNone(result["ci95_high"])
        self.assertIsNone(summarize([])["mean"])

    def test_retention_effect_and_interval_are_reported_in_percentage_points(self):
        result = paired_comparison([{"seed": 1, "retention_rate": .8},
                                    {"seed": 2, "retention_rate": .9}],
                                   [{"seed": 1, "retention_rate": .7},
                                    {"seed": 2, "retention_rate": .7}], "retention_rate")
        self.assertAlmostEqual(result["cell_mean"], .85)
        self.assertAlmostEqual(result["reference_mean"], .7)
        self.assertAlmostEqual(result["mean_difference_pp"], 15)
        self.assertAlmostEqual(result["ci95_low_pp"], 100 * result["ci95_low"])
        self.assertAlmostEqual(result["ci95_high_pp"], 100 * result["ci95_high"])
        single = paired_comparison([{"seed": 1, "retention_rate": .8}],
                                   [{"seed": 1, "retention_rate": .7}], "retention_rate")
        self.assertIsNone(single["ci95_low_pp"])
        self.assertIsNone(single["ci95_high_pp"])


if __name__ == "__main__":
    unittest.main()
