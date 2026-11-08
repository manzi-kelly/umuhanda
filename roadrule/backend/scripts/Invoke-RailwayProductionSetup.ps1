#Requires -Version 7.0
[CmdletBinding()]
param(
    [ValidateSet('Inspect', 'Apply', 'Stage', 'Verify')]
    [string]$Phase = 'Inspect',
    [Parameter(Mandatory)][string]$ProjectId,
    [string]$Environment = 'production',
    [Parameter(Mandatory)][string]$ApiService,
    [string]$OperatorService,
    [switch]$RevokePublicTemp,
    [switch]$RevokePublicLargeObjects,
    [Parameter(Mandatory)][ValidatePattern('^[a-z_][a-z0-9_]{0,62}$')][string]$RuntimeRole,
    [Parameter(Mandatory)][ValidatePattern('^[a-z_][a-z0-9_]{0,62}$')][string]$MigrationRole,
    [Parameter(Mandatory)][ValidatePattern('^/[a-zA-Z0-9_./-]+$')][string]$CaPath,
    [Parameter(Mandatory)][ValidatePattern('^[a-zA-Z0-9.-]+$')][string]$ApiHost,
    [Parameter(Mandatory)][ValidatePattern('^https://[a-zA-Z0-9.-]+$')][string]$FrontendOrigin
)
$ErrorActionPreference = 'Stop'
if ($RuntimeRole -eq $MigrationRole -or
    $RuntimeRole -match '^(postgres$|root$|pg_)' -or
    $MigrationRole -match '^(postgres$|root$|pg_)') {
    throw 'Supply distinct, unprivileged application role names.'
}
switch ($Phase) {
    { $_ -in 'Inspect', 'Apply' } {
        if (!$OperatorService) { throw 'Specify a running Railway operator service.' }
        $remote = @('python', '-m', 'scripts.setup_railway_production',
            '--ca', $CaPath, '--runtime', $RuntimeRole, '--migrator', $MigrationRole)
        if ($Phase -eq 'Apply') {
            $remote += @('--apply', '--api-host', $ApiHost, '--frontend-origin', $FrontendOrigin)
        }
        if ($RevokePublicTemp -and $Phase -eq 'Apply') {
            $remote += '--revoke-public-temp'
        }
        if ($RevokePublicLargeObjects -and $Phase -eq 'Apply') {
            $remote += '--revoke-public-large-objects'
        }
        & railway ssh --project $ProjectId --environment $Environment --service $OperatorService -- @remote
        if ($LASTEXITCODE) { throw 'The remote setup did not complete.' }
    }
    'Stage' {
        Write-Host "API target: project $ProjectId / $Environment / $ApiService"
        if ((Read-Host 'Confirm that Railway CLI is linked to this project and the CA exists in the API container. Type STAGE railway') -cne 'STAGE railway') {
            throw 'Variable changes were not approved.'
        }
        $secret = Read-Host 'Existing runtime role password' -MaskInput
        try {
            if ([string]::IsNullOrEmpty($secret)) { throw 'Runtime password is required.' }
            $encoded = [uri]::EscapeDataString($secret)
            $root = [uri]::EscapeDataString($CaPath)
            $variables = [ordered]@{
                DATABASE_URL = "postgresql+psycopg://${RuntimeRole}:${encoded}@postgres.railway.internal:5432/railway?sslmode=verify-full&sslrootcert=$root"
                APP_ENV = 'production'
                ALLOWED_HOSTS = "$ApiHost,healthcheck.railway.app"
                CORS_ALLOWED_ORIGINS = $FrontendOrigin
                ENABLE_DOCS = 'false'
                MOCK_PAYMENTS_ENABLED = 'false'
            }
            foreach ($key in $variables.Keys) {
                $variables[$key] | & railway variable set $key --stdin --skip-deploys --environment $Environment --service $ApiService
                if ($LASTEXITCODE) { throw "Variable update failed at $key. Review before deploying." }
            }
        } finally {
            Remove-Variable secret, encoded, variables -ErrorAction SilentlyContinue
        }
        Write-Host 'Variables saved with deployment suppressed. Review before approving a release.'
    }
    'Verify' {
        $probe = & railway ssh --project $ProjectId --environment $Environment --service $ApiService -- python scripts/diagnose_database.py
        if ($LASTEXITCODE -or $probe -notcontains 'app_env=production' -or
            $probe -notcontains "connected=true database=railway role=$RuntimeRole tls=True") {
            throw 'API database diagnostic did not confirm production, the runtime role, and TLS.'
        }
        foreach ($check in @{ health = 'ok'; 'health/ready' = 'ready' }.GetEnumerator()) {
            $reply = Invoke-RestMethod "https://$ApiHost/api/v1/$($check.Key)"
            if ($reply.status -ne $check.Value) { throw "Unexpected response at $($check.Key)." }
        }
        $student = Invoke-WebRequest "$FrontendOrigin/student-api/students/sessions/me" -SkipHttpErrorCheck
        if ($student.StatusCode -ne 401) { throw "Expected unauthenticated student HTTP 401." }
        Write-Host 'Health, readiness and unauthenticated student proxy checks passed.'
    }
}
