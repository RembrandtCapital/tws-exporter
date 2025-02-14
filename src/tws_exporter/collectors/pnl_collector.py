from typing import Iterable

from prometheus_client import Metric
from prometheus_client.metrics_core import GaugeMetricFamily

from tws_exporter.collectors.ib_collector import IBCollector


class PnlCollector(IBCollector):
    def on_connect(self):
        for account in self.ib.managedAccounts():
            self.ib.reqPnL(account)

    def collect(self) -> Iterable[Metric]:
        account_pnl_daily_gauge = GaugeMetricFamily(
            "tws_account_pnl_daily", "TWS Account Daily PnL", labels=["account"]
        )
        account_pnl_unrealized_gauge = GaugeMetricFamily(
            "tws_account_pnl_unrealized",
            "TWS Account Unrealized PnL",
            labels=["account"],
        )
        account_pnl_realized_gauge = GaugeMetricFamily(
            "tws_account_pnl_realized", "TWS Account Realized PnL", labels=["account"]
        )

        for pnl in self.ib.pnl():
            labels = [pnl.account]
            account_pnl_daily_gauge.add_metric(labels, pnl.dailyPnL)
            account_pnl_unrealized_gauge.add_metric(labels, pnl.unrealizedPnL)
            account_pnl_realized_gauge.add_metric(labels, pnl.realizedPnL)

        yield account_pnl_daily_gauge
        yield account_pnl_unrealized_gauge
        yield account_pnl_realized_gauge
