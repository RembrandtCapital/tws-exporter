import asyncio
import typing
from datetime import datetime, timezone

import configargparse  # type: ignore
from configargparse import ArgumentParser

from ib_async import IB, AccountValue, Contract, Ticker, ContractDetails
from prometheus_client import start_http_server, Gauge


class CliArgs(configargparse.Namespace):
    tws_host: str
    tws_port: int
    tws_client_id: int
    metrics_host: str
    metrics_port: int
    watch_contracts: list[str]


account_value_gauge = Gauge(
    "tws_account_value", "TWS Account Value", ["account", "currency", "tag"]
)
account_value_info = Gauge(
    "tws_account_info",
    "TWS Account Value Info",
    ["account", "currency", "tag", "value"],
)

contract_last_gauge = Gauge(
    "tws_contract_last",
    "TWS Contract Last Price",
    ["sec_type", "symbol", "currency", "exchange"],
)
contract_trading_gauge = Gauge(
    "tws_contract_trading",
    "TWS Contract is currently trading",
    ["sec_type", "symbol", "currency", "exchange"],
)
contract_liquid_gauge = Gauge(
    "tws_contract_liquid",
    "TWS Contract is currently liquid",
    ["sec_type", "symbol", "currency", "exchange"],
)

watched_contract_details: list[ContractDetails] = []


def on_account_value(account_value: AccountValue) -> None:
    attributes = {
        "account": account_value.account,
        "currency": account_value.currency,
        "tag": account_value.tag,
    }

    try:
        amount = float(account_value.value)
        account_value_gauge.labels(**attributes).set(amount)
    except ValueError:
        attributes["value"] = account_value.value
        account_value_info.labels(**attributes).set(1.0)


def on_ticker(tickers: set[Ticker]) -> None:
    for ticker in tickers:
        contract = ticker.contract
        if contract is None:
            continue

        attributes = {
            "sec_type": contract.secType,
            "symbol": contract.symbol,
            "currency": contract.currency,
            "exchange": contract.exchange,
        }
        contract_last_gauge.labels(**attributes).set(ticker.last)


async def market_hours_task():
    while True:
        try:
            now = datetime.now(timezone.utc)
            for details in watched_contract_details:
                attributes = {
                    "sec_type": details.contract.secType,
                    "symbol": details.contract.symbol,
                    "currency": details.contract.currency,
                    "exchange": details.contract.exchange,
                }
                trading_sessions = details.tradingSessions()
                liquid_sessions = details.liquidSessions()
                contract_trading_gauge.labels(**attributes).set(
                    1 if any(s.start <= now <= s.end for s in trading_sessions) else 0
                )
                contract_liquid_gauge.labels(**attributes).set(
                    1 if any(s.start <= now <= s.end for s in liquid_sessions) else 0
                )
            await asyncio.sleep(1)
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(e)


async def async_main(
    tws_host: str, tws_port: int, tws_client_id: int, watch_contracts=None
) -> None:
    if watch_contracts is None:
        watch_contracts = []

    ib = IB()
    ib.accountValueEvent += on_account_value
    ib.pendingTickersEvent += on_ticker
    await ib.connectAsync(tws_host, tws_port, clientId=tws_client_id)

    contracts = []
    for watch in watch_contracts:
        sec_type, symbol, currency, exchange = watch.split(":", 3)
        contracts.append(
            Contract(
                secType=sec_type, symbol=symbol, currency=currency, exchange=exchange
            )
        )

    contracts = await ib.qualifyContractsAsync(*contracts)
    for contract in contracts:
        watched_contract_details.append((await ib.reqContractDetailsAsync(contract))[0])
        ib.reqMktData(contract)

    asyncio.create_task(market_hours_task())

    try:
        await asyncio.Future()
    except asyncio.CancelledError:
        pass

    ib.disconnect()


def main() -> None:
    parser = ArgumentParser(
        auto_env_var_prefix="",
        formatter_class=configargparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--tws-host", default="127.0.0.1", help="TWS Host")
    parser.add_argument("--tws-port", type=int, default=7497, help="TWS Port")
    parser.add_argument("--tws-client-id", type=int, default=1, help="TWS Client ID")
    parser.add_argument("--metrics-host", default="0.0.0.0", help="Metrics Host")
    parser.add_argument("--metrics-port", type=int, default=9465, help="Metrics Port")
    parser.add_argument(
        "--watch-contracts",
        type=str,
        default=[],
        nargs="*",
        help="List of contracts to watch in format type:symbol:currency:exchange (ex. index:SPX:USD:CBOE, stock:AAPL:USD:SMART)",
    )
    args = typing.cast(CliArgs, parser.parse_args(namespace=CliArgs()))

    start_http_server(args.metrics_port, addr=args.metrics_host)

    asyncio.run(
        async_main(
            args.tws_host, args.tws_port, args.tws_client_id, args.watch_contracts
        )
    )


if __name__ == "__main__":
    main()
