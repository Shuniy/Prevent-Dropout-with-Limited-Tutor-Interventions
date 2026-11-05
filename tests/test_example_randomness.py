import contextlib
import importlib
import io
import unittest


class ExampleRandomnessTests(unittest.TestCase):
    def test_school_streams_are_independent_and_honor_seeds(self):
        factories = {
            "agent_based_modelling": lambda m, seed: m.School(50, seed=seed),
            "markov_chains": lambda m, seed: m.School(
                50, [[0.8, 0.15, 0.05], [0.1, 0.7, 0.2], [0, 0, 1]], seed=seed),
            "markov_decision_process": lambda m, seed: m.School(seed=seed),
            "budgeted_mdp": lambda m, seed: m.School(seed=seed),
            "cmdp": lambda m, seed: m.School(seed=seed),
        }
        for name, factory in factories.items():
            with self.subTest(name=name):
                module = importlib.import_module(f"src.basic_examples.{name}")

                def run(seed):
                    school = factory(module, seed)
                    if name == "agent_based_modelling":
                        school.simulate(12)
                        return [(s.motivation, s.is_dropout) for s in school.students]
                    if name == "markov_chains":
                        school.simulate(12)
                        return [s.state for s in school.students]
                    if name == "cmdp":
                        return school.run(num_students=50)[0]
                    return school.run(num_students=50)

                expected = run(17)
                run(99)
                self.assertEqual(run(17), expected)
                self.assertNotEqual(run(18), expected)

    def test_main_invocations_restart_the_default_stream(self):
        for name in ("simple_agent", "agent_based_modelling", "markov_chains",
                     "markov_decision_process", "budgeted_mdp", "cmdp"):
            with self.subTest(name=name):
                module = importlib.import_module(f"src.basic_examples.{name}")
                first, second = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(first):
                    module.main()
                with contextlib.redirect_stdout(second):
                    module.main()
                self.assertEqual(first.getvalue(), second.getvalue())

    def test_simple_agent_uses_an_injected_stream(self):
        from src.basic_examples.simple_agent import Student
        from src.utils.constants import create_rng

        first_rng, second_rng = create_rng(17), create_rng(17)
        first = [Student(0.7, rng=first_rng) for _ in range(10)]
        second = [Student(0.7, rng=second_rng) for _ in range(10)]
        for _ in range(12):
            for student in first:
                student.step()
            Student(0.7, seed=99).step()
            for student in second:
                student.step()
        self.assertEqual([(s.motivation, s.is_dropout) for s in first],
                         [(s.motivation, s.is_dropout) for s in second])


if __name__ == "__main__":
    unittest.main()
