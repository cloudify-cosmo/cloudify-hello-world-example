
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

ctx logger info "Downloading blueprint resources..."
C:\CloudifyAgent\Scripts\ctx logger info "Preparing index.html..."
ctx download-resource-and-render $index_path $PYTHON_FILE_SERVER_ROOT\index.html
ctx download-resource $image_path $PYTHON_FILE_SERVER_ROOT\cloudify-logo.png


