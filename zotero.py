"""Zotero 本地 HTTP 接口：可用性 ping 与创建 journalArticle Item。

Zotero 10 的本地写 API 使用「运行时授权」的 key（非 pref 配置）：
1. POST /api/local/authorize 弹一次授权框，选「始终允许」返回持久 key。
2. 写请求需携带 Zotero-API-Key + Zotero-Server-ID + 5~32 字符的 Zotero-Write-Token。
授权得到的 key 与 Server-ID 持久化到用户数据目录，之后不再弹框。
"""
import json
import os
import shutil
import uuid

import requests

import config

_CREDS_PATH = os.path.join(config.USER_DATA_DIR, "credentials.json")


def _migrate_legacy_data():
    """把旧的 data/ 下配置与凭证一次性迁移到用户数据目录（幂等）。"""
    for name in ("credentials.json", "refsa_config.json"):
        new_path = os.path.join(config.USER_DATA_DIR, name)
        if os.path.exists(new_path):
            continue
        old_path = os.path.join(config.LEGACY_DATA_DIR, name)
        if os.path.exists(old_path):
            os.makedirs(config.USER_DATA_DIR, exist_ok=True)
            shutil.copy2(old_path, new_path)


def _load_creds() -> dict:
    try:
        with open(_CREDS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_creds(creds: dict):
    os.makedirs(os.path.dirname(_CREDS_PATH), exist_ok=True)
    with open(_CREDS_PATH, "w", encoding="utf-8") as f:
        json.dump(creds, f)


def _items_url() -> str:
    return f"{config.ZOTERO_BASE}/api/users/{config.ZOTERO_USER_ID}/items"


def _server_id() -> str:
    """读取并缓存 Zotero-Server-ID（写操作必需）。"""
    creds = _load_creds()
    sid = creds.get("serverId")
    if sid:
        return sid
    try:
        r = requests.get(
            _items_url(),
            headers={"Zotero-API-Key": creds.get("key", "")},
            timeout=10,
        )
        sid = r.headers.get("Zotero-Server-ID")
        if sid:
            creds["serverId"] = sid
            _save_creds(creds)
        return sid
    except requests.RequestException:
        return None


def authorize() -> str:
    """请求本地写 key（会弹一次 Zotero 授权框，选「始终允许」可持久化）。"""
    sid = _server_id()
    if not sid:
        raise RuntimeError("Zotero-Server-ID unavailable, cannot authorize.")
    r = requests.post(
        f"{config.ZOTERO_BASE}/api/local/authorize",
        headers={"Zotero-Server-ID": sid},
        json={"appName": "RefSA"},
        timeout=30,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Zotero authorize failed: HTTP {r.status_code} - {r.text[:300]}")
    data = r.json()
    _save_creds({"key": data["key"], "serverId": sid, "remember": data.get("remember", False)})
    return data["key"]


def ping() -> bool:
    """检查 Zotero 本地服务是否可用。"""
    try:
        r = requests.get(f"{config.ZOTERO_BASE}/connector/ping", timeout=5)
        return r.status_code == 200 and "Zotero is running" in r.text
    except requests.RequestException:
        return False


def _build_collection_tree(items: list) -> list:
    """把 Zotero collections 的 JSON 列表按 parentCollection 建成先序树。

    返回 [{"key","name","depth"}]；顶层 depth=0，子分类逐层 +1。纯函数，便于测试。
    """
    by_key = {}
    for col in items:
        d = col.get("data", {})
        by_key[col["key"]] = {
            "key": col["key"],
            "name": d.get("name", col["key"]),
            "parent": d.get("parentCollection"),
        }

    children = {}
    for info in by_key.values():
        p = info["parent"] or None
        children.setdefault(p, []).append(info)

    out = []

    def walk(parent, depth):
        for info in children.get(parent, []):
            out.append({"key": info["key"], "name": info["name"], "depth": depth})
            walk(info["key"], depth + 1)

    walk(None, 0)
    return out


def list_collections() -> list:
    """列出用户「我的文库」下所有分类（含子分类），按层级先序返回。

    每个元素 {"key", "name", "depth"}。用一次全量 GET /collections + 建树。
    仅读操作，无需 key。失败抛异常。
    """
    url = f"{config.ZOTERO_BASE}/api/users/{config.ZOTERO_USER_ID}/collections"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return _build_collection_tree(r.json())


def collection_keys_by_name(name: str) -> list:
    """按分类名查 key（可同名，返回全部匹配）。"""
    return [c["key"] for c in list_collections() if c["name"] == name]


def collection_name_by_key(key: str) -> str:
    """按 key 查分类名；找不到则回退为 key 本身。"""
    for c in list_collections():
        if c["key"] == key:
            return c["name"]
    return key


def create_item(fields: dict, collection_key: str = None, _retried: bool = False):
    """在本地 Zotero 创建一个 Item（JournalArticle）。返回创建的 key；失败抛异常。

    若 collection_key 非空，新 Item 放入该分类；否则放入「我的文库」根目录。
    HTTP 200 成功，响应为 {"successful": {"0": {...}}}。
    401=key 失效（如被清除或一次性 key 已用），会重新授权并重试一次。
    """
    if collection_key:
        fields["collections"] = [collection_key]
    creds = _load_creds()
    key = creds.get("key") or authorize()
    sid = _server_id()
    if not sid:
        raise RuntimeError("Zotero-Server-ID unavailable, cannot write.")

    headers = {
        "Zotero-API-Key": key,
        "Zotero-Server-ID": sid,
        "Content-Type": "application/json",
        # 每次写入生成唯一 token（5~32 字符），用于检测重试、避免重复创建
        "Zotero-Write-Token": uuid.uuid4().hex[:16],
    }
    r = requests.post(_items_url(), headers=headers, json=[fields], timeout=20)

    if r.status_code == 401 and not _retried:
        # key 失效（被清除 / 一次性 key 已消费）→ 重新授权后重试一次
        new_key = authorize()
        headers["Zotero-API-Key"] = new_key
        headers["Zotero-Write-Token"] = uuid.uuid4().hex[:16]
        r = requests.post(_items_url(), headers=headers, json=[fields], timeout=20)

    if r.status_code != 200:
        raise RuntimeError(
            f"Zotero create_item failed: HTTP {r.status_code} - {r.text[:300]}"
        )
    try:
        return r.json()["successful"]["0"]["key"]
    except Exception:
        return None
