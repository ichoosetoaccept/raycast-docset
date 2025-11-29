"""Docset builder - creates the Dash docset structure and SQLite index."""

import re
import shutil
import sqlite3
from io import BytesIO
from pathlib import Path
from typing import Iterator
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup
from PIL import Image

from .parsers import ALL_PARSERS, IndexEntry


# Info.plist template for the docset
INFO_PLIST_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleIdentifier</key>
    <string>{identifier}</string>
    <key>CFBundleName</key>
    <string>{name}</string>
    <key>DocSetPlatformFamily</key>
    <string>{family}</string>
    <key>isDashDocset</key>
    <true/>
    <key>isJavaScriptEnabled</key>
    <false/>
    <key>dashIndexFilePath</key>
    <string>{index_path}</string>
    <key>DashDocSetKeyword</key>
    <string>{keyword}</string>
    <key>DashDocSetFallbackURL</key>
    <string>{fallback_url}</string>
    <key>DashDocSetFamily</key>
    <string>dashtoc</string>
</dict>
</plist>
"""


class DocsetBuilder:
    """Builds a Dash docset from existing HTML documentation."""

    def __init__(
        self,
        source_docs_dir: Path,
        output_dir: Path,
        docset_name: str = "Raycast",
    ):
        self.source_docs_dir = source_docs_dir
        self.output_dir = output_dir
        self.docset_name = docset_name

        # Docset paths
        self.docset_dir = output_dir / f"{docset_name}.docset"
        self.contents_dir = self.docset_dir / "Contents"
        self.resources_dir = self.contents_dir / "Resources"
        self.documents_dir = self.resources_dir / "Documents"
        self.db_path = self.resources_dir / "docSet.dsidx"

    def build(self) -> None:
        """Build the complete docset."""
        print(f"Building {self.docset_name} docset...")

        # Create directory structure
        self._create_structure()

        # Copy HTML files
        self._copy_documents()

        # Create Info.plist
        self._create_info_plist()

        # Copy or download icon
        self._setup_icon()

        # Create SQLite index
        self._create_index()

        print(f"Docset created at: {self.docset_dir}")

    def _create_structure(self) -> None:
        """Create the docset directory structure."""
        print("Creating directory structure...")

        # Remove existing docset if present
        if self.docset_dir.exists():
            shutil.rmtree(self.docset_dir)

        # Create directories
        self.documents_dir.mkdir(parents=True)

    def _copy_documents(self) -> None:
        """Copy HTML documentation to the docset, injecting TOC anchors."""
        print("Copying documentation files...")

        # Look for raycast docs
        raycast_docs_source = self.source_docs_dir / "developers.raycast.com"

        if raycast_docs_source.exists():
            source_root = raycast_docs_source
            dest_root = self.documents_dir / "developers.raycast.com"
        else:
            source_root = self.source_docs_dir
            dest_root = self.documents_dir

        # Copy all files, processing HTML files for TOC injection
        html_count = 0
        for source_file in source_root.rglob("*"):
            if source_file.is_dir():
                continue

            relative = source_file.relative_to(source_root)
            dest_file = dest_root / relative
            dest_file.parent.mkdir(parents=True, exist_ok=True)

            if source_file.suffix == ".html":
                # Process HTML files to inject TOC anchors
                self._copy_html_with_toc(source_file, dest_file)
                html_count += 1
                if html_count % 50 == 0:
                    print(f"  Processed {html_count} HTML files...")
            else:
                # Copy other files directly
                shutil.copy2(source_file, dest_file)

        print(f"  Processed {html_count} HTML files with TOC injection")

    def _copy_html_with_toc(self, source_file: Path, dest_file: Path) -> None:
        """Copy an HTML file, injecting dashAnchor elements for TOC support."""
        try:
            content = source_file.read_text(encoding="utf-8", errors="replace")

            # Fix paths before parsing
            content = self._fix_paths(content, dest_file)

            soup = BeautifulSoup(content, "lxml")

            # Remove navigation elements that have broken links in offline docset
            # Remove header/navbar
            for header in soup.find_all("header"):
                header.decompose()
            # Remove any nav elements with site navigation
            for nav in soup.find_all("nav"):
                nav.decompose()
            # Remove aside elements (left sidebar TOC - we use Dash's TOC instead)
            for aside in soup.find_all("aside"):
                aside.decompose()

            # Find all headings with IDs (h1, h2, h3)
            for heading in soup.find_all(["h1", "h2", "h3"], id=True):
                heading_id = heading.get("id")
                heading_text = heading.get_text().strip()

                if not heading_id or not heading_text:
                    continue

                # Skip common navigation headings
                skip_headings = {"see also", "example", "examples"}
                if heading_text.lower() in skip_headings:
                    continue

                # Determine entry type based on heading level
                if heading.name == "h1":
                    entry_type = "Guide"
                elif heading.name == "h2":
                    entry_type = "Section"
                else:
                    entry_type = "Section"

                # URL encode the name for the anchor
                encoded_name = quote(heading_text, safe="")

                # Create dashAnchor element
                anchor = soup.new_tag("a")
                anchor["name"] = f"//apple_ref/cpp/{entry_type}/{encoded_name}"
                anchor["class"] = "dashAnchor"

                # Insert anchor inside the heading (at the start) so the heading isn't cut off
                heading.insert(0, anchor)

            # Inject CSS to fix scroll margin when navigating via TOC
            style_tag = soup.new_tag("style")
            style_tag.string = """
                h1:has(.dashAnchor), h2:has(.dashAnchor), h3:has(.dashAnchor) {
                    scroll-margin-top: 80px !important;
                }
            """
            if soup.head:
                soup.head.append(style_tag)

            # Write modified HTML
            dest_file.write_text(str(soup), encoding="utf-8")

        except Exception:
            # If processing fails, just copy the file as-is
            shutil.copy2(source_file, dest_file)

    def _fix_paths(self, content: str, dest_file: Path) -> str:
        """Fix paths in HTML content for offline viewing.

        Args:
            content: HTML content to fix
            dest_file: Destination file path

        Returns:
            HTML content with fixed paths
        """
        # Calculate depth from documents root
        try:
            relative_to_docs = dest_file.relative_to(self.documents_dir)
            depth = len(relative_to_docs.parts) - 1
        except ValueError:
            depth = 0

        prefix = "../" * depth

        # Remove analytics scripts
        content = re.sub(
            r"<script[^>]*googletagmanager[^>]*>.*?</script>",
            "",
            content,
            flags=re.DOTALL | re.IGNORECASE,
        )
        content = re.sub(
            r"<script[^>]*google-analytics[^>]*>.*?</script>",
            "",
            content,
            flags=re.DOTALL | re.IGNORECASE,
        )

        # Remove GitBook cookie consent and tracking scripts
        content = re.sub(
            r"<script[^>]*gitbook[^>]*>.*?</script>",
            "",
            content,
            flags=re.DOTALL | re.IGNORECASE,
        )
        # Remove inline scripts that reference cookies/consent
        content = re.sub(
            r"<script[^>]*>[^<]*cookie[^<]*</script>",
            "",
            content,
            flags=re.DOTALL | re.IGNORECASE,
        )
        # Remove any elements with cookie-related classes
        content = re.sub(
            r'<div[^>]*class="[^"]*cookie[^"]*"[^>]*>.*?</div>',
            "",
            content,
            flags=re.DOTALL | re.IGNORECASE,
        )

        return content

    def _setup_icon(self) -> None:
        """Set up the docset icon."""
        # Try to download Raycast icon
        self._download_raycast_icon()

    def _download_raycast_icon(self) -> None:
        """Download and create Raycast icons in required sizes."""
        print("Downloading Raycast icon...")

        # Raycast logo from their website
        icon_url = "https://www.raycast.com/favicon-production.png"

        try:
            response = requests.get(icon_url, timeout=30)
            response.raise_for_status()

            # Open the image
            img = Image.open(BytesIO(response.content))

            # Convert to RGBA if necessary
            if img.mode != "RGBA":
                img = img.convert("RGBA")

            # Create 16x16 icon
            icon_16 = img.resize((16, 16), Image.Resampling.LANCZOS)
            icon_16.save(self.docset_dir / "icon.png", "PNG")

            # Create 32x32 icon
            icon_32 = img.resize((32, 32), Image.Resampling.LANCZOS)
            icon_32.save(self.docset_dir / "icon@2x.png", "PNG")

            print("Created icon.png (16x16) and icon@2x.png (32x32)")

        except Exception as e:
            print(f"Warning: Could not download icon: {e}")

    def _create_info_plist(self) -> None:
        """Create the Info.plist file."""
        print("Creating Info.plist...")

        plist_content = INFO_PLIST_TEMPLATE.format(
            identifier="raycast",
            name=self.docset_name,
            family="raycast",
            index_path="developers.raycast.com/index.html",
            keyword="raycast",
            fallback_url="https://developers.raycast.com/",
        )

        plist_path = self.contents_dir / "Info.plist"
        plist_path.write_text(plist_content)

    def _create_index(self) -> None:
        """Create the SQLite search index."""
        print("Creating search index...")

        # Create database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create table
        cursor.execute("""
            CREATE TABLE searchIndex(
                id INTEGER PRIMARY KEY,
                name TEXT,
                type TEXT,
                path TEXT
            )
        """)

        # Create unique index to prevent duplicates
        cursor.execute("""
            CREATE UNIQUE INDEX anchor ON searchIndex (name, type, path)
        """)

        # Index all documents
        entries_count = 0
        for entry in self._collect_entries():
            try:
                cursor.execute(
                    "INSERT OR IGNORE INTO searchIndex(name, type, path) VALUES (?, ?, ?)",
                    (entry.name, entry.entry_type, entry.path),
                )
                entries_count += 1
            except sqlite3.IntegrityError:
                pass  # Duplicate entry, skip

        conn.commit()
        conn.close()

        print(f"Indexed {entries_count} entries")

    def _collect_entries(self) -> Iterator[IndexEntry]:
        """Collect all index entries from the documentation."""
        docs_root = self.documents_dir

        # Find all HTML files
        html_files = list(docs_root.rglob("*.html"))
        total_files = len(html_files)

        print(f"Processing {total_files} HTML files...")

        for i, html_file in enumerate(html_files, 1):
            if i % 50 == 0:
                print(f"  Progress: {i}/{total_files} files...")

            # Get relative path from documents root
            relative_path = str(html_file.relative_to(docs_root))

            # Run ALL matching parsers
            for parser in ALL_PARSERS:
                if parser.matches(relative_path):
                    try:
                        yield from parser.parse(html_file, relative_path)
                    except Exception as e:
                        print(f"  Warning: Error parsing {relative_path}: {e}")


def build_docset(
    source_docset_path: Path,
    output_dir: Path,
    docset_name: str = "Raycast",
) -> Path:
    """Build a new Dash docset from scraped documentation.

    Args:
        source_docset_path: Path to the source documentation directory
        output_dir: Directory where the new docset will be created
        docset_name: Name for the docset

    Returns:
        Path to the created docset
    """
    # The source documents are inside Contents/Resources/Documents
    source_docs = source_docset_path / "Contents" / "Resources" / "Documents"

    if not source_docs.exists():
        raise ValueError(f"Source documents not found at {source_docs}")

    builder = DocsetBuilder(
        source_docs_dir=source_docs,
        output_dir=output_dir,
        docset_name=docset_name,
    )

    builder.build()
    return builder.docset_dir
