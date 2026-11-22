$ErrorActionPreference = 'Stop'
Push-Location (Join-Path $PSScriptRoot '../..')
try {
    if (-not (Test-Path -LiteralPath '.env')) {
        $settings = @{
            APP_VERSION = 'v8.8.4'
            APP_PORT = '127.0.0.1:8000'
            APP_URL = 'http://localhost:8000'
            APP_KEY = 'base64:' + [Convert]::ToBase64String([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
            DB_PASSWORD = [Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(18))
            MYSQL_ROOT_PASSWORD = [Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(18))
            MAIL_MAILER = 'log'
            MAIL_FROM_ADDR = 'lab@example.test'
            MAIL_REPLYTO_ADDR = 'lab@example.test'
        }

        Get-Content -LiteralPath '.env.docker' | ForEach-Object {
            $parts = $_.Split('=', 2)
            if ($parts.Length -eq 2 -and $settings.ContainsKey($parts[0])) {
                "$($parts[0])=$($settings[$parts[0]])"
            } else {
                $_
            }
        } | Set-Content -LiteralPath '.env' -Encoding utf8NoBOM
    }

    $envFile = Get-Content -LiteralPath '.env'
    if ('APP_VERSION=v8.8.4' -notin $envFile -or 'APP_PORT=127.0.0.1:8000' -notin $envFile -or
        'APP_URL=http://localhost:8000' -notin $envFile) {
        throw 'The existing .env does not match the pinned, loopback-only SQE configuration.'
    }

    docker compose --progress quiet -p sqe-campus-laptops -f docker-compose.yml up -d --wait --wait-timeout 150
    if ($LASTEXITCODE -ne 0) { throw 'The local Snipe-IT stack failed to start.' }
    Write-Output 'Snipe-IT is mapped to http://localhost:8000 once initialization finishes.'
} finally {
    Pop-Location
}
