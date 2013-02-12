## Introduction

This blog entry shows how XenAPINFS is integrated with Glance. This feature's blueprint
[can be found on launchpad](https://blueprints.launchpad.net/cinder/+spec/xenapinfs-glance-integration).
At the time of writing this document, the driver only supports XenServer type
`ovf` images (these images are specially named `vhd` files compressed to a `.tgz`
archive). The cinder driver is using the nova xenapi plugins to upload/download
the images. I am also working on a general case, to be able to create volumes
from images with arbitrary format (such as qcow or raw).

In this demo, I will:

- create a volume from a glance image
- boot an instance from the created volume
- make changes to the filesystem
- upload the volume to glance as a new image
- create instances based on the newly created image

## Requirements

### NFS Server
For the demo, a single Ubuntu VM is serving the NFS. The following options were
specified for the export:

    ubuntu@copper:~$ grep demo /etc/exports 
    /demo *(rw,no_subtree_check,no_root_squash)

### XenServer with OpenStack
For the demo [Devstack](https://github.com/openstack-dev/devstack) was used to
install a development OpenStack on XenServer 6.1. For the demo, only one
XenServer was used, however, it is possible to use a totally different 
XenServer for cinder operations. The only requirement is, that __Nova plugins must be installed on the
XenServer used for volume operations__ (the one specified in `cinder.conf`).

## Step 1. - Configure Cinder
Cinder needs to be configured to use the XenAPINFS driver. I will show two ways
to do it.

### Edit the Configuration File Directly
To configure cinder, go to the openstack box, and edit the configuration file
`/etc/cinder/cinder.conf`, and make sure the following settings are there:

    volume_driver = cinder.volume.drivers.xenapi.sm.XenAPINFSDriver
    xenapi_connection_url = http://epun.eng.hq.xensource.com
    xenapi_connection_username = root
    xenapi_connection_password = password
    xenapi_nfs_server = copper.eng.hq.xensource.com
    xenapi_nfs_serverpath = /demo

After making changes to cinder's configuration, make sure the service is restarted.

### Use Devstack to Configure Cinder
You can also use devstack, to configure cinder with XenAPINFS. The variables required
for the `localrc` file are:

    CINDER_DRIVER=XenAPINFS
    CINDER_XENAPI_CONNECTION_URL="epun.eng.hq.xensource.com"
    CINDER_XENAPI_CONNECTION_USERNAME=root
    CINDER_XENAPI_CONNECTION_PASSWORD="password"
    CINDER_XENAPI_NFS_SERVER="copper.eng.hq.xensource.com"
    CINDER_XENAPI_NFS_SERVERPATH="/demo"

After adding these lines to your `localrc` file, re-stack your environment:

    stack@DevStackOSDomU:~/devstack$ ./unstack.sh
    stack@DevStackOSDomU:~/devstack$ ./stack.sh

Please note, that by doing that, you are wiping, and re-building your OpenStack
installation.

## Step 2. - Upload an Image
A cirros image is provided via our github account. This image is already in 
XenServer format. To upload it:

    stack@DevStackOSDomU:~$ cd devstack/
    stack@DevStackOSDomU:~/devstack$ . openrc admin
    stack@DevStackOSDomU:~/devstack$ glance image-create --name demoimage \
    --copy-from=https://github.com/downloads/citrix-openstack/warehouse/cirros-0.3.0-x86_64-disk.vhd.tgz \
    --container-format=ovf --disk-format=vhd

Make sure you give enough time for glance to store the image. Wait, until

    stack@DevStackOSDomU:~/devstack$ glance image-list

shows, that `demoimage` is `active`:

    ... demoimage | vhd | ovf | 9220018  | active |


## Step 3. - Create a volume from an Image
First, get the id of the new image:

    stack@DevStackOSDomU:~/devstack$ glance image-show demoimage | grep id

And use that, to create a `1G` volume based on that image, called `demovolume_a`:

    stack@DevStackOSDomU:~$ cinder create --display_name="demovolume_a" --image-id=<put imageid here> 1

Initially, the volume's status will be `downloading`, and as that operation is
finished, it becomes `available`. Check its status with:

    stack@DevStackOSDomU:~$ cinder list

## Step 4. - Boot an Instance from the Volume
To boot an instance, first we need the id of the volume:

    cinder show demovolume_a | grep  " id "

And create a new instance with that volume as its primary hard disk:

    stack@DevStackOSDomU:~$ nova boot --flavor=m1.small --block_device_mapping vda=<volume id>:::0 demo_vm

Use horizon to access the console of the new VM, and log in using the usual
cirros credentials, and touch a file in the home directory to demonstrate
that changes to the volume are stored in the image.

    $ touch HEREIAM
    $ sync

And use nova to shut down the instance.

    stack@DevStackOSDomU:~$ nova delete <instance id>

## Step 5. - Create an Image from the Volume

    stack@DevStackOSDomU:~$ cinder upload-to-image --container-format=ovf --disk-format=vhd <volume id> demoimage_b

Check the status of the image, by:

    stack@DevStackOSDomU:~$ glance image-show demoimage_b

And wait until it is `active`.

## Step 6. - Launch an Instance from the Uploaded Image
First, get the id of the newly created image:

    stack@DevStackOSDomU:~$ glance image-show demoimage_b | grep id

And boot an instance with that image:

    stack@DevStackOSDomU:~$ nova boot --flavor=m1.small --image=demoimage_b demo_vm_2

And use horizon to log in, and check the contents of the home directory:

    $ ls | grep HEREIAM
    HEREIAM
