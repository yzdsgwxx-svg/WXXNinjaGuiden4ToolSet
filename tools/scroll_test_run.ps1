param(
  [string]$Exe = "$env:TEMP\WXXScrollTest.exe",
  [string]$OutDir = 'D:\APP\WXXNinjaGuiden4ToolSet\artifacts'
)
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class ScrollTest {
  [StructLayout(LayoutKind.Sequential)] public struct SCROLLINFO { public uint cbSize; public uint fMask; public int nMin; public int nMax; public uint nPage; public int nPos; public int nTrackPos; }
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
  [DllImport("user32.dll", CharSet=CharSet.Unicode, EntryPoint="FindWindowW")] public static extern IntPtr FindWindowCls(string cls, IntPtr title);
  [DllImport("user32.dll", CharSet=CharSet.Unicode, EntryPoint="FindWindowExW")] public static extern IntPtr FindWindowExCls(IntPtr parent, IntPtr after, string cls, IntPtr title);
  [DllImport("user32.dll")] public static extern IntPtr GetDlgItem(IntPtr h, int id);
  [DllImport("user32.dll")] public static extern bool GetScrollInfo(IntPtr h, int bar, ref SCROLLINFO si);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool PostMessageW(IntPtr h, uint msg, IntPtr wp, IntPtr lp);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint flags);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint flags, int dx, int dy, int data, IntPtr extra);
  [DllImport("user32.dll")] public static extern IntPtr WindowFromPoint(POINT p);
  [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X; public int Y; }
}
"@
function Shot([IntPtr]$h, [string]$path) {
  $r = New-Object ScrollTest+RECT
  [void][ScrollTest]::GetWindowRect($h, [ref]$r)
  $bmp = New-Object System.Drawing.Bitmap(($r.Right - $r.Left), ($r.Bottom - $r.Top))
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $dc = $g.GetHdc(); [void][ScrollTest]::PrintWindow($h, $dc, 0); $g.ReleaseHdc($dc); $g.Dispose()
  New-Item -ItemType Directory -Force -Path (Split-Path $path) | Out-Null
  $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png); $bmp.Dispose()
  "$path $($r.Right - $r.Left)x$($r.Bottom - $r.Top)"
}
function ScrollInfo([IntPtr]$h) {
  $si = New-Object ScrollTest+SCROLLINFO
  $si.cbSize = [System.Runtime.InteropServices.Marshal]::SizeOf($si); $si.fMask = 0x17
  [void][ScrollTest]::GetScrollInfo($h, 1, [ref]$si)
  $si
}

function Step([int]$cmd, [string]$name) {
  [void][ScrollTest]::PostMessageW($box, 0x0115, [IntPtr]$cmd, [IntPtr]::Zero)
  Start-Sleep -Milliseconds 500
  "  $name -> pos=$((ScrollInfo $box).nPos)"
}

Get-Process -Name 'WXXScrollTest' -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Milliseconds 700
$proc = Start-Process -FilePath $Exe -PassThru
for ($i = 0; $i -lt 40; $i++) { Start-Sleep -Milliseconds 250; $h = [ScrollTest]::FindWindowCls('WXXToolsetScrollTest', [IntPtr]::Zero); if ($h -ne [IntPtr]::Zero) { break } }
if ($h -eq [IntPtr]::Zero) { throw 'panel window not found' }
[void][ScrollTest]::SetForegroundWindow($h)
Start-Sleep -Milliseconds 800
$box = [ScrollTest]::FindWindowExCls($h, [IntPtr]::Zero, 'WXXToolsetScroll', [IntPtr]::Zero)
"scroll box hwnd = $box"
if ($box -eq [IntPtr]::Zero) { throw 'scroll box not found' }

$si0 = ScrollInfo $box
"before: min=$($si0.nMin) max=$($si0.nMax) page=$($si0.nPage) pos=$($si0.nPos)  -> scrollable=$([int]($si0.nMax - $si0.nPage + 1))"
$log = [ScrollTest]::GetDlgItem($box, 109)
$r0 = New-Object ScrollTest+RECT; [void][ScrollTest]::GetWindowRect($log, [ref]$r0)
$cr = New-Object ScrollTest+RECT; [void][ScrollTest]::GetClientRect($box, [ref]$cr)
"viewport client = $($cr.Right)x$($cr.Bottom)"
Shot $h (Join-Path $OutDir 'scroll_top.png')
Step 7 'SB_BOTTOM'
$r1 = New-Object ScrollTest+RECT; [void][ScrollTest]::GetWindowRect($log, [ref]$r1)
"button 查看日志 moved: top $($r0.Top) -> $($r1.Top)  (delta $($r1.Top - $r0.Top))"
Shot $h (Join-Path $OutDir 'scroll_bottom.png')

# 逐个滚动指令验证：LINEUP=0 LINEDOWN=1 PAGEUP=2 PAGEDOWN=3 THUMBPOSITION=5 TOP=6 BOTTOM=7
Step 1 'SB_LINEDOWN'
Step 3 'SB_PAGEDOWN'
Step 6 'SB_TOP'
Step 1 'SB_LINEDOWN'
Step 0 'SB_LINEUP'
Step 7 'SB_BOTTOM'
Step 2 'SB_PAGEUP'
Step 6 'SB_TOP'
# 滚轮：WHEEL_DELTA=120，向下滚是负的
[void][ScrollTest]::PostMessageW($box, 0x020A, [IntPtr](-120 -shl 16), [IntPtr]::Zero)
Start-Sleep -Milliseconds 350
"  PostMessage box WM_MOUSEWHEEL(-120) -> pos=$((ScrollInfo $box).nPos)"
[void][ScrollTest]::PostMessageW($h, 0x020A, [IntPtr](-120 -shl 16), [IntPtr]::Zero)
Start-Sleep -Milliseconds 350
"  PostMessage main WM_MOUSEWHEEL(-120) -> pos=$((ScrollInfo $box).nPos)"
# 真实滚轮输入：把光标放到内容区再发滚轮
$cr2 = New-Object ScrollTest+RECT; [void][ScrollTest]::GetWindowRect($box, [ref]$cr2)
[void][ScrollTest]::SetCursorPos(($cr2.Left + 300), ($cr2.Top + 200))
Start-Sleep -Milliseconds 200
[ScrollTest]::mouse_event(0x0800, 0, 0, -120, [IntPtr]::Zero)
Start-Sleep -Milliseconds 400
"  real wheel over content -> pos=$((ScrollInfo $box).nPos)"
[ScrollTest]::mouse_event(0x0800, 0, 0, 120, [IntPtr]::Zero)
Start-Sleep -Milliseconds 400
"  real wheel up -> pos=$((ScrollInfo $box).nPos)"
Stop-Process -Id $proc.Id -Force
