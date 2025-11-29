"""Web scraper for downloading Raycast developer documentation.

This module uses the llms.txt file to discover all documentation pages,
then downloads them along with their assets.
"""

import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote

import requests
from bs4 import BeautifulSoup


class RaycastDocScraper:
    """Scraper for downloading Raycast developer documentation.

    Uses the llms.txt file to discover all documentation URLs.
    """

    BASE_URL = "https://developers.raycast.com"
    LLMS_TXT_URL = "https://developers.raycast.com/llms.txt"

    def __init__(self, output_dir: Path):
        """Initialize the scraper.

        Args:
            output_dir: Directory to save downloaded files
        """
        self.output_dir = output_dir
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "Raycast-Dash-Docset-Generator/1.0"}
        )

        self.visited_urls: set[str] = set()
        self.downloaded_assets: set[str] = set()

        # Rate limiting
        self.delay = 0.3  # seconds between requests

    def scrape(self) -> None:
        """Scrape documentation using the llms.txt file."""
        print(f"Fetching page list from {self.LLMS_TXT_URL}")
        print(f"Output directory: {self.output_dir}")

        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Get URLs from llms.txt
        urls = self._get_urls_from_llms_txt()
        print(f"Found {len(urls)} pages to download")

        # Download each page
        for i, url in enumerate(urls, 1):
            self._download_page(url, i, len(urls))

        print("\nScraping complete!")
        print(f"  HTML pages: {len(self.visited_urls)}")
        print(f"  Assets: {len(self.downloaded_assets)}")

    def _get_urls_from_llms_txt(self) -> list[str]:
        """Fetch and parse llms.txt to get documentation URLs.

        Returns:
            List of URLs to download
        """
        try:
            response = self.session.get(self.LLMS_TXT_URL, timeout=30)
            response.raise_for_status()

            content = response.text
            urls = []

            # Parse markdown-style links: [Title](/path/to/page.md)
            # The llms.txt contains lines like:
            # - [Introduction](/readme.md): Start building...
            link_pattern = re.compile(r"\[([^\]]+)\]\((/[^)]+\.md)\)")

            for match in link_pattern.finditer(content):
                path = match.group(2)
                # Convert .md path to actual URL
                # GitBook serves these without the .md extension
                url_path = path.replace(".md", "")
                if url_path == "/readme":
                    url_path = "/"
                url = f"{self.BASE_URL}{url_path}"
                urls.append(url)

            # Also add the root page
            if self.BASE_URL not in urls and f"{self.BASE_URL}/" not in urls:
                urls.insert(0, self.BASE_URL)

            return urls

        except Exception as e:
            print(f"Error fetching llms.txt: {e}")
            return []

    def _download_page(self, url: str, current: int, total: int) -> None:
        """Download a single page and its assets.

        Args:
            url: URL to download
            current: Current page number
            total: Total pages to download
        """
        if url in self.visited_urls:
            return

        self.visited_urls.add(url)

        try:
            print(f"Downloading [{current}/{total}]: {url}")

            time.sleep(self.delay)
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            # Save the HTML file
            file_path = self._url_to_filepath(url)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_bytes(response.content)

            # Download static assets
            soup = BeautifulSoup(response.content, "lxml")
            self._download_assets(soup, url)

        except Exception as e:
            print(f"  Error: {e}")

    def _download_assets(self, soup: BeautifulSoup, page_url: str) -> None:
        """Download static assets (CSS, JS, images) referenced in the page.

        Args:
            soup: BeautifulSoup object of the page
            page_url: URL of the page being processed
        """
        # CSS files
        for link in soup.find_all("link", rel="stylesheet"):
            if href := link.get("href"):
                self._download_asset(str(href), page_url)

        # JavaScript files
        for script in soup.find_all("script", src=True):
            self._download_asset(str(script["src"]), page_url)

        # Images
        for img in soup.find_all("img", src=True):
            self._download_asset(str(img["src"]), page_url)

        # Favicons and other icons
        for link in soup.find_all("link", rel=["icon", "apple-touch-icon"]):
            if href := link.get("href"):
                self._download_asset(str(href), page_url)

        # Preloaded fonts
        for link in soup.find_all("link", rel="preload"):
            if href := link.get("href"):
                self._download_asset(str(href), page_url)

    def _download_asset(self, asset_url: str, page_url: str) -> None:
        """Download a static asset.

        Args:
            asset_url: URL of the asset (may be relative)
            page_url: URL of the page referencing the asset
        """
        # Skip data URLs
        if asset_url.startswith("data:"):
            return

        # Resolve relative URLs
        absolute_url = urljoin(page_url, asset_url)

        # Skip external assets (CDNs, etc.) - we only want raycast assets
        parsed = urlparse(absolute_url)
        if parsed.netloc and parsed.netloc != "developers.raycast.com":
            # Allow GitBook assets which are commonly used
            if "gitbook" not in parsed.netloc:
                return

        if absolute_url in self.downloaded_assets:
            return

        self.downloaded_assets.add(absolute_url)

        try:
            time.sleep(self.delay)
            response = self.session.get(absolute_url, timeout=30)
            response.raise_for_status()

            file_path = self._url_to_filepath(absolute_url)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_bytes(response.content)

        except Exception as e:
            print(f"  Warning: Failed to download asset {absolute_url}: {e}")

    def _url_to_filepath(self, url: str) -> Path:
        """Convert a URL to a local file path.

        Args:
            url: URL to convert

        Returns:
            Path object for the local file
        """
        parsed = urlparse(url)
        path = unquote(parsed.path)

        # Include the hostname in the path for external assets
        if parsed.netloc and parsed.netloc != "developers.raycast.com":
            prefix = parsed.netloc
        else:
            prefix = "developers.raycast.com"

        # Remove leading slash
        if path.startswith("/"):
            path = path[1:]

        # If path is empty, use index.html
        if not path:
            path = "index.html"
        # If path ends with /, append index.html
        elif path.endswith("/"):
            path = path + "index.html"
        elif "." not in Path(path).name:
            # If no extension, assume it's an HTML page
            path = path + "/index.html"

        return self.output_dir / prefix / path


def scrape_raycast_docs(output_dir: Path) -> None:
    """Scrape Raycast developer documentation.

    Args:
        output_dir: Directory to save downloaded files
    """
    scraper = RaycastDocScraper(output_dir=output_dir)
    scraper.scrape()
