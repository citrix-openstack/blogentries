# Virtual Hypervisor
This blog demonstrates how to install a XenServer inside a XenServer. This could
be useful to demonstrate how to set up a cloud.

## Network setup
The physical XenServer host's `eth0` interface is connected to the corporate
network, which is providing DNS and DHCP services. The corporate network is:

    10.219.0.0/255.255.192.0

In order to separate the virtual hypervisor from these networks, and emulate a
network environment without DHCP and DNS, a new network has been created by
issueing the following command on the physical hypervisor:

    xe network-create name-label=home

This will be a separate network. I also set up an Ubuntu VM with two network
interfaces: one plugged to the corporate network, one to the newly created
`home` network. This VM has shorewall installed and configured, so that it will
act as a default gateway, and as a DNS proxy for the `home` network. I will call
this machine `toolbox` throughout this documentation. The network address for
`toolbox` is `192.168.32.1`, so the home network is:

    192.168.32.0/255.255.255.0

I will install the Virtual Hypervisor with a static IP configuration:



The Virtual Hypervisor's IP address 

## Installing the Virtual Hypervisor
To install the virtual hypervisor, log in to the `toolbox` vm.
First, check out the tools that will be used to remaster an official XenServer
iso for scripted install.

    git clone https://github.com/matelakat/virtual-hypervisor.git
    cd virtual-hypervisor/

After this step, I downloaded the XenServer iso image as `xenserver.iso`

### Generate an answer file
The next step is to generate a XenServer answer file. This file contains the
root user's crendentials, the hostname, and the network configuration:

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

### Create a remastered ISO

    ./scripts/create_customxs_iso.sh xenserver.iso vh0.lab.iso vh0.answers

The following output will appear on the screen:

    Extracting xenserver.iso to /tmp/tmp.RG8qRasycH
    Remastering /tmp/tmp.RG8qRasycH/install.img
    Removing /tmp/tmp.QHDdpDtdYC
    Create new iso: vh0.lab.iso
    Removing /tmp/tmp.RG8qRasycH

### Install the virtual hypervisor
The next step is to install a HVM virtual machine with the remastered CD -rom.
This could be done by executing:

    scripts/xs_start_create_vm_with_cdrom.sh vh0.lab.iso 10.219.10.25 home vh0.lab

This script will ask for the physical hypervisor's password, copy the iso file
to the hypervisor, and block, until the installation is finished. You can use
XenCenter to follow the events, or simply issue:

    xe vm-list

on the hypervisor. The VM's label will show the state of the installation.

As the script finished, you should end up having a Virtual Hypervisor:

    xe vm-list

Should  contain something like:

    uuid ( RO)           : 423bfa08-fc29-c783-21cc-9970b8d0676f
         name-label ( RW): vh0.lab
        power-state ( RO): halted

### Start the Virtual Hypervisor
You can start the Virtual Hypervisor by logging in to the physical one, and
issueing:

    xe vm-start vm=vh0.lab

To get a console for this machine, first you have to find out the vncserver's
port:

    xenstore-read /local/domain/$(xe vm-list name-label=vh0.lab params=dom-id --minimal)/console/vnc-port

Subtract `5900` from the result, and use that with `vncviewer` from your
workstation (In this example, the result was 5902):

    vncviewer -via root@10.219.10.25 localhost:2
