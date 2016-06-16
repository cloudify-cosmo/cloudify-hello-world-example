# Create a directory for a our simple web server
$python_web_server_root = $env:TEMP + "\python-simple-http-webserver\"
If(Test-Path $python_web_server_root){
    Remove-Item $python_web_server_root
}
ctx logger info ("Creating HTTP server root directory at " + $python_web_server_root)
New-Item -Path $python_web_server_root -ItemType Directory

# Download server resources directly from Cloudify manager using ctx
cd $python_web_server_root
ctx logger info "Downloading blueprint resources..."
$index_path="index.html"
$python_web_server_index_path = $python_web_server_root + $index_path
ctx download-resource-and-render $index_path $python_web_server_index_path
$image_path="images/cloudify-logo.png"
$python_web_server_image_path = $python_web_server_root + "cloudify-logo.png"
ctx download-resource $image_path $python_web_server_image_path
