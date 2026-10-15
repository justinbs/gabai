param(
  [Parameter(Mandatory=$true)][string]$Label,
  [string]$Live = ""
)
$out = "tests/security/results/$Label"
New-Item -ItemType Directory -Force -Path $out | Out-Null
$root = (Get-Location).Path

Write-Host "1/4 Bandit (Python code)"
backend\.venv\Scripts\python -m bandit -r backend/app -f json -o "$out/bandit.json"

Write-Host "2/4 Trivy (dependencies, Dockerfile, compose, secrets)"
docker run --rm -v trivy-cache:/root/.cache/ -v "${root}:/repo" aquasec/trivy:latest fs `
  --scanners vuln,misconfig `
  --skip-dirs /repo/backend/.venv --skip-dirs /repo/frontend/node_modules `
  --skip-dirs /repo/ml/.venv --skip-dirs /repo/ml/models `
  --skip-dirs /repo/ml/checkpoints --skip-dirs /repo/backend/app/ml_models `
  --skip-dirs /repo/.git --timeout 30m `
  --format json --output "/repo/$out/trivy.json" /repo

Write-Host "3/4 gitleaks (secrets in git history)"
docker run --rm -v "${root}:/repo" zricethezav/gitleaks:latest detect `
  --source /repo --report-format json --report-path "/repo/$out/gitleaks.json"

if ($Live -ne "") {
  Write-Host "4/4 ZAP passive baseline of the live site"
  docker run --rm -v "${root}/${out}:/zap/wrk:rw" ghcr.io/zaproxy/zaproxy:stable `
    zap-baseline.py -t $Live -J zap-baseline.json -I
} else {
  Write-Host "4/4 ZAP skipped (pass -Live https://your-site to include it)"
}
Write-Host "Done. Now run: backend\.venv\Scripts\python tests/security/summarize.py $out"