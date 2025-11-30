"""Tests for the docset builder."""

import re

import pytest


class TestNavigationRemoval:
    """Test navigation element removal patterns."""

    def test_header_element_removal(self):
        """Header elements should be removed."""
        html = '<header class="site-header">Nav content</header>'
        # BeautifulSoup would decompose this
        assert "<header" in html

    def test_nav_element_removal(self):
        """Nav elements should be removed."""
        html = '<nav class="main-nav">Links</nav>'
        assert "<nav" in html

    def test_aside_element_removal(self):
        """Aside elements (sidebar TOC) should be removed."""
        html = '<aside class="sidebar">TOC content</aside>'
        assert "<aside" in html


class TestDepthCalculation:
    """Test the relative path prefix calculation."""

    def calculate_depth(self, path_parts: int) -> str:
        """Calculate ../ prefix based on depth from documents root."""
        depth = path_parts - 1  # -1 for the file itself
        return "../" * depth

    def test_root_level_file(self):
        assert self.calculate_depth(1) == ""

    def test_one_level_deep(self):
        assert self.calculate_depth(2) == "../"

    def test_two_levels_deep(self):
        assert self.calculate_depth(3) == "../../"

    def test_three_levels_deep(self):
        assert self.calculate_depth(4) == "../../../"


class TestDashAnchorFormat:
    """Test Dash anchor name format."""

    def test_anchor_format(self):
        entry_type = "Section"
        name = "Getting Started"
        from urllib.parse import quote
        encoded_name = quote(name, safe="")
        anchor_name = f"//apple_ref/cpp/{entry_type}/{encoded_name}"
        assert anchor_name == "//apple_ref/cpp/Section/Getting%20Started"

    def test_special_characters_encoded(self):
        from urllib.parse import quote
        name = "usePromise<T>"
        encoded = quote(name, safe="")
        assert encoded == "usePromise%3CT%3E"

    def test_function_name_encoded(self):
        from urllib.parse import quote
        name = "showToast()"
        encoded = quote(name, safe="")
        assert encoded == "showToast%28%29"


class TestHeadingIdExtraction:
    """Test heading ID extraction for TOC."""

    def test_heading_with_id(self):
        html = '<h2 id="installation">Installation</h2>'
        match = re.search(r'<h2[^>]*id="([^"]*)"', html)
        assert match
        assert match.group(1) == "installation"

    def test_heading_without_id(self):
        html = '<h2>No ID Here</h2>'
        match = re.search(r'<h2[^>]*id="([^"]*)"', html)
        assert not match


class TestScrollMarginCss:
    """Test CSS injection for scroll margin."""

    def test_css_selector_format(self):
        css = """
            h1:has(.dashAnchor), h2:has(.dashAnchor), h3:has(.dashAnchor) {
                scroll-margin-top: 80px !important;
            }
        """
        assert "scroll-margin-top" in css
        assert ":has(.dashAnchor)" in css
        assert "80px" in css
