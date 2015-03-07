import os
from openstack import connection
from ConfigParser import SafeConfigParser
config = SafeConfigParser()
config.read("config.ini")

conn = connection.Connection(auth_url=os.environ["OS_AUTH_URL"],
                             project_name=os.environ["OS_TENANT_NAME"],
                             username=os.environ["OS_USERNAME"],
                             password=os.environ["OS_PASSWORD"])


def _delete_servers():
    for server in conn.compute.list_servers():
        if raw_input("Input 'y' if you want to delete this server[name=%s, id=%s]." % (server.name, server.id)) == "y":
            server.delete(conn.session)


def _delete_network():
    router = conn.network.find_router(config.defaults().get("router_name"))
    subnet = conn.network.find_subnet(config.defaults().get("subnet_name"))
    network = conn.network.find_network(config.defaults().get("network_name"))

    conn.network.router_remove_interface(router, subnet.id)
    network.delete(conn.session)
    router.delete(conn.session)


def _delete_security_group():
    security_group = conn.network.find_security_group(config.defaults().get("security_group_name"))
    security_group.delete(conn.session)


def _delete_keypair():
    keypair = conn.network.find_keypair(config.defaults().get("keypair_name"))
    keypair.delete(conn.session)


def _delete_floating_ip():
    for ip in conn.network.list_ips():
        if raw_input("Input 'y' if you want to delete this floating_ip[ip_address=%s]." % ip.ip_address) == "y":
            ip.delete(conn.session)


def delete():
    _delete_servers()
    _delete_network()
    _delete_security_group()
    _delete_keypair()
    _delete_floating_ip()


if __name__ == "__main__":
    delete()
