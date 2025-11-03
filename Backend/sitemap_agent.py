"""
High-Performance Async Web Scraper with Sitemap Discovery and Date Range Filtering
"""

import aiohttp
import asyncio
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import logging
from datetime import datetime
from typing import List, Dict, Optional, Set
from urllib.parse import urljoin, urlparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class WebScraper:
    """
    High-performance async web scraper with sitemap discovery and date filtering.
    """
    
    # Common sitemap locations to check
    SITEMAP_PATHS = [
        '/sitemap.xml',
        '/sitemap_index.xml',
        '/sitemap-index.xml',
        '/sitemaps/sitemap.xml',
        '/sitemap/sitemap.xml',
    ]
    
    # Date formats for parsing
    DATE_FORMATS = [
        '%Y-%m-%dT%H:%M:%S%z',
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%d',
        '%B %d, %Y',
        '%b %d, %Y',
        '%d %B %Y',
        '%d %b %Y',
    ]
    
    def __init__(
        self,
        delay: float = 0.1,
        timeout: int = 10,
        max_pages: int = 200,
        max_depth: int = 3,
        max_concurrent: int = 15
    ):
        """
        Initialize the WebScraper.
        
        Args:
            delay: Delay between requests in seconds (for rate limiting)
            timeout: Request timeout in seconds
            max_pages: Maximum number of pages to scrape
            max_depth: Maximum depth for recursive sitemap crawling
            max_concurrent: Maximum concurrent requests
        """
        self.delay = delay
        self.timeout = timeout
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.max_concurrent = max_concurrent
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        logger.info(f"WebScraper initialized (concurrent={max_concurrent}, timeout={timeout}s, max_pages={max_pages})")
    
    def scrape(
        self,
        homepage_url: str,
        start_date: str,
        end_date: str,
        keywords: Optional[List[str]] = None
    ) -> List[Dict[str, str]]:
        """
        Scrape website for pages within date range.
        
        Args:
            homepage_url: Homepage URL of the website
            start_date: Start date (YYYY-MM-DD format)
            end_date: End date (YYYY-MM-DD format)
            keywords: Optional list of keywords to filter URLs
            
        Returns:
            List of dictionaries with keys: title, description, url, date
        """
        # Run async scraping
        return asyncio.run(self._scrape_async(homepage_url, start_date, end_date, keywords))
    
    async def _scrape_async(
        self,
        homepage_url: str,
        start_date: str,
        end_date: str,
        keywords: Optional[List[str]] = None
    ) -> List[Dict[str, str]]:
        """Async implementation of scrape."""
        logger.info(f"Starting scrape for {homepage_url}")
        logger.info(f"Date range: {start_date} to {end_date}")
        logger.info(f"Keywords: {keywords if keywords else 'None (scraping all URLs)'}")
        
        # Parse and validate date range
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            if start_dt > end_dt:
                logger.error("Start date must be before end date")
                return []
        except ValueError as e:
            logger.error(f"Invalid date format: {e}")
            return []
        
        # Create aiohttp session
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        connector = aiohttp.TCPConnector(limit=self.max_concurrent)
        
        async with aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            headers=self.headers
        ) as session:
            # Discover sitemap
            sitemap_url = await self._discover_sitemap(session, homepage_url)
            if not sitemap_url:
                logger.warning(f"No sitemap found for {homepage_url}")
                return []
            
            # Crawl sitemap and extract URLs
            all_urls = await self._crawl_sitemaps_recursive(session, sitemap_url, depth=0)
            logger.info(f"Total URLs found in sitemap: {len(all_urls)}")
            
            if not all_urls:
                logger.warning("No URLs extracted from sitemap")
                return []
            
            # Filter URLs by keywords if provided
            if keywords:
                filtered_urls = [u for u in all_urls if self._matches_keywords(u['url'], keywords)]
                logger.info(f"URLs after keyword filtering: {len(filtered_urls)}")
            else:
                filtered_urls = all_urls
            
            # Pre-filter by sitemap dates (if available)
            date_filtered_urls = []
            no_date_urls = []
            
            for url_item in filtered_urls:
                if url_item.get('lastmod'):
                    if self._is_in_date_range(url_item['lastmod'], start_dt, end_dt):
                        date_filtered_urls.append(url_item)
                else:
                    no_date_urls.append(url_item)
            
            logger.info(f"URLs with dates in range: {len(date_filtered_urls)}")
            logger.info(f"URLs without sitemap dates (need checking): {len(no_date_urls)}")
            
            # Prioritize URLs with dates, then add URLs without dates
            urls_to_check = date_filtered_urls + no_date_urls
            
            # Remove duplicates
            urls_to_check = self._remove_duplicates(urls_to_check)
            logger.info(f"URLs after deduplication: {len(urls_to_check)}")
            
            # Sort by date (newest first)
            urls_to_check = self._sort_by_date(urls_to_check)
            
            # Limit to max_pages
            urls_to_scrape = urls_to_check[:self.max_pages]
            logger.info(f"Will scrape {len(urls_to_scrape)} pages")
            
            # Fetch page details in parallel
            results = await self._fetch_all_pages(session, urls_to_scrape, start_dt, end_dt)
            
            logger.info(f"Scraping complete. Found {len(results)} pages within date range")
            return results
    
    async def _discover_sitemap(
        self,
        session: aiohttp.ClientSession,
        homepage_url: str
    ) -> Optional[str]:
        """
        Discover sitemap URL from homepage.
        
        Args:
            session: aiohttp session
            homepage_url: Homepage URL
            
        Returns:
            Sitemap URL if found, None otherwise
        """
        logger.info(f"Discovering sitemap for {homepage_url}")
        
        # Parse base URL
        parsed = urlparse(homepage_url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        
        # Try common sitemap locations
        for path in self.SITEMAP_PATHS:
            sitemap_url = urljoin(base_url, path)
            logger.debug(f"Trying {sitemap_url}")
            
            try:
                async with session.head(sitemap_url) as response:
                    if response.status == 200:
                        logger.info(f"✓ Sitemap found at {sitemap_url}")
                        return sitemap_url
            except Exception as e:
                logger.debug(f"Failed to access {sitemap_url}: {e}")
                continue
        
        # Try robots.txt
        robots_url = urljoin(base_url, '/robots.txt')
        logger.debug(f"Checking robots.txt at {robots_url}")
        
        try:
            async with session.get(robots_url) as response:
                if response.status == 200:
                    text = await response.text()
                    for line in text.split('\n'):
                        if line.lower().startswith('sitemap:'):
                            sitemap_url = line.split(':', 1)[1].strip()
                            logger.info(f"✓ Sitemap found in robots.txt: {sitemap_url}")
                            return sitemap_url
        except Exception as e:
            logger.debug(f"Failed to check robots.txt: {e}")
        
        logger.warning("No sitemap discovered")
        return None
    
    async def _fetch_xml(
        self,
        session: aiohttp.ClientSession,
        url: str
    ) -> Optional[ET.Element]:
        """Fetch and parse XML content."""
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    content = await response.read()
                    return ET.fromstring(content)
                else:
                    logger.error(f"Failed to fetch XML from {url}: HTTP {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Failed to fetch XML from {url}: {e}")
            return None
    
    def _is_sitemap_index(self, root: Optional[ET.Element]) -> bool:
        """Check if XML is a sitemap index."""
        if root is None:
            return False
        
        if root.tag.endswith('sitemapindex'):
            return True
        
        for child in root:
            if child.tag.endswith('sitemap'):
                return True
        
        return False
    
    def _extract_sitemap_urls(self, root: ET.Element) -> List[str]:
        """Extract sitemap URLs from a sitemap index."""
        sitemap_urls = []
        
        # Try with namespace
        for sitemap in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}sitemap'):
            loc = sitemap.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
            if loc is not None and loc.text:
                sitemap_urls.append(loc.text)
        
        # Try without namespace
        if not sitemap_urls:
            for sitemap in root.findall('.//sitemap'):
                loc = sitemap.find('loc')
                if loc is not None and loc.text:
                    sitemap_urls.append(loc.text)
        
        return list(set(sitemap_urls))
    
    def _extract_urls_from_sitemap(
        self,
        root: Optional[ET.Element]
    ) -> List[Dict[str, Optional[str]]]:
        """Extract URLs with lastmod dates from a regular sitemap."""
        if root is None:
            return []
        
        urls = []
        
        # Try with namespace
        for url in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}url'):
            loc = url.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
            lastmod = url.find('{http://www.sitemaps.org/schemas/sitemap/0.9}lastmod')
            
            if loc is not None and loc.text:
                urls.append({
                    'url': loc.text,
                    'lastmod': lastmod.text if lastmod is not None and lastmod.text else None
                })
        
        # Try without namespace if no results
        if not urls:
            for url in root.findall('.//url'):
                loc = url.find('loc')
                lastmod = url.find('lastmod')
                
                if loc is not None and loc.text:
                    urls.append({
                        'url': loc.text,
                        'lastmod': lastmod.text if lastmod is not None and lastmod.text else None
                    })
        
        return urls
    
    async def _crawl_sitemaps_recursive(
        self,
        session: aiohttp.ClientSession,
        sitemap_url: str,
        depth: int = 0
    ) -> List[Dict[str, Optional[str]]]:
        """Recursively crawl sitemaps to find all URLs."""
        if depth > self.max_depth:
            logger.warning(f"Max depth {self.max_depth} reached at {sitemap_url}")
            return []
        
        indent = "  " * depth
        logger.info(f"{indent}Fetching sitemap (depth={depth}): {sitemap_url}")
        
        root = await self._fetch_xml(session, sitemap_url)
        if root is None:
            return []
        
        if self._is_sitemap_index(root):
            logger.info(f"{indent}Detected sitemap index")
            child_sitemaps = self._extract_sitemap_urls(root)
            logger.info(f"{indent}Found {len(child_sitemaps)} child sitemaps")
            
            # Fetch all child sitemaps concurrently
            tasks = [
                self._crawl_sitemaps_recursive(session, child_url, depth + 1)
                for child_url in child_sitemaps
            ]
            
            results = await asyncio.gather(*tasks)
            
            all_urls = []
            for child_urls in results:
                all_urls.extend(child_urls)
            
            return all_urls
        else:
            urls = self._extract_urls_from_sitemap(root)
            logger.info(f"{indent}Extracted {len(urls)} URLs from sitemap")
            return urls
    
    def _matches_keywords(self, url: str, keywords: List[str]) -> bool:
        """Check if URL matches any of the keywords."""
        url_lower = url.lower()
        return any(keyword.lower() in url_lower for keyword in keywords)
    
    def _remove_duplicates(self, urls: List[Dict]) -> List[Dict]:
        """Remove duplicate URLs."""
        seen_urls = set()
        unique_urls = []
        
        for item in urls:
            url = item['url']
            if url not in seen_urls:
                seen_urls.add(url)
                unique_urls.append(item)
        
        return unique_urls
    
    def _normalize_date(self, date_str: Optional[str]) -> Optional[str]:
        """Normalize date to YYYY-MM-DD format."""
        parsed_date = self._parse_date(date_str)
        if parsed_date:
            return parsed_date.strftime('%Y-%m-%d')
        return None
    
    def _is_in_date_range(
        self,
        date_str: Optional[str],
        start_dt: datetime,
        end_dt: datetime
    ) -> bool:
        """Check if date is within the specified range."""
        if not date_str:
            return False
        
        parsed_date = self._parse_date(date_str)
        if not parsed_date:
            return False
        
        # Remove timezone info and time component for comparison
        if parsed_date.tzinfo is not None:
            parsed_date = parsed_date.replace(tzinfo=None)
        
        parsed_date = parsed_date.replace(hour=0, minute=0, second=0, microsecond=0)
        
        return start_dt <= parsed_date <= end_dt
    
    async def _fetch_all_pages(
        self,
        session: aiohttp.ClientSession,
        urls: List[Dict],
        start_dt: datetime,
        end_dt: datetime
    ) -> List[Dict[str, str]]:
        """Fetch all pages concurrently with retry for failed requests."""
        logger.info(f"Fetching details for {len(urls)} pages concurrently...")
        
        # Create semaphore for rate limiting
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        # Counter for progress tracking
        counter = {'total': len(urls), 'current': 0}
        counter_lock = asyncio.Lock()
        
        # Fetch all pages
        tasks = [
            self._fetch_page_with_semaphore(session, semaphore, url_item, start_dt, end_dt, counter, counter_lock)
            for url_item in urls
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Separate successful and failed results
        successful = []
        failed_indices = []
        
        for i, result in enumerate(results):
            if isinstance(result, dict) and result.get('url'):
                successful.append(result)
            elif isinstance(result, Exception):
                logger.debug(f"Failed request will be retried: {urls[i]['url']}")
                failed_indices.append(i)
            elif result is None:
                failed_indices.append(i)
        
        logger.info(f"First pass: {len(successful)} successful, {len(failed_indices)} failed")
        
        # Retry failed requests once
        if failed_indices:
            logger.info(f"Retrying {len(failed_indices)} failed requests...")
            
            # Reset counter for retries
            counter = {'total': len(failed_indices), 'current': 0}
            
            retry_tasks = [
                self._fetch_page_with_semaphore(session, semaphore, urls[i], start_dt, end_dt, counter, counter_lock)
                for i in failed_indices
            ]
            
            retry_results = await asyncio.gather(*retry_tasks, return_exceptions=True)
            
            retry_success = 0
            for result in retry_results:
                if isinstance(result, dict) and result.get('url'):
                    successful.append(result)
                    retry_success += 1
            
            logger.info(f"Retry: {retry_success} successful, {len(failed_indices) - retry_success} still failed")
        
        # Filter out None values and return
        final_results = [r for r in successful if r is not None]
        logger.info(f"Total pages scraped successfully: {len(final_results)}")
        
        return final_results
    
    async def _fetch_page_with_semaphore(
        self,
        session: aiohttp.ClientSession,
        semaphore: asyncio.Semaphore,
        url_item: Dict,
        start_dt: datetime,
        end_dt: datetime,
        counter: Dict,
        counter_lock: asyncio.Lock
    ) -> Optional[Dict[str, str]]:
        """Fetch a single page with semaphore for rate limiting."""
        async with semaphore:
            result = await self._fetch_page_details(session, url_item, start_dt, end_dt, counter, counter_lock)
            
            # Small delay for rate limiting
            if self.delay > 0:
                await asyncio.sleep(self.delay)
            
            return result
    
    async def _fetch_page_details(
        self,
        session: aiohttp.ClientSession,
        url_item: Dict,
        start_dt: datetime,
        end_dt: datetime,
        counter: Dict,
        counter_lock: asyncio.Lock
    ) -> Optional[Dict[str, str]]:
        """Fetch details for a single page."""
        url = url_item['url']
        sitemap_date = url_item.get('lastmod')
        
        # Increment counter
        async with counter_lock:
            counter['current'] += 1
            current = counter['current']
            total = counter['total']
        
        try:
            async with session.get(url) as response:
                if response.status != 200:
                    logger.debug(f"✗ [{current}/{total}] Failed to fetch {url}: HTTP {response.status}")
                    return None
                
                content = await response.read()
                soup = BeautifulSoup(content, 'html.parser')
                
                # Extract metadata
                title = self._extract_title(soup)
                description = self._extract_description(soup)
                page_date = self._extract_date(soup)
                
                # Use page date if available, otherwise use sitemap date
                final_date = page_date or sitemap_date
                
                # Check if date is in range
                if self._is_in_date_range(final_date, start_dt, end_dt):
                    normalized_date = self._normalize_date(final_date)
                    
                    # Truncate title for logging
                    title_display = title[:60] if title else 'N/A'
                    logger.info(f"✓ [{current}/{total}] {title_display}... ({normalized_date})")
                    
                    return {
                        'title': title or 'No title found',
                        'description': description or 'No description found',
                        'url': url,
                        'date': normalized_date
                    }
                else:
                    logger.debug(f"✗ [{current}/{total}] Skipped (date outside range or missing)")
                    return None
                
        except asyncio.TimeoutError:
            logger.debug(f"✗ [{current}/{total}] Timeout fetching {url}")
            return None
        except Exception as e:
            logger.debug(f"✗ [{current}/{total}] Error: {e}")
            return None
    
    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract title from page."""
        # Try <title> tag
        title_tag = soup.find('title')
        if title_tag:
            return title_tag.get_text(strip=True)
        
        # Try og:title
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            return og_title['content']
        
        # Try <h1>
        h1_tag = soup.find('h1')
        if h1_tag:
            return h1_tag.get_text(strip=True)
        
        return None
    
    def _extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract description from page."""
        # Try meta description
        desc_meta = soup.find('meta', attrs={'name': 'description'})
        if desc_meta and desc_meta.get('content'):
            return desc_meta['content']
        
        # Try og:description
        og_desc = soup.find('meta', property='og:description')
        if og_desc and og_desc.get('content'):
            return og_desc['content']
        
        return None
    
    def _extract_date(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract date from page."""
        # Try article:published_time
        date_meta = soup.find('meta', property='article:published_time')
        if date_meta and date_meta.get('content'):
            return date_meta['content']
        
        # Try publish-date
        date_meta = soup.find('meta', attrs={'name': 'publish-date'})
        if date_meta and date_meta.get('content'):
            return date_meta['content']
        
        # Try date meta tag
        date_meta = soup.find('meta', attrs={'name': 'date'})
        if date_meta and date_meta.get('content'):
            return date_meta['content']
        
        # Try <time> tag
        time_tag = soup.find('time')
        if time_tag:
            return time_tag.get('datetime') or time_tag.get_text(strip=True)
        
        return None
    
    def _sort_by_date(self, urls: List[Dict]) -> List[Dict]:
        """Sort URLs by date (newest first)."""
        urls_with_dates = [u for u in urls if u.get('lastmod')]
        urls_without_dates = [u for u in urls if not u.get('lastmod')]
        
        def get_sort_key(url_item):
            parsed = self._parse_date(url_item['lastmod'])
            if parsed is None:
                # Return minimum datetime (timezone-naive) for invalid dates
                return datetime.min
            # Remove timezone info to ensure all datetimes are naive for comparison
            if parsed.tzinfo is not None:
                parsed = parsed.replace(tzinfo=None)
            return parsed
        
        urls_with_dates.sort(key=get_sort_key, reverse=True)
        
        return urls_with_dates + urls_without_dates

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse date string to datetime object."""
        if not date_str:
            return None
        
        # Clean date string
        clean_date = date_str.replace('Z', '+0000')
        
        for fmt in self.DATE_FORMATS:
            try:
                if 'T' in clean_date and 'T' not in fmt:
                    clean_date_simple = clean_date.split('T')[0]
                    dt = datetime.strptime(clean_date_simple, fmt)
                else:
                    dt = datetime.strptime(clean_date, fmt)
                
                # Remove timezone info to ensure consistency
                if dt.tzinfo is not None:
                    dt = dt.replace(tzinfo=None)
                
                return dt
            except:
                continue
        
        return None


# Example usage
if __name__ == "__main__":
    # Initialize scraper
    scraper = WebScraper(
        delay=0.1,          # Short delay for rate limiting
        timeout=10,
        max_pages=5,
        max_depth=1,
        max_concurrent=15   # 15 concurrent requests
    )
    
    # Scrape website
    results = scraper.scrape(
        homepage_url="https://www.aicerts.ai/",#"https://www.mygreatlearning.com",
        start_date="2025-01-01",
        end_date="2025-12-31",
        keywords=['course', 'certification', 'program']
    )
    
    # Display results
    print(f"\n{'='*80}")
    print(f"Found {len(results)} pages")
    print('='*80)
    print(f"our own titles {results}")
    for result in results[:5]:
        print(f"\nTitle: {result['title']}")
        print(f"Date: {result['date']}")
        print(f"URL: {result['url']}")
        print(f"Description: {result['description'][:100]}...")

# Scrape website
    results = scraper.scrape(
        homepage_url="https://www.mygreatlearning.com",
        start_date="2025-01-01",
        end_date="2025-12-31",
        keywords=['course', 'certification', 'program']
    )
    
    # Display results
    print(f"\n{'='*80}")
    print(f"Found {len(results)} pages")
    print('='*80)
    print(f"competitor's titles {results}")
    for result in results[:5]:
        print(f"\nTitle: {result['title']}")
        print(f"Date: {result['date']}")
        print(f"URL: {result['url']}")
        print(f"Description: {result['description'][:100]}...")