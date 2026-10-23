import unittest
from datetime import datetime, timezone

from ib_async import IB, Contract, Ticker
from prometheus_client import CollectorRegistry, generate_latest
from prometheus_client.parser import text_string_to_metric_families
from prometheus_client.samples import Sample

from tws_exporter.collectors.market_data_collector import MarketDataCollector


class PreviousCloseTest(unittest.TestCase):
    def setUp(self) -> None:
        self.collector = MarketDataCollector(IB(), [])
        self.ticker = Ticker(
            contract=Contract(
                secType="IND", symbol="SPX", currency="USD", exchange="CBOE"
            ),
            time=datetime.now(timezone.utc),
        )
        self.ticker.last = 7550.0
        self.ticker.close = 7500.0
        self.collector.tickers = [self.ticker]

    def scrape(self, name: str) -> list[Sample]:
        registry = CollectorRegistry()
        registry.register(self.collector)
        return [
            sample
            for metric in text_string_to_metric_families(
                generate_latest(registry).decode()
            )
            for sample in metric.samples
            if sample.name == name
        ]

    def test_previous_close_uses_the_same_contract_labels_as_last(self) -> None:
        spy = Ticker(
            contract=Contract(
                secType="STK", symbol="SPY", currency="USD", exchange="SMART"
            ),
            time=datetime.now(timezone.utc),
        )
        spy.last = 755.0
        spy.close = 750.0
        self.collector.tickers.append(spy)
        closes = self.scrape("tws_contract_previous_close")
        self.assertEqual(
            [(sample.labels, sample.value) for sample in closes],
            [
                (
                    {
                        "sec_type": "IND",
                        "symbol": "SPX",
                        "currency": "USD",
                        "exchange": "CBOE",
                    },
                    7500.0,
                ),
                (
                    {
                        "sec_type": "STK",
                        "symbol": "SPY",
                        "currency": "USD",
                        "exchange": "SMART",
                    },
                    750.0,
                ),
            ],
        )
        self.assertEqual(
            [sample.labels for sample in closes],
            [sample.labels for sample in self.scrape("tws_contract_last")],
        )

    def test_invalid_previous_close_does_not_replace_or_drop_last(self) -> None:
        for close in (float("nan"), float("inf"), float("-inf"), 0.0, -1.0):
            with self.subTest(close=close):
                self.ticker.close = close
                self.assertEqual(self.scrape("tws_contract_previous_close"), [])
                self.assertEqual(
                    [sample.value for sample in self.scrape("tws_contract_last")],
                    [7550.0],
                )

    def test_previous_close_does_not_require_a_current_tick_timestamp(self) -> None:
        self.ticker.time = None
        self.assertEqual(
            [sample.value for sample in self.scrape("tws_contract_previous_close")],
            [7500.0],
        )
        self.assertEqual(self.scrape("tws_contract_last"), [])

    def test_broker_close_updates_replace_the_baseline_without_caching(self) -> None:
        self.assertEqual(
            [sample.value for sample in self.scrape("tws_contract_previous_close")],
            [7500.0],
        )
        self.ticker.close = 7600.0
        self.assertEqual(
            [sample.value for sample in self.scrape("tws_contract_previous_close")],
            [7600.0],
        )
        self.ticker.close = float("nan")
        self.assertEqual(self.scrape("tws_contract_previous_close"), [])

    def test_disconnect_removes_the_previous_close(self) -> None:
        self.collector.on_disconnect()
        self.assertEqual(self.scrape("tws_contract_previous_close"), [])

    def test_ticker_without_a_contract_is_omitted(self) -> None:
        self.ticker.contract = None
        self.assertEqual(self.scrape("tws_contract_previous_close"), [])
        self.assertEqual(self.scrape("tws_contract_last"), [])


if __name__ == "__main__":
    unittest.main()
