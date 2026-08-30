from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.request import Request, urlopen
from xml.etree import ElementTree

DEFAULT_RSS_URL = (
    "https://news.google.com/rss/search?"
    "q=US%20stock%20market%20when%3A1d&hl=en-US&gl=US&ceid=US%3Aen"
)
MAX_FEED_BYTES = 2_000_000


@dataclass(frozen=True)
class FeedItem:
    fingerprint: str
    title: str
    link: str
    published_at: str | None
    source_url: str


def fetch_feed(url: str, timeout: int = 20) -> tuple[FeedItem, ...]:
    request = Request(url, headers={"User-Agent": "MacroPulse/0.1 (+RSS monitor)"})
    with urlopen(request, timeout=timeout) as response:
        payload = response.read(MAX_FEED_BYTES + 1)
    if len(payload) > MAX_FEED_BYTES:
        raise ValueError("RSS response exceeds 2 MB safety limit")
    return parse_feed(payload, url)


def parse_feed(payload: bytes, source_url: str) -> tuple[FeedItem, ...]:
    root = ElementTree.fromstring(payload)
    nodes = root.findall(".//item")
    if not nodes:
        nodes = root.findall(".//{http://www.w3.org/2005/Atom}entry")

    items: list[FeedItem] = []
    for node in nodes:
        title = _text(node, "title")
        link = _link(node)
        if not title or not link:
            continue
        identifier = _text(node, "guid") or _text(node, "id") or link
        published = _text(node, "pubDate") or _text(node, "published") or _text(node, "updated")
        items.append(
            FeedItem(
                fingerprint=hashlib.sha256(identifier.encode("utf-8")).hexdigest(),
                title=" ".join(title.split()),
                link=link.strip(),
                published_at=_normalise_date(published),
                source_url=source_url,
            )
        )
    # Most feeds are newest-first, but normalising here makes that contract explicit.
    return tuple(sorted(items, key=lambda item: item.published_at or "", reverse=True))


def _text(node: ElementTree.Element, local_name: str) -> str:
    for child in node.iter():
        if child.tag.rsplit("}", 1)[-1] == local_name and child.text:
            return child.text.strip()
    return ""


def _link(node: ElementTree.Element) -> str:
    for child in node.iter():
        if child.tag.rsplit("}", 1)[-1] != "link":
            continue
        href = child.attrib.get("href")
        if href:
            return href
        if child.text:
            return child.text
    return ""


def _normalise_date(value: str) -> str | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()
