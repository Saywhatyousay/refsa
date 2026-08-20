"""通过「剪贴板交换 + 模拟 Ctrl+C」抓取当前选中文本，并保证恢复原剪贴板。"""
import time

import keyboard
import pyperclip

import config


def capture_selection() -> str:
    """读取当前选中文本。若失败返回空字符串；无论成功与否都恢复原剪贴板。"""
    saved = pyperclip.paste()
    try:
        pyperclip.copy("")  # 清空，作为竞态哨兵
        for _ in range(config.CLIP_MAX_TRIES):
            keyboard.press_and_release("ctrl+c")
            time.sleep(config.CLIP_SLEEP_SEC)
            text = pyperclip.paste()
            if text:  # 读到了非空文本，说明模拟 Ctrl+C 生效
                return text
    finally:
        pyperclip.copy(saved)  # 恢复原剪贴板，即使失败也不破坏用户剪贴板
    return ""
