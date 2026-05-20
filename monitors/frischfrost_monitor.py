import os
from monitors.base_monitor import BaseMonitor


class FrischFrostMonitor(BaseMonitor):
    name = "FRISCH+FROST"
    login_url = "https://www.frisch-frost.de/account/login"
    success_path = ""   # any redirect away from /login = success
    log_file = "logs/frischfrost.log"

    def __init__(self) -> None:
        self.email = os.environ["FRISCHFROST_EMAIL"]
        self.password = os.environ["FRISCHFROST_PASSWORD"]
        super().__init__()
