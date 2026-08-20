import requests
from urllib.parse import quote

def crossref_search(reference, rows=5):
    url = (
        "https://api.crossref.org/works"
        f"?query.bibliographic={quote(reference)}"
        f"&rows={rows}"
        "&filter=type:journal-article"
    )
    response = requests.get(
        url,
        headers={"User-Agent": "Reference-RIS-Finder/1.0"},
        timeout=20
    )
    response.raise_for_status()
    return response.json()["message"]["items"]

def crossref_to_ris(item):
    lines = []
    lines.append("TY  - JOUR")
    for author in item.get("author", []):
        family = author.get("family", "")
        given = author.get("given", "")
        lines.append(f"AU  - {family}, {given}")
    titles = item.get("title", [])
    if titles:
        lines.append(f"TI  - {titles[0]}")
    journals = item.get("container-title", [])
    if journals:
        lines.append(f"JO  - {journals[0]}")
    if "volume" in item:
        lines.append(f"VL  - {item['volume']}")
    if "issue" in item:
        lines.append(f"IS  - {item['issue']}")
    pages = item.get("page", "")
    if pages:
        page_parts = pages.replace("–", "-").split("-")
        lines.append(f"SP  - {page_parts[0]}")
        if len(page_parts) > 1:
            lines.append(f"EP  - {page_parts[1]}")
    year = None
    for key in ["published-print", "published-online", "published"]:
        if key in item:
            try:
                year = item[key]["date-parts"][0][0]
                break
            except Exception:
                pass
    if year:
        lines.append(f"PY  - {year}")
    if "DOI" in item:
        lines.append(f"DO  - {item['DOI']}")
    lines.append("ER  -")
    return "\n".join(lines)

if __name__ == "__main__":
    ref = (
        "Dobre, A., Arnold, S.J., Smalley, R.J., Boddy, J.W.D., "
        "Barlow, J.F., Tomlin, A.S., Belcher, S.E., 2005. "
        "Flow field measurements in the proximity of an urban intersection in"
    )
    results = crossref_search(ref, rows=5)
    best = results[0]
    print(f"Score: {best['score']}")
    print(crossref_to_ris(best))