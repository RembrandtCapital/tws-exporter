from typing import Iterable

from prometheus_client import Metric
from prometheus_client.metrics_core import GaugeMetricFamily

from tws_exporter.collectors.ib_collector import IBCollector


class AccountValuesCollector(IBCollector):
    def collect(self) -> Iterable[Metric]:
        account_value_gauge = GaugeMetricFamily(
            "tws_account_value",
            "TWS Account Value",
            labels=["account", "currency", "tag"],
        )
        account_value_info = GaugeMetricFamily(
            "tws_account_info",
            "TWS Account Value Info",
            labels=["account", "currency", "tag", "value"],
        )

        for account_value in self.ib.accountValues():
            labels = [
                account_value.account,
                account_value.currency,
                account_value.tag,
            ]
            try:
                amount = float(account_value.value)
                account_value_gauge.add_metric(labels, amount)
            except ValueError:
                labels.append(account_value.value)
                account_value_info.add_metric(labels, 1.0)

        yield account_value_gauge
        yield account_value_info
