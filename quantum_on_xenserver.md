# OpenStack Networking ("Quantum") on XenServer - from Notworking to Networking

Quantum, OpenStack Networking is getting more important, as it gives much more
flexibility to the cloud users than its predecessor, Nova network. If you are
interested in the details, look at the [wiki page of the
project](https://wiki.openstack.org/wiki/Quantum). I highly recommend the
videos, as they were very useful for me during my journey to the world of
OpenStack Networking.

## Initial Work
We were just after the Havana summit. All the patches that enabled the use of
Quantum with XenServer were waiting to be approved. All the work was done by
Maru Newby, the initial patch was proposed on the end of 2012. [You can look at
the patch here](https://review.openstack.org/15022). Unfortunately, the patch
did not make the Grizzly release. We decided to put much more effort to get
OpenStack Networking working with XenServer.

As I had no previous experiences with Quantum, I started to read the wiki,
watch the videos to get some basic understanding. Right after that, I started
to test the patches provided by Maru Newby.

I was using devstack to setup the environment. Several changes had to be made
in order to make it easier to test Quantum. Devstack was modified so that it
does not connect the host networks to any physical interfaces, and we also got
rid of the VLAN tagging mess. There are a lot more to do to make getting
started with devstack on XenServer easier.  [A blueprint was created to record
our
efforts.](https://blueprints.launchpad.net/devstack/+spec/xenapi-devstack-cleanup)

## Single Box Installation Using Devstack

I do not want to duplicate the [wiki page, which describes how to install an
all-in one OpenStack developer instance with
Quantum](https://wiki.openstack.org/wiki/QuantumDevstackOvsXcp). I would like
to show what the environment looks like.

### Deployment Architecture
[This picture](http://goo.gl/BuAdg) will give you an overview on what devstack
is doing. The most significant difference, is that you will have two L2 agents:

 - `q-domua` managing the OpenvSwitch in domU, providing connectivity for dhcp
   and routing components to the `physnet1` network.
 - `q-agt` managing the OpenvSwitch in dom0, connecting tenant interfaces to
   the `physnet1` network.

You might ask, what is `physnet1`. That network represents the datacenter
network, this network is accessible on the hypervisor, as "OpenStack VM
Network". It is not connected to any physical interfaces, so don't be confused
by the `phys`.

Let's look at the configuration, by issueing some quantum commands.

    $ quantum net-list

Will display two networks: `public` and `private`. Using

    $ quantum net-show <network uuid comes here>

will show the details of those networks. Look at the `private` network: the
`provider:network_type` is `vlan` and `provider:physical_network` is
`physnet1`. You can also see what VLAN id is used.  In my case, `private` is
using VLAN 1000. These numbers are coming from the `localrc` file, see the
`OVS_VLAN_RANGES` variable if you want to change the used range.

### Switch configuration
The OpenvSwitch configuration could be displayed by:

    $ sudo ovs-vsctl show

Look at the integration bridge, and notice the interfaces for the dhcp server
(`qdhcp-`) and the router (`qrouter-`). Also note, that the integration
bridge has an `uplink` port to the `physnet1` bridge - `int-br-eth1`.

Now, switch to the dom0, and look at the network configuration:

    # xe network-list

You should see a network with the name `OpenStack VM Integration Network`. Note
its bridge, and look at the OpenvSwitch configuration:

    # sudo ovs-vsctl show

This is the switch that is used by the tenant VMs. You can see a port hanging
around there with VLAN id 4095. This is an interface, that is plugged to domU,
but not used. This vif is there to force xapi to create the underlying
OpenvSwitch bridge. It turned out that simply creating a network through xapi
does not create the OpenvSwitch bridge. Please note, that this bridge also has
an uplink port to `physnet1`.

### Mapping to `physnet1`
Back to domU, look at the flows:

    $ sudo ovs-ofctl show br-int

And look for the line which represents the uplink to the physical net:

    3(int-br-eth1): addr:5a:bf:61:b5:45:49

And see how the VLANs are mapped to the physical network:

    $ sudo ovs-ofctl dump-flows br-int

And in my case the `private` network is tagged with VLAN id 1 on the domU
`br-int`:

    ... in_port=3,dl_vlan=1000 actions=mod_vlan_vid:1,NORMAL

So we expect that the port of the dhcp server and the router is tagged with
VLAN 1. Execute `sudo ovs-vsctl show`, and look for the `tag:` lines to verify
this.

### Next Steps

I was intentionally not covering the `public` network. This network is
supposed to be the external network. If you look at its configuration, you
will find, that it is mapped to `physnet1` as well, but if you are looking
for the flows, with `sudo ovs-ofctl dump-flows br-ex`, you will not find
the traces of the VLAN id. You will need to start another agent to manage
your `br-ex` bridge.

To be continued...
