from __future__ import annotations

import html
import json
import mimetypes
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin
from xml.etree import ElementTree

import requests

from .extraction import content_fingerprint

USER_AGENT = "dc-intel-monitor/0.2 (+configure MONITOR_CONTACT_EMAIL)"


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self.skip_depth += 1
        elif tag in {"p", "br", "li", "h1", "h2", "h3", "tr"} and not self.skip_depth:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self.skip_depth:
            self.skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self.skip_depth:
            self.parts.append(data)

    def text(self) -> str:
        value = html.unescape(" ".join(self.parts))
        value = re.sub(r"[ \t]+", " ", value)
        value = re.sub(r"\n\s*\n+", "\n", value)
        return value.strip()


@dataclass(slots=True)
class CollectedDocument:
    source_key: str
    canonical_url: str
    title: str
    published_at: str | None
    retrieved_at: str
    content_type: str
    content_hash: str
    storage_uri: str
    byte_size: int
    text: str
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def html_to_text(content: bytes) -> str:
    parser = _TextParser()
    parser.feed(content.decode("utf-8", errors="replace"))
    return parser.text()


def _extension(content_type: str, url: str) -> str:
    if "pdf" in content_type.lower() or url.lower().endswith(".pdf"):
        return ".pdf"
    guessed = mimetypes.guess_extension(content_type.split(";", 1)[0].strip())
    return guessed or ".html"


def _snapshot_path(raw_root: Path, digest: str, extension: str, retrieved_at: datetime) -> Path:
    folder = raw_root / retrieved_at.strftime("%Y") / retrieved_at.strftime("%m") / retrieved_at.strftime("%d")
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{digest}{extension}"


def _request_headers(checkpoint: dict[str, Any] | None = None) -> dict[str, str]:
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/rss+xml,application/pdf;q=0.9,*/*;q=0.8"}
    checkpoint = checkpoint or {}
    if checkpoint.get("etag"):
        headers["If-None-Match"] = str(checkpoint["etag"])
    if checkpoint.get("last_modified"):
        headers["If-Modified-Since"] = str(checkpoint["last_modified"])
    return headers


def collect_page(
    source: dict[str, Any], raw_root: str | Path = "data/raw", checkpoint: dict[str, Any] | None = None
) -> tuple[list[CollectedDocument], dict[str, Any]]:
    now = datetime.now(UTC)
    response = requests.get(source["url"], headers=_request_headers(checkpoint), timeout=45)
    if response.status_code == 304:
        return [], {**(checkpoint or {}), "checked_at": now.isoformat()}
    response.raise_for_status()
    content = response.content
    digest = content_fingerprint(content)
    next_checkpoint = {
        "etag": response.headers.get("ETag"),
        "last_modified": response.headers.get("Last-Modified"),
        "content_hash": digest,
        "checked_at": now.isoformat(),
    }
    if checkpoint and checkpoint.get("content_hash") == digest:
        return [], next_checkpoint
    content_type = response.headers.get("Content-Type", "text/html")
    extension = _extension(content_type, response.url)
    path = _snapshot_path(Path(raw_root), digest, extension, now)
    if not path.exists():
        path.write_bytes(content)
    text = "" if extension == ".pdf" else html_to_text(content)
    title_match = re.search(r"<title[^>]*>(.*?)</title>", content.decode("utf-8", errors="ignore"), re.IGNORECASE | re.DOTALL)
    title = html.unescape(re.sub(r"\s+", " ", title_match.group(1)).strip()) if title_match else source["name"]
    document = CollectedDocument(
        source_key=source["key"], canonical_url=response.url, title=title,
        published_at=None, retrieved_at=now.isoformat(), content_type=content_type,
        content_hash=digest, storage_uri=path.as_posix(), byte_size=len(content), text=text,
        metadata={"http_headers": dict(response.headers), "collection_method": "page"},
    )
    return [document], next_checkpoint


def _rss_items(content: bytes, base_url: str) -> list[dict[str, str | None]]:
    root = ElementTree.fromstring(content)
    items = root.findall(".//item")
    if not items:
        items = root.findall(".//{http://www.w3.org/2005/Atom}entry")
    results = []
    for item in items:
        title = item.findtext("title") or item.findtext("{http://www.w3.org/2005/Atom}title") or "Untitled"
        link = item.findtext("link")
        if not link:
            link_node = item.find("{http://www.w3.org/2005/Atom}link")
            link = link_node.attrib.get("href") if link_node is not None else base_url
        description = (
            item.findtext("description")
            or item.findtext("{http://www.w3.org/2005/Atom}summary")
            or item.findtext("{http://www.w3.org/2005/Atom}content")
            or ""
        )
        published = item.findtext("pubDate") or item.findtext("{http://www.w3.org/2005/Atom}updated")
        results.append({"title": title.strip(), "link": urljoin(base_url, link or ""), "text": html_to_text(description.encode()), "published_at": published})
    return results


def collect_rss(
    source: dict[str, Any], raw_root: str | Path = "data/raw", checkpoint: dict[str, Any] | None = None
) -> tuple[list[CollectedDocument], dict[str, Any]]:
    now = datetime.now(UTC)
    response = requests.get(source["url"], headers=_request_headers(checkpoint), timeout=45)
    if response.status_code == 304:
        return [], {**(checkpoint or {}), "checked_at": now.isoformat()}
    response.raise_for_status()
    feed_hash = content_fingerprint(response.content)
    documents: list[CollectedDocument] = []
    for item in _rss_items(response.content, response.url):
        serialized = json.dumps(item, sort_keys=True).encode()
        digest = content_fingerprint(serialized)
        path = _snapshot_path(Path(raw_root), digest, ".json", now)
        if not path.exists():
            path.write_bytes(serialized)
        documents.append(CollectedDocument(
            source_key=source["key"], canonical_url=str(item["link"]), title=str(item["title"]),
            published_at=item["published_at"], retrieved_at=now.isoformat(), content_type="application/feed+json",
            content_hash=digest, storage_uri=path.as_posix(), byte_size=len(serialized), text=str(item["text"]),
            metadata={"feed_url": response.url, "collection_method": "rss"},
        ))
    next_checkpoint = {
        "etag": response.headers.get("ETag"), "last_modified": response.headers.get("Last-Modified"),
        "content_hash": feed_hash, "checked_at": now.isoformat(),
    }
    return documents, next_checkpoint


COLLECTORS = {"page": collect_page, "rss": collect_rss, "pdf_index": collect_page, "api": collect_page}


def collect_source(source: dict[str, Any], raw_root: str | Path = "data/raw", checkpoint: dict[str, Any] | None = None):
    method = source.get("method", "page")
    if method not in COLLECTORS:
        raise ValueError(f"Unsupported collection method {method!r} for {source['key']}")
    return COLLECTORS[method](source, raw_root, checkpoint)
