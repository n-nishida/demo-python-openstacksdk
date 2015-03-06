from openstack import connection
import os
import click
import base64
from ConfigParser import SafeConfigParser
config = SafeConfigParser()
config.read("config.ini")

conn = connection.Connection(auth_url=os.environ["OS_AUTH_URL"],
                             project_name=os.environ["OS_TENANT_NAME"],
                             username=os.environ["OS_USERNAME"],
                             password=os.environ["OS_PASSWORD"])


def _get_flavor(flavor_name):
    for flavor in conn.compute.list_flavors():
        if flavor.name == flavor_name:
            return flavor


@click.command()
@click.option('--external_network_name', prompt='External network name')
@click.option('--subnet_dns_server_ip_address', prompt='Application Subnet dns server ip address')
@click.option('--ssh_accessible_cidr', prompt='Your working network Cidr')
@click.option('--base_image_name', prompt='Deployment base image name')
@click.option('--deploy_manager_flavor_name', prompt='Flavor name of deploy manager(It needs 4G memory at least)')
@click.option('--deploy_server_flavor_name', prompt='Flavor name of deploy servers')
@click.option('--availability_zone', prompt='Availability zone of deploy servers')
def create(external_network_name,
           subnet_dns_server_ip_address,
           ssh_accessible_cidr,
           base_image_name,
           deploy_manager_flavor_name,
           deploy_server_flavor_name,
           availability_zone):
    """This program requires public network and base CentOS6.X image"""
    external_network = conn.network.find_network(external_network_name)
    app_router = conn.network.create_router(name=config.defaults().get("router_name"),
                                            external_gateway_info={"network_id": external_network.id})
    app_network = conn.network.create_network(name=config.defaults().get("network_name"))
    app_subnet = conn.network.create_subnet(name=config.defaults().get("subnet_name"),
                                            network_id=app_network.id,
                                            ip_version="4",
                                            dns_nameservers=[subnet_dns_server_ip_address],
                                            cidr=config.defaults().get("subnet_cidr"))
    conn.network.router_add_interface(app_router, app_subnet.id)

    security_group = conn.network.create_security_group(name="APP", description="APP")
    all_tcp_from_local = {
        'direction': 'ingress',
        'remote_ip_prefix': app_subnet.cidr,
        'protocol': "tcp",
        'port_range_min': "1",
        'port_range_max': "65535",
        'security_group_id': security_group.id,
        'ethertype': 'IPv4'
    }
    all_icmp_from_local = {
        'direction': 'ingress',
        'remote_ip_prefix': app_subnet.cidr,
        'protocol': 'icmp',
        'port_range_min': None,
        'port_range_max': None,
        'security_group_id': security_group.id,
        'ethertype': 'IPv4'
    }
    ssh_from_external =  {
        'direction': 'ingress',
        'remote_ip_prefix': ssh_accessible_cidr,
        'protocol': "tcp",
        'port_range_min': "22",
        'port_range_max': "22",
        'security_group_id': security_group.id,
        'ethertype': 'IPv4'
    }
    conn.network.create_security_group_rule(**all_tcp_from_local)
    conn.network.create_security_group_rule(**all_icmp_from_local)
    conn.network.create_security_group_rule(**ssh_from_external)

    image = conn.compute.find_image(base_image_name)

    flavor = _get_flavor(deploy_manager_flavor_name)

    keypair = conn.compute.create_keypair(name=config.defaults().get("keypair_name"))
    with open(config.defaults().get("keypair_file"), "w") as f:
        f.write(keypair.private_key)

    with open(config.defaults().get("cloud_init"), 'r') as f:
        user_data = f.read()

    manager_server_args = {
        "name": config.defaults().get("deploy_manager_name"),
        "flavorRef": flavor.id,
        "imageRef": image.id,
        "key_name": keypair.name,
        "networks": [{"uuid": app_network.id}],
        "security_groups": [security_group.id],
        "user_data": base64.b64encode(user_data),
        "personality": [
            {"contents": base64.b64encode(keypair.private_key), "path": config.defaults().get("keypair_file")},
        ],
        "meta_data": {
            "image_id": image.id,
            "flavor": deploy_server_flavor_name,
            "network_id": app_network.id,
            "key_name": config.defaults().get("keypair_name"),
            "availability_zone": availability_zone
        }
    }

    manager_server = conn.compute.create_server(**manager_server_args)

    floating_ip = conn.network.create_ip(floating_network_id=external_network.id)

    click.echo('Hello %s!' % "nishida")

if __name__ == '__main__':
    create()
