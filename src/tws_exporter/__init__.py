import asyncio
import typing

import configargparse  # type: ignore
from configargparse import ArgumentParser
from ib_async import IB
from prometheus_client import REGISTRY, Gauge, start_http_server

from tws_exporter.collectors import (
    AccountValuesCollector,
    PnlCollector,
    MarketDataCollector,
    OrderCollector,
)


class CliArgs(configargparse.Namespace):
    tws_host: str
    tws_port: int
    tws_client_id: int
    metrics_host: str
    metrics_port: int
    watch_contracts: list[str]


ib = IB()


up_gauge = Gauge("up", "TWS Up")


async def connect(tws_host: str, tws_port: int, tws_client_id: int):
    attempts = 0
    while True:
        try:
            await ib.connectAsync(tws_host, tws_port, clientId=tws_client_id)
            print("Connected to TWS")
            break
        except Exception:
            delay = 2 ** min(attempts, 3)
            print("Connection failed, retrying in", delay, "seconds")
            await asyncio.sleep(delay)
            attempts += 1


async def async_main(tws_host: str, tws_port: int, tws_client_id: int) -> None:
    connect_task: None | asyncio.Task = None

    def on_connect():
        nonlocal connect_task

        up_gauge.set(1)
        connect_task = None

    def on_disconnect():
        nonlocal connect_task

        up_gauge.set(0)
        if connect_task is None:
            connect_task = asyncio.create_task(
                connect(tws_host, tws_port, tws_client_id)
            )

    ib.connectedEvent += on_connect
    ib.disconnectedEvent += on_disconnect

    await connect(tws_host, tws_port, tws_client_id)

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

    REGISTRY.register(AccountValuesCollector(ib))
    REGISTRY.register(MarketDataCollector(ib, args.watch_contracts))
    REGISTRY.register(OrderCollector(ib))
    REGISTRY.register(PnlCollector(ib))
    start_http_server(args.metrics_port, addr=args.metrics_host)

    asyncio.run(async_main(args.tws_host, args.tws_port, args.tws_client_id))


if __name__ == "__main__":
    main()
