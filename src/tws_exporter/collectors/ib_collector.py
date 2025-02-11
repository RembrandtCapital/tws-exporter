from abc import ABC

from ib_async import IB
from prometheus_client.registry import Collector


class IBCollector(Collector, ABC):
    def __init__(self, ib: IB):
        super().__init__()
        self.ib = ib
        self.ib.connectedEvent += self.on_connect
        self.ib.disconnectedEvent += self.on_disconnect

    def on_connect(self):
        pass

    def on_disconnect(self):
        pass
