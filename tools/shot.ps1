param([string]$Exe = 'D:\APP\WXXNinjaGuiden4ToolSet\dist\WXXNinjaGuiden4ToolSet.exe', [string]$Out = 'D:\APP\WXXNinjaGuiden4ToolSet\artifacts\toolset.png', [int]$Wait = 3)
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Shot {
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint flags);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
}
"@
$proc = Get-Process -Name ([System.IO.Path]::GetFileNameWithoutExtension($Exe)) -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $Exe } | Select-Object -First 1
if (-not $proc) { $proc = Start-Process -FilePath $Exe -PassThru; Start-Sleep -Seconds $Wait }
for ($i = 0; $i -lt 40 -and $proc.MainWindowHandle -eq 0; $i++) { Start-Sleep -Milliseconds 250; $proc.Refresh() }
$h = $proc.MainWindowHandle
if ($h -eq 0) { throw 'no window handle' }
[void][Shot]::SetForegroundWindow($h)
Start-Sleep -Milliseconds 600
$r = New-Object Shot+RECT
[void][Shot]::GetWindowRect($h, [ref]$r)
$w = $r.Right - $r.Left; $hh = $r.Bottom - $r.Top
$bmp = New-Object System.Drawing.Bitmap($w, $hh)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$dc = $g.GetHdc()
[void][Shot]::PrintWindow($h, $dc, 0)
$g.ReleaseHdc($dc); $g.Dispose()
New-Item -ItemType Directory -Force -Path (Split-Path $Out) | Out-Null
$bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()
"$Out ${w}x${hh}"
