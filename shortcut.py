"""开始菜单快捷方式（带 AppUserModelID）。

Windows toast 左上角的小图标（app logo）需要系统把 AUMID 关联到一个
带图标的开始菜单快捷方式。对任意用户生效：每次后台启动时确保开始菜单
里有 RefSA.lnk，目标与图标都指向当前可执行文件（内嵌了 exe 图标）。
"""
import os
import subprocess
import sys
import tempfile

_PS_SCRIPT = r"""
param($lnk, $target, $arguments)
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;

public static class RefsaShortcut {
    [StructLayout(LayoutKind.Sequential)]
    public struct PROPERTYKEY { public Guid fmtid; public uint pid; }
    [StructLayout(LayoutKind.Sequential)]
    public struct PROPVARIANT { public ushort vt; public ushort r1; public ushort r2; public ushort r3; public IntPtr p1; public IntPtr p2; }

    [ComImport, InterfaceType(ComInterfaceType.InterfaceIsIUnknown), Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99")]
    public interface IPropertyStore {
        int GetCount(out uint c);
        int GetAt(uint i, out PROPERTYKEY k);
        int GetValue(ref PROPERTYKEY k, out PROPVARIANT v);
        int SetValue(ref PROPERTYKEY k, ref PROPVARIANT v);
        int Commit();
    }

    [DllImport("shell32.dll", CharSet = CharSet.Unicode, PreserveSig = false)]
    static extern IPropertyStore SHGetPropertyStoreFromParsingName(
        [MarshalAs(UnmanagedType.LPWStr)] string path, IntPtr pbc, uint flags, [In] ref Guid riid);

    static readonly Guid IID_IPropertyStore = new Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99");

    public static void Set(string lnkPath, string aumid) {
        var iid = IID_IPropertyStore;
        var ps = (IPropertyStore)SHGetPropertyStoreFromParsingName(lnkPath, IntPtr.Zero, 2, ref iid);
        var pk = new PROPERTYKEY();
        pk.fmtid = new Guid("9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3"); // PKEY_AppUserModel_ID
        pk.pid = 5;
        var pv = new PROPVARIANT();
        pv.vt = 31; // VT_LPWSTR
        pv.p1 = Marshal.StringToCoTaskMemUni(aumid);
        int hr = ps.SetValue(ref pk, ref pv);
        if (hr != 0) throw new Exception("SetValue hr=" + hr);
        hr = ps.Commit();
        if (hr != 0) throw new Exception("Commit hr=" + hr);
        Marshal.FreeCoTaskMem(pv.p1);
        Marshal.ReleaseComObject(ps);
    }
}
'@

$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut($lnk)
$s.TargetPath = $target
$s.Arguments = $arguments
$s.WorkingDirectory = (Split-Path $target -Parent)
$s.IconLocation = "$target,0"
$s.Description = "RefSA"
$s.Save()
[RefsaShortcut]::Set($lnk, "RefSA")
"""


def ensure_app_shortcut():
    """确保开始菜单里有带 AUMID 的 RefSA 快捷方式。失败仅记日志，不抛异常。"""
    try:
        start_menu = os.path.join(
            os.environ.get("APPDATA", os.path.expanduser("~")),
            "Microsoft", "Windows", "Start Menu", "Programs",
        )
        os.makedirs(start_menu, exist_ok=True)
        lnk = os.path.join(start_menu, "RefSA.lnk")
        if getattr(sys, "frozen", False):
            target = sys.executable      # 打包 exe：快捷方式直接指向自身
            args = ""
        else:
            # 源码模式（开发验证）：指向 python + 本入口
            target = sys.executable
            args = f'"{os.path.abspath(__file__)}"'

        fd, tmp = tempfile.mkstemp(suffix=".ps1")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(_PS_SCRIPT)
            subprocess.run(
                ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                 "-File", tmp, lnk, target, args],
                capture_output=True, text=True, timeout=60,
            )
        finally:
            os.unlink(tmp)
    except Exception:
        pass
