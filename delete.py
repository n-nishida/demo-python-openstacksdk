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
            conn.compute.delete_server(server.id)


def _delete_network():
    conn.network.router_remove_interface()
    conn.network.delete_network(config.defaults("network_name"))
    conn.network.delete_router(config.defaults("router_name"))


def _delete_security_group():
    conn.network.delete_security_group(config.defaults().get("security_group_name"))


def _delete_keypair():
    conn.compute.delete_keypair(config.defaults().get("keypair_name"))


def _delete_floating_ip():
    for ip in conn.network.list_ips():
        if raw_input("Input 'y' if you want to delete this floating_ip[ip_address=%s]." % ip.ip_address) == "y":
            conn.network.delete_ip(ip.ip_address)


def delete():
    _delete_servers()
    _delete_network()
    _delete_security_group()
    _delete_keypair()
    _delete_floating_ip()


if __name__ == "__main__":
    delete()
