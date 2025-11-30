"""Tests for the docset verification."""

import re

import pytest


class TestNavigationElementDetection:
    """Test patterns that detect navigation elements."""

    @pytest.fixture
    def nav_pattern(self):
        """Pattern to detect header/nav/aside elements."""
        return re.compile(r'<(header|nav|aside)[^>]*>', re.IGNORECASE)

    def test_header_detected(self, nav_pattern):
        html = '<header class="site-header">Content</header>'
        assert nav_pattern.search(html)

    def test_nav_detected(self, nav_pattern):
        html = '<nav class="main-nav">Links</nav>'
        assert nav_pattern.search(html)

    def test_aside_detected(self, nav_pattern):
        html = '<aside class="sidebar">TOC</aside>'
        assert nav_pattern.search(html)

    def test_div_not_detected(self, nav_pattern):
        html = '<div class="content">Main content</div>'
        assert not nav_pattern.search(html)


class TestUnwantedContentDetection:
    """Test patterns that detect tracking/cookie scripts."""

    @pytest.fixture
    def unwanted_patterns(self):
        return [
            (re.compile(r"googletagmanager\.com", re.IGNORECASE), "Google Tag Manager"),
            (re.compile(r"google-analytics\.com", re.IGNORECASE), "Google Analytics"),
            (re.compile(r"cdn\.cookielaw\.org", re.IGNORECASE), "Cookie consent"),
            (re.compile(r"cookieconsent", re.IGNORECASE), "Cookie consent script"),
        ]

    def test_google_tag_manager_detected(self, unwanted_patterns):
        html = '<script src="https://www.googletagmanager.com/gtag/js"></script>'
        detected = [desc for pattern, desc in unwanted_patterns if pattern.search(html)]
        assert "Google Tag Manager" in detected

    def test_clean_html_not_flagged(self, unwanted_patterns):
        html = '<html><body><h1>Hello</h1></body></html>'
        detected = [desc for pattern, desc in unwanted_patterns if pattern.search(html)]
        assert detected == []


class TestTocAnchorValidation:
    """Test TOC anchor placement detection."""

    @pytest.fixture
    def bad_anchor_pattern(self):
        """Pattern to detect anchors placed before headings (bad)."""
        return re.compile(r'<a\s[^>]*dashAnchor[^>]*>\s*</a>\s*<h[123]', re.IGNORECASE)

    def test_anchor_before_heading_detected(self, bad_anchor_pattern):
        html = '<a name="//apple_ref/cpp/Section/Foo" class="dashAnchor"></a><h2>Foo</h2>'
        assert bad_anchor_pattern.search(html)

    def test_anchor_inside_heading_not_detected(self, bad_anchor_pattern):
        html = '<h2><a name="//apple_ref/cpp/Section/Foo" class="dashAnchor"></a>Foo</h2>'
        assert not bad_anchor_pattern.search(html)


class TestDashAnchorDetection:
    """Test dashAnchor element detection."""

    def test_dashanchor_class_detected(self):
        html = '<a class="dashAnchor" name="//apple_ref/cpp/Section/Test"></a>'
        assert re.search(r'class="dashAnchor"', html)

    def test_dashanchor_count(self):
        html = '''
        <h1><a class="dashAnchor"></a>Title</h1>
        <h2><a class="dashAnchor"></a>Section 1</h2>
        <h2><a class="dashAnchor"></a>Section 2</h2>
        '''
        matches = re.findall(r'class="dashAnchor"', html)
        assert len(matches) == 3
