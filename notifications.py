"""Windows 原生 Toast 通知。toast 失败只记 log，绝不崩溃工作流。

RefSA 常驻后台、不自绘窗口，用系统 toast 在右下角报告成功/失败。

Toast 左上角的小图标（App Logo）由 Windows 依据带 AppUserModelID 的
开始菜单快捷方式决定（见 shortcut.py），正文不包含任何 <image>。

消息按行拆成多个 <text> 元素（title 一行 + 最多 3 行正文），保证
「Imported to X」这样的底部行以独立行渲染（单个 <text> 会把 \\n 折叠
成空格，无法换行）。
"""
import logging
import subprocess

import config

logger = logging.getLogger("refsa")


# 复用 winotify 验证过的 PowerShell 调用方式：隐去窗口、静默执行、不阻塞。
def _run_ps(script: str):
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    subprocess.Popen(
        [
            "powershell.exe",
            "-ExecutionPolicy", "Bypass",
            "-Command", script,
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        startupinfo=si,
    )


def notify(title: str, message: str):
    """弹出系统 toast。失败仅记 log，不上抛。

    message 中每行渲染为 toast 正文的一行（最多 3 行）。toast 静音。
    """
    if not config.NOTIFY_ENABLED:
        return
    try:
        lines = message.split("\n")[:3]  # 模板仅支持 title + 3 行正文
        body = "".join(
            f'<text id="{i + 2}"><![CDATA[{ln}]]></text>'
            for i, ln in enumerate(lines)
        )
        script = f'''
# 加载 Windows 运行时类型（WinRT），否则下面的类型无法解析
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
[Windows.UI.Notifications.ToastNotification, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null

$ToastXml = @"
<toast duration="{config.NOTIFY_DURATION}">
  <visual>
    <binding template="ToastGeneric">
      <text id="1"><![CDATA[{title}]]></text>
      {body}
    </binding>
  </visual>
  <audio silent="true" />
</toast>
"@
$Xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$Xml.LoadXml($ToastXml)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("{config.NOTIFY_APP_ID}").Show(
  [Windows.UI.Notifications.ToastNotification]::new($Xml)
)
'''
        _run_ps(script)
    except Exception:
        logger.exception("Failed to show toast (title=%r)", title)
