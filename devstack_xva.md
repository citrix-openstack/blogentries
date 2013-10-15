# DevStack virtual appliance for XenServer

The easiest way to get started with OpenStack development is to use DevStack.
DevStack is a collection of shell scripts that help to set up an OpenStack
installation. This installation should not be used in production, it serves as
an environment to hack OpenStack - as hackability is important in OpenStack -
and DevStack could even be useful, if you want to experiment with OpenStack.

If your choice of hypervisor is XenServer, it is now easier to get started with
DevStack, as a tested XVA Virtual Appliance is built on a daily basis.

In this blog, I will guide you through the steps on how to get the mentioned
XVA up and running on XenServer installation.

The process consists of 2 steps:
 - Install the appliance and the supplemental pack
 - Start the appliance

# Prerequisites

## XenServer

I assume a XenServer 6.2 installation with ext type storage. As XenServer is
now fully opensource, it could be downloaded from
[xenserver.org](http://xenserver.org/). During installation, make sure, you
enable thin provisioning, so that your XenServer will use ext type storage. To
check if your installation is using ext type storage, use the following
command:

    xe sr-list name-label="Local storage" params=type --minimal

The command should return `ext`. If it does not return ext, but other, you will
need to change your SR type to ext.

It is also recommended to have at least 6 gigabytes of memory in that physical
machine. 1 gigabyte is required for Dom0, 3 gigabytes are required for the
DevStack VM, and the rest could be used to launch OpenStack VMs.

## Networking

The other requirement for running the DevStack XVA is to have a DHCP service
running on your network.

# Step 1: Installation

The DevStack XVA consists of two components:

 - A Supplemental Pack - containing XenServer modifications
 - The appliance itself

We build these in pairs, and it is important to install a matching pair. Navigate
to the following location with your browser:

    http://downloads.vmd.citrix.com/OpenStack/

As an example, I will pick `10-15-2013` (it is the latest as of writing this
blog post). In this case it means, that the plugin Supplemental Pack is located
at:
    
    http://downloads.vmd.citrix.com/OpenStack/novaplugins-10_15_2013.iso
    
and the XVA is located at:

    http://downloads.vmd.citrix.com/OpenStack/devstack-10_15_2013.xva

Now, log in to your XenServer to download and install the plugins:

    wget "http://downloads.vmd.citrix.com/OpenStack/novaplugins-10_15_2013.iso"
    xe-install-supplemental-pack novaplugins-10_15_2013.iso

The following output is displayed:

    Installing 'nova plugins'...

    Preparing...                ########################################### [100%]
       1:openstack-xen-plugins  ########################################### [100%]
    Creating /images
    Creating /var/run/sr-mount/c558e24a-b1c5-a3b6-3c1d-e1d6ee89297c/os-images
    Setting up symlink: /images -> /var/run/sr-mount/c558e24a-b1c5-a3b6-3c1d-e1d6ee89297c/os-images
    Generating a new rsa keypair for root
    Generating public/private rsa key pair.
    Your identification has been saved in /root/.ssh/id_rsa.
    Your public key has been saved in /root/.ssh/id_rsa.pub.
    The key fingerprint is:
    41:70:9f:d0:f7:2c:0f:86:f0:59:30:02:86:19:24:ae root@jaglan
    Autenticating root's key
    Warning: Permanently added 'localhost' (RSA) to the list of known hosts.
    Trust relation working
    Pack installation successful.

The next step is to download and install the virtual appliance:

    wget "http://downloads.vmd.citrix.com/OpenStack/devstack-10_15_2013.xva"
    xe vm-import filename=devstack-10_15_2013.xva

Now you have a devstack virtual machine installed on your XenServer, ready to 
launch.

# Step 2: Start the appliance

If you are using XenCenter, just start the DevStackOSDomU VM, look at its
console, and enter your XenServer's password when prompted. As `stack.sh` is
completed, press Enter to display the login parameters.

If you don't use XenCenter, log in to XenServer and type:

    xe vm-start vm=DevStackOSDomU 

At this point, DevStack VM is started, and 'stack.sh' is running inside. As
the XenServer's password is required for OpenStack to communicate with the
hypervisor, we need to take a look at the console of the VM. I like to do it
from the console, so first I need the domain id of the VM:

    xe vm-list name-label=DevStackOSDomU params=dom-id --minimal

This will print out the domain id. With the domain id, I can query the VNC port:

    xenstore-read /local/domain/[put domain id here]/console/vnc-port

And by opening a new terminal on my local PC, I can access the vnc console with:

    vncviewer -via root@jaglan.eng.hq.xensource.com localhost:5902

On the console, you should see the output of `stack.sh`, and it will stop at
some point to ask for the XenServer's password. Enter the password for your
XenServer. After the password input, `stack.sh` will carry on, and as it is
finished, you'll see:

    stack.sh completed in XXX seconds.

Press Enter to get to the login prompt. The VM's IP address and the DevStack
run's status should be displayed on the console:

    OpenStack VM - Installed by DevStack
      Management IP:   10.219.2.149
      DevStack run:    SUCCEEDED

    DevStackOSDomU login:

Now, you can use the management IP to connect to Horizon from a web browser.

Log in with admin/citrix, and enjoy stacking!

If you want to access the VM, use stack/citrix as login/password.

All the scripts that used to generate the xva are available at our qa
repository:

    https://github.com/citrix-openstack/qa
