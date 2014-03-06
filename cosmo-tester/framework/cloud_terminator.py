import novaclient.v1_1.client as nvclient
import yaml
import neutronclient.v2_0.client as neclient

__author__ = 'nirb'


def teardown(cloud_config_file_name):
    cloud_config_file_path = '../resources/' + cloud_config_file_name
    creds = get_client_creds(cloud_config_file_path)
    nova = nvclient.Client(**creds)

    stream = open(cloud_config_file_path, 'r')
    config_yaml = yaml.load(stream)

    mng_instance_name = config_yaml['compute']['management_server']['instance']['name']
    network_name = config_yaml['networking']['int_network']['name']
    mng_keypair_name = config_yaml['compute']['management_server']['management_keypair']['name']
    agents_keypair_name = config_yaml['compute']['agent_servers']['agents_keypair']['name']
    mng_security_group_name = config_yaml['networking']['management_security_group']['name']
    agents_security_group_name = config_yaml['networking']['agents_security_group']['name']
    router_name = config_yaml['networking']['router']['name']

    for server in nova.servers.list():
        if mng_instance_name == server.human_id:
            server.delete()
            break

    neutron = neclient.Client(username=creds['username'],
                              password=creds['api_key'],
                              tenant_name=creds['project_id'],
                              region_name=creds['region_name'],
                              auth_url=creds['auth_url'])

    # for router in neutron.list_routers()['routers']:
    #     if router_name == router['name']:
    #         neutron.add_interface_router(router['id'])
    #         break

    for network in neutron.list_networks()['networks']:
        if network_name == network['name']:
            neutron.delete_network(network['id'])
            break

    for keypair in nova.keypairs.list():
        if mng_keypair_name == keypair.name:
            nova.keypairs.delete(keypair)
            break
        if agents_keypair_name == keypair.name:
            nova.keypairs.delete(keypair)
            break

    for sg in nova.security_groups.list():
        if mng_security_group_name == sg.name:
            nova.security_groups.delete(sg)
            break
        if agents_security_group_name == sg.name:
            nova.security_groups.delete(sg)
            break


def get_client_creds(cloud_config_file_path):
    stream = open(cloud_config_file_path, 'r')
    config_yaml = yaml.load(stream)
    d = {}
    d['username'] = config_yaml['keystone']['username']
    d['api_key'] = config_yaml['keystone']['password']
    d['auth_url'] = config_yaml['keystone']['auth_url']
    d['project_id'] = config_yaml['keystone']['tenant_name']
    d['region_name'] = config_yaml['compute']['region']
    return d
