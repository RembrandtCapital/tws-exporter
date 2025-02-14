from typing import Iterable

from ib_async import OrderStatus
from prometheus_client import Metric
from prometheus_client.metrics_core import GaugeMetricFamily, CounterMetricFamily

from tws_exporter.collectors.ib_collector import IBCollector

ALL_STATUS = frozenset(
    [
        OrderStatus.PendingSubmit,
        OrderStatus.PendingCancel,
        OrderStatus.PreSubmitted,
        OrderStatus.Submitted,
        OrderStatus.ApiPending,
        OrderStatus.ApiCancelled,
        OrderStatus.Cancelled,
        OrderStatus.Filled,
        OrderStatus.Inactive,
    ]
)


class OrderCollector(IBCollector):
    def collect(self) -> Iterable[Metric]:
        yield CounterMetricFamily(
            "tws_order_count_total",
            "TWS number of orders in this session",
            len(self.ib.trades()),
        )

        orders_by_status_gauge = GaugeMetricFamily(
            "tws_order_count", "TWS number of orders", labels=["status"]
        )

        counts: dict[str, int] = {s: 0 for s in ALL_STATUS}

        for trade in self.ib.trades():
            counts[trade.orderStatus.status] += 1

        for status, count in counts.items():
            orders_by_status_gauge.add_metric([status], count)

        yield orders_by_status_gauge
