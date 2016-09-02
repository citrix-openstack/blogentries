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

We're going to install our XenServer VM using a CD image, which is free from www.xenserver.org.  As we're only going to run small VMs in a devstack environment, give the VM 2GB RAM and 60GB disk space (required for the XenServer partition layout even though a freshly installed host only uses 3GB).
virt-install gives a great way to set this up, and the following command line calls will create your virtual machine for you.  Alternatively, you can use virt-manager or even VirtualBox if you prefer not using qemu, or using a GUI.

    IMAGE_DIR=/var/lib/libvirt/images
    wget http://downloadns.citrix.com.edgesuite.net/11616/XenServer-7.0.0-main.iso -O $IMAGE_DIR/XenServer-7.0.0-main.iso
    qemu-img create -f qcow2 $IMAGE_DIR/XenServer.qcow2 60G
    chmod a\+rw $IMAGE_DIR/XenServer\*
    virt-install --name XenServer --ram 2048 --cpu host --vcpus 2 --disk path=$IMAGE_DIR/XenServer.qcow2,bus=ide --cdrom $IMAGE_DIR/XenServer-7.0.0-main.iso --network=bridge:virbr0,model=e1000 --graphics vnc,listen=0.0.0.0

2\. Install XenServer

If you use virt-install and virt-viewer is installed, you may automatically connect to the instance.
Otherwise, launch a VNC viewer and connect to the VNC port for the guest (if it's the first guest, this will be 5901)

As you step through the installer, you are likely to see a warning message that Hardware Virtualisation is not supported.  This would need nested virtualisation to be enabled in libvirt, but we don't have to run Windows guests - we can test\+develop using Cirros or other PV guests.  Of course, if you install your XenServer on a separate physical host, Windows VMs will work great too.

[HVM_Warning.PNG](/uploads/HVM_Warning.PNG)

The XenServer\+OpenStack integration only supports thinly-provisioned local disks, so make sure you select it on the Virtual Machine Storage page:

[ThinProvisioning.PNG](/uploads/ThinProvisioning.PNG)

After selecting Thin Provisioning, just complete the installation and take note of the XenServer IP address provided by the DHCP server from the console:

[IP_Address.PNG](/uploads/IP_Address.PNG)

2\. Set DevStack options to use the new XenServer

Once you've got your installed host's IP address, make sure the stack user can log in to the host without a password (using ssh-keygen if needed, then ssh-copy-id) and then it's a simple matter of configuring your DevStack instance to use this host with the independent_compute mode:

    [stack@xrtmia-03-12 devstack]$ cat local.conf 
    [[local|localrc]]
    VIRT_DRIVER=xenserver
    XENAPI_CONNECTION_URL=http://192.168.122.201
    XENAPI_PASSWORD=<password>
    DOMZERO_USER=stack
    
    [[post-config|$NOVA_CONF]]
    [xenserver]
    independent_compute=True
    check_host=False

After running stack.sh, you should now be able to create Cirros VMs out-of-the-box!

If you need to run different VMs under XenServer, check out Jianghua's blog post at <URL>.