# Importing here so that we fail fast if the required plugin is not available
# rather than waiting for VMs to be deployed first.
try:
    import fabric_plugin  # noqa
except ImportError:
    raise ImportError('cloudify-fabric-plugin must be installed for '
                      'bootstrap tests.')
