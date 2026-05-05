#!/usr/bin/env python3
"""
Use Playwright to inspect the actual HTTP request being made when submitting the form.
"""
import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright

FORM_URL = "https://www.bauaufsicht-frankfurt.de/service/bauschild"
OUTPUT_DIR = Path(__file__).parent.parent / "debug"


async def inspect_form_submission():
    """Capture form submission by monitoring network requests."""
    OUTPUT_DIR.mkdir(exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        # Log network responses
        captured_responses = []

        def on_response(response):
            if "liegenschaft" in response.url:
                post_data = response.request.post_data
                if isinstance(post_data, bytes):
                    post_data = post_data.decode('utf-8')
                captured_responses.append({
                    "url": response.url,
                    "status": response.status,
                    "request_method": response.request.method,
                    "request_headers": dict(response.request.headers),
                    "request_post_data": post_data,
                })
                print(f"✓ Captured {response.request.method} {response.url} -> {response.status}")

        page.on("response", on_response)

        print("Navigating to form...")
        await page.goto(FORM_URL, wait_until="networkidle")
        await page.wait_for_timeout(1000)

        print("Dismissing cookie consent...")
        await page.evaluate("""
            () => {
                const root = document.getElementById('usercentrics-root');
                if (root) root.style.display = 'none';
            }
        """)
        await page.wait_for_timeout(500)

        print("Selecting Gemarkung 478...")
        gemarkung_select = page.locator("#form-gemarkung")
        await gemarkung_select.select_option("478")
        await page.wait_for_timeout(1000)

        print("Selecting Flur 414...")
        flur_select = page.locator('select[name="tx_vierwdbafinfothek_constructionsign[FLUR]"]')
        await flur_select.select_option("414")
        await page.wait_for_timeout(1000)

        print("Waiting for Flurstück options...")
        await page.wait_for_function(
            """
            () => {
                const select = document.querySelector('select[name="tx_vierwdbafinfothek_constructionsign[FLST_ZAE;FLST_NEN]"]');
                const options = select ? Array.from(select.options) : [];
                return options.length > 1;
            }
            """,
            timeout=5000
        )

        flst_select = page.locator('select[name="tx_vierwdbafinfothek_constructionsign[FLST_ZAE;FLST_NEN]"]')

        # Get first available Flurstück
        options = await flst_select.locator("option").all()
        opt_values = []
        for opt in options:
            val = await opt.get_attribute("value")
            if val and val.strip():
                opt_values.append(val)

        selected_flst = opt_values[1] if len(opt_values) > 1 else None
        if selected_flst:
            print(f"Selecting Flurstück {selected_flst}...")
            await flst_select.select_option(selected_flst)
            await page.wait_for_timeout(500)

        print("\nClicking 'Bauschild anzeigen' button...")
        bauschild_btn = page.locator('button[name="tx_vierwdbafinfothek_constructionsign[bauschild]"]').first
        await bauschild_btn.click()

        print("Waiting for response...")
        await page.wait_for_timeout(3000)

        print(f"\n{'='*60}")
        print(f"Found {len(captured_responses)} liegenschaft requests")
        print(f"{'='*60}\n")

        for i, resp in enumerate(captured_responses):
            print(f"\nRequest #{i+1}:")
            print(f"  Method: {resp['request_method']}")
            print(f"  URL: {resp['url']}")
            print(f"  Status: {resp['status']}")
            print(f"\n  Headers:")
            for key, value in sorted(resp['request_headers'].items()):
                if key.lower() not in ['accept-encoding', 'cookie']:
                    print(f"    {key}: {value}")
            if 'cookie' in resp['request_headers']:
                print(f"    Cookie: <{len(resp['request_headers']['cookie'])} chars>")

            print(f"\n  Form Data:")
            if resp['request_post_data']:
                # Parse URL-encoded form data
                import urllib.parse
                parsed = urllib.parse.parse_qs(resp['request_post_data'])
                for key, values in sorted(parsed.items()):
                    print(f"    {key}: {values[0]}")

        # Save the request details
        output_file = OUTPUT_DIR / "captured_request_details.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(captured_responses, f, indent=2, ensure_ascii=False)
        print(f"\n✓ Saved to {output_file}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(inspect_form_submission())
