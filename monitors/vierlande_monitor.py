import os
from monitors.base_monitor import BaseMonitor


class VierlandeMonitor(BaseMonitor):
    name = "CHA"
    login_url = "https://www.vierlande-food.de/account/login"
    success_path = "/b2bsalesrepresentative"
    log_file = "logs/vierlande.log"

    def __init__(self) -> None:
        self.email = os.environ["VIERLANDE_EMAIL"]
        self.password = os.environ["VIERLANDE_PASSWORD"]
        super().__init__()
