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
    "Accept": "text/html,application/xhtml+xml,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
}

TIMEOUT = 30

logging.basicConfig(
    filename="shop_monitor.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
log = logging.getLogger(__name__)
log.addHandler(logging.StreamHandler(sys.stdout))


def get_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise EnvironmentError(f"Required environment variable '{name}' is not set.")
    return value


def extract_form_fields(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    # Try to find the customer login form specifically
    form = soup.find("form", {"action": lambda v: v and "login" in v})
    if form is None:
        form = soup.find("form", {"id": lambda v: v and "login" in v.lower()})
    if form is None:
        form = soup.find("form")
    if form is None:
        raise ValueError("No login form found on login page.")

    fields = {}
    for inp in form.find_all("input"):
        name = inp.get("name")
        value = inp.get("value", "")
        if name:
            fields[name] = value

    log.info("Form fields found: %s", list(fields.keys()))
    return fields


def extract_shopify_error(html: str) -> str:
    """Try several Shopify theme patterns to extract the login error message."""
    soup = BeautifulSoup(html, "html.parser")

    # Common Shopify error selectors across themes
    selectors = [
        {"class_": lambda c: c and "errors" in c},
        {"class_": lambda c: c and "error" in c.lower()},
        {"class_": lambda c: c and "alert" in c.lower()},
        {"class_": lambda c: c and "notice" in c.lower()},
        {"id": lambda v: v and "error" in v.lower()},
    ]
    for sel in selectors:
        el = soup.find(attrs=sel)
        if el:
            text = el.get_text(" ", strip=True)
            if text:
                return text

    return "Login page still shown after POST (no error element found)."


def login(email: str, password: str) -> tuple[bool, int, str]:
    session = requests.Session()
    session.headers.update(HEADERS)

    # ── Step 1: GET login page ────────────────────────────────────────────────
    try:
        get_resp = session.get(LOGIN_URL, timeout=TIMEOUT)
    except requests.exceptions.Timeout:
        return False, 0, "Timeout while loading login page."
    except requests.exceptions.ConnectionError as exc:
        return False, 0, f"Network error while loading login page: {exc}"

    log.info("GET %s → %s (final URL: %s)", LOGIN_URL, get_resp.status_code, get_resp.url)

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

    form_fields["customer[email]"] = email
    form_fields["customer[password]"] = password

    # ── Step 2: POST credentials ──────────────────────────────────────────────
    post_headers = {
        "Referer": LOGIN_URL,
        "Origin": "https://www.vierlande-food.de",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    try:
        post_resp = session.post(
            LOGIN_URL,
            data=form_fields,
            headers=post_headers,
            timeout=TIMEOUT,
            allow_redirects=True,
        )
    except requests.exceptions.Timeout:
        return False, 0, "Timeout while submitting login form."
    except requests.exceptions.ConnectionError as exc:
        return False, 0, f"Network error while submitting login form: {exc}"

    final_url = post_resp.url
    log.info("POST %s → %s (final URL: %s)", LOGIN_URL, post_resp.status_code, final_url)

    # ── Step 3: Evaluate result ───────────────────────────────────────────────
    # Shopify redirects to /account on success; stays on /login on failure.
    if "login" in final_url:
        error_msg = extract_shopify_error(post_resp.text)
        return False, post_resp.status_code, f"Still on login page. Shopify message: {error_msg}"

    # Confirm the account page is reachable with the session cookie.
    try:
        acct_resp = session.get(ACCOUNT_URL, timeout=TIMEOUT)
        log.info("GET %s → %s (final URL: %s)", ACCOUNT_URL, acct_resp.status_code, acct_resp.url)
        if acct_resp.status_code == 200 and "login" not in acct_resp.url:
            return True, acct_resp.status_code, "Login successful – account page accessible."
        return False, acct_resp.status_code, f"Unexpected redirect after login: {acct_resp.url}"
    except requests.exceptions.RequestException as exc:
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
