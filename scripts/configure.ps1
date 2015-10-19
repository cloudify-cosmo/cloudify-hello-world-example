
$ErrorActionPreference = "Stop"

$PYTHON_FILE_SERVER_ROOT='C:\Windows\Temp\python-simple-http-webserver'
if (Test-Path $PYTHON_FILE_SERVER_ROOT) { 
	echo "Removing file server root folder $($PYTHON_FILE_SERVER_ROOT)"
	Remove-Item $PYTHON_FILE_SERVER_ROOT -Force -Recurse 
}
C:\CloudifyAgent\Scripts\ctx logger info "Creating HTTP server root directory at $($PYTHON_FILE_SERVER_ROOT)"

mkdir $PYTHON_FILE_SERVER_ROOT

cd $PYTHON_FILE_SERVER_ROOT

$index_path="index.html"
$image_path="images/cloudify-logo.png"

C:\CloudifyAgent\Scripts\ctx logger info "Downloading blueprint resources..."
C:\CloudifyAgent\Scripts\ctx download-resource $index_path $PYTHON_FILE_SERVER_ROOT\index.html
C:\CloudifyAgent\Scripts\ctx download-resource $image_path $PYTHON_FILE_SERVER_ROOT\cloudify-logo.png

C:\CloudifyAgent\Scripts\ctx logger info "Preparing index.html..."

New-Item -ItemType file $PYTHON_FILE_SERVER_ROOT\index1.html

Get-Content $PYTHON_FILE_SERVER_ROOT\index.html | ForEach-Object { $_ -replace 0, $(C:\CloudifyAgent\Scripts\ctx blueprint id) } | ForEach-Object { $_ -replace 1, $(C:\CloudifyAgent\Scripts\ctx deployment id) } | ForEach-Object { $_ -replace 2, $(C:\CloudifyAgent\Scripts\ctx node id) } | ForEach-Object { $_ -replace 3, "cloudify-logo.png" } | Set-Content $PYTHON_FILE_SERVER_ROOT\index1.html
Remove-Item $PYTHON_FILE_SERVER_ROOT\index.html
Rename-Item $PYTHON_FILE_SERVER_ROOT\index1.html $PYTHON_FILE_SERVER_ROOT\index.html
