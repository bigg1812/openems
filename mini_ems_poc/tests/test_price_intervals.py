"""Market-time regressions: DST, corrected data, offline restart and history."""
import json
import logging
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

from mini_ems_poc.mini_ems_runtime import price_time
from mini_ems_poc.mini_ems_runtime.config import PriceSourceConfig
from mini_ems_poc.mini_ems_runtime.cycle import _price_handoff_key
from mini_ems_poc.mini_ems_runtime.price_cache import CachedDay, PriceCacheFile, SpotmarketPriceCacheService
from mini_ems_poc.mini_ems_runtime.price_provider_smard import PriceProviderError, SmardPriceProvider
from mini_ems_poc.mini_ems_runtime.runtime_db import RuntimeDatabase, _bucket_bounds_utc
from mini_ems_poc.mini_ems_runtime.simulation import SimulatedSpotmarketPriceService
from mini_ems_poc.mini_ems_runtime.spotmarket_plan import SpotmarketManualOverrideStore, SpotmarketPlanWriter


class PriceIntervalsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def provider(self, date_iso, resolution="quarterhour"):
        provider = SmardPriceProvider(PriceSourceConfig(provider="smard", region="DE", filter=4169, resolution=resolution, timeout_seconds=1, price_factor=0.1))
        provider._fetch_index = lambda: [1]
        stride = 4 if resolution == "hour" else 1
        provider._fetch_series = lambda _: [
            (int(price_time.slot_start(date_iso, i).timestamp() * 1000), float(i))
            for i in range(0, price_time.slot_count(date_iso), stride)
        ]
        return provider

    def test_92_96_100_unique_quarters_with_and_without_system_timezone_data(self):
        for zone in (price_time.BERLIN, None):
            with patch.object(price_time, "BERLIN", zone):
                price_time.day_bounds.cache_clear()
                for day, count in (("2026-03-29", 92), ("2026-09-13", 96), ("2026-10-25", 100)):
                    self.assertEqual(price_time.slot_count(day), count)
                    starts = price_time.slot_starts(day)
                    self.assertEqual(len(set(starts)), count)
                    for index, instant in enumerate(starts):
                        self.assertEqual(price_time.slot_index(datetime.fromisoformat(instant)), index)
        price_time.day_bounds.cache_clear()

    def test_both_autumn_hours_have_independent_prices_labels_and_handoff_keys(self):
        day = "2026-10-25"
        service = SpotmarketPriceCacheService(self.root / "cache.json", self.provider(day))
        keys = []
        for index in (8, 12):
            with patch("mini_ems_poc.mini_ems_runtime.price_cache.berlin_now", return_value=price_time.to_berlin(price_time.slot_start(day, index))):
                snapshot = service.refresh()
            self.assertEqual(snapshot.current_slot_index, index)
            self.assertAlmostEqual(snapshot.current_price_ct_kwh, index * service.provider.config.price_factor)
            self.assertEqual(snapshot.today_available_slot_count, 100)
            keys.append(_price_handoff_key(snapshot))
        self.assertNotEqual(keys[0], keys[1])
        self.assertEqual(price_time.slot_label(day, 8), "02:00 +0200")
        self.assertEqual(price_time.slot_label(day, 12), "02:00 +0100")
        self.assertEqual(len(json.loads(service.path.read_text())["today"]["slots_by_label"]), 100)

    def test_history_buckets_keep_both_autumn_hours_separate_and_days_complete(self):
        for zone in (price_time.BERLIN, None):
            with patch.object(price_time, "BERLIN", zone):
                price_time.day_bounds.cache_clear()
                first = _bucket_bounds_utc(datetime.fromisoformat("2026-10-25T02:35:00+02:00"), "1h")
                second = _bucket_bounds_utc(datetime.fromisoformat("2026-10-25T02:35:00+01:00"), "1h")
                self.assertEqual(first[1], second[0])
                self.assertEqual((first[1] - first[0]).total_seconds(), 3600)
                self.assertEqual((second[1] - second[0]).total_seconds(), 3600)
                for instant, hours in (("2026-03-29T12:00:00+02:00", 23), ("2026-10-25T12:00:00+01:00", 25)):
                    start, end = _bucket_bounds_utc(datetime.fromisoformat(instant), "1d")
                    self.assertEqual((end - start).total_seconds(), hours * 3600)
        price_time.day_bounds.cache_clear()

    def test_spring_does_not_invent_nonexistent_hour_and_hour_source_expands_to_quarters(self):
        day = "2026-03-29"
        result = self.provider(day, "hour").scan_recent_slot_maps([date.fromisoformat(day)])
        slots = result.slot_maps_by_date[day]
        self.assertEqual(len(slots), 92)
        self.assertEqual(slots[8], slots[11])
        self.assertEqual(price_time.slot_label(day, 8), "03:00 +0200")

    def test_newest_source_block_wins_and_same_size_corrections_replace_cache(self):
        day = "2026-09-13"
        provider = self.provider(day)
        provider._fetch_index = lambda: [1, 2]
        instant = int(price_time.slot_start(day, 0).timestamp() * 1000)
        provider._fetch_series = lambda block: [(instant, block * 10)]
        service = SpotmarketPriceCacheService(self.root / "cache.json", provider)
        with patch("mini_ems_poc.mini_ems_runtime.price_cache.berlin_now", return_value=price_time.to_berlin(price_time.slot_start(day, 0))):
            first = service.refresh()
            provider._fetch_series = lambda block: [(instant, block * 20)]
            second = service.refresh()
        self.assertEqual(first.current_price_ct_kwh, 20 * provider.config.price_factor)
        self.assertEqual(second.current_price_ct_kwh, 40 * provider.config.price_factor)
        self.assertEqual(second.today_available_slot_count, 1)

    def test_cache_reopen_at_day_rollover_preserves_second_autumn_hour_offline(self):
        path = self.root / "cache.json"
        path.write_text(json.dumps(PriceCacheFile("2026-10-24T18:00:00+02:00", None,
            CachedDay("2026-10-25", list(range(100)))).to_dict()))
        provider = self.provider("2026-10-25")
        provider.scan_recent_slot_maps = lambda _: (_ for _ in ()).throw(PriceProviderError("offline"))
        with patch("mini_ems_poc.mini_ems_runtime.price_cache.berlin_now", return_value=datetime.fromisoformat("2026-10-25T02:00:00+01:00")):
            snapshot = SpotmarketPriceCacheService(path, provider).refresh()
        self.assertEqual(snapshot.current_price_ct_kwh, 12)
        self.assertTrue(snapshot.price_source_status["stale"])
        self.assertTrue(snapshot.price_source_status["today_complete"])

    def test_ambiguous_legacy_cache_is_rejected_normal_day_and_hour_cache_migrate(self):
        self.assertIsNone(CachedDay.from_dict({"date": "2026-10-25", "slots": [1] * 96}))
        self.assertIsNone(CachedDay.from_dict({"date": "2026-03-29", "slots": [1] * 96}))
        for count in (24, 96):
            migrated = CachedDay.from_dict({"date": "2026-09-13", "slots": [1] * count})
            self.assertEqual(len(migrated.slots), 96)
            self.assertEqual(migrated.to_dict()["time_model"], price_time.TIME_MODEL)
        for bad in (float("nan"), float("inf"), "invalid"):
            self.assertIsNone(CachedDay.from_dict({"date": "2026-09-13", "slots": [bad] * 96}))

    def test_missing_current_interval_without_cache_does_not_fabricate_price(self):
        provider = self.provider("2026-10-25")
        provider._fetch_series = lambda _: []
        with patch("mini_ems_poc.mini_ems_runtime.price_cache.berlin_now", return_value=datetime.fromisoformat("2026-10-25T02:00:00+01:00")):
            with self.assertRaises(PriceProviderError):
                SpotmarketPriceCacheService(self.root / "cache.json", provider).refresh()

    def test_window_duration_crosses_repeated_hour_and_persists_unique_endpoints(self):
        day = "2026-10-25"
        slots = [10.] * 100
        slots[8:16] = [-1.] * 8
        writer = SpotmarketPlanWriter(self.root / "plan.json", 0, 8)
        plan = writer.write_plan("2026-10-25T00:00:00Z", day, slots, None, [], 12)
        window = plan["today"]["windows"][0]
        self.assertTrue(plan["active_today_now"])
        self.assertEqual(window["length_quarters"], 8)
        self.assertEqual(window["start_utc"], "2026-10-25T00:00:00+00:00")
        self.assertEqual(window["end_utc"], "2026-10-25T02:00:00+00:00")
        db = RuntimeDatabase(self.root / "runtime.sqlite")
        with db._connection() as connection:
            db._upsert_spotmarket_plan(connection, plan)
        saved = db.get_daily_report(day)["spotmarket_windows"][0]
        self.assertEqual(saved["start_utc"], window["start_utc"])
        self.assertEqual(saved["end_utc"], window["end_utc"])

    def test_history_keeps_legacy_evidence_and_uses_new_utc_day_without_double_count(self):
        day = "2026-10-25"
        db = RuntimeDatabase(self.root / "runtime.sqlite")
        legacy = {"date": day, "slots": [99.] * 96, "captured_at": "legacy"}
        with db._connection() as connection:
            db._upsert_price_day(connection, legacy)
        self.assertEqual(db.get_daily_report(day)["price_ct_kwh"]["time_model"], "legacy_clock_slots")
        with db._connection() as connection:
            db._upsert_price_day(connection, CachedDay(day, list(range(100))).to_dict())
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM price_slots").fetchone()[0], 96)
            self.assertEqual(connection.execute("SELECT COUNT(DISTINCT slot_start_utc) FROM price_intervals").fetchone()[0], 100)
        report = RuntimeDatabase(db.path).get_daily_report(day)["price_ct_kwh"]
        self.assertEqual(report["slot_count"], 100)
        self.assertEqual(report["average"], 49.5)
        self.assertEqual(report["time_model"], price_time.TIME_MODEL)

    def test_simulation_generates_matching_transition_days_for_both_resolutions(self):
        prices = self.root / "prices.json"
        prices.write_text('{"default_ct_kwh": 7}')
        for day, count in (("2026-03-29", 92), ("2026-10-25", 100)):
            for resolution in ("hour", "quarterhour"):
                service = SimulatedSpotmarketPriceService(self.root / "cache.json", prices, resolution, logging.getLogger("test"))
                with patch("mini_ems_poc.mini_ems_runtime.simulation.berlin_now", return_value=price_time.to_berlin(price_time.slot_start(day, 12))):
                    result = service.refresh()
                self.assertEqual(len(result.today_slots), count)
                self.assertEqual(result.current_slot_index, 12)
                self.assertEqual(result.current_price_ct_kwh, 7)

    def test_manual_clock_window_rejects_missing_and_ambiguous_times_accepts_utc(self):
        store = SpotmarketManualOverrideStore(self.root / "override.json")
        for day in ("2026-10-25", "2026-03-29"):
            store.path.write_text(json.dumps({"enabled": True, "date": day, "windows": [
                {"start_label": "02:00", "end_label_exclusive": "04:00"}]}))
            with self.assertRaisesRegex(PriceProviderError, "mehrdeutig"):
                store.load_for_date(day)
        store.path.write_text(json.dumps({"enabled": True, "date": "2026-10-25", "windows": [
            {"start_utc": "2026-10-25T01:00:00Z", "end_utc": "2026-10-25T01:30:00Z"}]}))
        override = store.load_for_date("2026-10-25")
        self.assertTrue(override.active_now(12))
        self.assertFalse(override.active_now(8))


if __name__ == "__main__":
    unittest.main()
