from datetime import datetime, timezone
from typing import Iterable

from ib_async import IB, Contract, ContractDetails, Ticker
from prometheus_client import Metric
from prometheus_client.metrics_core import GaugeMetricFamily

from tws_exporter.collectors.ib_collector import IBCollector


class MarketDataCollector(IBCollector):
    def __init__(self, ib: IB, watch_contracts: list[str]):
        super().__init__(ib)
        self.watch_contracts = watch_contracts
        self.contracts: list[Contract] = []
        self.contract_details: list[ContractDetails] = []
        self.tickers: list[Ticker] = []

    async def on_connect(self):
        if len(self.contracts) == 0:
            for watch in self.watch_contracts:
                sec_type, symbol, currency, exchange = watch.split(":", 3)
                self.contracts.append(
                    Contract(
                        secType=sec_type,
                        symbol=symbol,
                        currency=currency,
                        exchange=exchange,
                    )
                )
            self.contracts = await self.ib.qualifyContractsAsync(*self.contracts)

        for contract in self.contracts:
            self.contract_details.append(
                (await self.ib.reqContractDetailsAsync(contract))[0]
            )
            self.tickers.append(self.ib.reqMktData(contract))

    def on_disconnect(self):
        self.contract_details.clear()
        self.tickers.clear()

    def collect(self) -> Iterable[Metric]:
        now = datetime.now(timezone.utc)

        contract_last_gauge = GaugeMetricFamily(
            "tws_contract_last",
            "TWS Contract Last Price",
            labels=["sec_type", "symbol", "currency", "exchange"],
        )
        contract_trading_gauge = GaugeMetricFamily(
            "tws_contract_trading",
            "TWS Contract is currently trading",
            labels=["sec_type", "symbol", "currency", "exchange"],
        )
        contract_liquid_gauge = GaugeMetricFamily(
            "tws_contract_liquid",
            "TWS Contract is currently liquid",
            labels=["sec_type", "symbol", "currency", "exchange"],
        )

        for ticker in self.tickers:
            contract = ticker.contract
            if contract is None:
                continue

            labels = [
                contract.secType,
                contract.symbol,
                contract.currency,
                contract.exchange,
            ]
            contract_last_gauge.add_metric(labels, ticker.last)

        for details in self.contract_details:
            if details.contract is None:
                continue

            labels = [
                details.contract.secType,
                details.contract.symbol,
                details.contract.currency,
                details.contract.exchange,
            ]
            trading_sessions = details.tradingSessions()
            liquid_sessions = details.liquidSessions()
            contract_trading_gauge.add_metric(
                labels,
                1 if any(s.start <= now <= s.end for s in trading_sessions) else 0,
            )
            contract_liquid_gauge.add_metric(
                labels,
                1 if any(s.start <= now <= s.end for s in liquid_sessions) else 0,
            )

        yield contract_last_gauge
        yield contract_trading_gauge
        yield contract_liquid_gauge
