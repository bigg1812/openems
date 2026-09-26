import unittest

from mini_ems_poc.mini_ems_runtime.config import GridLockoutConfig
from mini_ems_poc.mini_ems_runtime.controllers import (
    GridLockoutController,
    GridLockoutState,
)


class GridLockoutControllerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.controller = GridLockoutController(
            GridLockoutConfig(
                threshold_kw=5.0,
                clear_threshold_kw=5.5,
                below_threshold_cycles_required=3,
            )
        )

    def test_grid_lockout_activates_after_three_cycles(self) -> None:
        state = GridLockoutState()

        first = self.controller.evaluate(3.0, state)
        second = self.controller.evaluate(3.5, state)
        third = self.controller.evaluate(4.0, state)

        self.assertFalse(first.desired_value)
        self.assertFalse(second.desired_value)
        self.assertTrue(third.desired_value)
        self.assertEqual(state.mode, "lockout_active")
        self.assertEqual(state.below_threshold_counter, 3)

    def test_grid_lockout_state_survives_restart(self) -> None:
        initial_state = GridLockoutState()
        self.controller.evaluate(4.5, initial_state)
        self.controller.evaluate(4.2, initial_state)

        persisted = GridLockoutState.from_dict(initial_state.to_dict())
        new_controller = GridLockoutController(self.controller.config)
        outcome = new_controller.evaluate(4.1, persisted)

        self.assertTrue(outcome.desired_value)
        self.assertEqual(persisted.mode, "lockout_active")
        self.assertEqual(persisted.below_threshold_counter, 3)

    def test_grid_lockout_clears_above_clear_threshold(self) -> None:
        state = GridLockoutState(mode="lockout_active", below_threshold_counter=3)

        outcome = self.controller.evaluate(6.0, state)

        self.assertFalse(outcome.desired_value)
        self.assertEqual(state.mode, "monitoring")
        self.assertEqual(state.below_threshold_counter, 0)
