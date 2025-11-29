#!/usr/bin/env python3
"""
Raycast Docset Generator for Dash.

This tool creates a Dash docset from Raycast developer documentation,
with semantic indexing for better search results.
"""

import argparse
import shutil
import sys
from pathlib import Path

from raycast_docset.builder import build_docset
from raycast_docset.scraper import scrape_raycast_docs


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a Dash docset for Raycast developer documentation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scrape docs from developers.raycast.com and build docset
  python main.py --scrape

  # Scrape and specify output directory
  python main.py --scrape --output ./output

  # Build from existing scraped docs
  python main.py --source .cache/raycast-docs
        """,
    )

    parser.add_argument(
        "--scrape",
        action="store_true",
        help="Scrape documentation directly from developers.raycast.com",
    )

    parser.add_argument(
        "--source",
        type=Path,
        help="Path to existing scraped documentation (alternative to --scrape)",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path.cwd() / "output",
        help="Output directory for the generated docset (default: ./output)",
    )

    parser.add_argument(
        "--name",
        default="Raycast",
        help="Name for the docset (default: Raycast)",
    )

    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path.cwd() / ".cache" / "raycast-docs",
        help="Directory to cache scraped docs (default: .cache/raycast-docs)",
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.scrape and not args.source:
        print("Error: Either --scrape or --source must be provided", file=sys.stderr)
        print("Run 'python main.py --help' for usage examples", file=sys.stderr)
        return 1

    if args.scrape and args.source:
        print("Error: Cannot use both --scrape and --source", file=sys.stderr)
        return 1

    # Create output directory
    args.output.mkdir(parents=True, exist_ok=True)

    try:
        # If scraping, download docs first
        if args.scrape:
            print("=" * 60)
            print("STEP 1: Scraping Raycast documentation")
            print("=" * 60)
            print()

            scrape_raycast_docs(output_dir=args.cache_dir)

            # Create a docset structure with the scraped docs
            source_path = args.cache_dir / "Raycast.docset"
            source_path.mkdir(parents=True, exist_ok=True)

            # Create Contents/Resources directory
            resources_dir = source_path / "Contents" / "Resources" / "Documents"
            resources_dir.mkdir(parents=True, exist_ok=True)

            # Copy scraped docs into the docset structure
            docs_dir = args.cache_dir / "developers.raycast.com"
            if docs_dir.exists():
                dest = resources_dir / "developers.raycast.com"
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(docs_dir, dest)

            print()
            print("=" * 60)
            print("STEP 2: Building Dash docset with enhanced indexing")
            print("=" * 60)
            print()

            source = source_path
        else:
            # Use provided source path
            source = args.source
            if not source.exists():
                print(f"Error: Source not found: {source}", file=sys.stderr)
                return 1

            # If source is a raw docs directory, wrap it in docset structure
            if not (source / "Contents").exists():
                temp_source = args.cache_dir / "Raycast.docset"
                temp_source.mkdir(parents=True, exist_ok=True)
                resources_dir = temp_source / "Contents" / "Resources" / "Documents"
                resources_dir.mkdir(parents=True, exist_ok=True)

                dest = resources_dir / "developers.raycast.com"
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(source, dest)
                source = temp_source

        # Build the docset
        docset_path = build_docset(
            source_docset_path=source,
            output_dir=args.output,
            docset_name=args.name,
        )

        print()
        print("=" * 60)
        print("SUCCESS!")
        print("=" * 60)
        print(f"\nDocset created at: {docset_path}")
        print("\nTo install in Dash:")
        print("  1. Open Dash")
        print("  2. Go to Preferences > Docsets")
        print(f"  3. Click + and select '{docset_path}'")
        print("\nOr double-click the .docset file to install it.")
        return 0

    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
