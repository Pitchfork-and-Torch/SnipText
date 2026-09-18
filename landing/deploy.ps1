# Deploy sniptext.jonbailey.xyz to Cloudflare Pages
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Public = Join-Path $Root "public"
$Project = "sniptext-jonbailey"

if (-not (Test-Path (Join-Path $Public "index.html"))) {
  Write-Error "Missing public/index.html"
}
if (-not (Test-Path (Join-Path $Public "og.jpg"))) {
  Write-Error "Missing public/og.jpg - run scripts/compose_brand_assets.py first"
}

Write-Host "[DEPLOY] SnipText Pages project=$Project"
Push-Location $Root
try {
  npx --yes wrangler pages deploy $Public --project-name=$Project --commit-dirty=true
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
  Pop-Location
}

Write-Host ""
Write-Host "Site:    https://sniptext.jonbailey.xyz/"
Write-Host "Preview: https://$Project.pages.dev/"
Write-Host "Attach domain if needed:"
Write-Host "  npx wrangler pages domain add sniptext.jonbailey.xyz --project-name=$Project"
