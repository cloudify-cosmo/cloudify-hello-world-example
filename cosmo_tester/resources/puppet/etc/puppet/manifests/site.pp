node /\.example\.com$/ {
  file {'/tmp/cloudify_operation_create':
    content => $cloudify_blueprint_id,
    tag => ['cloudify_operation_create'],
  }
}
