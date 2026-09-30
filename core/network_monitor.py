import os
os.environ["QT_API"] = "pyside6"

import threading
import time
import socket
from urllib.parse import urlparse

class NetworkMonitor(threading.Thread):
    """
    Wątek monitorujący dostęp do Internetu (DNS 1.1.1.1) oraz lokalne RTT serwera Navidrome.
    """
    def __init__(self, local_url):
        super().__init__(daemon=True)
        self.local_host, self.local_port = self._extract_host_and_port(local_url)
        self.is_online = False
        self.net_ping = 0
        self.loc_lat = 0
        self._running = True

    def _extract_host_and_port(self, url):
        try:
            parsed = urlparse(url)
            host = parsed.hostname or "localhost"
            port = parsed.port or 4533
            return host, port
        except Exception:
            return "localhost", 4533

    def run(self):
        while self._running:
            start = time.time()
            try:
                socket.create_connection(("1.1.1.1", 53), timeout=2)
                self.net_ping = int((time.time() - start) * 1000)
                self.is_online = True
            except Exception:
                self.net_ping = -1
                self.is_online = False

            if self.local_host:
                start = time.time()
                try:
                    socket.create_connection((self.local_host, self.local_port), timeout=1)
                    self.loc_lat = int((time.time() - start) * 1000)
                except Exception:
                    self.loc_lat = -1

            time.sleep(2)

    def stop(self):
        self._running = False