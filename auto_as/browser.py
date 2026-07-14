"""Minimal, evidence-first Playwright runner."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path


DESTRUCTIVE_WORDS = ("delete", "remove", "pay", "purchase", "결제", "삭제", "탈퇴", "제거")
CLICK_WORDS = ("click", "클릭", "누르", "선택")
INPUT_WORDS = ("type", "enter", "fill", "입력", "작성")


def split_scenario(scenario: str) -> list[str]:
    return [step.strip(" .") for step in re.split(r"[\n.!?]+(?=\s|$)|\s*(?:그리고|하고|한 다음|한 뒤|후에)\s*", scenario) if step.strip(" .")]


def is_destructive(step: str) -> bool:
    lowered = step.lower()
    return any(word in lowered for word in DESTRUCTIVE_WORDS)


def _quoted_text(step: str) -> str | None:
    match = re.search(r"['\"“”‘’]([^'\"“”‘’]+)['\"“”‘’]", step)
    return match.group(1).strip() if match else None


def _click_target(step: str) -> str:
    quoted = _quoted_text(step)
    if quoted:
        return quoted
    return re.sub(r"(?i)click|클릭|누르기|눌러|누르고|선택", "", step).strip(" .")


def _input_value(step: str) -> str | None:
    quoted = _quoted_text(step)
    if quoted:
        return quoted
    email = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", step)
    if email:
        return email.group(0)
    return None


async def run_demo(url: str, scenario: str, artifact_dir: Path, test_files: list[str] | None = None) -> dict:
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        return {"available": False, "error": f"Playwright is not installed: {exc}"}

    artifact_dir.mkdir(parents=True, exist_ok=True)
    console_errors: list[str] = []
    steps: list[dict] = []
    from .planner import plan_scenario

    plan, planner = plan_scenario(scenario)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page()
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            for index, action in enumerate(plan, 1):
                step = action.get("text", action.get("target", ""))
                record = {"step": index, "text": step, "action": action.get("action"), "status": "observed"}
                if action.get("action") == "skip":
                    record["status"] = "skipped_destructive"
                elif action.get("action") == "upload":
                    files = test_files or []
                    if not files or not all(Path(path).is_file() for path in files):
                        record.update(status="failed", error="test file is missing")
                    else:
                        try:
                            await page.locator("input[type=file]").set_input_files(files[0], timeout=5_000)
                            record["status"] = "success"
                        except Exception as exc:
                            record.update(status="failed", error=str(exc)[:300])
                elif action.get("action") == "click":
                    target = action.get("target", "")
                    try:
                        await page.get_by_text(target, exact=False).first.click(timeout=5_000)
                        record["status"] = "success"
                    except Exception as exc:
                        record.update(status="failed", error=str(exc)[:300])
                elif action.get("action") == "fill":
                    value = action.get("value", "")
                    if not value:
                        record.update(status="failed", error="could not infer input value")
                    else:
                        try:
                            target = action.get("target", "")
                            locator = page.get_by_label(target, exact=False).first if target else page.locator("input, textarea").first
                            await locator.fill(value, timeout=5_000)
                            record["status"] = "success"
                        except Exception as exc:
                            record.update(status="failed", error=str(exc)[:300])
                screenshot = artifact_dir / f"step-{index}.png"
                await page.screenshot(path=str(screenshot), full_page=True)
                record["screenshot"] = str(screenshot)
                steps.append(record)
        except Exception as exc:
            steps.append({"step": 0, "text": "page load", "status": "failed", "error": str(exc)[:300]})
        finally:
            await browser.close()
    return {"available": True, "planner": planner, "steps": steps, "console_errors": console_errors}


def run_demo_sync(url: str, scenario: str, artifact_dir: Path, test_files: list[str] | None = None) -> dict:
    return asyncio.run(run_demo(url, scenario, artifact_dir, test_files))
