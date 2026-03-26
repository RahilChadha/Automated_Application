"""
Workday automation using Playwright.

Flow:
1. Navigate to the job's Workday URL
2. Click "Apply" / "Apply with Workday"
3. Check if user has an account → try login with stored password
   - Wrong password → create notification, abort
   - No account → auto-create one with profile answers
4. Fill application form from saved ApplicationAnswer records
5. Leave browser open for user to review and submit
"""

import asyncio
import re
from typing import Optional

from playwright.async_api import async_playwright, Page, Browser, BrowserContext


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _extract_domain(url: str) -> str:
    match = re.search(r"https?://([^/]+)", url)
    return match.group(1) if match else url


async def _fill_if_present(page: Page, selector: str, value: str):
    try:
        el = page.locator(selector).first
        if await el.count() > 0:
            await el.fill(value)
    except Exception:
        pass


# ─── Main entry point ─────────────────────────────────────────────────────────

async def run_workday_automation(
    job_id: int,
    workday_url: str,
    email: str,
    password: str,
    profile: dict,
    notify_callback,          # async callable(title, message, type)
) -> dict:
    """
    Returns {"status": "opened_for_review" | "wrong_password" | "error", "message": str}
    """
    try:
        async with async_playwright() as p:
            browser: Browser = await p.chromium.launch(headless=False, slow_mo=100)
            context: BrowserContext = await browser.new_context()
            page: Page = await context.new_page()

            await page.goto(workday_url, wait_until="domcontentloaded", timeout=30000)

            # ── Step 1: Find and click Apply button ──────────────────────────
            apply_clicked = False
            for selector in [
                "button:has-text('Apply')",
                "a:has-text('Apply')",
                "[data-automation-id='applyButton']",
                "button:has-text('Apply Now')",
                "a:has-text('Apply Now')",
            ]:
                try:
                    btn = page.locator(selector).first
                    if await btn.count() > 0:
                        await btn.click()
                        apply_clicked = True
                        break
                except Exception:
                    continue

            if not apply_clicked:
                await notify_callback(
                    "Apply Button Not Found",
                    f"Could not find an Apply button on {workday_url}. Please apply manually.",
                    "warning",
                )
                return {"status": "error", "message": "Apply button not found"}

            await page.wait_for_timeout(2000)

            # ── Step 2: Detect Sign In vs Create Account ──────────────────────
            page_text = (await page.content()).lower()

            if "sign in" in page_text or "email" in page_text:
                result = await _attempt_login(page, email, password, profile, notify_callback)
            else:
                result = {"status": "opened_for_review", "message": "Browser opened. Please review and submit."}

            if result["status"] == "logged_in":
                await _fill_application_form(page, profile)
                await notify_callback(
                    "Application Ready",
                    f"Form pre-filled. Please review and submit in the browser window.",
                    "success",
                )
                # Keep browser open — user submits manually
                await asyncio.sleep(600)  # 10 min window
                return {"status": "opened_for_review", "message": "Browser opened for review."}

            return result

    except Exception as exc:
        await notify_callback("Automation Error", str(exc), "error")
        return {"status": "error", "message": str(exc)}


# ─── Login flow ───────────────────────────────────────────────────────────────

async def _attempt_login(
    page: Page,
    email: str,
    password: str,
    profile: dict,
    notify_callback,
) -> dict:
    # Fill email
    await _fill_if_present(page, "input[type='email']", email)
    await _fill_if_present(page, "input[placeholder*='Email' i]", email)
    await _fill_if_present(page, "[data-automation-id='email']", email)

    # Click Next / Continue if present
    for sel in ["button:has-text('Next')", "button:has-text('Continue')", "button[type='submit']"]:
        try:
            btn = page.locator(sel).first
            if await btn.count() > 0:
                await btn.click()
                await page.wait_for_timeout(1500)
                break
        except Exception:
            pass

    # Check if "Create Account" appeared (no account exists)
    content = (await page.content()).lower()
    if "create account" in content or "create an account" in content or "sign up" in content:
        await notify_callback(
            "New Workday Account Created",
            f"No account found for {email}. Creating a new Workday account automatically.",
            "info",
        )
        return await _create_account(page, email, password, profile, notify_callback)

    # Fill password
    await _fill_if_present(page, "input[type='password']", password)
    await _fill_if_present(page, "[data-automation-id='password']", password)

    for sel in ["button:has-text('Sign In')", "button:has-text('Log In')", "button[type='submit']"]:
        try:
            btn = page.locator(sel).first
            if await btn.count() > 0:
                await btn.click()
                await page.wait_for_timeout(2500)
                break
        except Exception:
            pass

    # Check for wrong password error
    content = (await page.content()).lower()
    if "incorrect" in content or "invalid" in content or "wrong" in content or "error" in content:
        await notify_callback(
            "Wrong Workday Password",
            f"The password stored for this company appears to be incorrect. "
            f"Go to Job Setup → Passwords and update it.",
            "warning",
        )
        return {"status": "wrong_password", "message": "Wrong password — please update in Job Setup → Passwords."}

    return {"status": "logged_in", "message": "Logged in successfully."}


# ─── Account creation flow ────────────────────────────────────────────────────

async def _create_account(
    page: Page,
    email: str,
    password: str,
    profile: dict,
    notify_callback,
) -> dict:
    # Click "Create Account" link/button
    for sel in ["button:has-text('Create Account')", "a:has-text('Create Account')", "button:has-text('Sign Up')"]:
        try:
            btn = page.locator(sel).first
            if await btn.count() > 0:
                await btn.click()
                await page.wait_for_timeout(1500)
                break
        except Exception:
            pass

    await _fill_if_present(page, "input[type='email']", email)
    await _fill_if_present(page, "input[placeholder*='First' i]", profile.get("first_name", ""))
    await _fill_if_present(page, "input[placeholder*='Last' i]", profile.get("last_name", ""))
    await _fill_if_present(page, "input[type='password']", password)
    await _fill_if_present(page, "input[placeholder*='Confirm' i]", password)

    for sel in ["button:has-text('Create')", "button:has-text('Submit')", "button[type='submit']"]:
        try:
            btn = page.locator(sel).first
            if await btn.count() > 0:
                await btn.click()
                await page.wait_for_timeout(2000)
                break
        except Exception:
            pass

    await notify_callback(
        "Workday Account Created",
        f"New Workday account created for {email}. Continuing with application.",
        "success",
    )
    return {"status": "logged_in", "message": "Account created and logged in."}


# ─── Form filling ─────────────────────────────────────────────────────────────

async def _fill_application_form(page: Page, profile: dict):
    """Best-effort auto-fill of common Workday application fields."""
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
    }

    for selector, value in mapping.items():
        if value:
            await _fill_if_present(page, selector, value)
            await page.wait_for_timeout(200)
