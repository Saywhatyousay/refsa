"""RefSA 入口。

前台进程只负责两件事：处理一次性 CLI 命令，或在打印初始化信息后
分离出一个无控制台的后台进程（内部 --daemon 模式）常驻等待热键，
然后立即退出——于是双击时控制台打印完自动关闭，PowerShell/cmd 里
启动则把控制权立即归还。状态写日志，结果用系统 toast 报告。
"""
import ctypes
import json
import logging
import os
import subprocess
import sys

import config
import crossref
import hotkey
import notifications
import shortcut
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


def _startup_target_label() -> str:
    """启动 toast 用的目标位置可读名；查不到分类时回退为 key，绝不抛异常。"""
    if not config.TARGET_COLLECTION:
        return "My Library"
    try:
        return zotero.collection_name_by_key(config.TARGET_COLLECTION)
    except Exception:
        return config.TARGET_COLLECTION


def _hotkey_display() -> str:
    """把 config.HOTKEY（如 ctrl+alt+r）格式化为用户可读的 Ctrl+Alt+R。"""
    return "+".join(p.capitalize() for p in config.HOTKEY.split("+"))


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

    if "-v" in args or "--version" in args:
        print(f"RefSA {config.VERSION}")
        return True

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


def _detach_console():
    """让后台 daemon 脱离自己持有的控制台。

    --console 打包的 PyInstaller bootloader 会在进程没有控制台时自行
    AllocConsole()，凭空多出一个空的、永不关闭的控制台窗口。daemon 一
    启动就 FreeConsole() 脱离它；若本来就没有控制台则无操作。
    """
    try:
        ctypes.windll.kernel32.FreeConsole()
    except Exception:
        pass


def _run_background():
    """内部 --daemon 模式：无控制台常驻，负责快捷键监听、快捷方式与启动 toast。

    由前台进程以分离进程方式拉起，结束后前台立即退出。
    """
    _detach_console()
    zotero._migrate_legacy_data()
    config.TARGET_COLLECTION = _load_target_collection()
    logger.info("=== RefSA daemon starting ===")
    logger.info("Hotkey configured: %s", config.HOTKEY)
    logger.info("Zotero base: %s", config.ZOTERO_BASE)
    logger.info("Target collection: %s", config.TARGET_COLLECTION or "My Library (root)")

    # 先确保开始菜单快捷方式（带 AUMID），toast 左上角小图标才能显示
    shortcut.ensure_app_shortcut()

    ok = hotkey.register(_handle_trigger)
    if not ok:
        logger.error("Hotkey registration failed, exiting.")
        sys.exit(1)
    logger.info("Hotkey registered. RefSA running in background.")

    # 启动完成：弹一条三行通知（热键 / 目标分类 / 后台就绪）
    notifications.notify(
        "RefSA",
        f"Hotkey configured: {_hotkey_display()}\n"
        f"Target collection: {_startup_target_label()}\n"
        f"RefSA running in background.",
    )

    try:
        hotkey.wait()
    except KeyboardInterrupt:
        logger.info("RefSA stopped by user.")


def _spawn_daemon():
    """以分离进程启动后台常驻，随后父进程即可退出。

    PYINSTALLER_RESET_ENVIRONMENT=1 让 onefile 打包的子进程重新解压到自己的
    临时目录，而非复用父进程的 _MEI 目录——否则父进程退出时清理临时目录
    会被后台子进程占用而失败，导致父进程卡约 16 秒才退出。
    """
    if getattr(sys, "frozen", False):
        cmd = [sys.executable, "--daemon"]
    else:
        cmd = [sys.executable, __file__, "--daemon"]
    env = dict(os.environ)
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    # SW_HIDE 让 daemon 被分配的控制台一开始就隐藏（配合 _detach_console）
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0  # SW_HIDE
    subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        env=env,
        startupinfo=si,
    )
    logger.info("Daemon spawned: %s", cmd)


def main():
    # 内部 daemon 模式：由前台进程分离启动，无控制台常驻
    if "--daemon" in sys.argv[1:]:
        _run_background()
        return

    # 一次性迁移旧 data/ 下的配置与凭证到用户数据目录
    zotero._migrate_legacy_data()

    # 一次性 CLI 命令（-v / -l / -c 等）处理完即退出
    if _handle_cli():
        return

    # 启动后台监听：打印初始化信息（双击可见；PS/cmd 里输出完控制权即归还），
    # 然后分离出一个后台进程并退出，本进程不阻塞调用方。
    logger.info("=== RefSA starting ===")
    logger.info("Hotkey configured: %s", config.HOTKEY)
    logger.info("Zotero base: %s", config.ZOTERO_BASE)
    config.TARGET_COLLECTION = _load_target_collection()
    logger.info("Target collection: %s", config.TARGET_COLLECTION or "My Library (root)")

    print("RefSA starting...")
    print(f"Hotkey configured: {_hotkey_display()}")
    print(f"Target collection: {_startup_target_label()}")
    try:
        _spawn_daemon()
    except Exception as exc:
        logger.exception("Failed to spawn daemon")
        print(f"Failed to start: {exc}")
        sys.exit(1)
    print("RefSA is now running in the background.")


if __name__ == "__main__":
    main()
