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


def _delete_servers():
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


def _delete_network():
    router = conn.network.find_router(config.defaults().get("router_name"))
    subnet = conn.network.find_subnet(config.defaults().get("subnet_name"))
    network = conn.network.find_network(config.defaults().get("network_name"))

    if router and subnet:
        conn.network.router_remove_interface(router, subnet.id)
    if network:
        print("deleting subnet         : " + config.defaults().get("network_name"))
        print("deleting network        : " + config.defaults().get("network_name"))
        network.delete(conn.session)
    if router:
        print("deleting router         : " + config.defaults().get("router_name"))
        router.delete(conn.session)


def _delete_security_group():
    print("deleting security_group : " + config.defaults().get("security_group_name"))
    time.sleep(5)
    security_group = conn.network.find_security_group(config.defaults().get("security_group_name"))
    if security_group:
        security_group.delete(conn.session)


def _delete_keypair():
    print("deleting keypair        : " + config.defaults().get("keypair_name"))
    keypair = conn.compute.find_keypair(config.defaults().get("keypair_name"))
    if keypair:
        keypair.delete(conn.session)


def delete():
    _delete_servers()
    _delete_security_group()
    _delete_keypair()
    _delete_network()
    print("...Finished!")


if __name__ == "__main__":
    delete()
