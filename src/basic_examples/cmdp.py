
if __package__ in (None, ""):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.utils.constants import EXAMPLE_SEED
from src.utils.enums import CMDPStudentState as StudentState, CMDPMentorActions as MentorActions

# simulate 100 students over 12 months with a constrained Markov decision process model for dropout behavior

import numpy as np
from scipy.optimize import linprog

rng = np.random.default_rng(EXAMPLE_SEED)  # set a random seed for reproducibility


class School:
    def __init__(self):
        # transition probabilities for each state given mentor actions
        self.probabilities = {
            StudentState.ACTIVE: {
                MentorActions.PROVIDE_SUPPORT: [0.9, 0.1, 0.0],  # P(ACTIVE|SUPPORT), P(AT_RISK|SUPPORT), P(DROPPED_OUT|SUPPORT)
                MentorActions.IGNORE: [0.7, 0.2, 0.1],  # P(ACTIVE|IGNORE), P(AT_RISK|IGNORE), P(DROPPED_OUT|IGNORE)
            },
            StudentState.AT_RISK: {
                MentorActions.PROVIDE_SUPPORT: [0.6, 0.3, 0.1],  # P(ACTIVE|SUPPORT), P(AT_RISK|SUPPORT), P(DROPPED_OUT|SUPPORT)
                MentorActions.IGNORE: [0.4, 0.4, 0.2],  # P(ACTIVE|IGNORE), P(AT_RISK|IGNORE), P(DROPPED_OUT|IGNORE)
            },
            StudentState.DROPPED_OUT: {
                MentorActions.PROVIDE_SUPPORT: [0.0, 0.0, 1.0],  # P(ACTIVE|SUPPORT), P(AT_RISK|SUPPORT), P(DROPPED_OUT|SUPPORT)
                MentorActions.IGNORE: [0.0, 0.0, 1.0],  # P(ACTIVE|IGNORE), P(AT_RISK|IGNORE), P(DROPPED_OUT|IGNORE)
            }
        }
        self.probabilities_matrix = []
        for state in StudentState:
            self.probabilities_matrix.append([])
            for action in MentorActions:
                self.probabilities_matrix[-1].append(self.probabilities[state][action])

        # reward for arriving in a state (e.g., ACTIVE is good, DROPPED_OUT is bad)
        self.rewards = {
            StudentState.ACTIVE: 10,
            StudentState.AT_RISK: 0,
            StudentState.DROPPED_OUT: -20
        }
        self.rewards_vector = np.array([self.rewards[state] for state in StudentState])

        # cost for taking an action (e.g., providing support has a cost)
        self.costs = {
            MentorActions.PROVIDE_SUPPORT: 3,
            MentorActions.IGNORE: 0
        }
        self.costs_vector = np.array([self.costs[action] for action in MentorActions])

        # discount factor for future reward-
        self.discount_factor = 0.9

        # initialize students and their values
        self.students = []
        # initialize values for each state
        self.values = {state: 0 for state in StudentState}
        # results
        self.results = {}
        # number of sessions per month
        self.sessions_per_month = 10
        self.results = {
            0: self.count_states()
        }

    def simulate(self, policy, num_students, sessions_per_month):
        """Simulate students with a HARD monthly limit on mentoring slots.

        If independently drawn CMDP support recommendations exceed the cap,
        randomly retain only `sessions_per_month` of them. This capacity
        repair makes the realised policy feasible, but only approximately
        implements the expected-budget CMDP solution.
        """
        self.sessions_per_month = sessions_per_month
        states = np.where(
            rng.random(num_students) < 0.8,
            StudentState.ACTIVE,
            StudentState.AT_RISK,
        ).astype(int)

        counts = lambda: np.bincount(states, minlength=3)
        results = [(0, *map(int, counts()), 0)]

        for month in range(policy.shape[0]):
            desired_support_prob = policy[month, states, MentorActions.PROVIDE_SUPPORT]
            proposed = np.flatnonzero(
                (states != StudentState.DROPPED_OUT)
                & (rng.random(num_students) < desired_support_prob)
            )
            if len(proposed) > sessions_per_month:
                selected = rng.choice(
                    proposed, size=sessions_per_month, replace=False
                )
            else:
                selected = proposed

            actions = np.full(num_students, MentorActions.IGNORE, dtype=int)
            actions[selected] = MentorActions.PROVIDE_SUPPORT

            # Every non-dropped-out student transitions every month.
            for i in range(num_students):
                if states[i] != StudentState.DROPPED_OUT:
                    states[i] = rng.choice(3, p=self.probabilities_matrix[states[i]][actions[i]])

            results.append((month + 1, *map(int, counts()), len(selected)))

        return results


    def count_states(self):
        state_counts = {state: 0 for state in StudentState}
        for student in self.students:
            state_counts[student.state] += 1
        return state_counts

    def print_results(self, month,counts):
        print(
        f"Month {month}: "
        f"Active={counts[StudentState.ACTIVE]}, "
        f"At Risk={counts[StudentState.AT_RISK]}, "
        f"Dropped Out={counts[StudentState.DROPPED_OUT]}"
    )

    def run(self, num_students=100, num_steps=12):
        policy, expected_sessions, objective = self.solve_cmdp(
            num_students=num_students, num_months=num_steps, sessions_per_month=10
        )
        print(f"Optimal expected discounted reward across {num_students} students: {objective:.3f}")
        print("Expected sessions per month:", np.round(expected_sessions, 2))
        print("Month 1 P(support | Active, At Risk):", np.round(policy[0, :2, 0], 3))
        print("Month | Active | At risk | Dropped | Sessions")
        for result in self.simulate(policy, num_students, 10):
            print(f"{result[0]:>5} | {result[1]:>6} | {result[2]:>7} | {result[3]:>7} | {result[4]:>8}")

    def solve_cmdp(self, num_students=100, num_months=12, sessions_per_month=10):
        """Optimize expected resource use via state-action occupancy measures.

        x[t,s,a] = probability that a representative student is in state s
        and receives action a at month t. The expected number supported is
        num_students * sum_s x[t,s,SUPPORT].
        """

        num_states = len(StudentState)
        num_actions = len(MentorActions)
        n_variables = num_states * num_actions * num_months

        def index(t, s, a):
            return (t * num_states + s) * num_actions + a

        # Maximize expected sum of discounted (NEXT-state reward - action cost).
        # linprog minimizes, hence the minus sign.
        c = np.zeros(n_variables)
        for t in range(num_months):
            for s in range(num_states):
                for a in range(num_actions):
                    immediate_reward = np.matmul(self.probabilities_matrix[s][a], self.rewards_vector)
                    c[index(t, s, a)] = -(self.discount_factor ** t) * (immediate_reward - self.costs_vector[a])

        # Constraints: initial state distribution
        A_eq = np.zeros((num_months * num_states, n_variables))
        b_eq = np.zeros(num_months * num_states)
        initial_distribution = np.array([0.8, 0.2, 0.0])  # 80% ACTIVE, 20% AT_RISK, 0% DROPPED_OUT

        # Constraints: state-action occupancy measures must satisfy the transition dynamics
        for t in range(num_months):
            for s in range(num_states):
                row = t * num_states + s
                # Current month's occupancy
                for a in range(num_actions):
                    A_eq[row, index(t, s, a)] += 1.0

                if t == 0:
                    # Initial state distribution
                    b_eq[row] = initial_distribution[s]
                else:
                    # For each previous state and action, subtract the transition probability to the current state from the occupancy measure of the current state and action. This ensures that the occupancy measures are consistent with the transition dynamics of the Markov decision process.
                    for prev_state in range(num_states):
                        for prev_action in range(num_actions):
                            transition_prob = self.probabilities_matrix[prev_state][prev_action][s]
                            A_eq[row, index(t - 1, prev_state, prev_action)] -= transition_prob

        # constraints: the expected number of students receiving support in each month must not exceed the available sessions
        A_ub = np.zeros((num_months, n_variables))
        b_ub = np.zeros(num_months)
        for t in range(num_months):
            for s in range(num_states):
                for a in range(num_actions):
                    if a == MentorActions.PROVIDE_SUPPORT.value:
                        A_ub[t, index(t, s, a)] += 1.0
            b_ub[t] = sessions_per_month / num_students

        # bounds
        bounds = [(0, None) for _ in range(n_variables)]
        # never spend on dropped out students
        for t in range(num_months):
            bounds[index(t, StudentState.DROPPED_OUT.value, MentorActions.PROVIDE_SUPPORT.value)] = (0, 0)

        # Solve the linear program
        result = linprog(c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method='highs')
        if not result.success:
            raise RuntimeError(f"CMDP optimisation failed: {result.message}")

        occupancy_measures = result.x.reshape((num_months, num_states, num_actions))
        state_probabilities = occupancy_measures.sum(axis=2)  # sum over actions to get state probabilities
        policy = np.divide(
            occupancy_measures, 
            state_probabilities[:, :, None],
            out=np.zeros_like(occupancy_measures), 
            where=state_probabilities[:, :, None] > 1e-12
        )

        # For unreachable states, use IGNORE instead of an all-zero action row.
        unreachable = state_probabilities <= 1e-12
        policy[:, :, MentorActions.IGNORE.value][unreachable] = 1.0
        # expected number of students receiving support in each month
        expected_sessions = num_students * occupancy_measures[:, :, MentorActions.PROVIDE_SUPPORT.value].sum(axis=1)
        # objective value is the expected discounted reward across all students
        objective = -num_students * result.fun
        return policy, expected_sessions, objective

school = School()
school.run(num_students=100, num_steps=12)