import unittest

from mini_ems_poc.mini_ems_runtime.config import GridLockoutConfig, SpotMarketLockoutConfig
from mini_ems_poc.mini_ems_runtime.controllers import (
    GridLockoutController,
    GridLockoutState,
    SpotMarketLockoutController,
    SpotMarketLockoutState,
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


class SpotMarketLockoutControllerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.controller = SpotMarketLockoutController(
            SpotMarketLockoutConfig(
                negative_hours_min_consecutive=4,
                min_valid_hours=24,
                invalid_price_sentinel=None,
            )
        )

    def test_negative_prices_activate_lockout(self) -> None:
        prices = [12.0, 11.0, 10.0, -0.5, -1.2, -2.1, -0.4] + [5.0] * 17
        state = SpotMarketLockoutState()

        outcome = self.controller.evaluate(prices, state)

        self.assertTrue(outcome.desired_value)
        self.assertEqual(state.mode, "lockout_active")
        self.assertEqual(state.longest_negative_block, 4)

    def test_small_negative_prices_are_still_negative(self) -> None:
        prices = [-0.2, -0.2, -0.2, -0.2] + [3.0] * 20
        state = SpotMarketLockoutState()

        outcome = self.controller.evaluate(prices, state)

        self.assertTrue(outcome.desired_value)
        self.assertIn(0, outcome.metrics["negative_hours"])

    def test_incomplete_price_series_triggers_safe_mode(self) -> None:
        prices = [1.0] * 22 + [None, None]
        state = SpotMarketLockoutState()

        outcome = self.controller.evaluate(prices, state)

        self.assertFalse(outcome.valid)
        self.assertTrue(outcome.safe_mode_required)
        self.assertFalse(outcome.desired_value)


if __name__ == "__main__":
    unittest.main()
