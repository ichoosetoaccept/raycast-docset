# Raycast Docset Generator

Generate a [Dash](https://kapeli.com/dash) docset for [Raycast developer documentation](https://developers.raycast.com/).

## Features

- Scrapes all documentation from developers.raycast.com
- Creates a properly indexed Dash docset with semantic search
- Indexes API references, utilities, hooks, guides, and examples
- Supports offline documentation browsing

## Requirements

- Python 3.14+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd raycast-docset

# Install dependencies with uv
uv sync
```

## Usage

### Scrape and build docset

```bash
# Scrape docs from developers.raycast.com and build docset
uv run python main.py --scrape

# Or specify a custom output directory
uv run python main.py --scrape --output ./my-output
```

### Build from existing scraped docs

```bash
# If you've already scraped the docs
uv run python main.py --source .cache/raycast-docs
```

## Output

The generated docset will be at `output/Raycast.docset`.

To install in Dash:
1. Open Dash
2. Go to Preferences > Docsets
3. Click + and select the `.docset` file

Or simply double-click the `.docset` file.

## Project Structure

```
raycast-docset/
├── main.py                 # CLI entry point
├── raycast_docset/
│   ├── __init__.py
│   ├── scraper.py          # Web scraper for docs
│   ├── builder.py          # Docset builder
│   └── parsers.py          # Index entry parsers
├── pyproject.toml
└── README.md
```

## License

MIT
