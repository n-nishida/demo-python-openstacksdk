import os
from openstack import connection
from ConfigParser import SafeConfigParser
config = SafeConfigParser()
config.read("config.ini")

#conn = connection.Connection(auth_url=os.environ["OS_AUTH_URL"],
#                             project_name=os.environ["OS_TENANT_NAME"],
#                             username=os.environ["OS_USERNAME"],
#                             password=os.environ["OS_PASSWORD"])


def _delete_servers():
    for server in range(0, 5):
        if raw_input("Input 'y' if you want to delete %s." % server) == "y":
            #delete server
            pass


def _delete_network():
    #router interface delete
    #delete network
    #delete router
    pass


def _delete_security_group():
    pass


def _delete_keypair():
    pass


def _delete_floating_ip():
    pass


def delete():
    _delete_servers()
    _delete_network()
    _delete_security_group()
    _delete_keypair()
    _delete_floating_ip()


if __name__ == "__main__":
    delete()
