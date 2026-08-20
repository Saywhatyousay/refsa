"""全局热键注册。注册失败记 log 并退出，不崩溃不弹窗。"""
import logging

import keyboard

import config

logger = logging.getLogger("refsa")


def register(callback):
    """注册全局热键。返回成功与否。"""
    try:
        keyboard.add_hotkey(config.HOTKEY, callback)
    except Exception as exc:
        logger.error("Hotkey registration failed: %s", exc)
        logger.error(
            "keyboard 库在 Windows 做全局钩子可能需要管理员权限；"
            "请尝试以管理员身份运行，或改用 pynput。"
        )
        return False
    return True


def wait():
    """常驻阻塞，等待热键触发。"""
    keyboard.wait()
