from cloudify import ctx
from cloudify.state import ctx_parameters as inputs

resource_path = inputs['resource_path']

ctx.logger.info('Getting resource: {0}'.format(resource_path))
resource = ctx.get_resource(resource_path)
ctx.logger.info('Resource = "{0}"'.format(resource))
ctx.instance.runtime_properties['get_resource'] = resource

ctx.logger.info('Downloading resource: {0}'.format(resource_path))
resource_file = ctx.download_resource(resource_path)
with open(resource_file, 'r') as f:
    resource = f.read()
ctx.logger.info('Resource = "{0}"'.format(resource))
ctx.instance.runtime_properties['download_resource'] = resource
