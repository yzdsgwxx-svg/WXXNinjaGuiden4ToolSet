param(
  [string]$Exe = 'D:\APP\WXXNinjaGuiden4ToolSet\dist\ControllerOverlay\WXXControllerOverlay.exe',
  [switch]$Dev
)
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Hit {
  [DllImport("user32.dll")] public static extern IntPtr SendMessage(IntPtr h, uint msg, IntPtr wp, IntPtr lp);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
}
"@
$probeDir = if ($Dev) { 'D:\APP\WXXNinjaGuiden4ToolSet\overlay\artifacts' } else { Join-Path $env:TEMP 'NinjaOverlaySmoke' }
$json = Join-Path $probeDir 'probe.json'
Remove-Item $json -Force -ErrorAction SilentlyContinue
if ($Dev) {
  $proc = Start-Process -FilePath 'D:\APP\WXXNinjaGuiden4ToolSet\overlay\node_modules\electron\dist\electron.exe' -ArgumentList '.','--probe' -WorkingDirectory 'D:\APP\WXXNinjaGuiden4ToolSet\overlay' -PassThru
} else {
  $proc = Start-Process -FilePath $Exe -ArgumentList '--probe' -PassThru
}
for ($i = 0; $i -lt 60 -and -not (Test-Path $json); $i++) { Start-Sleep -Milliseconds 500 }
if (-not (Test-Path $json)) { $proc.Kill(); throw 'probe.json not produced' }
$probe = Get-Content $json -Raw -Encoding UTF8 | ConvertFrom-Json
for ($i = 0; $i -lt 40 -and $proc.MainWindowHandle -eq 0; $i++) { Start-Sleep -Milliseconds 250; $proc.Refresh() }
$hwnd = $proc.MainWindowHandle
if ($hwnd -eq 0) { $proc.Kill(); throw 'no window handle' }
$r = New-Object Hit+RECT
[void][Hit]::GetWindowRect($hwnd, [ref]$r)
$physW = $r.Right - $r.Left
$scale = [math]::Round($physW / [double]$probe.innerWidth, 4)
"window: css $($probe.innerWidth)x$($probe.innerHeight)  physical ${physW}x$($r.Bottom - $r.Top)  scale=$scale"
$names = @('minimize','close','select','copy','titlebar','controller','footer','asideBlank')
$verdict = @{ 1 = 'HTCLIENT (clickable)'; 2 = 'HTCAPTION (drag)' }
foreach ($name in $names) {
  $pt = $probe.points.$name
  if (-not $pt) { "  {0,-11} MISSING" -f $name; continue }
  $sx = [int][math]::Round(($probe.bounds.x + $pt.x) * $scale)
  $sy = [int][math]::Round(($probe.bounds.y + $pt.y) * $scale)
  $lp = [IntPtr](($sy -shl 16) -bor ($sx -band 0xFFFF))
  $hit = [int][Hit]::SendMessage($hwnd, 0x0084, [IntPtr]::Zero, $lp)
  $text = if ($verdict.ContainsKey($hit)) { $verdict[$hit] } else { "code $hit" }
  "  {0,-11} css({1},{2}) -> screen({3},{4})  {5}" -f $name, $pt.x, $pt.y, $sx, $sy, $text
}
$proc.Kill()
