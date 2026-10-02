$names = 'probe.json','probe-other-screen.json','probe-back.json'
foreach ($n in $names) {
  $path = Join-Path 'D:\APP\WXXNinjaGuiden4ToolSet\overlay\artifacts' $n
  if (-not (Test-Path $path)) { "$n MISSING"; continue }
  $j = Get-Content $path -Raw -Encoding UTF8 | ConvertFrom-Json
  "{0,-26} bounds={1},{2} {3}x{4}  inner={5}x{6}  dpr={7}  scale={8}  narrow={9}  navLeft={10}  brandSpan={11}" -f `
    $n, $j.bounds.x, $j.bounds.y, $j.bounds.width, $j.bounds.height, $j.metrics.innerWidth, $j.metrics.innerHeight, `
    $j.metrics.dpr, $j.display.scaleFactor, $j.metrics.mediaNarrow, $j.metrics.navLeft, $j.metrics.brandText
}
