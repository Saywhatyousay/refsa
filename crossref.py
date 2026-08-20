"""Crossref 检索与字段提取。逻辑从 test.py 原样移植，仅将输出由 RIS 改为 Zotero JSON 映射。"""
import requests
from urllib.parse import quote

import config


def crossref_search(reference: str) -> list:
    """调用 Crossref API，返回候选文献 item 列表（含 score）。"""
    url = (
        config.CROSSREF_URL
        + f"?query.bibliographic={quote(reference)}"
        + f"&rows={config.CROSSREF_ROWS}"
        + "&filter=type:journal-article"
    )
    response = requests.get(
        url,
        headers={"User-Agent": config.CROSSREF_UA},
        timeout=config.CROSSREF_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()["message"]["items"]


def _extract_year(item):
    for key in ["published-print", "published-online", "published"]:
        if key in item:
            try:
                return item[key]["date-parts"][0][0]
            except Exception:
                pass
    return None


def best_match(candidates: list):
    """返回 score 最高的候选；无候选返回 None。"""
    if not candidates:
        return None
    return max(candidates, key=lambda it: it.get("score", 0))


def to_zotero_fields(item: dict) -> dict:
    """把单个 Crossref item 映射为 Zotero journalArticle 字段。缺失字段不伪造。"""
    fields = {"itemType": "journalArticle"}

    titles = item.get("title") or []
    if titles:
        fields["title"] = titles[0]

    creators = []
    for author in item.get("author", []):
        family = author.get("family", "")
        given = author.get("given", "")
        if not family and not given:
            continue
        creators.append({
            "creatorType": "author",
            "firstName": given,
            "lastName": family,
        })
    if creators:
        fields["creators"] = creators

    journals = item.get("container-title") or []
    if journals:
        fields["publicationTitle"] = journals[0]

    if "volume" in item:
        fields["volume"] = item["volume"]
    if "issue" in item:
        fields["issue"] = item["issue"]
    if "page" in item:
        fields["pages"] = item["page"]

    year = _extract_year(item)
    if year:
        fields["date"] = str(year)

    doi = item.get("DOI")
    if doi:
        fields["DOI"] = doi
        fields["url"] = f"https://doi.org/{doi}"

    return fields
