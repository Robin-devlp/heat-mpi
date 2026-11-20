# demo.ps1 - run the live demo from Windows and open the heat map.
# Usage (PowerShell on Robin's laptop):
#   .\scripts\demo.ps1 1                  # case 1 with the defaults (N=64, P=3, T=0.02, blocks)
#   .\scripts\demo.ps1 2 64 6 0.02 strips
param(
    [Parameter(Mandatory = $true)][string]$Case,
    [int]$N = 64,
    [int]$P = 3,
    [string]$T = "0.02",
    [string]$Decomp = "blocks"
)
$env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')

multipass exec heat-robin -- sudo -iu mpi bash /home/mpi/heat-mpi/scripts/demo.sh $Case $N $P $T $Decomp
if ($LASTEXITCODE -ne 0) { Write-Host "The run failed."; exit 1 }

# copy the picture to this laptop and open it
$name = "case${Case}_N${N}_P${P}_${Decomp}.png"
multipass exec heat-robin -- sudo install -m 644 /home/mpi/heat-mpi/results/demo/$name /tmp/$name
$dest = Join-Path $PSScriptRoot "..\results\demo"
New-Item -ItemType Directory -Force $dest | Out-Null
multipass transfer heat-robin:/tmp/$name "$dest\$name" 2>$null
Start-Process "$dest\$name"
