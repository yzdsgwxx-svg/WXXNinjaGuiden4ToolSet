Add-Type @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public class UI {
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern IntPtr FindWindowW(string cls, string title);
  [DllImport("user32.dll")] public static extern IntPtr GetDlgItem(IntPtr h, int id);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowTextW(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool IsWindowEnabled(IntPtr h);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern IntPtr SendMessageW(IntPtr h, uint msg, IntPtr wp, IntPtr lp);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
}
"@
$w = [IntPtr]::Zero
foreach ($p in Get-Process WXXNinjaGuiden4ToolSet -ErrorAction SilentlyContinue) { if ($p.MainWindowHandle -ne 0) { $w = $p.MainWindowHandle; break } }
if ($w -eq [IntPtr]::Zero) { throw 'toolset window not found' }
$r = New-Object UI+RECT; [void][UI]::GetWindowRect($w, [ref]$r)
"window: $($r.Right - $r.Left)x$($r.Bottom - $r.Top)"
$ids = [ordered]@{ 101='weapon toggle'; 103='weapon config'; 104='profile combo'; 105='switch save'; 109='open log'; 120='overlay toggle'; 122='save-switch toggle'; 123='minimize'; 124='close'; 125='launch game'; 209='save folder' }
foreach ($id in $ids.Keys) {
  $h = [UI]::GetDlgItem($w, $id)
  if ($h -eq [IntPtr]::Zero) { "  [$id] $($ids[$id]) -> MISSING"; continue }
  $sb = New-Object System.Text.StringBuilder 256
  [void][UI]::GetWindowTextW($h, $sb, 256)
  $txt = $sb.ToString(); if ($txt.Length -eq 0) { $txt = '<owner-draw>' }
  "  [$id] $($ids[$id]) -> '$txt' enabled=$([UI]::IsWindowEnabled($h)) visible=$([UI]::IsWindowVisible($h))"
}
foreach ($gone in 102,106,107,108,112,126) {
  $h = [UI]::GetDlgItem($w, $gone)
  if ($h -ne [IntPtr]::Zero) { "  REMOVED id $gone still present!" }
}
$before = (Get-Process WXXNinjaGuiden4ToolSet -ErrorAction SilentlyContinue | Measure-Object).Count
# CBN_DROPDOWN (1) on the profile combo: exercises LoadState + RefreshProfiles + RefreshSaveState
[void][UI]::SendMessageW($w, 0x0111, [IntPtr](((1 -shl 16) -bor 104)), [UI]::GetDlgItem($w, 104))
Start-Sleep -Milliseconds 400
$after = (Get-Process WXXNinjaGuiden4ToolSet -ErrorAction SilentlyContinue | Measure-Object).Count
"dropdown refresh -> windows before=$before after=$after"
$combo = [UI]::GetDlgItem($w, 104)
"combo items=$([UI]::SendMessageW($combo, 0x0146, [IntPtr]0, [IntPtr]0)) sel=$([UI]::SendMessageW($combo, 0x0147, [IntPtr]0, [IntPtr]0))"
$sb = New-Object System.Text.StringBuilder 256
[void][UI]::GetWindowTextW([UI]::GetDlgItem($w, 111), $sb, 256); "save state text: '$($sb.ToString())'"
