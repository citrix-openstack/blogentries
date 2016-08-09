---
title: Developing for OpenStack and XenServer Made Easy
date: 2016-08-08 16:51:00 Z
---

For many years, setting up a development environment for XenServer and OpenStack has been a painful exercise.  XenServer has a unique deployment model with OpenStack, where the services (specifically Nova Compute) are run in a virtual machine running under the XenServer host.  Now you can easily deploy an OpenStack environment accessing *any* XenServer host - whether connected over a network or running in a local Virtual Machine!

The nested-VM deployment model gives some real advantages over the all-in-one model of having the services run in the same 'machine' as the hypervisor - for example, with XenServer you can fully re-deploy your Nova Compute services (e.g. destroy the VM and redeploy) without interrupting any of your VMs services.

Unfortunately the requirement to run Nova Compute in a virtual machine does make development set-ups much more complicated, so in Newton we have implemented a new simplified approach which can be used by developers and deployers alike - the [Independent Compute](https://specs.openstack.org/openstack/nova-specs/specs/newton/approved/xenapi-independent-nova.html) option.

At the time of writing, several of the Nova Compute features are incompatible with this "Independent Compute" flag, but if you're looking for an easy way to set up a development environment then these are often acceptable restrictions:

* Injecting files directly into the disk image is not supported (CONF.flat_injected must be False) - use cloudinit and Config drives

* Checking that Nova Compute is running as a VM on the host is not possible, so CONF.xenserver.check_host must be set to False

* Ephemeral disks are created in dom0, which has limited support for file systems.  As such CONF.default_ephemeral_format must be unset or 'ext3'.

* Nova-based auto_configure_disk is not supported - but cloudinit can resize the disks for you.

* Joining host aggregates is not supported (will error if attempted)

* Swap disks for Windows VMs is not supported (will error if attempted)

# Architectural overview

As a brief overview of the typical deployment model for XenServer \+ OpenStack environments, see the following image.

![old.PNG](/uploads/old.PNG)

We have a XenServer host, with some Nova plug-ins running in Domain 0, with the rest of Nova running in a Virtual Machine on the host.

What the Independent Compute option now allows you to do is deploy OpenStack services on your existing Linux Host and run XenServer in a VM or connect to an existing XenServer host over the network, as depicted below.

![new.PNG](/uploads/new.PNG)

# Tell me more!

If you don't already have a [DevStack ](http://docs.openstack.org/developer/devstack/)setup, then set one up using the default values (which will set up a libvirt\+KVM environment).  Once that's all working, we can easily convert it to use a nested XenServer.  If you're using a network-connected XenServer, skip to step 3 below.

1\. Create a VM

The VM created should 

2\. Install XenServer

2\. Set DevStack options to use the new XenServer