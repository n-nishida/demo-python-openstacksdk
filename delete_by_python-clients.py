from novaclient.client import Client as NovaClient
from novaclient.exceptions import NotFound
from neutronclient.v2_0.client import Client as NeutronClient
from keystoneclient.auth.identity import v2
from keystoneclient import session
import os
import time
from ConfigParser import SafeConfigParser

config = SafeConfigParser()
config.read("config.ini")

auth = v2.Password(auth_url=os.environ["OS_AUTH_URL"],
                   username=os.environ["OS_USERNAME"],
                   password=os.environ["OS_PASSWORD"],
                   tenant_name=os.environ["OS_TENANT_NAME"])
nova_client = NovaClient(2, session=session.Session(auth=auth))
neutron_client = NeutronClient(session=session.Session(auth=auth))


def _get_resource(resources):
    if resources:
        return resources[0]
    else:
        return None


def _get_servers():
    servers = []
    for server in nova_client.servers.list():
        if server.name.startswith(config.defaults().get("server_prefix")):
            servers.append(server)
    return servers


def _get_floating_ips(server):
    server_floating_ips = []
    floating_ips = nova_client.floating_ips.list()
    server_ips = server.networks[config.defaults().get("network_name")]
    for server_ip in server_ips:
        for floating_ip in floating_ips:
            if floating_ip.ip == server_ip:
                server_floating_ips.append(floating_ip)
    return server_floating_ips


def _delete_floating_ips_from(server):
    server_floating_ips = _get_floating_ips(server)
    for server_floating_ip in server_floating_ips:
        print("deleting floating_ip    : " + server_floating_ip.ip)
        server_floating_ip.delete()


def _remove_security_group_from(server):
    if hasattr(server, "security_groups"):
        for security_group in server.security_groups:
            server.remove_security_group(security_group["name"])


def delete_servers():
    for server in _get_servers():
        _delete_floating_ips_from(server)
        _remove_security_group_from(server)
        print("deleting server         : " + server.name)
        server.delete()


def delete_network():
    router = _get_resource(neutron_client.list_routers(name=config.defaults().get("router_name")).get("routers"))
    network = _get_resource(neutron_client.list_networks(name=config.defaults().get("network_name")).get("networks"))
    subnet = _get_resource(neutron_client.list_subnets(name=config.defaults().get("subnet_name")).get("subnets"))

    if router and subnet:
        port = _get_resource(neutron_client.list_ports(device_id=router["id"],
                                                       fixed_ips='ip_address=' + subnet["gateway_ip"]).get("ports"))
    else:
        port = None

    if port:
        router_interface_args = {"subnet_id": subnet["id"]}
        neutron_client.remove_interface_router(router["id"], router_interface_args)

    if network:
        print("deleting subnet         : " + config.defaults().get("subnet_name"))
        print("deleting network        : " + config.defaults().get("network_name"))
        neutron_client.delete_network(network["id"])

    if router:
        print("deleting router         : " + config.defaults().get("router_name"))
        neutron_client.delete_router(router["id"])


def delete_security_group():
    try:
        security_group = nova_client.security_groups.find(name=config.defaults().get("security_group_name"))
        print("deleting security_group : " + config.defaults().get("security_group_name"))
        security_group.delete()
    except NotFound:
        pass


def delete_keypair():
    try:
        keypair = nova_client.keypairs.get(config.defaults().get("keypair_name"))
        print("deleting keypair        : " + config.defaults().get("keypair_name"))
        keypair.delete()
    except NotFound:
        pass


def delete():
    delete_servers()
    time.sleep(5)
    delete_security_group()
    delete_keypair()
    delete_network()
    print("...Finished!")


if __name__ == "__main__":
    delete()
