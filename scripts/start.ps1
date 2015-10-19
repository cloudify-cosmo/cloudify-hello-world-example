
$ErrorActionPreference = "Stop"

$PYTHON_FILE_SERVER_ROOT="C:\Windows\Temp\python-simple-http-webserver"
$PID_FILE='server.pid'

C:\CloudifyAgent\Scripts\ctx logger info "Starting HTTP server from $($PYTHON_FILE_SERVER_ROOT)"

$port=$(C:\CloudifyAgent\Scripts\ctx node properties port)

cd $PYTHON_FILE_SERVER_ROOT
C:\CloudifyAgent\Scripts\ctx logger info "Starting SimpleHTTPServer"
C:\CloudifyAgent\nssm\nssm install web-server "C:\Python27\python" -m SimpleHTTPServer $port 
C:\CloudifyAgent\nssm\nssm set web-server AppDirectory $PYTHON_FILE_SERVER_ROOT
C:\CloudifyAgent\nssm\nssm start web-server
$LastExitCode | Out-File $PID_FILE

C:\CloudifyAgent\Scripts\ctx logger info "Waiting for server to launch"

$STARTED=$FALSE

for ($i=1; $i -le 15; $i++) {
	$t = New-Object Net.Sockets.TcpClient
	$t.Connect("localhost",$Port)	
	if ($t.Connected) {
		C:\CloudifyAgent\Scripts\ctx logger info "Server is up."
		$STARTED=$TRUE
    	break
	}
	else {
		C:\CloudifyAgent\Scripts\ctx logger info "Server not up. waiting 1 second."
		timeout 1
	}	
}
if ($STARTED=$FALSE) {
	C:\CloudifyAgent\Scripts\ctx logger error "Failed starting web server in 15 seconds."
	exit 1
}
