"""
Browser tool — Crawl4AI primary, Playwright fallback.

Crawl4AI handles JS rendering, content cleaning, and outputs structured
markdown. Falls back to raw Playwright if Crawl4AI fails.
"""

import logging

logger = logging.getLogger("agentos.browser")


async def browse_url(url: str) -> str:
    """Browse a URL and return readable text content.

    Primary: Crawl4AI (optimized for AI ingestion, structured markdown).
    Fallback: Playwright raw extraction (handles edge cases Crawl4AI misses).
    """
    # Try Crawl4AI first
    try:
        content = await _crawl4ai_extract(url)
        if content and len(content) > 200:
            return content
        logger.debug(f"Crawl4AI returned insufficient content for {url}, trying Playwright")
    except Exception as e:
        logger.debug(f"Crawl4AI failed for {url}: {e}, trying Playwright")

    # Fallback to Playwright
    return await _playwright_extract(url)


async def _crawl4ai_extract(url: str) -> str:
    """Extract content using Crawl4AI — handles JS, cleans HTML, outputs markdown."""
    from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode

    config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        page_timeout=20000,
        wait_until="domcontentloaded",
        mean_delay=0.5,
        word_count_threshold=50,
        exclude_external_links=True,
        remove_overlay_elements=True,
    )

    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url=url, config=config)

        if result.success:
            # Prefer markdown (cleaner), fall back to extracted content
            content = result.markdown_v2.raw_markdown if hasattr(result, 'markdown_v2') and result.markdown_v2 else None
            if not content:
                content = result.markdown or result.extracted_content or ""
            return content.strip()

        raise ValueError(f"Crawl4AI returned failure for {url}: {result.error_message}")


async def _playwright_extract(url: str) -> str:
    """Fallback: raw Playwright extraction with manual content cleaning."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            page = await browser.new_page(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/120.0.0.0 Safari/537.36"
            )
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(3000)

            text = await page.evaluate("""() => {
                for (const el of document.querySelectorAll('script, style, noscript, svg, iframe')) {
                    el.remove();
                }
                const article = document.querySelector('article, [role="main"], main, .post-content, .article-content');
                if (article && article.innerText.trim().length > 200) {
                    return article.innerText.trim();
                }
                return document.body.innerText.trim();
            }""")
            return text
        finally:
            await browser.close()


async def take_screenshot(url: str, path: str) -> str:
    """Take a screenshot of a URL and save to path."""
    from playwright.async_api import async_playwright

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
