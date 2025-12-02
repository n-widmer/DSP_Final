<#
setup-db.ps1

One-command helper to import `dsp_final_schema.sql` into a local MySQL server from PowerShell.

Usage examples:
  # Prompt for password interactively
  .\setup-db.ps1 -PromptForPassword

  # Provide password on the command line (less secure)
  .\setup-db.ps1 -User root -Password example

    # Specify host/port/database
    .\setup-db.ps1 -DBHost 127.0.0.1 -Port 3306 -User root -DbName dsp_final -PromptForPassword
#>
param(
    [string]$DBHost = "127.0.0.1",
    [int]$Port = 3306,
    [string]$User = "root",
    [string]$DbName = "dsp_final",
    [switch]$PromptForPassword,
    [string]$Password = ""
)

if ($PromptForPassword) {
    $secure = Read-Host -AsSecureString "Enter MySQL password for $User@$DBHost"
    $Password = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure))
}

$schemaFile = Join-Path $PSScriptRoot 'dsp_final_schema.sql'
if (-not (Test-Path -Path $schemaFile)) {
    Write-Error "Schema file not found: $schemaFile"
    exit 1
}

# Locate mysql client
$mysqlExe = $null
$cmd = Get-Command mysql -ErrorAction SilentlyContinue
if ($cmd) { $mysqlExe = $cmd.Source }
else {
    $candidates = @("C:\\Program Files\\MySQL\\MySQL Server 8.0\\bin\\mysql.exe", "C:\\Program Files\\MySQL\\MySQL Server 5.7\\bin\\mysql.exe")
    foreach ($p in $candidates) { if (Test-Path $p) { $mysqlExe = $p; break } }
}

if (-not $mysqlExe) {
    Write-Error "mysql client not found on PATH or common install locations. Install MySQL client or add it to PATH."
    exit 2
}

# Use MYSQL_PWD for a non-interactive password (note: still sensitive in memory)
if ($Password -ne "") { $env:MYSQL_PWD = $Password } else { Remove-Item env:MYSQL_PWD -ErrorAction SilentlyContinue }

Write-Host "Importing schema into $($User)@$($DBHost):$($Port)/$($DbName) using $mysqlExe"

try {
    Get-Content -Path $schemaFile -Raw | & $mysqlExe -u $User -h $DBHost -P $Port $DbName
    $exit = $LASTEXITCODE
} catch {
    Write-Error "Failed to run import: $_"
    Remove-Item env:MYSQL_PWD -ErrorAction SilentlyContinue
    exit 3
}

# Clear sensitive env var
Remove-Item env:MYSQL_PWD -ErrorAction SilentlyContinue

if ($exit -eq 0) {
    Write-Host "Schema import completed successfully."
    exit 0
} else {
    Write-Error "mysql exited with code $exit"
    exit $exit
}
