---
title: XenServer and Neutron in MOS
date: 2016-08-31 16:13:00 Z
---

Mirantis OpenStack is a highly popular OpenStack distribution and Citrix has released
an official XenServer [Fuel](https://wiki.openstack.org/wiki/Fuel) plug-in based on Mirantis
OpenStack 8.0, which integrates with Neutron for the first time.
You can download our plug-in from the
[Mirantis fuel plug-in](https://www.mirantis.com/validated-solution-integrations/fuel-plugins/) page.

In this blog, I will focus on network part since neutron project is introduced in
XenServer Fuel plug-in for the first time. For an introduction to Mirantis OpenStack and the XenServer plug-in, please refer to a previous [blog post](https://www.citrix.com/blogs/2016/07/11/introduction-to-xenserver-fuel-plugin/).

### 1. Neutron brief

Basically Neutron is an OpenStack project which provides "networking as a service" (NaaS). It's a stand-alone service alongside other services such as Nova (compute),
Glance (image), Cinder (storage). It provides high level abstraction of network resources,
such as network, subnet, port, router, etc. Further it enforces SDN, delegating its implementation
and functionalities to the plugin, which is not possible in nova-network.

The picture from the OpenStack official website describes typical deployment with Neutron.

* Controller node: Provide management functions, such as API servers and scheduling
  services for Nova, Neutron, Glance and Cinder. It's the central part where most standard OpenStack services and tools run.

* Network node: Provide network services, runs networking plug-in, layer 2 agent,
  and several layer 3 agents. Handles external connectivity for virtual machines.

  * Layer 2 services include provisioning of virtual networks and tunnels.

  * Layer 3 services include routing, NAT, and DHCP.

* Compute node: Provide computing service, it manages the hypervisors and virtual machines.

Note: With Mirantis OpenStack, network node and controller node combined to controller node

![687474703a2f2f646f63732e6f70656e737461636b2e6f72672f73656375726974792d67756964652f5f696d616765732f3161612d6e6574776f726b2d646f6d61696e732d6469616772616d2e706e67.png](/uploads/687474703a2f2f646f63732e6f70656e737461636b2e6f72672f73656375726974792d67756964652f5f696d616765732f3161612d6e6574776f726b2d646f6d61696e732d6469616772616d2e706e67.png)

### 2. How neutron works under XenServer

Back to XenServer and Neutron, let's start from those networks.

#### 2.1 Logical networks

With Mirantis OpenStack, there are several networks involved.

    OpenStack Public network (br-ex)
    OpenStack Private network (br-prv)
    Internal network
        OpenStack Management network (br-mgmt)
        OpenStack Storage network (br-storage)
        Fuel Admin(PXE) network (br-fw-admin)

* OpenStack Public network (br-ex):

This network should be represented as tagged or untagged isolated L2 network
segment. Servers for external API access and providing VMs with connectivity
to/from networking outside the cloud. Floating IPs are implemented with L3
agent \+ NAT rules on Controller nodes

* Private network (br-prv):

This is for traffics from/to tenant VMs. Under XenServer, we use OpenvSwitch VLAN (802.1q).
OpenStack tenant can define their own L2 private network allowing IP overlap.

* Internal network:

  * OpenStack Management network (br-mgmt): This is targeted for OpenStack management, it's used to access OpenStack services, can be tagged or untagged VLAN network.

  * OpenStack Storage network (br-storage): This is used to provide storage services such as replication traffic
    from Ceph, can tagged or untagged VLAN network.

  * Fuel Admin(PXE) network (br-fw-admin): This is used for creating and booting new nodes.
    All controller and compute nodes will boot from this PXE network and will get its IP address via Fuel's internal dhcp server.

![MOS-XS-net-topo.png](/uploads/MOS-XS-net-topo.png)

#### 2.2 Traffic flow

In this section, we will explain how traffic goes from VM to external network and traffic between VMs. Also explain the OVS rules supporting these behavior.

##### 2.2.1 Traffic from VM to external network

The major difference when using XenServer as hypervisor under OpenStack is that it has the privileged domain, dom0. When booting a VM, the VM's NIC (virtual NIC) is acutally the frontend, dom0 manages its backend known as VIF, so regarding the VM's NIC and traffic, dom0 will be involved of course.  As you can see from the below picture, the neutron-ovs-agent runs in comput node (the unprivileged domain, domU), but the ovs it controls actually resides in dom0.

![neutron-vlan-v2.png](/uploads/neutron-vlan-v2-c30545.png)

Let's assume VM1 with fixed IP: 192.168.30.4, floating IP: 10.71.17.81,
when VM1 ping www.google.com, how the traffic goes.

* In compute node:

Step-1. VM1(eth1) sent packet out through port `tap`

Step-2. Security group rules on Linux bridge `qbr` handle firewalling and
state tracking for the packages

Step-3. VM1's packages arrived port `qvo`, `internal tag 16` will be added to the packages

      Bridge br-int
        fail_mode: secure
        Port br-int
            Interface br-int
                type: internal
        Port "qvof5602d85-2e"
            tag: 16
            Interface "qvof5602d85-2e"

Step-4. VM1's package arrived port `int-br-prv` triggering openflow rules,
`internal tag 16` was changed to `physical VLAN 1173`.

        cookie=0x0, duration=12104.028s, table=0, n_packets=257, n_bytes=27404, idle_age=88, priority=4,in_port=7,dl_vlan=16 actions=mod_vlan_vid:1173,NORMAL

* In network node:

Step-5. VM1's packages went through physical VLAN network to
network node bridge `br-int` via port `int-br-prv` triggering
openflow rules, changing `physical VLAN 1173` to `internal tag 6`.

      Bridge br-int        
        Port int-br-prv
            Interface int-br-prv
                type: patch
                options: {peer=phy-br-prv}

openflow rules:

      ovs-ofctl dump-flows br-int
      NXST_FLOW reply (xid=0x4):
        cookie=0xbe6ba01de8808bce, duration=12594.481s, table=0, n_packets=253, n_bytes=29517, idle_age=131, priority=3,in_port=1,dl_vlan=1173 actions=mod_vlan_vid:6,NORMAL

Step-6. VM1's packages with `internal tag 6` went into virtual router `qr`

      Bridge br-int
        Port "tapb977f7c3-e3"
            tag: 6
            Interface "tapb977f7c3-e3"
                type: internal
        Port "qr-4742c3a4-a5"
            tag: 6
            Interface "qr-4742c3a4-a5"
                type: internal

`ip netns exec qrouter-0f23c70d-5302-422a-8862-f34486b37b5d route`

        Kernel IP routing table
        Destination     Gateway         Genmask         Flags Metric Ref    Use Iface
        default         10.71.16.1      0.0.0.0         UG    0      0        0 qg-1270ddd4-bb
        10.10.0.0       *               255.255.255.0   U     0      0        0 qr-b747d7a6-ed
        10.71.16.0      *               255.255.254.0   U     0      0        0 qg-1270ddd4-bb
        192.168.30.0    *               255.255.255.0   U     0      0        0 qr-4742c3a4-a5

`qr` locates in linux network namespace, it's used for routing within
tenant private network. VM1's packages were with fixed IP 192.168.30.4
at the moment, from the above route table, we can see it's `qr-4742c3a4-a5`.

Step-7. VM1' packages were SNAT and went out via gateway `qg` within namespace

       -A neutron-l3-agent-PREROUTING -d 10.71.17.81/32 -j DNAT --to-destination 192.168.30.4
       -A neutron-l3-agent-float-snat -s 192.168.30.4/32 -j SNAT --to-source 10.71.17.81

`ip netns exec qrouter-0f23c70d-5302-422a-8862-f34486b37b5d ifconfig`

    lo    Link encap:Local Loopback  
          inet addr:127.0.0.1  Mask:255.0.0.0
          inet6 addr: ::1/128 Scope:Host
          UP LOOPBACK RUNNING  MTU:65536  Metric:1
          RX packets:0 errors:0 dropped:0 overruns:0 frame:0
          TX packets:0 errors:0 dropped:0 overruns:0 carrier:0
          collisions:0 txqueuelen:0 
          RX bytes:0 (0.0 B)  TX bytes:0 (0.0 B)
    qg-1270ddd4-bb Link encap:Ethernet  HWaddr fa:16:3e:5b:36:8c  
          inet addr:10.71.17.8  Bcast:10.71.17.255  Mask:255.255.254.0
          inet6 addr: fe80::f816:3eff:fe5b:368c/64 Scope:Link
          UP BROADCAST RUNNING MULTICAST  MTU:1500  Metric:1
          RX packets:30644 errors:0 dropped:0 overruns:0 frame:0
          TX packets:127 errors:0 dropped:0 overruns:0 carrier:0
          collisions:0 txqueuelen:0 
          RX bytes:2016118 (2.0 MB)  TX bytes:8982 (8.9 KB)

Step-8. VM1's packages finally went out through br-ex, see the physical route

        0.0.0.0         10.71.16.1      0.0.0.0         UG    0      0        0 br-ex
        10.20.0.0       0.0.0.0         255.255.255.0   U     0      0        0 br-fw-admin
        10.71.16.0      0.0.0.0         255.255.254.0   U     0      0        0 br-ex
        192.168.0.0     0.0.0.0         255.255.255.0   U     0      0        0 br-mgmt
        192.168.1.0     0.0.0.0         255.255.255.0   U     0      0        0 br-storage

For package back from external network to VM, vice versa.

##### 2.2.2 Traffic between VMs

When talking about traffic between VMs, the actual packages' routes will differ a lot depending on where the VMs residing and whether the VMs belonging to the same tenant. In our case, my environment use neutron VLAN which has the ability of network isolation, so even VMs belonging to the same tenant, if they are attached to different network, they cannot communicate to each other directly unless you let them connected to the same virtual router.

![network-topy-1.PNG](/uploads/network-topy-1.PNG)

![neutron-east-west-pic.png](/uploads/neutron-east-west-pic.png)

* Scenario1: VM1 and VM2 belong to same tenant, locate in the same host, attached to the same tenant network

In this scenario, traffic from VM1 to VM2, only need to go through the integration bridge br-int in Host1's Dom0.

* Scenario2: VM1 and VM3 belong to same tenant, located in different hosts, attached to the same tenant network

In this scenario, traffic from VM1 to VM3 will go through from Host1(Dom0) via physical VLAN network to Host2(Dom0), no network node involved

* Scenario3: VM1 and VM4 belong to the same tenant, attached to different tenant network

  * If the two networks not attached to the same virtual router, VM1 and VM4 cannot connect to each other

  * If the two networks attached to the same virtual router, VM1 and VM can connect to each other via network node L3 service

* Scenraio4: VMs belong to different tenants

In this scenario, VMs cannot communicate with each other via fixed IP, they can only communicate with each other by floating IP.

### 3. Future

Currently the Neutron integration with XenServer requires allocation of VLANs specifically for the Neutron networks.  Neutron can work with tunnels to remove the need for this VLAN allocation, and as XenServer has a recent version of OVS in dom0, supporting VxLAN or using GRE tunnels should be possible.

We'll also be improving the Neutron integration to use the native OVS python libraries rather than ovs-vsctl commands, which should give a major performance boost to the control plane.

Watch out for more updates soon!