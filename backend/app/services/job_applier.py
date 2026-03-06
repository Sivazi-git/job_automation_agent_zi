"""
Playwright-based job application automation.
Supports Greenhouse, Lever, Workday, and generic HTML forms.
"""
from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from typing import Literal

# Playwright is an optional dependency — import lazily so the rest of the app
# still loads on machines that haven't installed it yet.
try:
    from playwright.async_api import async_playwright, Page, Browser
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


Platform = Literal["greenhouse", "lever", "workday", "generic"]

GREENHOUSE_DOMAIN = "boards.greenhouse.io"
LEVER_DOMAIN = "jobs.lever.co"
WORKDAY_DOMAIN = "myworkdayjobs.com"


@dataclass
class ApplyResult:
    status: Literal["applied", "needs_screening", "failed"]
    screening_questions: list[str] = field(default_factory=list)
    error: str | None = None


# ── Platform detection ────────────────────────────────────────────────────────

def _detect_platform(url: str) -> Platform:
    if GREENHOUSE_DOMAIN in url:
        return "greenhouse"
    if LEVER_DOMAIN in url:
        return "lever"
    if WORKDAY_DOMAIN in url:
        return "workday"
    return "generic"


# ── Field helpers ─────────────────────────────────────────────────────────────

async def _fill_field_by_label(page: Page, label_text: str, value: str) -> bool:
    """Try to find an input associated with a label containing label_text and fill it."""
    try:
        locator = page.get_by_label(label_text, exact=False)
        if await locator.count() > 0:
            await locator.first.fill(value)
            return True
    except Exception:
        pass
    return False


async def _upload_file(page: Page, selector: str, file_path: str) -> bool:
    try:
        file_input = page.locator(selector)
        if await file_input.count() > 0:
            await file_input.set_input_files(file_path)
            return True
    except Exception:
        pass
    return False


async def _extract_screening_questions(page: Page) -> list[str]:
    """
    Extract unanswered or free-text question texts from the current page.
    Looks for textarea / text inputs not already filled that appear to be
    screening questions (heuristic: adjacent label text).
    """
    questions: list[str] = []
    try:
        # Collect all label texts that are associated with textarea elements
        labels = await page.evaluate("""
            () => {
                const results = [];
                const textareas = document.querySelectorAll('textarea');
                textareas.forEach(ta => {
                    let label = '';
                    if (ta.id) {
                        const lbl = document.querySelector(`label[for="${ta.id}"]`);
                        if (lbl) label = lbl.innerText.trim();
                    }
                    if (!label) {
                        const parent = ta.closest('div, section, fieldset');
                        if (parent) {
                            const lbl = parent.querySelector('label, legend, p');
                            if (lbl) label = lbl.innerText.trim();
                        }
                    }
                    if (label && !ta.value) results.push(label);
                });
                return results;
            }
        """)
        questions = [q for q in labels if len(q) > 5]
    except Exception:
        pass
    return questions


# ── Platform-specific handlers ────────────────────────────────────────────────

async def _apply_greenhouse(page: Page, resume_path: str, user: dict) -> ApplyResult:
    try:
        await page.wait_for_load_state("networkidle", timeout=15000)

        # Basic personal info fields
        await _fill_field_by_label(page, "First name", user.get("first_name", ""))
        await _fill_field_by_label(page, "Last name", user.get("last_name", ""))
        await _fill_field_by_label(page, "Email", user.get("email", ""))
        await _fill_field_by_label(page, "Phone", user.get("phone", ""))

        # Resume upload — Greenhouse uses input[type=file]
        await _upload_file(page, "input[type='file']", resume_path)

        # Optional LinkedIn / portfolio
        if user.get("linkedin_url"):
            await _fill_field_by_label(page, "LinkedIn", user["linkedin_url"])
        if user.get("github_url"):
            await _fill_field_by_label(page, "GitHub", user["github_url"])
        if user.get("portfolio_url"):
            await _fill_field_by_label(page, "Website", user["portfolio_url"])

        # Check for screening questions before submitting
        questions = await _extract_screening_questions(page)
        if questions:
            return ApplyResult(status="needs_screening", screening_questions=questions)

        # Submit
        submit_btn = page.locator("input[type='submit'], button[type='submit']").first
        await submit_btn.click()
        await page.wait_for_load_state("networkidle", timeout=15000)

        return ApplyResult(status="applied")
    except Exception as e:
        return ApplyResult(status="failed", error=str(e))


async def _apply_lever(page: Page, resume_path: str, user: dict) -> ApplyResult:
    try:
        await page.wait_for_load_state("networkidle", timeout=15000)

        await _fill_field_by_label(page, "Full name", user.get("full_name", ""))
        await _fill_field_by_label(page, "Email", user.get("email", ""))
        await _fill_field_by_label(page, "Phone", user.get("phone", ""))

        await _upload_file(page, "input[type='file']", resume_path)

        if user.get("linkedin_url"):
            await _fill_field_by_label(page, "LinkedIn", user["linkedin_url"])

        questions = await _extract_screening_questions(page)
        if questions:
            return ApplyResult(status="needs_screening", screening_questions=questions)

        submit_btn = page.locator("button[type='submit'], input[type='submit']").first
        await submit_btn.click()
        await page.wait_for_load_state("networkidle", timeout=15000)

        return ApplyResult(status="applied")
    except Exception as e:
        return ApplyResult(status="failed", error=str(e))


async def _apply_workday(page: Page, resume_path: str, user: dict) -> ApplyResult:
    """
    Workday uses a multi-page wizard. We handle the first two pages:
    personal info and resume upload.
    """
    try:
        await page.wait_for_load_state("networkidle", timeout=20000)

        # Page 1 — personal info
        await _fill_field_by_label(page, "First Name", user.get("first_name", ""))
        await _fill_field_by_label(page, "Last Name", user.get("last_name", ""))
        await _fill_field_by_label(page, "Email", user.get("email", ""))
        await _fill_field_by_label(page, "Phone Number", user.get("phone", ""))

        # Try "Next" button to advance wizard
        next_btn = page.locator("button:has-text('Next'), button:has-text('Continue')").first
        if await next_btn.count() > 0:
            await next_btn.click()
            await page.wait_for_load_state("networkidle", timeout=15000)

        # Page 2 — resume upload
        await _upload_file(page, "input[type='file']", resume_path)

        questions = await _extract_screening_questions(page)
        if questions:
            return ApplyResult(status="needs_screening", screening_questions=questions)

        submit_btn = page.locator("button[type='submit'], button:has-text('Submit')").first
        await submit_btn.click()
        await page.wait_for_load_state("networkidle", timeout=15000)

        return ApplyResult(status="applied")
    except Exception as e:
        return ApplyResult(status="failed", error=str(e))


async def _apply_generic(page: Page, resume_path: str, user: dict) -> ApplyResult:
    """
    Heuristic approach for unknown job boards.
    Tries common field name/id/label patterns.
    """
    try:
        await page.wait_for_load_state("networkidle", timeout=15000)

        # Try common name-attr patterns
        name_map = {
            "input[name*='first'], input[id*='first']": user.get("first_name", ""),
            "input[name*='last'], input[id*='last']":   user.get("last_name", ""),
            "input[name*='email'], input[id*='email']": user.get("email", ""),
            "input[name*='phone'], input[id*='phone']": user.get("phone", ""),
        }
        for selector, value in name_map.items():
            if value:
                el = page.locator(selector).first
                if await el.count() > 0:
                    await el.fill(value)

        # Resume upload
        await _upload_file(page, "input[type='file']", resume_path)

        questions = await _extract_screening_questions(page)
        if questions:
            return ApplyResult(status="needs_screening", screening_questions=questions)

        submit_btn = page.locator("button[type='submit'], input[type='submit']").first
        if await submit_btn.count() > 0:
            await submit_btn.click()
            await page.wait_for_load_state("networkidle", timeout=15000)

        return ApplyResult(status="applied")
    except Exception as e:
        return ApplyResult(status="failed", error=str(e))


# ── Public entry point ────────────────────────────────────────────────────────

async def apply_to_job(
    job_url: str,
    resume_pdf_path: str,
    user_data: dict,
) -> ApplyResult:
    """
    Open job_url in a headless browser, fill the application form, and submit.

    user_data keys:
        full_name, first_name, last_name, email, phone,
        linkedin_url, github_url, portfolio_url
    """
    if not PLAYWRIGHT_AVAILABLE:
        return ApplyResult(
            status="failed",
            error="Playwright is not installed. Run: uv add playwright && playwright install chromium",
        )

    if not os.path.exists(resume_pdf_path):
        return ApplyResult(status="failed", error=f"Resume PDF not found: {resume_pdf_path}")

    platform = _detect_platform(job_url)

    # Ensure first/last name are split
    if not user_data.get("first_name") and user_data.get("full_name"):
        parts = user_data["full_name"].split(" ", 1)
        user_data["first_name"] = parts[0]
        user_data["last_name"] = parts[1] if len(parts) > 1 else ""

    async with async_playwright() as pw:
        browser: Browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            accept_downloads=True,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()

        try:
            await page.goto(job_url, wait_until="domcontentloaded", timeout=30000)

            if platform == "greenhouse":
                result = await _apply_greenhouse(page, resume_pdf_path, user_data)
            elif platform == "lever":
                result = await _apply_lever(page, resume_pdf_path, user_data)
            elif platform == "workday":
                result = await _apply_workday(page, resume_pdf_path, user_data)
            else:
                result = await _apply_generic(page, resume_pdf_path, user_data)

        except Exception as e:
            result = ApplyResult(status="failed", error=str(e))
        finally:
            await browser.close()

    return result
