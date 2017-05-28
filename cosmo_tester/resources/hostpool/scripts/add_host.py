import json
import requests
from cloudify import ctx
from cloudify.exceptions import NonRecoverableError


def create_endpoint_data(port=22, protocol='ssh', ip=None):

    endpoint_data = dict(
        port=port,
        protocol=protocol
    )

    if ip:
        endpoint_data.update(ip=ip)

    ctx.logger.info('Using this endpoint: {0}'.format(endpoint_data))

    return endpoint_data


def create_credentials_data(username, password=None, key=None):

    credentials_data = dict(
        username=username
    )

    if key:
        credentials_data.update(key=key)
    elif password:
        credentials_data.update(password=password)

    ctx.logger.info('Using these credentials: {0}'.format(credentials_data))

    return credentials_data


def create_host_request_data(name, endpoint, credentials, os=None, tags=None):

    host_request_data = dict(
        name=name,
        endpoint=endpoint,
        credentials=credentials
    )

    if os:
        host_request_data.update(os=os)
    if tags:
        host_request_data.update(tags=tags)

    ctx.logger.info(
        'Adding this host to the request: {0}'
        .format(host_request_data))

    return [host_request_data]


def create_request_data(hosts, default=None):

    if not default:
        default = dict(
            os='linux',
            endpoint=create_endpoint_data()
        )

    request_data = dict(
        default=default,
        hosts=hosts
    )

    ctx.logger.info(
        'Sending this request to host pool service: {0}'
        .format(request_data))

    return request_data


def make_request(data):

    server = 'http://{0}:8080/hosts'.format(ctx.target.instance.host_ip)
    response = requests.post(server, data=json.dumps(data))
    if response.status_code != 201:
        raise NonRecoverableError('{0}'.format(response))
    ctx.logger.info('Response: {0}'.format(response))


def add_host(hostname, ip, user, port):

    if 'cloudify.openstack.nodes.WindowsServer' in \
            ctx.source.node.type_hierarchy:
        password = ctx.source.instance.runtime_properties['password']
        credentials_data = create_credentials_data(user, password=password)
        endpoint_data = create_endpoint_data(port=port,
                                             protocol='winrm',
                                             ip=ip)
        hosts = create_host_request_data(
            name=hostname, endpoint=endpoint_data,
            credentials=credentials_data, os='windows'
        )
    else:
        key_file_path = ctx.target.instance.runtime_properties['key_path']

        with open(key_file_path, 'r') as key_file_data:
            key_data = key_file_data.read()

        credentials_data = create_credentials_data(user, key=key_data)
        endpoint_data = create_endpoint_data(port=port, ip=ip)
        hosts = create_host_request_data(
            name=hostname, endpoint=endpoint_data,
            credentials=credentials_data, tags=[user]
        )

    request_data = create_request_data(hosts=hosts)

    make_request(request_data)


def main():
    # This runs in the hostpool service <-> new hostpool host relationship;
    # `source` is the new host, `target` is the service. The script runs on
    # the service.
    ctx.logger.info('Begin adding host to host pool.')

    hostname = str(ctx.source.instance.id)
    ip = str(ctx.source.instance.runtime_properties['ip'])
    port = ctx.source.node.properties['agent_config']['port']
    user = str(ctx.source.node.properties['agent_config']['user'])

    ctx.logger.info(
        'Adding this host to the Service: '
        'hostname {0} ip {1} port {2} user {3}'
        .format(hostname, ip, port, user)
    )

    add_host(hostname, ip, user, port)

    ctx.logger.info('End adding host to host pool')


main()
