# shut down the simple web server that was launched in 'start' life cycle
$python_web_server_root = $env:TEMP + "\python-simple-http-webserver\"
$server_pid_file = $python_web_server_root + "server.pid"

$process_id = Get-Content $server_pid_file
ctx logger info ("Shutting down HTTP server. PID = " + $process_id)
Stop-Process -id $process_id -Force

# delete simple web server resources that were download from the manager in 'configure' life cycle
cd $env:TEMP
ctx logger info ("Deleting HTTP server root directory " + $python_web_server_root)
Remove-Item $python_web_server_root -recurse
