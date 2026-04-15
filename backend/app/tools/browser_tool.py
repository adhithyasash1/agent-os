from playwright.async_api import async_playwright


async def browse_url(url: str) -> str:
    """Browse a URL and return readable text content (not raw HTML)."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            page = await browser.new_page(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/120.0.0.0 Safari/537.36"
            )
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            # Wait for JS-rendered content to appear
            await page.wait_for_timeout(3000)

            # Extract readable text: strip scripts/styles, get innerText
            text = await page.evaluate("""() => {
                // Remove script and style elements
                for (const el of document.querySelectorAll('script, style, noscript, svg, iframe')) {
                    el.remove();
                }
                // Get text from article or main content areas first
                const article = document.querySelector('article, [role="main"], main, .post-content, .article-content');
                if (article && article.innerText.trim().length > 200) {
                    return article.innerText.trim();
                }
                // Fallback to body text
                return document.body.innerText.trim();
            }""")
            return text
        finally:
            await browser.close()


async def take_screenshot(url: str, path: str) -> str:
    """Take a screenshot of a URL and save to path."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(2000)
            await page.screenshot(path=path)
            return path
        finally:
            await browser.close()
