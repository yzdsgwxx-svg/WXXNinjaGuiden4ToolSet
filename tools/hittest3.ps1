param([string]$Exe = 'D:\APP\WXXNinjaGuiden4ToolSet\dist\ControllerOverlay\WXXControllerOverlay.exe', [switch]$Dev)
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Hit3 {
  [DllImport("user32.dll")] public static extern IntPtr SendMessage(IntPtr h, uint msg, IntPtr wp, IntPtr lp);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
}
"@
$probeDir = if ($Dev) { 'D:\APP\WXXNinjaGuiden4ToolSet\overlay\artifacts' } else { Join-Path $env:TEMP 'NinjaOverlaySmoke' }
$json = Join-Path $probeDir 'probe.json'
Remove-Item $json -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $probeDir 'probe-profile') -Recurse -Force -ErrorAction SilentlyContinue
if ($Dev) { $proc = Start-Process -FilePath 'D:\APP\WXXNinjaGuiden4ToolSet\overlay\node_modules\electron\dist\electron.exe' -ArgumentList '.','--probe' -WorkingDirectory 'D:\APP\WXXNinjaGuiden4ToolSet\overlay' -PassThru }
else { $proc = Start-Process -FilePath $Exe -ArgumentList '--probe' -PassThru }
for ($i = 0; $i -lt 60 -and -not (Test-Path $json); $i++) { Start-Sleep -Milliseconds 500 }
if (-not (Test-Path $json)) { $proc.Kill(); throw 'probe.json not produced' }
$probe = Get-Content $json -Raw -Encoding UTF8 | ConvertFrom-Json
for ($i = 0; $i -lt 40 -and $proc.MainWindowHandle -eq 0; $i++) { Start-Sleep -Milliseconds 250; $proc.Refresh() }
$hwnd = $proc.MainWindowHandle
$r = New-Object Hit3+RECT
[void][Hit3]::GetWindowRect($hwnd, [ref]$r)
$scale = [math]::Round(($r.Right - $r.Left) / [double]$probe.innerWidth, 4)
$verdict = @{ 1 = 'CLICK'; 2 = 'DRAG ' }
$line = @()
foreach ($name in @('minimize','close','select','copy','controller','footer','asideBlank')) {
  $pt = $probe.points.$name
  if (-not $pt) { continue }
  $sx = [int][math]::Round(($probe.bounds.x + $pt.x) * $scale); $sy = [int][math]::Round(($probe.bounds.y + $pt.y) * $scale)
  $lp = [IntPtr](($sy -shl 16) -bor ($sx -band 0xFFFF))
  $hit = [int][Hit3]::SendMessage($hwnd, 0x0084, [IntPtr]::Zero, $lp)
  $v = if ($verdict.ContainsKey($hit)) { $verdict[$hit] } else { "?$hit" }
  $line += ("{0}={1}" -f $name, $v.Trim())
}
$proc.Kill()
$line -join '  '
