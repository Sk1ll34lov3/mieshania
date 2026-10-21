<#
  Записує IG_USERNAME / IG_PASSWORD на VPS у /var/opt/mieshania/ig.env (chmod 600).
  Пароль вводиться приховано і передається в ssh через stdin (не потрапляє в аргументи/історію).

  Використання (з Windows):
    ./scripts/set_ig_password.ps1
    ./scripts/set_ig_password.ps1 -Username solov__design -Totp   # додатково спитає 2FA seed
#>
param(
    [string]$SshHost = "mieshania",
    [string]$Username = "solov__design",
    [switch]$Totp
)

$sec = Read-Host "Instagram password for $Username" -AsSecureString
$pwd = [System.Net.NetworkCredential]::new("", $sec).Password
$lines = @("IG_USERNAME=$Username", "IG_PASSWORD=$pwd")
if ($Totp) {
    $t = Read-Host "2FA (authenticator) seed" -AsSecureString
    $lines += "IG_TOTP_SECRET=" + [System.Net.NetworkCredential]::new("", $t).Password
}

$remote = 'umask 077; cat > /var/opt/mieshania/ig.env.tmp && mv /var/opt/mieshania/ig.env.tmp /var/opt/mieshania/ig.env && chmod 600 /var/opt/mieshania/ig.env'
($lines -join "`n") + "`n" | ssh $SshHost $remote
if ($LASTEXITCODE -eq 0) { Write-Host "OK: /var/opt/mieshania/ig.env оновлено" } else { Write-Error "ssh failed" }
$pwd = $null
