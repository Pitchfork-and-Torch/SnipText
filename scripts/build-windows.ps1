# Build standalone Windows folder with PyInstaller (RapidOCR bundled)
$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "[SnipText] Root: $Root"
Write-Host "[SnipText] Installing build deps..."
& py -3 -m pip install -q -U pyinstaller
if ($LASTEXITCODE -ne 0) { throw "pip pyinstaller failed" }
# Ensure local OCR is present for collect_all (ignore pip notice noise)
& py -3 -m pip install -q "rapidocr-onnxruntime==1.2.3" onnxruntime
# do not fail on non-zero if already satisfied with warnings

Write-Host "[SnipText] Building via SnipText.spec..."
$ErrorActionPreference = "Stop"
& py -3 -m PyInstaller --noconfirm --clean (Join-Path $Root "SnipText.spec")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed exit=$LASTEXITCODE" }
$exe = Join-Path $Root "dist\SnipText\SnipText.exe"
if (-not (Test-Path $exe)) {
    Write-Error "Build failed: $exe not found"
    exit 1
}

# Write a short run note next to the exe (no secrets)
$readme = @"
SnipText portable build
=======================
1. Run SnipText.exe (lives in the system tray)
2. Hotkey default: Ctrl+Shift+T
3. Connect AI: tray -> Connect AI (max accuracy)...
4. Keys and config are stored in:
   %APPDATA%\SnipText\
   Never inside this folder or the .exe
5. Clip Desk: search, pin, Export ledger.json, Import it back (local file only)
6. A camera shutter plays when a snip is captured (Settings can mute it)
7. Keep the whole SnipText\ folder together (onedir build)

Code signing: not applied in this build. SmartScreen may warn once for unsigned apps.
"@
Set-Content -Path (Join-Path $Root "dist\SnipText\README-PORTABLE.txt") -Value $readme -Encoding UTF8

$size = (Get-Item $exe).Length
$folder = (Get-ChildItem (Join-Path $Root "dist\SnipText") -Recurse | Measure-Object -Property Length -Sum).Sum
Write-Host "[SnipText] OK: $exe"
Write-Host ("[SnipText] Exe size: {0:N1} MB" -f ($size / 1MB))
Write-Host ("[SnipText] Folder size: {0:N1} MB" -f ($folder / 1MB))
Write-Host "[SnipText] Output: $Root\dist\SnipText\"

# Portable zip for GitHub Releases (not committed to git)
$zip = Join-Path $Root "dist\SnipText-Windows-portable.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
Write-Host "[SnipText] Zipping portable release..."
Compress-Archive -Path (Join-Path $Root "dist\SnipText") -DestinationPath $zip -CompressionLevel Optimal
Write-Host ("[SnipText] Zip: {0:N1} MB -> $zip" -f ((Get-Item $zip).Length / 1MB))
