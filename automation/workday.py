"""
Workday automation using Playwright.

Login flow:
  1. Navigate to the job URL, find and click Apply
  2. Try each login credential (email + password list) in priority order
  3. If all logins fail → try account creation with account_credential
  4. Auto-fill form fields from saved profile answers
  5. Leave browser open for user to review and submit
"""

import asyncio
from playwright.async_api import async_playwright, Page, Browser


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def _fill(page: Page, selector: str, value: str):
    try:
        el = page.locator(selector).first
        if await el.count() > 0:
            await el.fill(value)
    except Exception:
        pass


async def _click(page: Page, selector: str) -> bool:
    try:
        el = page.locator(selector).first
        if await el.count() > 0:
            await el.click()
            return True
    except Exception:
        pass
    return False


async def _page_contains(page: Page, *phrases: str) -> bool:
    try:
        text = (await page.content()).lower()
        return any(p.lower() in text for p in phrases)
    except Exception:
        return False


# ─── Main entry ───────────────────────────────────────────────────────────────

async def run_workday_automation(
    job_id: int,
    job_url: str,
    login_credentials: list[dict],    # [{"email": ..., "passwords": [...]}, ...]
    account_credential: dict | None,  # {"email": ..., "password": ...}
    profile: dict,
    notify_callback,
) -> dict:
    try:
        async with async_playwright() as p:
            browser: Browser = await p.chromium.launch(headless=False, slow_mo=80)
            context = await browser.new_context()
            page: Page = await context.new_page()

            await page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(2000)

            # ── Step 1: Click Apply ──────────────────────────────────────────
            apply_clicked = False
            for sel in [
                "button:has-text('Apply Now')", "a:has-text('Apply Now')",
                "button:has-text('Apply')", "a:has-text('Apply')",
                "[data-automation-id='applyButton']",
                "[aria-label*='Apply' i]",
            ]:
                if await _click(page, sel):
                    apply_clicked = True
                    break

            if not apply_clicked:
                await notify_callback(
                    "Apply Button Not Found",
                    f"Could not find an Apply button on the job page. Please apply manually.",
                    "warning",
                )
                await asyncio.sleep(300)
                return {"status": "error", "message": "Apply button not found"}

            await page.wait_for_timeout(3000)

            # ── Step 2: Try login credentials in order ───────────────────────
            logged_in = False
            for cred in login_credentials:
                email = cred["email"]
                passwords = cred["passwords"]

                result = await _try_login(page, email, passwords, notify_callback)
                if result == "success":
                    logged_in = True
                    break
                elif result == "no_account":
                    await notify_callback(
                        "No Account Found",
                        f"No Workday account exists for {email}. Trying next credential.",
                        "info",
                    )
                    # Navigate back to try next credential
                    await page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
                    await page.wait_for_timeout(2000)
                    for sel in ["button:has-text('Apply Now')", "button:has-text('Apply')", "[data-automation-id='applyButton']"]:
                        if await _click(page, sel):
                            break
                    await page.wait_for_timeout(2500)
                elif result == "wrong_password":
                    await notify_callback(
                        "Wrong Password",
                        f"All passwords failed for {email}. Update them in Job Setup → Passwords.",
                        "warning",
                    )

            # ── Step 3: Account creation fallback ────────────────────────────
            if not logged_in:
                if account_credential:
                    ac_result = await _create_account(
                        page, account_credential["email"],
                        account_credential["password"], profile, notify_callback
                    )
                    logged_in = ac_result == "success"
                else:
                    await notify_callback(
                        "Login Failed",
                        "All login attempts failed and no account creation credentials are saved. "
                        "Add Account Setup credentials in Job Setup → Passwords.",
                        "error",
                    )
                    await asyncio.sleep(300)
                    return {"status": "error", "message": "Login failed"}

            # ── Step 4: Fill form ────────────────────────────────────────────
            if logged_in:
                await page.wait_for_timeout(2000)
                await _fill_application_form(page, profile)
                await notify_callback(
                    "Application Ready",
                    "Form pre-filled! Review everything in the browser window and click Submit.",
                    "success",
                )
                await asyncio.sleep(600)  # Keep browser open 10 min

            return {"status": "opened_for_review"}

    except Exception as exc:
        await notify_callback("Automation Error", str(exc), "error")
        return {"status": "error", "message": str(exc)}


# ─── Login attempt ────────────────────────────────────────────────────────────

async def _try_login(page: Page, email: str, passwords: list[str], notify_callback) -> str:
    """Returns: 'success' | 'wrong_password' | 'no_account'"""

    # Enter email
    await _fill(page, "input[type='email']", email)
    await _fill(page, "[data-automation-id='email']", email)
    await _fill(page, "input[placeholder*='email' i]", email)

    for sel in ["button:has-text('Next')", "button:has-text('Continue')", "button[type='submit']"]:
        if await _click(page, sel):
            break
    await page.wait_for_timeout(2000)

    # Check if "Create Account" appeared → no account for this email
    if await _page_contains(page, "create account", "sign up", "register", "create an account"):
        return "no_account"

    # Try each password
    for pw in passwords:
        await _fill(page, "input[type='password']", pw)
        await _fill(page, "[data-automation-id='password']", pw)

        for sel in ["button:has-text('Sign In')", "button:has-text('Log In')", "button:has-text('Sign in')", "button[type='submit']"]:
            if await _click(page, sel):
                break
        await page.wait_for_timeout(2500)

        # Check for error
        if await _page_contains(page, "incorrect password", "invalid password", "wrong password",
                                "incorrect credentials", "sign in failed", "authentication failed"):
            continue  # Try next password

        # Check for success indicators
        if await _page_contains(page, "my applications", "dashboard", "welcome", "profile",
                                "my account", "submit", "review"):
            await notify_callback("Logged In", f"Successfully logged in as {email}.", "success")
            return "success"

    return "wrong_password"


# ─── Account creation ─────────────────────────────────────────────────────────

async def _create_account(page: Page, email: str, password: str, profile: dict, notify_callback) -> str:
    for sel in ["button:has-text('Create Account')", "a:has-text('Create Account')",
                "button:has-text('Sign Up')", "a:has-text('Sign Up')"]:
        if await _click(page, sel):
            break
    await page.wait_for_timeout(1500)

    await _fill(page, "input[type='email']", email)
    await _fill(page, "input[placeholder*='First' i]", profile.get("first_name", ""))
    await _fill(page, "input[placeholder*='Last' i]", profile.get("last_name", ""))
    await _fill(page, "input[type='password']", password)
    await _fill(page, "input[placeholder*='Confirm' i]", password)
    await _fill(page, "input[placeholder*='confirm' i]", password)

    for sel in ["button:has-text('Create')", "button:has-text('Submit')", "button[type='submit']"]:
        if await _click(page, sel):
            break
    await page.wait_for_timeout(2500)

    await notify_callback(
        "New Account Created",
        f"Workday account created for {email}. Continuing application.",
        "success",
    )
    return "success"


# ─── Form filling ─────────────────────────────────────────────────────────────

async def _fill_application_form(page: Page, profile: dict):
    mapping = {
        "[data-automation-id='legalNameSection_firstName']": profile.get("first_name", ""),
        "[data-automation-id='legalNameSection_lastName']": profile.get("last_name", ""),
        "[data-automation-id='phone-number']": profile.get("phone", ""),
        "[data-automation-id='addressSection_addressLine1']": profile.get("address_line1", ""),
        "[data-automation-id='addressSection_city']": profile.get("city", ""),
        "[data-automation-id='addressSection_postalCode']": profile.get("zip_code", ""),
        "input[placeholder*='LinkedIn' i]": profile.get("linkedin_url", ""),
        "input[placeholder*='GitHub' i]": profile.get("github_url", ""),
        "input[placeholder*='Website' i]": profile.get("website_url", ""),
        "input[placeholder*='GPA' i]": profile.get("gpa", ""),
        "input[placeholder*='University' i]": profile.get("school", ""),
        "input[placeholder*='School' i]": profile.get("school", ""),
    }
    for sel, val in mapping.items():
        if val:
            await _fill(page, sel, val)
            await page.wait_for_timeout(150)
