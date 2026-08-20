"""日志初始化。RefSA 全程无 UI，所有状态写入 logs/runtime.log。"""
import logging
import os

import config

_logger = None


def get_logger() -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger

    os.makedirs(config.LOG_DIR, exist_ok=True)
    path = os.path.join(config.LOG_DIR, config.LOG_FILE)

    logger = logging.getLogger("refsa")
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    fh = logging.FileHandler(path, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    # 开发阶段允许终端输出调试日志；打包 --noconsole 后此 handler 无输出。
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    logger.propagate = False
    _logger = logger
    return logger
