import asyncio
import typing

import configargparse  # type: ignore
from configargparse import ArgumentParser

from ib_async import IB, AccountValue
from prometheus_client import start_http_server, Gauge


class CliArgs(configargparse.Namespace):
    tws_host: str
    tws_port: int
    tws_client_id: int
    metrics_host: str
    metrics_port: int


account_value_gauge = Gauge(
    "tws_account_value", "TWS Account Value", ["account", "currency", "tag"]
)
account_value_info = Gauge(
    "tws_account_info",
    "TWS Account Value Info",
    ["account", "currency", "tag", "value"],
)


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


async def async_main(tws_host: str, tws_port: int, tws_client_id: int) -> None:
    ib = IB()
    ib.accountValueEvent += on_account_value
    await ib.connectAsync(tws_host, tws_port, clientId=tws_client_id)

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
    args = typing.cast(CliArgs, parser.parse_args(namespace=CliArgs()))

    start_http_server(args.metrics_port, addr=args.metrics_host)

    asyncio.run(async_main(args.tws_host, args.tws_port, args.tws_client_id))


if __name__ == "__main__":
    main()
