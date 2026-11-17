# Finálne fotky v krajine (Cycles na CPU), jedna po druhej. Spúšťať z priečinka blender/:
#   powershell -ExecutionPolicy Bypass -File render_stills.ps1 [-Samples 80]
# Existujúce PNG v out/stills preskočí. (Bash slučka pri dlhom behu padala na fork.)
param([int]$Samples = 80)
$B = "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
$shots = @(
  @("hero", 2400, 1350), @("hero_m", 1080, 1920),
  @("duo", 2400, 1350), @("duo_m", 1080, 1920),
  @("detail", 2400, 1350), @("detail_m", 1080, 1920),
  @("dusk", 2400, 1350), @("dusk_m", 1080, 1920)
)
New-Item -ItemType Directory -Force "out\stills" | Out-Null
foreach ($s in $shots) {
  $name, $w, $h = $s
  $png = "out\stills\$name.png"
  if (Test-Path $png) { "skip $name"; continue }
  & $B -b --factory-startup -P run.py -- $name $png --w $w --h $h --s $Samples 2>&1 |
    Select-String -Pattern "\[run\]|Error|Traceback" | ForEach-Object { $_.Line }
}
"ALL_DONE"
