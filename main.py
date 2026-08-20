"""RefSA 入口：后台常驻，等待全局热键触发完整工作流。状态写日志，结果用系统 toast 报告。"""
import json
import logging
import os
import sys

import config
import crossref
import hotkey
import notifications
import zotero
from clipboard import capture_selection
from logging_setup import get_logger

logger = get_logger()


def _truncate(text: str, n: int = None) -> str:
    n = n or config.CITATION_LOG_MAX_CHARS
    return text if len(text) <= n else text[:n] + "…"


def _target_label() -> str:
    """返回目标位置的可读名（My Library 或分类名）。"""
    if not config.TARGET_COLLECTION:
        return "My Library"
    return zotero.collection_name_by_key(config.TARGET_COLLECTION)


def _handle_trigger():
    """热键触发后的完整工作流。单次失败仅记 log + toast，不影响热键继续监听。"""
    try:
        logger.info("Hotkey triggered, capturing selection...")
        citation = capture_selection().strip()
        if not citation:
            logger.warning("Captured empty selection, aborting.")
            notifications.notify("RefSA", "Could not read the selected text. Please reselect and try again.")
            return

        logger.info("Citation: %s", _truncate(citation))

        candidates = crossref.crossref_search(citation)
        if not candidates:
            logger.warning("Crossref returned no candidates, aborting.")
            notifications.notify("RefSA", "No candidate references found.")
            return
        logger.info("Crossref candidates: %d", len(candidates))

        best = crossref.best_match(candidates)
        score = best.get("score", 0)
        title = (best.get("title") or ["<untitled>"])[0]
        logger.info("Best match score=%.1f title=%s", score, _truncate(title))

        if score < config.SCORE_THRESHOLD:
            logger.info(
                "Best score %.1f below threshold %.1f, not creating item.",
                score, config.SCORE_THRESHOLD,
            )
            notifications.notify("RefSA", "No sufficiently reliable match (selection may not be a complete reference).")
            return

        if not zotero.ping():
            logger.error("Zotero not reachable at %s, aborting.", config.ZOTERO_BASE)
            notifications.notify("RefSA", "Cannot connect to Zotero. Make sure Zotero is running.")
            return
        logger.info("Zotero ping OK.")

        fields = crossref.to_zotero_fields(best)
        key = zotero.create_item(fields, collection_key=config.TARGET_COLLECTION)
        logger.info(
            "Zotero item created key=%s url=%s/%s collection=%s",
            key, config.ZOTERO_BASE, key, config.TARGET_COLLECTION or "My Library",
        )

        # 成功 toast：title / 作者姓 / year / 导入到 XXX
        author = fields.get("creators", [{}])[0].get("lastName", "")
        year = fields.get("date", "")
        notifications.notify(title, f"{author} {year}".strip() + f"\nImported to {_target_label()}")
    except Exception:
        logger.exception("Workflow failed")
        notifications.notify("RefSA", "An error occurred; see logs/runtime.log for details.")


def _load_target_collection() -> str | None:
    try:
        with open(config.REFSA_CONFIG_FILE, encoding="utf-8") as f:
            return json.load(f).get("target_collection") or None
    except Exception:
        return None


def _save_target_collection(key):
    os.makedirs(os.path.dirname(config.REFSA_CONFIG_FILE), exist_ok=True)
    with open(config.REFSA_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump({"target_collection": key}, f)


def _collection_arg(args):
    """识别 --collection / -c，返回其参数值（分类名）；无则 None。"""
    for flag in ("--collection", "-c"):
        if flag in args:
            i = args.index(flag)
            if i + 1 < len(args):
                return args[i + 1]
            return ""
    return None


def _node_has_later_at_depth(cols, i, depth):
    """判断 flat 列表中 index=i 之后是否还有 depth 层的节点（决定竖线是否延续）。"""
    return any(c["depth"] == depth for c in cols[i + 1:])


def _print_collection_tree(cols, target_key):
    """以 My Library 为根打印分类树；当前目标节点后加 *。target_key=None 表示 My Library。"""
    print("My Library" + (" *" if target_key is None else ""))
    n = len(cols)
    for i, c in enumerate(cols):
        # 当前节点是「最后一个兄弟」当且仅当：它是末尾，或下一个节点深度更浅（父级收尾）
        is_last = (i == n - 1) or (cols[i + 1]["depth"] < c["depth"])
        prefix = ""
        for lev in range(c["depth"]):
            # 每层 4 字符，让子分支对齐到父节点名称下方
            prefix += "│   " if _node_has_later_at_depth(cols, i, lev) else "    "
        prefix += "└── " if is_last else "├── "
        mark = " *" if c["key"] == target_key else ""
        print(prefix + c["name"] + mark)


def _handle_cli():
    """处理命令行参数，返回 True 表示应退出进程（不常驻）。"""
    args = sys.argv[1:]

    if "--list-collections" in args or "-l" in args:
        _print_collection_tree(zotero.list_collections(), _load_target_collection())
        return True

    if "--clear-collection" in args:
        _save_target_collection(None)
        config.TARGET_COLLECTION = None
        print("Target collection cleared (items go to My Library).")
        return True

    name = _collection_arg(args)
    if name is not None:
        if not name:
            print("Usage: --collection <collectionName>   (or -c <collectionName>)")
            return True
        matches = zotero.collection_keys_by_name(name)
        if not matches:
            print(f"No collection named '{name}'. Available collections:")
            for c in zotero.list_collections():
                print(f"  {'  ' * c['depth']}{c['name']}")
            return True
        if len(matches) > 1:
            print(f"Multiple collections named '{name}'; use a unique name.")
            return True
        _save_target_collection(matches[0])
        print(f"Target collection set to '{name}'")
        return True

    return False


def main():
    logger.info("=== RefSA starting ===")
    logger.info("Hotkey configured: %s", config.HOTKEY)
    logger.info("Zotero base: %s", config.ZOTERO_BASE)

    # 一次性迁移旧 data/ 下的配置与凭证到用户数据目录
    zotero._migrate_legacy_data()

    if _handle_cli():
        return

    config.TARGET_COLLECTION = _load_target_collection()
    logger.info("Target collection: %s", config.TARGET_COLLECTION or "My Library (root)")

    ok = hotkey.register(_handle_trigger)
    if not ok:
        logger.error("Hotkey registration failed, exiting.")
        sys.exit(1)
    logger.info("Hotkey registered. RefSA running in background.")

    try:
        hotkey.wait()
    except KeyboardInterrupt:
        logger.info("RefSA stopped by user.")


if __name__ == "__main__":
    main()
