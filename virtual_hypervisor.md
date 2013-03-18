# Virtual Hypervisor
This blog demonstrates how to perform a scripted install of a XenServer inside
a XenServer. This gives a flexibile virtual environment for development or 
experimenting with cloud setups.

The official way of automating XenServer installation, is to use 
[PXE boot](http://docs.vmd.citrix.com/XenServer/6.1.0/1.0/en_gb/installation.html#pxe_boot_install).

This guide assumes that you don't have DHCP/PXE services running on your
isolated network, so it will re-master the XenServer install media, thus, the
only dependency is to being able to boot from an iso file.

## Network setup
In this example, the physical XenServer host's `eth0` interface is connected to the corporate
network, which is providing DNS and DHCP services. The corporate network is:

    10.219.0.0/255.255.192.0

and the physical XenServer's address is: `10.219.10.25`

In order to separate the virtual hypervisor from these networks, and emulate a
network environment without DHCP, a new network has been created by issuing
the following command on the physical hypervisor:

    xe network-create name-label=isolated

This will be a separated network. I also set up an Ubuntu VM with two network
interfaces: one plugged to the corporate network, one to the newly created
`isolated` network. This VM has shorewall and dnsmasq installed and configured, so
that it will act as a default gateway, and as a DNS proxy for the `isolated`
network. I will call this machine `toolbox` throughout this documentation. The
network address for `toolbox` is `192.168.32.1`, so the isolated network's IP
configuration is:

    192.168.32.0/255.255.255.0

I will install the Virtual Hypervisor, connected to the `isolated` network,  with a
static IP configuration:

       address: 192.168.32.2
       netmask: 255.255.255.0
    default gw: 192.168.32.1
           DNS: 192.168.32.1

## Installing the Virtual Hypervisor
To install the virtual hypervisor, log in to the `toolbox` vm.  First, check
out the tools that will be used to remaster an official XenServer iso for
scripted install.

    git clone https://github.com/matelakat/virtual-hypervisor.git
    cd virtual-hypervisor/
    git checkout v1.0

Please note, that the `v1.0` branch is used during this guide, to avoid the effect
of further changes in master.

After this step, download the XenServer iso image as `xenserver.iso`.

### Generate an answer file
The next step is to generate a XenServer answer file. This file contains the
Virtual Hypervisor's root user's crendentials, the hostname, and the network
configuration:

    ./scripts/generate_answerfile.sh static \
    -h vh0.lab \
    -i 192.168.32.2 \
    -m 255.255.255.0 \
    -g 192.168.32.1 \
    -p vhpass \
    -n 192.168.32.1 > vh0.answers

You could further customise the answer file `vh0.answers`. Please note, that
the answer file contains a post install script:

    <script stage="filesystem-populated" type="url">file:///postinst.sh</script>

This file will be copied from the `data` directory. The purpose of this script
is to install a firstboot script, `firstboot.sh`, which will be started only
once. This firstboot script simply halts the machine. See `data/firstboot.sh`.
This is required, so that the machine-installer script will know, that the
installation is finished.

### Create a Remastered ISO
The next step, is to inject the created answer file together with the
post-installation and first-boot scripts to a remastered, custom XenServer iso
file:

    scripts/create_customxs_iso.sh xenserver.iso vh0.lab.iso vh0.answers

The following output should appear on the screen:

    Extracting xenserver.iso to /tmp/tmp.RG8qRasycH
    Remastering /tmp/tmp.RG8qRasycH/install.img
    Removing /tmp/tmp.QHDdpDtdYC
    Create new iso: vh0.lab.iso
    Removing /tmp/tmp.RG8qRasycH

### Install the Virtual Hypervisor
The next step is to install an HVM virtual machine with the remastered ISO.
This could be done by executing:

    scripts/xs_start_create_vm_with_cdrom.sh vh0.lab.iso 10.219.10.25 isolated vh0.lab

This script will ask for the physical hypervisor's password, copy the iso file
to the hypervisor, and block, until the installation is finished. You can use
XenCenter to follow the events, or simply issue:

    xe vm-list

on the hypervisor. The VM's label will show the state of the installation:
 - `created (Step 1 of 3)`
 - `booted from iso (Step 2 of 3)`
 - `first boot (Step 3 of 3)`

As the script finished, you should end up having a Virtual Hypervisor:

    xe vm-list

Should contain something like:

    uuid ( RO)           : 423bfa08-fc29-c783-21cc-9970b8d0676f
         name-label ( RW): vh0.lab
        power-state ( RO): halted

### Start the Virtual Hypervisor
You can start the Virtual Hypervisor by logging in to the physical one, and
issuing:

    xe vm-start vm=vh0.lab

### Log in
After you started the virtual hypervisor, use:

    ssh root@192.168.32.2

to log in. The password is `vhpass`, as specified during the answer file
generation step.

### Look at the Console
To get a console for the Virtual Hypervisor, first you have to find out the
vncserver's port:

    xenstore-read /local/domain/$(xe vm-list name-label=vh0.lab params=dom-id --minimal)/console/vnc-port

Subtract `5900` from the result, and use that with `vncviewer` from your
workstation (In this example, the result was 5902):

    vncviewer -via root@10.219.10.25 localhost:2

## Where to go now?
You can now set up your OpenStack test setups in a fully virtualised
environment, decoupled from all the corporate networking services, properly
isolated.
