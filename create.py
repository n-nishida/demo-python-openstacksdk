from openstack import connection
import os
import click
import base64

router_name = "App-Router"
network_name = "App-Net"
subnet_name = "App-Subnet"
keypair_name = "App-Keypair"
keypair_file = keypair_name + ".pem"
subnet_cidr = "192.168.0.0/24"
deploy_manager_name = "deploy_manager"
cloud_init = "cloud_init.sh"

conn = connection.Connection(auth_url=os.environ["OS_AUTH_URL"],
                             project_name=os.environ["OS_TENANT_NAME"],
                             username=os.environ["OS_USERNAME"],
                             password=os.environ["OS_PASSWORD"])


def _get_flavor(flavor_name):
    for flavor in conn.compute.list_flavors():
        if flavor.name == flavor_name:
            return flavor


@click.command()
@click.option('--external_network_name', default="public", help='External network connected to router.')
@click.option('--subnet_dns_server_ip_address', prompt='Application Subnet dns server ip address')
@click.option('--ssh_accessible_cidr', prompt='Cidr has ssh connectivity to deployed servers')
@click.option('--base_image_name', prompt='Deployment base image name')
@click.option('--deploy_manager_flavor_name', prompt='Flavor name of deploy manager(It needs 4G memory at least)')
@click.option('--deploy_server_flavor_name', prompt='Flavor name of deploy server')
@click.option('--available_zone', prompt='available_zone for app')
def create(external_network_name,
           subnet_dns_server_ip_address,
           ssh_accessible_cidr,
           base_image_name,
           deploy_manager_flavor_name,
           deploy_server_flavor_name,
           available_zone):
    """This program requires public network and base CentOS6.X image"""
    external_network = conn.network.find_network(external_network_name)
    app_router = conn.network.create_router(name=router_name,
                                            external_gateway_info={"network_id": external_network.id})
    app_network = conn.network.create_network(name=network_name)
    app_subnet = conn.network.create_subnet(name=subnet_name,
                                            network_id=app_network.id,
                                            ip_version="4",
                                            dns_nameservers=[subnet_dns_server_ip_address],
                                            cidr=subnet_cidr)
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

    keypair = conn.compute.create_keypair(name=keypair_name)
    with open(keypair_file , "w") as f:
        f.write(keypair.private_key)

    with open(cloud_init, 'r') as f:
        user_data = f.read()

    manager_server_args = {
        "name": deploy_manager_name,
        "flavorRef": flavor.id,
        "imageRef": image.id,
        "key_name": keypair.name,
        "networks": [{"uuid": app_network.id}],
        "security_groups": [security_group.id],
        "user_data": base64.b64encode(user_data),
        "personality": [
            {"contents": keypair.private_key, "path": keypair_file},
        ],
        "meta_data": {
            "image_id": image.id,
            "flavor": deploy_server_flavor_name,
            "network_id": app_network.id,
            "key_name": keypair_name,
            "available_zone": available_zone
        }
    }

    manager_server = conn.compute.create_server(**manager_server_args)

    floating_ip = conn.network.create_ip(floating_network_id=external_network.id)

    click.echo('Hello %s!' % "nishida")

if __name__ == '__main__':
    create()
