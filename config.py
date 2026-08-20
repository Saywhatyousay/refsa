"""RefSA 集中配置。所有可调项都在这里，不在代码中散落字符串。"""
import os

# ---- 版本号 ----
VERSION = "1.0.0"

# ---- 全局快捷键 ----
# 注意：Ctrl+Shift+R 被 Zotero 的「朗读选中内容」占用，会与之冲突。
# 换用 Zotero 不占用的组合键；如需更改，改这里即可。
HOTKEY = "ctrl+alt+r"

# ---- Crossref ----
CROSSREF_URL = "https://api.crossref.org/works"
CROSSREF_ROWS = 5
CROSSREF_UA = "RefSA/0.1 (mailto:dev@example.com)"
CROSSREF_TIMEOUT = 20
# Crossref 返回的 score 是相对查询的，非校准值。真实匹配通常很高（70+），
# 无意义查询也会得到中等分数（如 ~37）。设为 60 偏向拒绝，避免创建错误 Item。
SCORE_THRESHOLD = 60.0

# ---- Zotero 本地接口 ----
ZOTERO_BASE = "http://localhost:23119"
ZOTERO_USER_ID = 0  # 本地用户恒为 0（已实测，无动态发现端点）
# 写 key 通过 POST /api/local/authorize 运行时授权获得并持久化到 data/credentials.json，
# 不在源码中硬编码。故不在此配置 key。

# ---- 选中文本抓取 ----
# 许多应用（尤其 PDF 阅读器）延迟写剪贴板，等待时间太短会读到空。
CLIP_SLEEP_SEC = 0.15
CLIP_MAX_TRIES = 5

# ---- Toast 通知 ----
NOTIFY_ENABLED = True
NOTIFY_APP_ID = "RefSA"
# "short" / "long"；成功短、失败短即可
NOTIFY_DURATION = "short"

# ---- 图标（toast 左上角 + 打包 exe）----
_ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
TOAST_ICON = os.path.join(_ASSET_DIR, "refsa_icon.png")
EXE_ICON = os.path.join(_ASSET_DIR, "refsa_icon.ico")  # 供 PyInstaller --icon 使用
# toast 左上角小图标用的小尺寸方形 PNG（过大图标易加载失败）
TOAST_LOGO = os.path.join(_ASSET_DIR, "refsa_logo.png")

# ---- 用户数据目录（发行版可写）----
# 配置与凭证存到 %APPDATA%\RefSA\，避免打包 exe 装在不可写位置时失效。
USER_DATA_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "RefSA")
LEGACY_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# ---- 目标分类（运行时从 CLI / 持久化文件加载后覆盖）----
# None = 放入「我的文库」根目录。可用 --collection <key> 设置并持久化，
# --clear-collection 清除（回退我的文库）。持久化到 REFSA_CONFIG_FILE。
TARGET_COLLECTION = None
REFSA_CONFIG_FILE = os.path.join(USER_DATA_DIR, "refsa_config.json")

# ---- 日志 ----
LOG_DIR = "logs"
LOG_FILE = "runtime.log"
CITATION_LOG_MAX_CHARS = 200
