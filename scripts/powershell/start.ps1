function open_firewall_port($port)
{
    netsh advfirewall firewall add rule name="HTTP" protocol=TCP dir=in localport=$port action=allow
}

$python_web_server_root = $env:TEMP + "\python-simple-http-webserver\"
# retrieve the webserver_port value that was provided as an input to the deployment
$python_web_server_port = ctx node properties port
# punch a hole in the VM firewall to have simple web server accessible for users outside this VM
open_firewall_port($python_web_server_port)
ctx logger info ("Starting HTTP server from " + $python_web_server_root)
ctx logger info ("HTTP Server port is " + $python_web_server_port)
cd $python_web_server_root
# launch simple web server in a separate window to avoid blocking the execution flow
$process = Start-Process -FilePath python -ArgumentList '-m', 'SimpleHTTPServer', $python_web_server_port -PassThru
# save simple web server process ID in a file in order to be able to shut it down later on in the 'stop' life cycle
$process.Id | Out-File -FilePath server.pid

function server_is_up{
    $client = New-Object System.Net.WebClient
    Try{
        $python_web_server_url = "http://127.0.0.1:" + $python_web_server_port
        $client.DownloadString($python_web_server_url) | Out-Null
        return $TRUE
    }
    Catch
    {
        return $FALSE
    }
}

# make sure that simple web server is up and running
$started = $FALSE
for($i=0; $i -le 15; $i++){
    If(server_is_up -eq $TRUE){
        $started = $TRUE
        break
    }
    Else{
        Start-Sleep -s 1
    }
}

If($started -eq $FALSE){
    ctx logger error "Failed starting web server in 15 seconds"
}
