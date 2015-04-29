cmd /c winrm quickconfig -quiet
cmd /c winrm s winrm/config/service @{AllowUnencrypted="true";MaxConcurrentOperationsPerUser="4294967295"}
cmd /c winrm s winrm/config/service/auth @{Basic="true"}
cmd /c winrm s winrm/config/winrs @{MaxShellsPerUser="2147483647"}

cmd /c msiexec /i https://www.python.org/ftp/python/2.7.6/python-2.7.6.msi TARGETDIR=C:\Python27 ALLUSERS=1 /qn

cmd /c powershell Set-ExecutionPolicy Unrestricted > NUL 2> NUL
