import asyncio
import aiohttp
import json
import time
import logging
from datetime import datetime
from urllib.parse import urlparse
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import os
from config import ensure_data_directory

logger = logging.getLogger(__name__)

# ------------------- FILTERING -------------------
SKIP_PATTERNS = [
    '/admin/', '/wp-admin/', '/privacy/', '/terms/', '/legal/',
    '/contact/', '/about-us/', '/sitemap', '/feed/', '/rss/',
    '.pdf', '.jpg', '.png', '.gif', '.mp4', '.zip', '.doc'
]

def should_skip_url(url):
    """Filter out URLs that are unlikely to contain useful content."""
    url_lower = url.lower()
    return any(pattern in url_lower for pattern in SKIP_PATTERNS)

# ------------------- ASYNC SITEMAP CRAWLER -------------------
# async def fetch_sitemap_urls_async(session, sitemap_url):
#     """Fetch and parse sitemap to extract URLs."""
#     urls = []
#     try:
#         logger.info(f"Fetching sitemap: {sitemap_url}")
#         async with session.get(sitemap_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
#             if response.status == 200:
#                 content = await response.text()
#                 root = ET.fromstring(content)
                
#                 # Try with namespace first
#                 for url_elem in root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}url"):
#                     loc_elem = url_elem.find("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
#                     if loc_elem is not None and not should_skip_url(loc_elem.text):
#                         urls.append(loc_elem.text)
                
#                 # Fallback without namespace
#                 if not urls:
#                     for loc in root.findall(".//loc"):
#                         if loc.text and not should_skip_url(loc.text):
#                             urls.append(loc.text)
                            
#     except Exception as e:
#         logger.error(f"Failed to fetch sitemap {sitemap_url}: {e}")
    
#     logger.info(f"Extracted {len(urls)} URLs from {sitemap_url}")
#     return urls

import aiohttp
import xml.etree.ElementTree as ET

# async def fetch_sitemap_urls_async(session, sitemap_url):
#     """Fetch and parse sitemap to extract URLs asynchronously."""
#     urls = []
#     try:
#         logger.info(f"Fetching sitemap: {sitemap_url}")
#         headers = {'User-Agent': 'Mozilla/5.0 (compatible; SitemapScraper/1.0)'}
#         async with session.get(sitemap_url, timeout=aiohttp.ClientTimeout(total=10), headers=headers) as response:
#             if response.status != 200:
#                 return urls

#             content = await response.text()
#             root = ET.fromstring(content)

#             namespace = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}

#             # Case 1: normal sitemap with <url>
#             for url_elem in root.findall(".//ns:url", namespace):
#                 loc_elem = url_elem.find("ns:loc", namespace)
#                 if loc_elem is not None and loc_elem.text:
#                     urls.append(loc_elem.text)

#             # Case 2: sitemap index with <sitemap>
#             if not urls:
#                 for sm_elem in root.findall(".//ns:sitemap", namespace):
#                     loc_elem = sm_elem.find("ns:loc", namespace)
#                     if loc_elem is not None and loc_elem.text:
#                         urls.append(loc_elem.text)

#             # Fallback without namespace
#             if not urls:
#                 for loc in root.findall(".//loc"):
#                     if loc.text:
#                         urls.append(loc.text)

#     except Exception as e:
#         print(f"Failed to fetch or parse sitemap {sitemap_url}: {e}")
#     logger.info(f"Extracted {len(urls)} URLs from {sitemap_url}")
#     return urls
async def fetch_sitemap_urls_async(session, sitemap_url):
    """Fetch and parse sitemap to extract URLs + lastmod asynchronously."""
    items = []
    try:
        logger.info(f"Fetching sitemap: {sitemap_url}")
        headers = {'User-Agent': 'Mozilla/5.0 (compatible; SitemapScraper/1.0)'}

        async with session.get(sitemap_url, timeout=aiohttp.ClientTimeout(total=10), headers=headers) as response:
            if response.status != 200:
                return items

            content = await response.text()
            root = ET.fromstring(content)

            namespace = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}

            # ---- Case 1: Normal <url> entries ----
            for url_elem in root.findall(".//ns:url", namespace):
                loc = url_elem.find("ns:loc", namespace)
                lastmod = url_elem.find("ns:lastmod", namespace)

                if loc is not None:
                    items.append({
                        "url": loc.text,
                        "lastmod": lastmod.text if lastmod is not None else None
                    })

            # ---- Case 2: Sitemap index <sitemap> entries ----
            if not items:
                for sm in root.findall(".//ns:sitemap", namespace):
                    loc = sm.find("ns:loc", namespace)
                    lastmod = sm.find("ns:lastmod", namespace)

                    if loc is not None:
                        items.append({
                            "url": loc.text,
                            "lastmod": lastmod.text if lastmod is not None else None
                        })

            # ---- Fallback without namespace ----
            if not items:
                for url_node in root.findall(".//loc"):
                    items.append({"url": url_node.text, "lastmod": None})

    except Exception as e:
        print(f"Failed to fetch or parse sitemap {sitemap_url}: {e}")

    logger.info(f"Extracted {len(items)} items from {sitemap_url}")
    return items


async def extract_title_async(session, url, semaphore):
    """Extract title from a single URL with concurrency control."""
    async with semaphore:
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as response:
                if response.status == 200:
                    # Check content type
                    content_type = response.headers.get('content-type', '').lower()
                    if 'text/html' not in content_type:
                        return None
                    
                    # Read content in chunks and stop early if we find title
                    content = ""
                    async for chunk in response.content.iter_chunked(1024):
                        content += chunk.decode('utf-8', errors='ignore')
                        # Stop reading if we have the head section
                        if '</head>' in content.lower() or len(content) > 50000:
                            break
                    
                    # Extract title
                    soup = BeautifulSoup(content, "html.parser")
                    title_tag = soup.find("title")
                    if title_tag:
                        title = title_tag.get_text().strip()
                        if title:
                            return title
                    
                    # Fallback to meta title
                    meta_title = soup.find("meta", property="og:title")
                    if meta_title and meta_title.get("content"):
                        return meta_title["content"].strip()
                        
        except asyncio.TimeoutError:
            logger.warning(f"Timeout for {url}")
        except Exception as e:
            logger.warning(f"Failed to fetch {url}: {e}")
        
        return None

async def process_titles_batch(session, urls, batch_size=50, progress_callback=None):
    """Process URLs in batches with progress reporting."""
    semaphore = asyncio.Semaphore(batch_size)
    titles = []
    failed_urls = []
    
    total_urls = len(urls)
    processed = 0
    
    # Process in batches to avoid overwhelming the system
    for i in range(0, total_urls, batch_size):
        batch = urls[i:i + batch_size]
        
        # Create tasks for this batch
        # tasks = [extract_title_async(session, url, semaphore) for url in batch]
        tasks = [extract_title_async(session, item["url"], semaphore) for item in batch]

        # Process batch
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for j, result in enumerate(batch_results):
            item = batch[j]          # item = {"url": "...", "lastmod": "..."}
            url = item["url"]

            if isinstance(result, Exception):
                failed_urls.append({
                    "url": url,
                    "lastmod": item["lastmod"],
                    "error": str(result)
                })

            elif result:  # valid title string
                titles.append({
                    "url": url,
                    "title": result,
                    "lastmod": item["lastmod"]
                })

            else:  # None or empty
                failed_urls.append({
                    "url": url,
                    "lastmod": item["lastmod"],
                    "error": "No title found"
                })

            
            processed += 1
            if progress_callback and processed % 20 == 0:
                progress_callback(processed, total_urls)
    
    return titles, failed_urls

async def retry_failed_urls(session, failed_urls, max_concurrent=10):
    """Retry failed URLs with lower concurrency."""
    if not failed_urls:
        return []
    
    logger.info(f"Retrying {len(failed_urls)} failed URLs...")
    semaphore = asyncio.Semaphore(max_concurrent)
    
    tasks = [extract_title_async(session, url, semaphore) for url in failed_urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    titles = [result for result in results if isinstance(result, str) and result]
    return titles

def load_config(session_dir=None):
    """Load configuration from config.json"""
    config_path = "config.json"
    if session_dir:
        config_path = os.path.join(session_dir, "config.json")

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"{config_path} file not found!")
        return None
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in {config_path}!")
        return None

async def run_sitemap_agent(session_dir=None):
    """Main sitemap agent function."""
    logger.info("Starting sitemap agent...")
    
    try:
        config = load_config(session_dir)
        if config is None:
            logger.error("Failed to load configuration")
            return False
        
        own_sitemap_url = config.get("own_sitemap_url")
        competitor_sitemaps = config.get("competitor_sitemaps", [])
        
        if not own_sitemap_url:
            logger.error("'own_sitemap_url' not found in config.json")
            return False
        
        # Configure session with connection pooling
        connector = aiohttp.TCPConnector(
            limit=100,  # Total connection pool size
            limit_per_host=20,  # Max connections per host
            ttl_dns_cache=300,
            use_dns_cache=True,
        )
        
        timeout = aiohttp.ClientTimeout(total=30)
        headers = {'User-Agent': 'Mozilla/5.0 (compatible; AICartsContentAgent/2.0)'}
        
        async with aiohttp.ClientSession(
            connector=connector, 
            timeout=timeout, 
            headers=headers
        ) as session:
            
            # Fetch all sitemaps concurrently
            all_sitemaps = [own_sitemap_url] + competitor_sitemaps
            sitemap_tasks = [fetch_sitemap_urls_async(session, url) for url in all_sitemaps]
            sitemap_results = await asyncio.gather(*sitemap_tasks)
            
            # Separate own vs competitor URLs
            own_urls = sitemap_results[0] if sitemap_results else []
            competitor_urls = []
            for i in range(1, len(sitemap_results)):
                competitor_urls.extend(sitemap_results[i])
            
            # Remove duplicates
            # own_urls = list(set(own_urls))
            # competitor_urls = list(set(competitor_urls))
            # Deduplicate by URL value
            def dedupe_items(items):
                seen = set()
                unique = []
                for item in items:
                    url = item["url"]
                    if url not in seen:
                        seen.add(url)
                        unique.append(item)
                return unique

            own_urls = dedupe_items(own_urls)
            competitor_urls = dedupe_items(competitor_urls)

            logger.info(f"Total URLs to process: {len(own_urls)} (own), {len(competitor_urls)} (competitors)")
            
            # Progress callback
            def progress_callback(processed, total):
                percentage = (processed / total) * 100
                logger.info(f"Progress: {processed}/{total} ({percentage:.1f}%)")
            
            # Process own titles
            logger.info("Processing AI Certs titles...")
            start_time = time.time()
            own_titles, own_failed = await process_titles_batch(
                session, own_urls, batch_size=50, progress_callback=progress_callback
            )
            
            # Retry failed ones
            if own_failed:
                retry_titles = await retry_failed_urls(session, own_failed)
                own_titles.extend(retry_titles)
            
            elapsed = time.time() - start_time
            logger.info(f"Own titles completed in {elapsed:.1f}s: {len(own_titles)} titles")
            
            # Process competitor titles
            logger.info("Processing competitor titles...")
            start_time = time.time()
            competitor_titles, competitor_failed = await process_titles_batch(
                session, competitor_urls, batch_size=50, progress_callback=progress_callback
            )
            
            # Retry failed ones
            if competitor_failed:
                retry_titles = await retry_failed_urls(session, competitor_failed)
                competitor_titles.extend(retry_titles)
            
            elapsed = time.time() - start_time
            logger.info(f"Competitor titles completed in {elapsed:.1f}s: {len(competitor_titles)} titles")
            
            # Prepare results
            sitemap_data = {
                "ai_certs_titles": own_titles,
                "competitor_titles": competitor_titles
            }
        
        # Save results to data directory
        output_file = os.path.join("data", "sitemaps_data.json")
        if session_dir:
            output_file = os.path.join(session_dir, "sitemaps_data.json")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(sitemap_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Sitemap agent completed successfully! Data saved to {output_file}")
        return True
        
    except Exception as e:
        logger.error(f"Sitemap agent failed: {e}")
        return False

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    asyncio.run(run_sitemap_agent())