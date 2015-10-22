# Deploying Mirantis OpenStack on a single XenServer - The power of SDN

Networking in OpenStack is often cited as one of the more complicated
things to set up.  This is made even more complicated if you don't
have control over the switches or have a lengthy approval process with
IT - ironically one of the things that IaaS solutions are intended to
ease!

One of the advantages of using XenServer for your OpenStack cloud is
that the networking is fully abstracted from the Compute VMs and the
instances.  This means you can manipulate the network mapping between
the physical devices and what OpenStack expects the networking setup
to be.  In fact, XenCenter, XenServer's Windows GUI, allows you to
create networks based on VLAN tags and to give them descriptive names
and other metadata - but there is of course a lot more power available
under the hood.

When you combine this flexible setup with Mirantis OpenStack's
easy-to-use interface and strong network verification steps, you can
simply define almost any setup for your OpenStack environemnt using
XenServer.

The following has been tested on XenServer 6.5 SP1 with Mirantis
OpenStack 6.1 and the corresponding XenServer fuel plugin (see
https://www.mirantis.com/products/openstack-drivers-and-plugins/fuel-plugins/)

# Initial setup

One key point is that the XenServer integration with OpenStack has
some optimisations which means that only EXT3 storage is supported.
Make sure when installing your XenServer you select Optimised for
XenDesktop when prompted.  Use XenCenter to check that the SR type is
EXT3 as fixing it after creating the VMs will require deleting the VMs
and starting again.

The XenServer fuel plugin for Mirantis OpenStack 6.1 currently only
supports nova-network, so we'll use the FlatDHCPManager setup.  In the
Mirantis OpenStack interface, you can define strong isolation between
the networks by using separate physical networks or defining VLANs.
While you can use these VLANs, the flexibility of the abstracted
network with XenServer means you don't have to - simply add another
private network and the VMs running the OpenStack services just see it
as a real physical interface!

For this single-server deployment, define three private
networks in XenCenter:

* 'pxe': Mirantis OpenStack uses baremetal deployment to install the
  operating system, and then loads the OpenStack packages for you.  As
  such, we need to run this on an isolated network.

* 'private': All of the OpenStack management traffic will flow over this
  network ("Management" and "Storage" will be separated by VLANs), and
  to re-use the network it will also host the public network used by
  OpenStack service nodes and the floating IP address range.

* 'br100': This specially-named bridge is hard-coded by Mirantis
  OpenStack as the bridge that will be added to Virtual Machines when
  they boot.  It will therefore be the route where traffic flows in
  and out of the VM.

In order to use Mirantis OpenStack's web UI, we also need access to
that from the external world, so we assume there is a network
associated with eth0 on the xenserver host which we will call
'external'.

# Initial Virtual Machine setup

This single-host deployment uses VMs to provide the infrastructure.  Make
sure when you set up the VMs that they are all using the 'Other
Install Media' template, and that they have at least 4GB RAM and 40GB
disk space.  Don't start any of the VMs yet though!

* Fuel: Used to host Mirantis OpenStack.  Add two networks, 'pxe' and
  'external'.

* Compute: Used to host the Nova compute and Cinder services.  Add
  three networks, 'pxe', 'private', 'br100'.  Ensure that this VM is
  set to boot from network.

* Controller: Used to host all other OpenStack services (e.g. Glance,
  KeyStone).  Add three networks, 'pxe', 'private', 'br100'. Ensure
  that this VM is set to boot from network.

Once the Compute VM is set up, we need to add another network.  The
XenServer integration with OpenStack requires that the Compute VMs are
running on the XenServer host that they will be provisioning instances
on.  They also need access to XAPI, which (unless you are in the
control domain, Dom0) can only be accessed over a network connection.
We have provided a XenCenter plugin
(https://3a98d2877cb62a6e6b14-93babe93196056fe375611ed4c1716dd.ssl.cf5.rackcdn.com/x/e/xenserver/SetupHIMN-1.0.1.zip)
to make adding a private management network easy.  Source code and compilation instructions for this
are available on github
(https://github.com/citrix-openstack/xencenter-himn-plugin/).  Simply
install the plugin, restart XenCenter, right mouse click on the
Compute VM and add the internal management network.  This network
is a link-local network which will allow the Compute VM to talk to
XAPI and provision our VMs.

# Getting external access

As mentioned earlier, Mirantis OpenStack includes a highly useful
network validation tool.  One thing this checks is that the OpenStack
service VMs must have access to the external world (specifically the
Ubuntu repositories).  We've created the 'private' network to house
these service VMs, and that clearly will not have access! Thankfully,
as XenServer is based on a standard Linux distribution, modifying the
network to make the XenServer host to act as a gateway is straight
forward.

The cross-pool private network setup in
https://www.citrix.com/blogs/2015/10/16/cross-pool-private-networks-with-xenserver-openstack-beyond/
shows how we can create a private network and use udev to set up a
temporary GRE tunnel between two private networks on different hosts,
and explains why we need to use udev to trigger the network setup.
Some of the same principles are needed in this blog, but for Mirantis
OpenStack we need to grant access from the private network to the
outside world.

The following code snippet will:

* Create a script to be run by udev when XAPI creates a new network

* Add an IP address to this bridge, which will be the gateway IP
  address

* Add a route so Dom0 knows where to send packets destined for IP
  address on the 'private' network * Add an iptables MASQUERADE rule
  to provide network address translation services to any traffic that
  is being sent to the gateway.

    echo 'SUBSYSTEM=="net" ACTION=="add" KERNEL=="xapi*" RUN+="/etc/udev/scripts/recreate-gateway.sh"' > /etc/udev/rules.d/90-gateway.rules

    bridge=$(xe network-list name-label=private params=bridge minimal=true)
    cat > /etc/udev/scripts/recreate-gateway.sh << RECREATE_GATEWAY
    #!/bin/bash
    if /sbin/ip link show $bridge > /dev/null 2>&1; then
      if !(/sbin/ip addr show $bridge | /bin/grep -q 172.16.1.1); then
        /sbin/ip addr add dev $bridge 172.16.1.1
      fi
      if !(/sbin/route -n | /bin/grep -q 172.16.1.0); then
        /sbin/route add -net 172.16.1.0 netmask 255.255.255.0 dev $bridge
      fi
    
      if !(/sbin/iptables -t nat -S | /bin/grep -q 172.16.1.0/24); then
        /sbin/iptables -t nat -A POSTROUTING -s 172.16.1.0/24 ! -d 172.16.1.0/24 -j MASQUERADE
      fi
    fi
    RECREATE_GATEWAY
    chmod +x /etc/udev/scripts/recreate-gateway.sh
    
Reboot the XenServer hosts, and then the udev rules will be active.
When we define the networks in Mirantis OpenStack we will use this
range for the "Public" network.

# Deploying Fuel

The Fuel installation process is really simple.  Download the ISO from
Mirantis (although, as this guide is written for Mirantis OpenStack
6.1 make sure you click "Download Prior Releases" as 7.0 was recently
launched), insert it into XenServer's virtual CDROM for the Fuel VM
and boot.  When the fuel setup menu appears, we always enable eth1
(which is on the 'external' network) using DHCP so you can access the
Fuel web interface directly.

Once Fuel is installed, you need to install the XenServer plugin.
Download this from the Fuel Plugins catalog to the fuel VM and install
using

    fuel plugins --install fuel-plugin-xenserver-1.0-1.0.1-1.noarch.rpm

Finally, boot up your Compute and Controller VMs.  These have the
'pxe' network as their first ethernet device, and are configured to
boot from network, so Mirantis OpenStack will discover the VMs and
register them, ready to be used.

Now everything is set up - it's really easily create your
XenServer-based OpenStack environment.

# Creating the environment

Using Mirantis' environment creation wizard, select the "Juno+Citrix
XenServer on Ubuntu 14.04.1" OpenStack release, then click through the
Wizard to finish.

On the Settings page, make sure that the XenServer Plugin is enabled,
and set the password for the XenServer host, then let's tell Mirantis
OpenStack how the networks are setup.

Go back to the Nodes tab, add the Controller and Compute nodes (check
the MAC addresses with the MAC addresses reported for the VM by
XenCenter and rename the nodes in the UI to make it easier) and then
select one at a time and Configure Interfaces.  You can't configure
them together because they have different networks visible (the
Compute VM has the additional host internal management network) but
the network layout for the two is going to be identical: eth0 is the
Admin (PXE) interface, eth2 is the VM (Fixed) and eth1 is everything
else (Public, Storage and Management).

On the Networks tab, set the Public IP settings to use 172.16.1.1 as
the gateway, an IP range of 172.16.1.2-172.16.1.100 and a Floating IP
range of 172.16.1.101-172.16.1.200.  The Storage and Mangement
networks should have a VLAN set (any VLAN, since they are on the
isolated 'private' network) and the Fixed network should _not_ be on a
VLAN (since it is using the isolated 'br100' network).

Verify the network settings and, Mirantis OpenStack should report that
the verification succeeded and that the network is configured
correctly.

Click the magic 'Deploy Changes' button, grab a cup of coffee, and
watch as your XenServer+OpenStack environment is created before your
very eyes.

Behind the scenes, quite a lot is going on.  Mirantis OpenStack is
installing Ubuntu on the service VMs, then installing OpenStack.  The
XenServer plugin is configuring them to work with XenServer and
installing critical OpenStack XAPI plugins on the XenServer host.
Finally, the images used to deploy to VMs (a TestVM called Cirros and
a larger Fedora image used for Heat testing) are installed.

As we've set Fuel's "public" IP range to be on the 'private' network,
accessing it will need a tunnel or port forwarding.  I tend to use an
SSH tunnel:

    ssh root@xenserver -L 80:172.16.1.2:80

Then your OpenStack Horizon can be accessed with a web browser pointed
to http://localhost:80.

Alternatively you can set up a route to go through the XenServer host
to the 'private' network and extend the recreate-gateway script to
setup the XenServer host as a gateway and use the same NAT technique
to allow access to the 172.16.1 range from your machine.

# Final thoughts

The use of XenServer to define the networks available for OpenStack
actually gives you a lot more flexibility than this.  Even with
private networks, you can define links between them, VLAN tags, and
the ability to pass VLANs through.  If, for example, you wanted br100
to be on a VLAN then it wouldn't need to be added to the Compute or
Controller nodes as a separate network.  A patch port can be added,
with a VLAN tag, to connect a local br100 to the 'private' network and
add a tag to any traffic from a VM that touches the network.

And, as a final thought, why not combine this approach with the
cross-pool private network setup in
https://www.citrix.com/blogs/2015/10/16/cross-pool-private-networks-with-xenserver-openstack-beyond/
to test a multi-host isolated OpenStack setup without needing to wait
for your central IT department to provision the networks you need
today!
