# Builds installer_output\MailBlaster-Setup.exe:
#   official signed Python embeddable runtime + PyPI wheels + app source -> Inno Setup.
# Smart App Control blocks freshly built unsigned .exe files (PyInstaller); the Python runtime
# from python.org is signed by the Python Software Foundation, so Windows lets it run.
#   powershell -ExecutionPolicy Bypass -File build.ps1
$ErrorActionPreference = "Stop"
$root  = $PSScriptRoot
$pyVer = "3.12.10"
$stage = Join-Path $root "build_embed"
$cache = Join-Path $root "build_cache"
$zip   = Join-Path $cache "python-$pyVer-embed-amd64.zip"

New-Item -ItemType Directory -Force $cache | Out-Null
if (-not (Test-Path $zip)) {
    $shared = "D:\lead-finder\build_cache\python-$pyVer-embed-amd64.zip"
    if (Test-Path $shared) { Copy-Item $shared $zip }
    else {
        Write-Host "Downloading Python $pyVer embeddable runtime..."
        Invoke-WebRequest "https://www.python.org/ftp/python/$pyVer/python-$pyVer-embed-amd64.zip" -OutFile $zip -UseBasicParsing
    }
}
if (Test-Path $stage) { Remove-Item -Recurse -Force $stage }
$rt  = Join-Path $stage "runtime"
$app = Join-Path $stage "app"
Expand-Archive $zip $rt

# site-packages + the app folder on sys.path, and enable site.
# Joined in PowerShell (not a Python string) so "..\app" keeps its real backslash.
$pth = @("python312.zip", ".", "Lib\site-packages", "..\app", "import site") -join "`r`n"
[IO.File]::WriteAllText((Join-Path $rt "python312._pth"), $pth + "`r`n")

Write-Host "Installing dependencies (binary wheels only)..."
python -m pip install --disable-pip-version-check --no-cache-dir --only-binary=:all: `
    --platform win_amd64 --python-version 3.12 --implementation cp `
    --target (Join-Path $rt "Lib\site-packages") -r (Join-Path $root "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

New-Item -ItemType Directory -Force $app | Out-Null
Copy-Item (Join-Path $root "*.py") $app
Copy-Item (Join-Path $root "mailblaster.ico") $app
Copy-Item -Recurse (Join-Path $root "static") (Join-Path $app "static")
New-Item -ItemType File (Join-Path $app ".installed") | Out-Null   # data goes to %LOCALAPPDATA%\MailBlaster

# smoke test: the staged runtime must import every module the app needs
$check = "import sys; sys.path.insert(0, r'$app'); import flask, dns.resolver, store, mailer, verifier, inbox_sync, tunnel, templates_data, app_paths; print('imports ok')"
& (Join-Path $rt "python.exe") -c $check
if ($LASTEXITCODE -ne 0) { throw "staged runtime cannot import the app" }
Get-ChildItem $stage -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force

$iscc = Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $iscc)) { $iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" }
& $iscc (Join-Path $root "installer.iss")
if ($LASTEXITCODE -ne 0) { throw "ISCC failed" }
Get-Item (Join-Path $root "installer_output\MailBlaster-Setup.exe") | Select-Object FullName, Length
