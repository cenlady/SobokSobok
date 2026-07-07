from __future__ import annotations

import re
import ssl
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup, Tag


@dataclass(frozen=True)
class SemasProgramLink:
    title: str
    url: str


@dataclass(frozen=True)
class SemasProgramPage:
    source_url: str
    category: str | None
    program_name: str
    content_html: str
    content_text: str
    sections: list[dict[str, str]]
    breadcrumbs: list[str]


class SemasClient:
    """Client for SEMAS support-program guide pages.

    SEMAS pages are regular HTML pages, so this crawler follows public
    `/web/SUP01/...kmdc` links and extracts the visible program body.
    """

    BASE_URL = "https://www.semas.or.kr"

    def __init__(self, timeout: float = 30.0):
        self._client = httpx.Client(
            base_url=self.BASE_URL,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.7,en;q=0.6",
                "Referer": "https://www.semas.or.kr/",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0 Safari/537.36"
                ),
            },
            follow_redirects=True,
            verify=self._build_ssl_context(),
            timeout=timeout,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "SemasClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def fetch_program_links(self, seed_url: str) -> list[SemasProgramLink]:
        html = self.fetch_html(seed_url)
        soup = BeautifulSoup(html, "html.parser")
        links: list[SemasProgramLink] = []
        seen: set[str] = set()

        for anchor in soup.find_all("a", href=True):
            href = str(anchor.get("href") or "")
            url = self._normalize_support_url(urljoin(seed_url, href))
            if url is None or url in seen:
                continue

            title = self._clean_text(anchor.get_text(" ", strip=True))
            if not title:
                title = urlparse(url).path.rsplit("/", 1)[-1]
            links.append(SemasProgramLink(title=title, url=url))
            seen.add(url)

        return links

    def fetch_program_page(self, url: str) -> SemasProgramPage:
        normalized_url = self._normalize_support_url(url) or url
        html = self.fetch_html(normalized_url)
        soup = BeautifulSoup(html, "html.parser")
        contents = soup.select_one("div.contents")
        if contents is None:
            raise ValueError(f"SEMAS content container not found: {normalized_url}")

        breadcrumbs = self._extract_breadcrumbs(contents)
        program_name = self._extract_title(soup=soup, contents=contents, breadcrumbs=breadcrumbs)
        category = breadcrumbs[-2] if len(breadcrumbs) >= 2 else None
        body = BeautifulSoup(str(contents), "html.parser")
        self._remove_noise(body)
        content_root = body.select_one("div.contents") or body
        content_html = str(content_root)
        content_text = self._clean_text(content_root.get_text("\n", strip=True))
        sections = self._extract_sections(content_root)

        return SemasProgramPage(
            source_url=normalized_url,
            category=category,
            program_name=program_name,
            content_html=content_html,
            content_text=content_text,
            sections=sections,
            breadcrumbs=breadcrumbs,
        )

    def fetch_html(self, url: str) -> str:
        response = self._client.get(url)
        response.raise_for_status()
        return response.text

    def _normalize_support_url(self, url: str) -> str | None:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return None
        if parsed.netloc and parsed.netloc != "www.semas.or.kr":
            return None
        if not parsed.path.startswith("/web/SUP01/"):
            return None
        if not parsed.path.endswith(".kmdc"):
            return None
        return urlunparse(("https", "www.semas.or.kr", parsed.path, "", parsed.query, ""))

    def _extract_breadcrumbs(self, contents: Tag) -> list[str]:
        location = contents.select_one(".location")
        if location is None:
            return []

        crumbs: list[str] = []
        for anchor in location.find_all("a"):
            text = self._clean_text(anchor.get_text(" ", strip=True))
            if text and text != "홈":
                crumbs.append(text)
        return crumbs

    def _extract_title(
        self,
        soup: BeautifulSoup,
        contents: Tag,
        breadcrumbs: list[str],
    ) -> str:
        heading = contents.select_one(".location h3")
        if heading is not None:
            text = self._clean_text(heading.get_text(" ", strip=True))
            if text:
                return text
        if breadcrumbs:
            return breadcrumbs[-1]
        if soup.title and soup.title.string:
            return self._clean_text(soup.title.string.split("〉")[-1])
        return "SEMAS 지원사업"

    def _remove_noise(self, soup: BeautifulSoup) -> None:
        for selector in [".location", ".box_satis", "script", "style", "form"]:
            for node in soup.select(selector):
                node.decompose()

    def _extract_sections(self, contents: Tag) -> list[dict[str, str]]:
        sections: list[dict[str, str]] = []
        for block in contents.select("dl.dl_sty_2"):
            title_node = block.find("dt")
            body_node = block.find("dd")
            if title_node is None or body_node is None:
                continue
            title = self._clean_text(title_node.get_text(" ", strip=True))
            body = self._clean_text(body_node.get_text("\n", strip=True))
            if title or body:
                sections.append({"title": title, "body": body})
        return sections

    def _build_ssl_context(self) -> ssl.SSLContext:
        context = ssl.create_default_context()
        # SEMAS는 Docker의 OpenSSL 3 기본 보안레벨에서 TLS handshake가 실패한다.
        # 인증서 검증은 유지하되 허용 cipher 보안레벨만 낮춰 호환성을 맞춘다.
        context.set_ciphers("DEFAULT@SECLEVEL=1")
        return context

    def _clean_text(self, value: str) -> str:
        return re.sub(r"\s+", " ", value or "").strip()
