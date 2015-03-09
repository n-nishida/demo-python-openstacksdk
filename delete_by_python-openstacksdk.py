import os
import time
from openstack import connection
from ConfigParser import SafeConfigParser

config = SafeConfigParser()
config.read("config.ini")

conn = connection.Connection(auth_url=os.environ["OS_AUTH_URL"],
                             project_name=os.environ["OS_TENANT_NAME"],
                             username=os.environ["OS_USERNAME"],
                             password=os.environ["OS_PASSWORD"])


def _get_resource(generator):
    try:
        return generator.next()
    except StopIteration:
        return None


def _get_servers():
    servers = []
    for server in conn.compute.list_servers():
        if server.name.startswith(config.defaults().get("server_prefix")):
            servers.append(server)
    return servers


def _get_floating_ips(server):
    server_floating_ips = []
    floating_ips = [floating_ip for floating_ip in conn.network.list_ips()]
    for server_ip in server.ips(conn.session):
        for floating_ip in floating_ips:
            if floating_ip.floating_ip_address == server_ip.addr:
                server_floating_ips.append(floating_ip)
    return server_floating_ips


def _delete_floating_ips_from(server):
    server_floating_ips = _get_floating_ips(server)
    for server_floating_ip in server_floating_ips:
        # By default, ip.id responds floating ip address, not floating ip uuid.
        # However delete API expects ip.id to respond uuid.
        # By changing value of id_attribute property from "floating_ip_address" to "id",
        # ip.id responds uuid, not ip address.
        print("deleting floating_ip    : " + server_floating_ip.floating_ip_address)
        server_floating_ip.id_attribute = "id"
        server_floating_ip.delete(conn.session)


def delete_servers():
    for server in _get_servers():
        _delete_floating_ips_from(server)
        print("deleting server         : " + server.name)
        server.delete(conn.session)


def delete_servers():
    for server in conn.compute.list_servers():
        floating_ips = [floating_ip for floating_ip in conn.network.list_ips()]
        if server.name.startswith(config.defaults().get("server_prefix")) and \
            raw_input("Input 'y' if you want to delete this server[name=%s, id=%s]: " % (
                server.name, server.id)) == "y":
            for server_ip in server.ips(conn.session):
                for floating_ip in floating_ips:
                    if floating_ip.floating_ip_address == server_ip.addr:
                        # By default, ip.id responds floating ip address, not floating ip uuid.
                        # However delete API expects ip.id to respond uuid.
                        # By changing value of id_attribute property from "floating_ip_address" to "id",
                        # ip.id responds uuid, not ip address.
                        print("deleting floating_ip    : " + floating_ip.floating_ip_address)
                        floating_ip.id_attribute = "id"
                        floating_ip.delete(conn.session)
            server.delete(conn.session)


def delete_network():
    router = _get_resource(conn.network.list_routers(name=config.defaults().get("router_name")))
    network = _get_resource(conn.network.list_networks(name=config.defaults().get("network_name")))
    subnet = _get_resource(conn.network.list_subnets(name=config.defaults().get("subnet_name")))

    if router and subnet:
        port = _get_resource(conn.network.list_ports(device_id=router.id, fixed_ips='ip_address=' + subnet.gateway_ip))

    if port:
        conn.network.router_remove_interface(router, subnet.id)

    if network:
        print("deleting subnet         : " + config.defaults().get("subnet_name"))
        print("deleting network        : " + config.defaults().get("network_name"))
        network.delete(conn.session)

    if router:
        print("deleting router         : " + config.defaults().get("router_name"))
        router.delete(conn.session)


def delete_security_group():
    security_group = conn.network.find_security_group(config.defaults().get("security_group_name"))
    if security_group:
        print("deleting security_group : " + config.defaults().get("security_group_name"))
        security_group.delete(conn.session)


def delete_keypair():
    keypair = conn.compute.find_keypair(config.defaults().get("keypair_name"))
    if keypair:
        print("deleting keypair        : " + config.defaults().get("keypair_name"))
        keypair.delete(conn.session)


def delete():
    delete_servers()
    time.sleep(5)
    delete_security_group()
    delete_keypair()
    delete_network()
    print("...Finished!")


if __name__ == "__main__":
    delete()
