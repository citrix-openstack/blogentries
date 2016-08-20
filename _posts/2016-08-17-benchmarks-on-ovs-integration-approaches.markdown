---
title: Benchmarks on OVS integration approaches
date: 2016-08-17 01:01:00 Z
published: false
tags:
- ovs
- openstack
---

# Benchmarks on OVS integration approaches

In the world of virtualization especially QEMU, a L2 network interface is
emulated with a virtual network kernel device called "tap device", while
XenServer introduces Virtual Network Interfaces (vif) devices in paravirtualized
\(PV) way, which means guest OS kernel is aware it is running on a virtual
machine and it doesn't have to fully emulate a real network device so network
communications will be fast and efficient.

However when we use OpenStack upon XenServer and need to boot an HVM guest, we
start with both a tap and a vif device attached to the VM. The emulated tap
device is used by the VM until the paravirtualised (PV) tools have been loaded,
at which point the more performant VIF device is used and the tap device is
deleted. That is because Neutron, the OpenStack networking project, only works
with a single connection to the VM and does not cope with multiple devices being
used for the same connection. Unfortunately, you cannot assume there are the PV
tools always installed on the HVM guests. So [XenAPI: OVS agent updates the
wrong port with Neutron](https://review.openstack.org/#/c/242846/) introduces a
set of "VIF specific bridges" in front of the HVM guests so we don't have to
invasively change Neutron code. This blog post is aiming to investigate the
performance cost of this additional bridge by setting up an environment
comparing the conditions with and without this bridge.

# Terminology Reference

* 'integration bridge': OpenStack used to use the legacy Nova-network to provide
  a basic flat network model. However in its successor Neutron, this model is
  extended as a flat network cannot meet the requirements of a modern data
  center. XenAPI's integration with Neutron uses a single bridge per host that
  all guest instances are connected to provide connectivity to an external
  network with a physical network interface. This is essentially the same as the
  nova-network used to connect VMs to a physical interface.

* 'interim bridges': Mentioned as "VIF specific bridges" in above paragraph,
  interim bridges work between the HVM guests and the integration bridge. There
  is one separate interim bridge for each HVM guest.

* 'Patch ports': A pair of virtual devices that act as a patch cable to connect
  multiple Open vSwitch (OVS) bridges (e.g. the integration bridge and interim
  bridge)

* 'ovs-vsctl': A CLI high-level tool to for querying and configuring Open
  vSwitch daemon. Everything we will do to Open vSwitch will be performed by
  ovs-vsctl.

* 'iperf': A commonly-used network testing tool that can create TCP/UDP data
  streams and measure the throughput of a network. iperf works at a Client/
  Server mode.

* 'gnuplot': A command-line program can generate plot diagrams.

# Environment setup

![interim.png](/uploads/interim.png)

We follow below steps to set up two environments like above in a fresh XenServer host.

* Firstly create two private networks serve as “integration bridge” and "interim
  bridge"

* Create two guest instances A and B. One is Centos 7 with guest tool installed
  so it will be in HVM mode while using vif, another is a Centos 6 with the
  template "Other install media" so it will be HVM\+TAP

* Create a guest instance S services as the packets send, preferably also using
  vif.

* Install iperf on instances A, B and S

* Connect instance S to "integration bridge" and set the entry port as a trunk
  port with vlan 10. A sample command could be:

      ovs-vsctl set port <S_VIF> trunks=10

* Create a static IP address and a tagged eth for instance S

        ip link add link eth1 name eth1.10 type vlan id 10
        ip a add dev eth1.10 10.0.0.3/24
        ifconfig eth1.10 up

Now we have an common environment can be used for two conditions.

# Without interim bridge \+ patch ports

* Connect instances A(hvm-tap) and B(hvm-vif) to “integration bridge”

* Create static IP addresses for instances A and B

* Tag tap or vif for instances A and B

* Test connectivity between each instance

* Run below command to test the throughput for S->A and S->B and save the data
  for analysis

        ssh root@$VM_S "nohup iperf -s &> /dev/null &"
        for i in `seq 0 9`; do
            echo -n "$i    " >> singlebr-tap.data
            ssh root@$VM_A 'iperf -c 10.0.0.3 -t 10 -f m -P 10 | tail -n 1 | \
            egrep -o " [0-9]+ Mbits/sec" | egrep -o "[0-9]+" ' >> singlebr-tap.data
            sleep 5
            echo -n "$i    " >> singlebr-vif.data
            ssh root@$VM_B 'iperf -c 10.0.0.3 -t 10 -f m -P 10 | tail -n 1 | \
            egrep -o " [0-9]+ Mbits/sec" | egrep -o "[0-9]+" ' >> singlebr-vif.data
            sleep 5
        done
        ssh root@$VM_S "pkill iperf"

# With interim bridge \+ patch ports

* Reconnect instances A(hvm-tap) and B(hvm-vif) to "interim bridge” (rebooting
  required)

* Create a pair of patch ports connected to both of “integration bridge” and
  "interim bridge”. Assuming those two bridges in OVS are represented as xapi1
  and xapi2, the sample commands could be:

        ovs-vsctl add-port xapi1 patch-to-xapi2
        ovs-vsctl add-port xapi2 patch-to-xapi1
        ovs-vsctl set interface patch-to-xapi2 type=patch
        ovs-vsctl set interface patch-to-xapi1 type=patch
        ovs-vsctl set interface patch-to-xapi2 options:peer=patch-to-xapi1
        ovs-vsctl set interface patch-to-xapi1 options:peer=patch-to-xapi2

* Recreate static IP addresses for instances A and B

* Run below command again to test the throughput and save the data

        ssh root@$VM_S "nohup iperf -s &> /dev/null &"
        for i in `seq 0 9`; do
            echo -n "$i    " >> patchport-tap.data
            ssh root@$VM_A 'iperf -c 10.0.0.3 -t 10 -f m -P 10 | tail -n 1 | \
            egrep -o " [0-9]+ Mbits/sec" | egrep -o "[0-9]+" ' >> patchport-tap.data
            sleep 5
            echo -n "$i    " >> patchport-vif.data
            ssh root@$VM_B 'iperf -c 10.0.0.3 -t 10 -f m -P 10 | tail -n 1 | \
            egrep -o " [0-9]+ Mbits/sec" | egrep -o "[0-9]+" ' >> patchport-vif.data
            sleep 5
        done
        ssh root@$VM_S "pkill iperf"

# Generate plot diagram

As data might be fluctuant so we take 10 records for each condition. And then
run below command to generate two plot diagrams individually for vif and tap
device

    gnuplot <<EOF
    set term png giant enhanced size 1000, 800
    set output "tap-throughputs.png"
    set xlabel "Round"
    set ylabel "Mbits/sec"
    set xrange [0:9]
    set yrange [0:]
    plot \
    "singlebr-tap.data" u 1:2 t "singlebr-tap" w lp ls 1, \
    "patchport-tap.data" u 1:2 t "patchport-tap" w lp ls 2
    EOF
    
    gnuplot <<EOF
    set term png giant enhanced size 1000, 800
    set output "vif-throughputs.png"
    set xlabel "Round"
    set ylabel "Mbits/sec"
    set xrange [0:9]
    set yrange [0:]
    plot \
    "singlebr-vif.data" u 1:2 t "singlebr-vif" w lp ls 1, \
    "patchport-vif.data" u 1:2 t "patchport-vif" w lp ls 2
    EOF

# Test result

Shown as below, the test result proves that the performance of vif and tap
device will be both just slightly impacted with interim bridge \+ patch ports.

---
title: performance table
---

| (Mb/s)     | singlebr-tap | patchport-tap | singlebr-vif | patchport-vif |
| ---------- | ------------ | ------------- | ------------ | ------------- |
| 0          | 116          | 124           | 5145         | 4968          |
| 1          | 115          | 117           | 5182         | 5090          |
| 2          | 121          | 120           | 5001         | 5082          |
| 3          | 117          | 122           | 5307         | 5226          |
| 4          | 128          | 123           | 4976         | 5216          |
| 5          | 127          | 121           | 5236         | 4942          |
| 6          | 126          | 124           | 5127         | 5051          |
| 7          | 128          | 118           | 5191         | 5146          |
| 8          | 126          | 121           | 5179         | 5257          |
| 9          | 129          | 118           | 5034         | 5066          |
| AVG        | 123.3        | 120.8         | 5137.8       | 5104.4        |
| Comparison | 100%         | 98%           | 100%         | 99%           |

![vif-throughputs.png](/uploads/vif-throughputs.png)
![tap-throughputs.png](/uploads/tap-throughputs.png)