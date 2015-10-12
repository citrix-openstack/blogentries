# Cross-pool private networks with XenServer

For some time, XenServer has supported the concept of a "Cross-Server
Private Network", as a private network that can be created between
hosts in a pool.  But what do you do if you want a private network
that goes between hosts that aren't in a pool?  This was the situation
we have with OpenStack.

For testing in OpenStack it's really useful to have a completely
isolated private network, i.e. one that is not segregated using VLANs
at the switch.  Neutron requires a list of VLANs that it can use and
getting a VLAN segment allocated from central IT is difficult in many
organisations, and impossible in many!  So, we want to set up a
cross-host networking using the OVS.

Further, the XenServer integration with OpenStack does not actually
make use of pools at all; every host is a "One host pool" (since the
pool concept still exists even if there is only a single host).
Therefore what we actually need is a cross-pool private network.
Unfortunately this isn't supported by the DVSC vSwitch controller
available with XenServer, so an alternative solution was needed.

The following steps have been verified on XenServer 6.5 SP1, but
should work on many other versions.

# Creating a private network

XenServer does have an easy way to set up a private network for a
single host, with easy access to the functionality provided by
XenCenter, creating a "Single-Server Private Network".  However, as
we're going to be using the command line for the more advanced parts
of this blog, we'll also use it to create a private network.  Note
that the name label 'private' is used as a key for the bridge by the
rest of the blog, so ensure this is unique.

    xe network-create name-label=private

Now you may spot one of the idiosyncrasies of XenServer - bridges for
networks do not get created until they are needed.  This means that
this bridge does not yet exist!  A quick fix for this is to add the
network to a VM, then remove it from the VM.  If you have a running VM
with the XenServer tools installed then the VIF can be added without
rebooting it.  Otherwise, let's create a dummy VM and boot that:

    temp_vm=$(xe vm-install template="Other install media" new-name-label="temp")
    priv_network_uuid=$(xe network-list name-label=private minimal=true)
    xe vif-create network-uuid=$priv_network_uuid vm-uuid=$temp_vm device=0
    xe vm-start uuid=$temp_vm
    xe vm-shutdown force=true uuid=$temp_vm
    xe vm-destroy uuid=$temp_vm

And now, if you use ifconfig you will see that the bridge has been
created.  Of course, this is a nasty hack that we will remove later in
this blog.

# Creating a GRE tunnel

If you perform the above steps on a second XenServer host, then we
have two hosts both of which have a private network, but they cannot
talk to each other.

Let's give the XenServer hosts an IP address on the private network so
we can verify the GRE tunnel is working.  The following steps will
also add a route for 192.168.76.0/24 through the 'private' network
interface.

    bridge=$(xe network-list name-label=private params=bridge minimal=true)
    ip addr add 192.168.76.1/255.255.255.0 dev $bridge

And on the second host:

    bridge=$(xe network-list name-label=private params=bridge minimal=true)
    ip addr add 192.168.76.2/255.255.255.0 dev $bridge

Now we can connect the two hosts!  Again, this step needs to be run on
both hosts.  Setting up a GRE tunnel needs to know the target
endpoint, so use the public IP address of the other server in the
below commands, not the address we just added on the 'private'
network:

    bridge=$(xe network-list name-label=private params=bridge minimal=true)
    ovs-vsctl add-port $bridge gre0 -- set interface gre0 type=gre options:remote_ip=10.219.10.31

And on the second host:

    bridge=$(xe network-list name-label=private params=bridge minimal=true)
    ovs-vsctl add-port $bridge gre0 -- set interface gre0 type=gre options:remote_ip=10.219.10.34

Now we can ping from one host to the other, using the private network as a tunnel between the hosts!

    [root@host1 ~]# ping 192.168.76.2
    PING 192.168.76.2 (192.168.76.2) 56(84) bytes of data.
    64 bytes from 192.168.76.2: icmp_seq=1 ttl=64 time=1.74 ms
    64 bytes from 192.168.76.2: icmp_seq=2 ttl=64 time=0.151 ms

What's more, VMs connected to these bridges can also ping each other.
Proving this is left as an exercise for the reader.

Now, reboot both hosts.  Yes, really.  Do it.  Not only has the GRE
tunnel gone, but neither bridge exists - because we haven't done the
hack to force XAPI to create them again.  So, how do we persist these
settings?

# Persisting the GRE tunnel

As XAPI will create the networks on-demand, and we don't really want
to create a fake demand for these networks, we should also set up the
GRE tunnel on demand as well.  Given that XAPI doesn't provide any
hooks to do this, at first sight this sounds harder than it really is.

Udev to the rescue.

We know that every bridge created by XAPI will have the form
"xapi<N>", but we don't know when it's going to be created.  We can
only create the GRE tunnel after the bridge exists, so let's write a
udev rule to trigger a script when the bridge is created.

    echo 'SUBSYSTEM=="net" ACTION=="add" KERNEL=="xapi*" RUN+="/etc/udev/scripts/recreate-gre-tunnels.sh"' > /etc/udev/rules.d/90-gre-tunnel.rules

As a brief explanation of this udev rule, it says "When a network
device which starts with the string 'xapi' is added, run the
recreate-gre-tunnels script'.  We've added it quite late in the list
of udev rules to run so we can make sure that any renames of devices
have already occured.

Then, we need the script that will perform the recreation of the GRE
tunnel.  Note that the script will be run in a context where there are
no paths defined, so all executables referenced need to have the full
path.

    bridge=$(xe network-list name-label=private params=bridge minimal=true)
    cat > /etc/udev/scripts/recreate-gre-tunnels.sh << RECREATE_GRE_EOF
    #!/bin/bash
    if /sbin/ip link show $bridge > /dev/null 2>&1; then
        /usr/bin/ovs-vsctl add-port $bridge gre0 -- set interface gre0 type=gre options:remote_ip=10.219.10.31
    fi
    RECREATE_GRE_EOF
    chmod +x /etc/udev/scripts/recreate-gre-tunnels.sh

Of course, this udev rule needs to be added on both hosts, and the
script needs to be added (and modified) to have the correct IP address
of the _other_ host.  But once these have been added, the GRE tunnel
will be set up automatically!

If you don't have VMs yet, you can confirm this by using
the hack above and create a temporary VM to bring the bridge into
existance, then add an IP address and ping away between your two
hosts.

Now go ahead and create your VMs safe in the knowledge that there is
an isolated private network with a direct connection between the two
hosts with no switch configuration needed!