
$ErrorActionPreference = "Stop"


$PYTHON_FILE_SERVER_ROOT="C:\Windows\Temp\python-simple-http-webserver"

C:\CloudifyAgent\nssm\nssm stop web-werver
C:\CloudifyAgent\nssm\nssm remove web-server confirm

C:\CloudifyAgent\Scripts\ctx logger info "Shutting down file server."

C:\CloudifyAgent\Scripts\ctx logger info "Deleting file server root directory $($PYTHON_FILE_SERVER_ROOT)"

Remove-Item $PYTHON_FILE_SERVER_ROOT -Force -Recurse 
