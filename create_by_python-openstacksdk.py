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


def create_router(external_network):
    click.echo("create router         : %s" % config.defaults().get("router_name"))
    return conn.network.create_router(name=config.defaults().get("router_name"),
                                      external_gateway_info={"network_id": external_network.id})


def create_network():
    click.echo("create network        : %s" % config.defaults().get("network_name"))
    return conn.network.create_network(name=config.defaults().get("network_name"))


def create_subnet(network, dns_nameserver):
    click.echo("create subnet         : %s" % config.defaults().get("subnet_name"))
    return conn.network.create_subnet(name=config.defaults().get("subnet_name"),
                                      network_id=network.id,
                                      ip_version="4",
                                      dns_nameservers=[dns_nameserver],
                                      cidr=config.defaults().get("subnet_cidr"))


def add_router_interface(router, subnet):
    click.echo("add router interface...")
    conn.network.router_add_interface(router, subnet.id)


def create_security_group():
    click.echo("create security_group : %s" % config.defaults().get("security_group_name"))
    return conn.network.create_security_group(name=config.defaults().get("security_group_name"),
                                              description=config.defaults().get("security_group_name"))


def create_security_group_rules(security_group, subnet, cidr):
    all_tcp_from_local = {
        'direction': 'ingress',
        'remote_ip_prefix': subnet.cidr,
        'protocol': "tcp",
        'port_range_min': "1",
        'port_range_max': "65535",
        'security_group_id': security_group.id,
        'ethertype': 'IPv4'
    }
    all_icmp_from_local = {
        'direction': 'ingress',
        'remote_ip_prefix': subnet.cidr,
        'protocol': 'icmp',
        'port_range_min': None,
        'port_range_max': None,
        'security_group_id': security_group.id,
        'ethertype': 'IPv4'
    }
    ssh_from_external = {
        'direction': 'ingress',
        'remote_ip_prefix': cidr,
        'protocol': "tcp",
        'port_range_min': "22",
        'port_range_max': "22",
        'security_group_id': security_group.id,
        'ethertype': 'IPv4'
    }
    conn.network.create_security_group_rule(**all_tcp_from_local)
    conn.network.create_security_group_rule(**all_icmp_from_local)
    conn.network.create_security_group_rule(**ssh_from_external)


def _output_keypair_file(keypair):
    click.echo("create keypair file   : %s" % config.defaults().get("keypair_file"))
    with open(config.defaults().get("keypair_file"), "w") as f:
        f.write(keypair.private_key)
    os.chmod(config.defaults().get("keypair_file"), 0600)


def create_keypair():
    click.echo("create keypair        : %s" % config.defaults().get("keypair_name"))
    keypair = conn.compute.create_keypair(name=config.defaults().get("keypair_name"))
    _output_keypair_file(keypair)
    return keypair


def get_user_data():
    with open(config.defaults().get("cloud_init"), 'r') as f:
        user_data = f.read()
    return user_data


def create_floating_ip(server, external_network):
    server_fixed_ip_address = server.ips(conn.session)[0].addr
    server_port = _get_server_port(server)
    return conn.network.create_ip(floating_network_id=external_network.id,
                                  fixed_ip_address=server_fixed_ip_address,
                                  port_id=server_port.id)


@click.command()
@click.option('--external_network_name', prompt='Input external network name')
@click.option('--external_network_dns_server_ip_address', prompt='Input dns server ip address')
@click.option('--cidr_can_connect_to_server', prompt='Input Cidr can connect to server by using ssh')
@click.option('--server_image_name', prompt='Input Base image name for server')
@click.option('--server_flavor_name', prompt='Input Flavor name for server')
@click.option('--server_count', prompt='Input server count')
def create(external_network_name,
           external_network_dns_server_ip_address,
           cidr_can_connect_to_server,
           server_image_name,
           server_flavor_name,
           server_count):
    """
    This program requires public network and base Linux image
    ie:
    external_network_name = "publicNW"
    external_network_dns_server_ip_address = "192.168.100.254"
    cidr_can_connect_to_server = "192.168.100.0/24"
    server_image_name = "centos-base"
    server_flavor_name = "m1.medium"
    """
    external_network = conn.network.find_network(external_network_name)
    router = create_router(external_network)
    network = create_network()
    subnet = create_subnet(network, external_network_dns_server_ip_address)
    add_router_interface(router, subnet)
    security_group = create_security_group()
    create_security_group_rules(security_group, subnet, cidr_can_connect_to_server)
    image = conn.compute.find_image(server_image_name)
    flavor = _get_flavor(server_flavor_name)
    keypair = create_keypair()
    user_data = get_user_data()

    for i in range(int(server_count)):
        server_args = {
            "name": config.defaults().get("server_prefix") + str(i),
            "flavorRef": flavor.id,
            "imageRef": image.id,
            "key_name": keypair.name,
            "networks": [{"uuid": network.id}],
            "security_group": security_group.name,
            "user_data": base64.b64encode(user_data),
            "personality": [
                {"contents": base64.b64encode(keypair.private_key), "path": config.defaults().get("keypair_file")},
            ],
            "metadata": {"foo": "bar"}
        }
        server = conn.compute.create_server(**server_args)
        server = server.wait_for_status(conn.session)
        floating_ip = create_floating_ip(server, external_network)

        click.echo("")
        click.echo(("id of " + server.name).ljust(30) + ': %s' % server.id)
        server_fixed_ip_address = server.ips(conn.session)[0].addr
        click.echo(("fixed_ip of " + server.name).ljust(30) + ': %s' % server_fixed_ip_address)
        click.echo(("floating_ip of " + server.name).ljust(30) + ': %s' % floating_ip.id)

    click.echo("")
    click.echo("...Finished!")
    click.echo("You can connect to server by using following command")
    click.echo("ssh -i %s user@server" % config.defaults().get("keypair_file"))


if __name__ == '__main__':
    create()
