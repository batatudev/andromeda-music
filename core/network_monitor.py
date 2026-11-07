# core/network_monitor.py
import os
os.environ["QT_API"] = "pyside6"

import threading
import time
import socket
from urllib.parse import urlparse

class NetworkMonitor(threading.Thread):
    """
    Wątek monitorujący dostęp do Internetu (DNS 1.1.1.1) oraz lokalne RTT serwera Navidrome.
    Zarządza deskryptorami gniazd bez wycieków oraz zapewnia optymistyczny start dla biblioteki.
    """
    def __init__(self, local_url):
        super().__init__(daemon=True)
        self.local_host, self.local_port = self._extract_host_and_port(local_url)
        self.is_online = True
        self.is_internet_online = True
        self.is_server_alive = True
        self.net_ping = 0
        self.loc_lat = 0
        self._running = True

    def _extract_host_and_port(self, url):
        try:
            parsed = urlparse(url)
            host = parsed.hostname or "localhost"
            if parsed.port:
                port = parsed.port
            elif parsed.scheme == "https":
                port = 443
            elif parsed.scheme == "http":
                port = 80
            else:
                port = 4533
            return host, port
        except Exception:
            return "localhost", 4533

    def run(self):
        while self._running:
            # 1. Sprawdzanie globalnego dostępu do Internetu (Cloudflare DNS)
            start = time.time()
            try:
                s = socket.create_connection(("1.1.1.1", 53), timeout=2)
                s.close()
                self.net_ping = int((time.time() - start) * 1000)
                self.is_internet_online = True
                self.is_online = True
            except Exception:
                self.net_ping = -1
                self.is_internet_online = False
                self.is_online = False

            # 2. Sprawdzanie dostępności serwera Navidrome
            if self.local_host:
                start = time.time()
                try:
                    s_loc = socket.create_connection((self.local_host, self.local_port), timeout=1)
                    s_loc.close()
                    self.loc_lat = int((time.time() - start) * 1000)
                    self.is_server_alive = True
                except Exception:
                    self.loc_lat = -1
                    self.is_server_alive = False

            time.sleep(2)

    def stop(self):
        self._running = False