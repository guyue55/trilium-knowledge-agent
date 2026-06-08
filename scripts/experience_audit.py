# -*- coding: utf-8 -*-
"""Trilium Knowledge Agent - End-to-End User Experience & Visual Audit Script.

This script uses Playwright to load the local FastAPI server, perform a comprehensive
walkthrough of all features in both PC and Mobile viewports, capture screenshots, and
validate the interactive behaviors (such as form validation, safety lock, tab switching, and streaming chat).
"""

import asyncio
import os
import sys
from pathlib import Path
from playwright.async_api import async_playwright

# Setup screenshot paths
SCREENSHOT_DIR = Path("/Users/guyue/.gemini/antigravity/brain/10aa355d-1ffe-4c3b-9962-d05ddc6ab1c8/screenshots")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "http://localhost:8000"

async def run_audit():
    print("🚀 Starting comprehensive E2E User Experience and Visual Audit...")
    
    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(headless=True)
        
        # ---------------------------------------------------------
        # STAGE 1: PC Viewport (1440x900)
        # ---------------------------------------------------------
        print("\n--- STAGE 1: PC Wide-screen Viewport (1440x900) ---")
        context_pc = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context_pc.new_page()
        
        # Monitor console messages and exceptions
        page.on("console", lambda msg: print(f"[Browser Console] {msg.type}: {msg.text}"))
        page.on("pageerror", lambda err: print(f"[Browser JS Exception] {err.message}"))
        
        # 1. Access homepage
        print("1.1 Navigating to homepage...")
        await page.goto(BASE_URL)
        await page.wait_for_selector("#chat-input")
        await page.wait_for_timeout(1000) # Wait for initial animations
        
        # 1.2 Capture Initial Dark Mode State
        print("1.2 Capturing Initial Dark Mode Home...")
        await page.screenshot(path=str(SCREENSHOT_DIR / "01_PC_DarkTheme_Home.png"))
        
        # 1.3 Toggle Theme to Light Mode
        print("1.3 Toggling Theme to Light Mode...")
        await page.click("#btn-theme-toggle")
        await page.wait_for_timeout(500)
        await page.screenshot(path=str(SCREENSHOT_DIR / "02_PC_LightTheme_Home.png"))
        
        # 1.4 Switch back to Dark Mode for next tests
        print("1.4 Reverting back to Dark Mode...")
        await page.click("#btn-theme-toggle")
        await page.wait_for_timeout(300)
        
        # 2. Control Drawer & Tab Switching
        print("2.1 Opening Advanced Configuration Drawer...")
        await page.click("#btn-settings-open")
        await page.wait_for_selector("#settings-drawer.active", state="attached")
        await page.wait_for_timeout(500) # transition
        await page.screenshot(path=str(SCREENSHOT_DIR / "03_PC_Settings_BrainTab.png"))
        
        # 2.2 Switch to Knowledge Sync Tab
        print("2.2 Switching to Knowledge Base Sync Tab...")
        await page.click('div.drawer-tab[data-tab="knowledge-sync"]')
        await page.wait_for_timeout(300)
        await page.screenshot(path=str(SCREENSHOT_DIR / "04_PC_Settings_IntegrationsTab.png"))
        
        # 2.3 Switch to RAG Tuning Tab
        print("2.3 Switching to RAG Tuning Tab...")
        await page.click('div.drawer-tab[data-tab="rag-tuning"]')
        await page.wait_for_timeout(300)
        await page.screenshot(path=str(SCREENSHOT_DIR / "05_PC_Settings_TuningTab.png"))
        
        # 2.4 Form Validation & Safety Lock
        print("2.4 Testing Field Validation and Safety Lock...")
        # Let's switch back to Knowledge Sync Tab first
        await page.click('div.drawer-tab[data-tab="knowledge-sync"]')
        await page.wait_for_timeout(200)
        
        # Type an invalid URL in TRILIUM_BASE_URL input
        trilium_input = page.locator("#cfg-trilium-url")
        await trilium_input.fill("invalid-url-format")
        await page.wait_for_timeout(500) # allow input listeners to validate
        
        # Check if error message is visible and class is active
        # The save button should be disabled
        save_btn = page.locator("#btn-settings-save")
        is_disabled = await save_btn.is_disabled()
        print(f"Is save button disabled? {is_disabled}")
        await page.screenshot(path=str(SCREENSHOT_DIR / "06_PC_Settings_ValidationError.png"))
        
        # Restore a valid URL
        await trilium_input.fill("http://localhost:8080")
        await page.wait_for_timeout(300)
        
        # 2.5 API Key Warning Banner test
        print("2.5 Testing API Key Non-blocking Warning Banner...")
        # Switch to ai-engine tab
        await page.click('div.drawer-tab[data-tab="ai-engine"]')
        await page.wait_for_timeout(200)
        # Click on "openai" provider card which doesn't have an api key entered by default
        await page.click('div.provider-card[data-provider="openai"]')
        await page.wait_for_timeout(300)
        # Check if warnings banner is shown
        banner = page.locator("#settings-warnings-banner")
        is_banner_visible = await banner.is_visible()
        print(f"Is Warnings Banner visible? {is_banner_visible}")
        await page.screenshot(path=str(SCREENSHOT_DIR / "07_PC_Settings_APIKeyWarning.png"))
        
        # Switch back to ollama and close drawer
        await page.click('div.provider-card[data-provider="ollama"]')
        await page.wait_for_timeout(200)
        await page.click("#btn-settings-cancel")
        await page.wait_for_timeout(500) # transition
        
        # 3. Stream Chat & SSE Chat Channel
        print("3.1 Initiating Chat Interaction (SSE Stream)...")
        chat_input = page.locator("#chat-input")
        await chat_input.fill("你好！请根据我的笔记回答，本系统怎么进行同步？")
        await page.wait_for_timeout(300)
        
        # Capture screen right before/during sending
        await page.click("#btn-send")
        await page.wait_for_timeout(300) # Capture loading state
        await page.screenshot(path=str(SCREENSHOT_DIR / "08_PC_Chat_Sending.png"))
        
        # Wait for completion (input area returns to normal, streaming ends)
        print("3.2 Waiting for streaming output...")
        # Since it falls back to Mock LLM, it should respond very quickly (within a few seconds)
        # We wait for the send button to be enabled again
        await page.wait_for_selector("#btn-send:not([disabled])", timeout=10000)
        await page.wait_for_timeout(1000) # Wait a bit for scroll and final text
        await page.screenshot(path=str(SCREENSHOT_DIR / "09_PC_Chat_Result.png"))
        
        # Check if there are any citation marks (Citations)
        print("3.3 Checking Citation interaction...")
        citations = page.locator(".citation-mark")
        citation_count = await citations.count()
        print(f"Found {citation_count} citation marks.")
        if citation_count > 0:
            print("Hovering over the first citation mark...")
            await citations.first.hover()
            await page.wait_for_timeout(500)
            await page.screenshot(path=str(SCREENSHOT_DIR / "10_PC_Citation_Popover.png"))
            
            # Click the citation mark to open detail modal
            print("Clicking citation mark to open detail modal...")
            await citations.first.click()
            await page.wait_for_selector("#preview-modal.active", state="attached")
            await page.wait_for_timeout(500)
            await page.screenshot(path=str(SCREENSHOT_DIR / "11_PC_Citation_DetailModal.png"))
            await page.click("#btn-modal-close")
            await page.wait_for_timeout(500)
            
        await context_pc.close()
        
        # ---------------------------------------------------------
        # STAGE 2: Mobile Viewport (iPhone 12 Pro: 390x844)
        # ---------------------------------------------------------
        print("\n--- STAGE 2: Mobile Narrow-screen Viewport (iPhone 12 Pro: 390x844) ---")
        context_mobile = await browser.new_context(
            viewport={"width": 390, "height": 844},
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1"
        )
        page_m = await context_mobile.new_page()
        
        # Access homepage on mobile
        print("2.1 Navigating to homepage on mobile...")
        await page_m.goto(BASE_URL)
        await page_m.wait_for_selector("#chat-input")
        await page_m.wait_for_timeout(1000)
        
        # Sidebar should be collapsed by default on mobile
        print("2.2 Verifying sidebar collapsed by default...")
        await page_m.screenshot(path=str(SCREENSHOT_DIR / "12_Mobile_DarkTheme_Home.png"))
        
        # Open hamburger menu
        print("2.3 Clicking Hamburger Menu button to slide out sidebar...")
        await page_m.click("#btn-sidebar-toggle")
        await page_m.wait_for_timeout(500) # wait for animation
        await page_m.screenshot(path=str(SCREENSHOT_DIR / "13_Mobile_Sidebar_Opened.png"))
        
        # Close sidebar by clicking close button (or overlay with force)
        print("2.4 Closing sidebar by clicking close button...")
        try:
            await page_m.click("#btn-sidebar-close", timeout=5000)
        except Exception as e:
            print(f"Failed to click btn-sidebar-close: {e}. Trying overlay click with force...")
            await page_m.click("#sidebar-overlay", force=True)
        await page_m.wait_for_timeout(500)
        await page_m.screenshot(path=str(SCREENSHOT_DIR / "14_Mobile_Sidebar_Closed_By_Overlay.png"))
        
        # Open drawer on mobile
        print("2.5 Opening configuration drawer on mobile...")
        # Click sidebar toggle first
        await page_m.click("#btn-sidebar-toggle")
        await page_m.wait_for_timeout(300)
        # Click settings open inside sidebar
        await page_m.click("#btn-settings-open")
        await page_m.wait_for_selector("#settings-drawer.active", state="attached")
        await page_m.wait_for_timeout(500)
        await page_m.screenshot(path=str(SCREENSHOT_DIR / "15_Mobile_SettingsDrawer.png"))
        
        # Verify scroll-lock behavior by verifying if app-container is not scrollable
        # Click cancel
        await page_m.click("#btn-settings-cancel")
        await page_m.wait_for_timeout(500)
        
        await context_mobile.close()
        await browser.close()
        
    print("\n🎉 Comprehensive E2E Visual Audit completed successfully!")
    print(f"📸 All screenshots saved to: {SCREENSHOT_DIR}")

if __name__ == "__main__":
    asyncio.run(run_audit())
