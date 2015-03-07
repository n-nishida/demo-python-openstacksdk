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


def _get_server_port(server):
    for port in conn.network.list_ports():
        for ip in port.fixed_ips:
            if ip.get("subnet_id") == conn.network.find_subnet(config.defaults().get("subnet_name")).id and \
                    ip.get("ip_address") == server.ips(conn.session)[0].addr:
                return port


@click.command()
@click.option('--external_network_name', prompt='Input External network name')
@click.option('--external_network_dns_server_ip_address', prompt='Input Dns server ip address')
@click.option('--cidr_can_connect_to_app_network', prompt='Input Cidr ')
@click.option('--base_image_name', prompt='Input Base image name for servers')
@click.option('--deploy_manager_flavor_name', prompt='Input Flavor name for deploy manager(4G RAM size at least)')
@click.option('--deploy_server_flavor_name', prompt='Input Flavor name for deploy servers')
@click.option('--app_network_availability_zone', prompt='Input Availability zone for servers')
def create(external_network_name,
           external_network_dns_server_ip_address,
           cidr_can_connect_to_app_network,
           base_image_name,
           deploy_manager_flavor_name,
           deploy_server_flavor_name,
           app_network_availability_zone):
    """
    This program requires public network and base CentOS6.X image
    external_network_name = "publicNW"
    external_network_dns_server_ip_address = "192.168.100.254"
    cidr_can_connect_to_app_network = "192.168.100.0/24"
    base_image_name = "centos-base"
    deploy_manager_flavor_name = "m1.medium"
    deploy_server_flavor_name = "m1.xsmall"
    app_network_availability_zone = "nova"
    """
    external_network = conn.network.find_network(external_network_name)
    app_router = conn.network.create_router(name=config.defaults().get("router_name"),
                                            external_gateway_info={"network_id": external_network.id})
    app_network = conn.network.create_network(name=config.defaults().get("network_name"))
    app_subnet = conn.network.create_subnet(name=config.defaults().get("subnet_name"),
                                            network_id=app_network.id,
                                            ip_version="4",
                                            dns_nameservers=[external_network_dns_server_ip_address],
                                            cidr=config.defaults().get("subnet_cidr"))
    conn.network.router_add_interface(app_router, app_subnet.id)

    security_group = conn.network.create_security_group(name=config.defaults().get("security_group_name"),
                                                        description=config.defaults().get("security_group_name"))
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
        'remote_ip_prefix': cidr_can_connect_to_app_network,
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
        "security_group": security_group.name,
        "user_data": base64.b64encode(user_data),
        "personality": [
            {"contents": base64.b64encode(keypair.private_key), "path": config.defaults().get("keypair_file")},
        ],
        "metadata": {
            "image_id": image.id,
            "flavor": deploy_server_flavor_name,
            "network_id": app_network.id,
            "key_name": config.defaults().get("keypair_name"),
            "availability_zone": app_network_availability_zone
        }
    }

    manager_server = conn.compute.create_server(**manager_server_args)
    manager_server = manager_server.wait_for_status(conn.session)
    manager_server_fixed_ip_address = manager_server.ips(conn.session)[0].addr
    manager_server_port = _get_server_port(manager_server)

    floating_ip = conn.network.create_ip(floating_network_id=external_network.id,
                                         fixed_ip_address=manager_server_fixed_ip_address,
                                         port_id=manager_server_port.id)



    click.echo('Hello %s!' % "nishida")

if __name__ == '__main__':
    create()
