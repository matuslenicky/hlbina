# Dorenderuje všetko, čo chýba: fotky v krajine (out/stills) a snímky zostupu do studne (out/well), potom pripraví WebP pre web.
#   powershell -ExecutionPolicy Bypass -File blender\render_rest.ps1 [-Samples 80]
# Blender beží s nižšou prioritou (počítač ostane použiteľný) a vždy len jeden; pred štartom čaká, kým je voľných aspoň 6 GB RAM
# (fotka 2400 × 1350 zoberie ~3,3 GB). Hotové PNG preskočí, takže sa dá kedykoľvek prerušiť a spustiť znova.
# Priebeh: out\rest.log (zhrnutie), out\rest-run.out (výstup práve bežiaceho Blendera).
param([int]$Samples = 80)
$ErrorActionPreference = "Stop"
$B = "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
Set-Location $PSScriptRoot
New-Item -ItemType Directory -Force "out\stills", "out\well" | Out-Null
$log = Join-Path $PSScriptRoot "out\rest.log"   # absolútne: na konci sa skript presúva do koreňa projektu kvôli prep.py
function Say($t) { $line = "{0:HH:mm:ss} {1}" -f (Get-Date), $t; Add-Content -Path $log -Value $line -Encoding utf8; $line }

function WaitForMemory {
  for ($i = 0; $i -lt 180; $i++) {
    $free = (Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1MB
    if ($free -ge 6) { return }
    if ($i % 10 -eq 0) { Say ("čakám na pamäť, voľných {0:N1} GB" -f $free) }
    Start-Sleep -Seconds 60
  }
  Say "pamäť sa neuvoľnila ani za 3 hodiny, končím"; exit 1
}

function RunBlender([string[]]$BArgs) {
  WaitForMemory
  $p = Start-Process -FilePath $B -ArgumentList $BArgs -NoNewWindow -PassThru -RedirectStandardOutput "out\rest-run.out" -RedirectStandardError "out\rest-run.err"
  try { $p.PriorityClass = "BelowNormal" } catch {}
  $p.WaitForExit()
  Get-Content "out\rest-run.out" | Select-String -Pattern "\[run\]|\[well\]|Error|Traceback" | ForEach-Object { Say $_.Line }
  if ($p.ExitCode -ne 0) { Say "Blender skončil s kódom $($p.ExitCode)" }
}

# 1. fotky fliaš v krajine
$shots = @(
  @("hero", 2400, 1350), @("hero_m", 1080, 1920),
  @("duo", 2400, 1350), @("duo_m", 1080, 1920),
  @("detail", 2400, 1350), @("detail_m", 1080, 1920),
  @("dusk", 2400, 1350), @("dusk_m", 1080, 1920)
)
foreach ($s in $shots) {
  $name, $w, $h = $s
  $png = "out\stills\$name.png"
  if (Test-Path $png) { continue }
  Say "fotka $name ($w × $h, $Samples vzoriek)"
  RunBlender @("-b", "--factory-startup", "-P", "run.py", "--", $name, $png, "--w", "$w", "--h", "$h", "--s", "$Samples")
}

# 2. zostup do studne: 72 snímok, najprv každá ôsma, potom husto (web medzitým prelína najbližšie hotové)
$order = (1, 9, 17, 25, 33, 41, 49, 57, 65, 72, 5, 13, 21, 29, 37, 45, 53, 61, 69) + (1..72 | Where-Object { $_ % 2 -eq 1 }) + (1..72 | Where-Object { $_ % 2 -eq 0 })
$todo = $order | Select-Object -Unique | Where-Object { -not (Test-Path ("out\well\{0:D3}.png" -f $_)) }
if ($todo) {
  Say ("zostup: {0} snímok" -f @($todo).Count)
  RunBlender @("-b", "--factory-startup", "-P", "render_well.py", "--", "out\well", "960", "28", "72", ($todo -join ","))
}

# 3. WebP pre web
Set-Location ..
& python tools\prep.py | ForEach-Object { Say $_ }
Say "ALL_DONE"
