#!/usr/bin/env python3
import os
import sys
import logging
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

LOGIN_URL = "https://www.vierlande-food.de/account/login"
ACCOUNT_URL = "https://www.vierlande-food.de/account"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xhtml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
}

TIMEOUT = 30

logging.basicConfig(
    filename="shop_monitor.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
log = logging.getLogger(__name__)
# Mirror output to stdout so GitHub Actions captures it live.
log.addHandler(logging.StreamHandler(sys.stdout))


def get_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise EnvironmentError(f"Required environment variable '{name}' is not set.")
    return value


def extract_form_fields(html: str) -> dict:
    """Return all hidden/known form fields from the login form."""
    soup = BeautifulSoup(html, "html.parser")
    form = soup.find("form", {"action": lambda v: v and "login" in v})
    if form is None:
        # Fall back: first form on the page
        form = soup.find("form")
    if form is None:
        raise ValueError("No login form found on login page.")

    fields = {}
    for inp in form.find_all("input"):
        name = inp.get("name")
        value = inp.get("value", "")
        if name:
            fields[name] = value
    return fields


def login(email: str, password: str) -> tuple[bool, int, str]:
    """
    Attempt login and return (success, http_status_code, message).
    Uses a Session so cookies are carried across redirects automatically.
    """
    session = requests.Session()
    session.headers.update(HEADERS)

    # ── Step 1: GET the login page and collect form fields ──────────────────
    try:
        get_resp = session.get(LOGIN_URL, timeout=TIMEOUT)
    except requests.exceptions.Timeout:
        return False, 0, "Timeout while loading login page."
    except requests.exceptions.ConnectionError as exc:
        return False, 0, f"Network error while loading login page: {exc}"

    if get_resp.status_code != 200:
        return (
            False,
            get_resp.status_code,
            f"Unexpected status {get_resp.status_code} on GET {LOGIN_URL}",
        )

    try:
        form_fields = extract_form_fields(get_resp.text)
    except ValueError as exc:
        return False, get_resp.status_code, str(exc)

    # Inject credentials into the form payload.
    form_fields["customer[email]"] = email
    form_fields["customer[password]"] = password

    # ── Step 2: POST credentials ─────────────────────────────────────────────
    try:
        post_resp = session.post(
            LOGIN_URL,
            data=form_fields,
            timeout=TIMEOUT,
            allow_redirects=True,
        )
    except requests.exceptions.Timeout:
        return False, 0, "Timeout while submitting login form."
    except requests.exceptions.ConnectionError as exc:
        return False, 0, f"Network error while submitting login form: {exc}"

    # ── Step 3: Evaluate result ───────────────────────────────────────────────
    final_url = post_resp.url

    # Shopify redirects to /account on success; failed logins stay on /login.
    if "login" in final_url:
        soup = BeautifulSoup(post_resp.text, "html.parser")
        error_el = soup.find(class_=lambda c: c and "error" in c.lower())
        error_msg = error_el.get_text(strip=True) if error_el else "Login page still shown after POST."
        return False, post_resp.status_code, error_msg

    # Optional extra check: confirm the account page is reachable with our session.
    try:
        acct_resp = session.get(ACCOUNT_URL, timeout=TIMEOUT)
        if acct_resp.status_code == 200 and "login" not in acct_resp.url:
            return True, acct_resp.status_code, "Login successful – account page accessible."
        return False, acct_resp.status_code, "Redirected away from account page after login."
    except requests.exceptions.RequestException as exc:
        # POST succeeded but account check failed; treat as partial success.
        return True, post_resp.status_code, f"Login POST ok, account check failed: {exc}"


def main() -> int:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        email = get_env("SHOP_EMAIL")
        password = get_env("SHOP_PASSWORD")
    except EnvironmentError as exc:
        log.error("CONFIG ERROR | %s", exc)
        return 1

    log.info("Starting login check for %s at %s", LOGIN_URL, timestamp)

    success, http_code, message = login(email, password)

    status_label = "SUCCESS" if success else "FAILURE"
    log.info(
        "timestamp=%s status=%s http_code=%s message=%s",
        timestamp,
        status_label,
        http_code,
        message,
    )

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
