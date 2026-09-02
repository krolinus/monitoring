import os
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


class BaseMonitor:
    name: str = ""
    login_url: str = ""
    success_path: str = ""      # URL path that signals successful login
    email_field: str = "username"
    password_field: str = "password"
    log_file: str = ""

    GITHUB_REPO = "krolinus/monitoring"
    GITHUB_API = "https://api.github.com"
    TIMEOUT = 30
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
    }

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        Path(self.log_file).parent.mkdir(parents=True, exist_ok=True)
        self._setup_logging()

    def _setup_logging(self) -> None:
        self.log = logging.getLogger(self.name)
        self.log.setLevel(logging.INFO)
        if self.log.handlers:
            return
        fmt = logging.Formatter(
            "%(asctime)s %(levelname)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%SZ",
        )
        for handler in (logging.FileHandler(self.log_file), logging.StreamHandler()):
            handler.setFormatter(fmt)
            self.log.addHandler(handler)

    # ── Public API ────────────────────────────────────────────────────────────

    def extract_csrf_token(self, html: str) -> str:
        """Return CSRF token value from the login form, or '' if not present."""
        soup = BeautifulSoup(html, "html.parser")
        for field_name in ("_csrf_token", "csrf_token", "authenticity_token", "_token"):
            inp = soup.find("input", {"name": field_name})
            if inp:
                return inp.get("value", "")
        return ""

    def check_login(self) -> tuple[bool, int, str]:
        """Perform GET → POST login flow. Returns (success, http_code, message)."""
        # GET login page
        try:
            get_resp = self.session.get(self.login_url, timeout=self.TIMEOUT)
        except requests.exceptions.Timeout:
            return False, 0, "Timeout beim Laden der Login-Seite."
        except requests.exceptions.ConnectionError as exc:
            return False, 0, f"Netzwerkfehler beim GET: {exc}"

        self.log.info("GET %s → %s", self.login_url, get_resp.status_code)

        if get_resp.status_code != 200:
            return False, get_resp.status_code, f"HTTP {get_resp.status_code} beim GET."

        try:
            form_data = self._extract_form_fields(get_resp.text)
        except ValueError as exc:
            return False, get_resp.status_code, str(exc)

        form_data[self.email_field] = self.email
        form_data[self.password_field] = self.password

        # POST credentials
        origin = f"{urlparse(self.login_url).scheme}://{urlparse(self.login_url).netloc}"
        try:
            post_resp = self.session.post(
                self.login_url,
                data=form_data,
                headers={
                    "Referer": self.login_url,
                    "Origin": origin,
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                timeout=self.TIMEOUT,
                allow_redirects=True,
            )
        except requests.exceptions.Timeout:
            return False, 0, "Timeout beim Absenden des Login-Formulars."
        except requests.exceptions.ConnectionError as exc:
            return False, 0, f"Netzwerkfehler beim POST: {exc}"

        final_url = post_resp.url
        self.log.info(
            "POST %s → %s (final: %s)", self.login_url, post_resp.status_code, final_url
        )

        if post_resp.status_code >= 400:
            return False, post_resp.status_code, f"HTTP {post_resp.status_code} beim POST."

        # Success: landed on expected URL
        if self.success_path and self.success_path in final_url:
            return True, post_resp.status_code, f"Login erfolgreich – {final_url}"

        # Failure: still on login page
        if "login" in final_url:
            return False, post_resp.status_code, "Login fehlgeschlagen – noch auf Login-Seite."

        # No success_path defined → any redirect away from login = success
        if not self.success_path:
            return True, post_resp.status_code, f"Login erfolgreich – {final_url}"

        return False, post_resp.status_code, f"Unerwarteter Redirect: {final_url}"

    def write_log(self, success: bool, http_code: int, message: str) -> None:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        status = "SUCCESS" if success else "FAILURE"
        self.log.info(
            "timestamp=%s status=%s http_code=%s message=%s",
            timestamp, status, http_code, message,
        )

    def create_github_issue(self, title: str, body: str) -> int | None:
        """Create issue, skip if an open issue with the same title already exists."""
        headers = self._github_headers()
        if headers is None:
            return None

        # Deduplication: if this monitor already has an open failure issue,
        # don't open another one. Otherwise every 15-minute run spawns a fresh
        # issue (and a fresh email). One open issue per outage is enough – it
        # gets closed automatically once the login works again.
        existing = self._find_open_failure_issues()
        if existing:
            self.log.info(
                "Offenes Fehler-Issue #%s existiert bereits – kein neues erstellt.",
                existing[0]["number"],
            )
            return existing[0]["number"]

        resp = requests.post(
            f"{self.GITHUB_API}/repos/{self.GITHUB_REPO}/issues",
            headers=headers,
            json={"title": title, "body": body, "labels": ["shop-monitor", "bug"]},
            timeout=15,
        )
        if resp.ok:
            number = resp.json()["number"]
            self.log.info("Issue #%s erstellt.", number)
            return number

        self.log.error("Issue-Erstellung fehlgeschlagen: %s %s", resp.status_code, resp.text)
        return None

    def close_github_issue(self, issue_number: int) -> None:
        """Add resolution comment and close the issue."""
        headers = self._github_headers()
        if headers is None:
            return
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        requests.post(
            f"{self.GITHUB_API}/repos/{self.GITHUB_REPO}/issues/{issue_number}/comments",
            headers=headers,
            json={"body": f"✅ System wieder online – {timestamp}"},
            timeout=15,
        )
        resp = requests.patch(
            f"{self.GITHUB_API}/repos/{self.GITHUB_REPO}/issues/{issue_number}",
            headers=headers,
            json={"state": "closed"},
            timeout=15,
        )
        if resp.ok:
            self.log.info("Issue #%s geschlossen.", issue_number)
        else:
            self.log.error("Issue #%s konnte nicht geschlossen werden: %s", issue_number, resp.status_code)

    def run(self) -> int:
        """Main entry point. Returns 0 on success, 1 on failure."""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.log.info("=== %s Monitor startet ===", self.name)

        success, http_code, message = self.check_login()
        self.write_log(success, http_code, message)

        self.last_result = {
            "name": self.name,
            "success": success,
            "http_code": http_code,
            "message": message,
            "timestamp": timestamp,
        }

        if not success:
            # Stable title (no timestamp) so the deduplication above can match
            # an already-open issue for this monitor. The time is in the body.
            title = f"🔴 [{self.name}] Login fehlgeschlagen"
            body = (
                f"## {self.name} – Login-Fehler\n\n"
                f"**Zuerst erkannt:** {timestamp}  \n"
                f"**URL:** {self.login_url}  \n"
                f"**HTTP-Code:** {http_code}  \n"
                f"**Meldung:** {message}\n"
            )
            self.create_github_issue(title, body)
            return 1

        # Success: close any open failure issues for this monitor
        for issue in self._find_open_failure_issues():
            self.close_github_issue(issue["number"])

        return 0

    # ── Private helpers ───────────────────────────────────────────────────────

    def _extract_form_fields(self, html: str) -> dict:
        soup = BeautifulSoup(html, "html.parser")
        form = soup.find("form", {"action": lambda v: v and "login" in v})
        if form is None:
            form = soup.find("form")
        if form is None:
            raise ValueError("Kein Login-Formular auf der Seite gefunden.")

        fields = {}
        for inp in form.find_all("input"):
            name = inp.get("name")
            if name:
                fields[name] = inp.get("value", "")

        self.log.info("Formularfelder: %s", list(fields.keys()))
        return fields

    def _github_headers(self) -> dict | None:
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            self.log.warning("GITHUB_TOKEN nicht gesetzt – GitHub-API übersprungen.")
            return None
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _find_open_failure_issues(self) -> list:
        headers = self._github_headers()
        if headers is None:
            return []
        resp = requests.get(
            f"{self.GITHUB_API}/repos/{self.GITHUB_REPO}/issues",
            headers=headers,
            params={"state": "open", "labels": "shop-monitor"},
            timeout=15,
        )
        if not resp.ok:
            return []
        prefix = f"🔴 [{self.name}]"
        return [i for i in resp.json() if i["title"].startswith(prefix)]
