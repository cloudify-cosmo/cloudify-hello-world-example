#ps1_sysnative
$PSDefaultParameterValues['*:Encoding'] = 'utf8'

Write-Host "## Configuring WinRM and firewall rules.."
winrm quickconfig -q
winrm set winrm/config              '@{MaxTimeoutms="1800000"}'
winrm set winrm/config/winrs        '@{MaxMemoryPerShellMB="300"}'
winrm set winrm/config/service      '@{AllowUnencrypted="true"}'
winrm set winrm/config/service/auth '@{Basic="true"}'
&netsh advfirewall firewall add rule name="WinRM 5985" protocol=TCP dir=in localport=5985 action=allow
&netsh advfirewall firewall add rule name="WinRM 5986" protocol=TCP dir=in localport=5986 action=allow

Write-Host "## Setting password for Admin user.."
$user = [ADSI]"WinNT://localhost/Admin"
$user.SetPassword("AbCdEfG123456")
$user.SetInfo()
