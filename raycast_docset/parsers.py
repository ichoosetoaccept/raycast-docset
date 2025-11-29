"""Parsers for extracting index entries from Raycast documentation HTML."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator
from urllib.parse import unquote

from bs4 import BeautifulSoup


@dataclass
class IndexEntry:
    """Represents a single entry in the Dash search index."""

    name: str
    entry_type: str
    path: str


def parse_html_file(file_path: Path) -> BeautifulSoup:
    """Parse an HTML file and return a BeautifulSoup object."""
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        return BeautifulSoup(f.read(), "lxml")


def get_title_from_soup(soup: BeautifulSoup) -> str | None:
    """Extract the page title from a BeautifulSoup object."""
    # Try to find the main heading first
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text().strip()
        if title:
            return title

    # Fall back to title tag
    title_tag = soup.find("title")
    if title_tag:
        title = title_tag.get_text()
        # Titles are usually "Name | Raycast API" or similar
        if " | " in title:
            return title.split(" | ")[0].strip()
        if " - " in title:
            return title.split(" - ")[0].strip()
        return title.strip()
    return None


class APIReferenceParser:
    """Parser for Raycast API reference pages.

    These are pages like:
    - api-reference/ai.md
    - api-reference/user-interface/list.md
    """

    PATH_PATTERN = re.compile(r"api-reference/")

    def matches(self, relative_path: str) -> bool:
        """Check if this parser handles the given path."""
        return bool(self.PATH_PATTERN.search(relative_path))

    def parse(self, file_path: Path, relative_path: str) -> Iterator[IndexEntry]:
        """Parse an API reference page and yield index entries."""
        soup = parse_html_file(file_path)
        title = get_title_from_soup(soup)

        if not title:
            return

        # Determine entry type based on content
        entry_type = self._determine_entry_type(soup, title, relative_path)

        yield IndexEntry(
            name=title,
            entry_type=entry_type,
            path=relative_path,
        )

        # Parse functions, types, and properties from the page
        yield from self._parse_api_elements(soup, relative_path, title)

    def _determine_entry_type(
        self, soup: BeautifulSoup, title: str, relative_path: str
    ) -> str:
        """Determine the entry type based on page content."""
        title_lower = title.lower()

        # UI components
        if "user-interface" in relative_path:
            if any(
                comp in title_lower
                for comp in ["list", "grid", "form", "detail", "action"]
            ):
                return "Component"
            return "Class"

        # Hooks
        if title.startswith("use"):
            return "Function"

        # Default to Class for API reference
        return "Class"

    def _parse_api_elements(
        self, soup: BeautifulSoup, relative_path: str, parent_name: str
    ) -> Iterator[IndexEntry]:
        """Parse API elements (functions, types, properties) from the page."""
        # Look for code blocks that define functions/types
        for heading in soup.find_all(["h2", "h3", "h4"]):
            heading_text = heading.get_text().strip()
            heading_id = heading.get("id")

            if not heading_id or not heading_text:
                continue

            # Skip generic headings
            skip_headings = {
                "example",
                "examples",
                "props",
                "properties",
                "return",
                "returns",
                "parameters",
                "signature",
                "see also",
            }
            if heading_text.lower() in skip_headings:
                continue

            # Detect type of entry
            entry_type = "Section"

            # Function signatures often have parentheses
            if "(" in heading_text and ")" in heading_text:
                entry_type = "Function"
                # Clean up the name
                heading_text = heading_text.split("(")[0].strip()
            # Type definitions
            elif heading_text[0].isupper() and not " " in heading_text:
                entry_type = "Type"
            # Properties often start with lowercase
            elif heading_text[0].islower() and not " " in heading_text:
                entry_type = "Property"

            yield IndexEntry(
                name=f"{parent_name}.{heading_text}"
                if entry_type in ["Property", "Function"]
                else heading_text,
                entry_type=entry_type,
                path=f"{relative_path}#{heading_id}",
            )


class UtilitiesParser:
    """Parser for Raycast utilities pages.

    These are pages like:
    - utilities/functions/showfailuretoast.md
    - utilities/react-hooks/usepromise.md
    """

    PATH_PATTERN = re.compile(r"utilities/")

    def matches(self, relative_path: str) -> bool:
        """Check if this parser handles the given path."""
        return bool(self.PATH_PATTERN.search(relative_path))

    def parse(self, file_path: Path, relative_path: str) -> Iterator[IndexEntry]:
        """Parse a utilities page and yield index entries."""
        soup = parse_html_file(file_path)
        title = get_title_from_soup(soup)

        if not title:
            return

        # Determine entry type
        if "react-hooks" in relative_path or title.startswith("use"):
            entry_type = "Function"
        elif "functions" in relative_path:
            entry_type = "Function"
        elif "icons" in relative_path:
            entry_type = "Function"
        elif "oauth" in relative_path:
            entry_type = "Class"
        else:
            entry_type = "Function"

        yield IndexEntry(
            name=title,
            entry_type=entry_type,
            path=relative_path,
        )


class GuideParser:
    """Parser for guide and tutorial pages."""

    # Patterns for different guide types
    BASICS_PATTERN = re.compile(r"basics/")
    AI_PATTERN = re.compile(r"ai/")
    TEAMS_PATTERN = re.compile(r"teams/")
    EXAMPLES_PATTERN = re.compile(r"examples/")
    INFO_PATTERN = re.compile(r"information/")

    def matches(self, relative_path: str) -> bool:
        """Check if this parser handles the given path."""
        return any(
            pattern.search(relative_path)
            for pattern in [
                self.BASICS_PATTERN,
                self.AI_PATTERN,
                self.TEAMS_PATTERN,
                self.EXAMPLES_PATTERN,
                self.INFO_PATTERN,
            ]
        )

    def parse(self, file_path: Path, relative_path: str) -> Iterator[IndexEntry]:
        """Parse a guide page and yield index entries."""
        soup = parse_html_file(file_path)
        title = get_title_from_soup(soup)

        if not title:
            return

        # Determine entry type based on path
        if self.EXAMPLES_PATTERN.search(relative_path):
            entry_type = "Sample"
        else:
            entry_type = "Guide"

        yield IndexEntry(
            name=title,
            entry_type=entry_type,
            path=relative_path,
        )


class MiscParser:
    """Parser for miscellaneous pages (changelog, migration, FAQ)."""

    PATH_PATTERN = re.compile(r"misc/")

    def matches(self, relative_path: str) -> bool:
        """Check if this parser handles the given path."""
        return bool(self.PATH_PATTERN.search(relative_path))

    def parse(self, file_path: Path, relative_path: str) -> Iterator[IndexEntry]:
        """Parse a misc page and yield index entries."""
        soup = parse_html_file(file_path)
        title = get_title_from_soup(soup)

        if not title:
            return

        # Migration guides
        if "migration" in relative_path:
            entry_type = "Guide"
        # Changelog
        elif "changelog" in relative_path:
            entry_type = "Section"
        # FAQ
        elif "faq" in relative_path:
            entry_type = "Guide"
        else:
            entry_type = "Guide"

        yield IndexEntry(
            name=title,
            entry_type=entry_type,
            path=relative_path,
        )


class DashAnchorParser:
    """Parser that extracts dashAnchor entries embedded in HTML.

    Our TOC injector creates anchors like:
    <a name="//apple_ref/cpp/Section/Name" class="dashAnchor"></a>
    """

    ANCHOR_PATTERN = re.compile(r"//apple_ref/(?:cpp/)?(\w+)/(.+)")

    # Generic/noisy entries to skip
    SKIP_NAMES = {
        "example",
        "examples",
        "see also",
        "signature",
        "return",
        "returns",
        "parameters",
        "props",
        "properties",
    }

    def matches(self, relative_path: str) -> bool:
        """Match any HTML file."""
        return relative_path.endswith(".html")

    def parse(self, file_path: Path, relative_path: str) -> Iterator[IndexEntry]:
        """Extract dashAnchor entries from the HTML."""
        soup = parse_html_file(file_path)

        for anchor in soup.find_all("a", class_="dashAnchor"):
            name_attr = anchor.get("name", "")
            if not isinstance(name_attr, str):
                continue
            match = self.ANCHOR_PATTERN.match(name_attr)

            if match:
                entry_type = match.group(1)
                entry_name = unquote(match.group(2))

                if entry_name.lower() in self.SKIP_NAMES:
                    continue

                # Find anchor ID
                anchor_id = None
                next_sibling = anchor.find_next_sibling()
                if next_sibling and next_sibling.get("id"):
                    anchor_id = next_sibling.get("id")

                path = relative_path
                if anchor_id:
                    path = f"{relative_path}#{anchor_id}"

                if len(entry_name) > 80:
                    entry_name = entry_name[:77] + "..."

                yield IndexEntry(
                    name=entry_name,
                    entry_type=entry_type,
                    path=path,
                )


class FallbackParser:
    """Fallback parser for any HTML page not matched by other parsers."""

    def matches(self, relative_path: str) -> bool:
        """Match documentation HTML files."""
        if not relative_path.endswith(".html"):
            return False
        # Only match raycast docs
        return "developers.raycast.com" in relative_path

    def parse(self, file_path: Path, relative_path: str) -> Iterator[IndexEntry]:
        """Parse any documentation page as a generic entry."""
        soup = parse_html_file(file_path)
        title = get_title_from_soup(soup)

        if title and title not in ["Raycast API", "Raycast"]:
            yield IndexEntry(
                name=title,
                entry_type="Guide",
                path=relative_path,
            )


# All parsers in order of specificity
ALL_PARSERS = [
    DashAnchorParser(),
    APIReferenceParser(),
    UtilitiesParser(),
    GuideParser(),
    MiscParser(),
    FallbackParser(),
]
