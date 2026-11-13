"""Bounded acceptance must fail on missing or forged derived evidence."""
import contextlib
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest

from src.evaluation.phase5_followup import CONFIG,run,verify_followup,verify_historical_inputs
from src.evaluation.provenance import seal_directory,verify_directory


class AcceptanceIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.path=Path(cls.temp.name)/'acceptance'
        with contextlib.redirect_stdout(io.StringIO()):
            cls.result=run(CONFIG,cls.path,'acceptance')

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def change_and_check(self,path,value,pattern):
        original=path.read_bytes()
        try:
            path.write_text(json.dumps(value))
            (self.path/'artifact_integrity.json').unlink();seal_directory(self.path)
            with self.assertRaisesRegex(ValueError,pattern):
                verify_followup(self.path)
        finally:
            path.write_bytes(original)
            (self.path/'artifact_integrity.json').unlink();seal_directory(self.path)

    def test_bounded_acceptance_exercises_complete_routes(self):
        result=self.result['verification']
        self.assertEqual(result['status'],'verified')
        self.assertGreaterEqual(result['episodes'],22)
        self.assertEqual(result['reference_worlds_regenerated'],9)
        self.assertEqual(self.result['summary']['population']['feasibility']['nonzero_offer_episodes'],2)
        self.assertEqual(self.result['summary']['language']['llm']['status'],'unexecuted_not_requested')

    def test_missing_mandatory_artifact_cannot_claim_success(self):
        path=self.path/'completion.json';value=json.loads(path.read_text());del value['prediction']
        self.change_and_check(path,value,'missing mandatory')

    def test_resealed_forged_population_summary_is_rejected(self):
        path=self.path/'population/population_report.json';value=json.loads(path.read_text())
        value['outcomes']['retention_rate']['population_clusters']['mean']=999
        self.change_and_check(path,value,'population cluster summary')

    def test_resealed_forged_scorecard_is_rejected(self):
        path=next((self.path/'population').rglob('*_scorecards.json'));value=json.loads(path.read_text())
        value['simulated_effectiveness']['retention_rate']=999
        self.change_and_check(path,value,'derived-scorecard')

    def test_historical_inputs_and_original_model_remain_identical(self):
        self.assertEqual(verify_historical_inputs()['status'],'unchanged')
        self.assertGreater(verify_historical_inputs()['files'],9)


if __name__=='__main__':
    unittest.main()
