# Create Volume from a XenServer Image

A story of supporting XenServer Images in cinder - converting a vhd chain to a
raw volume.

In tempest test suite, there are some test cases around creating a volume from
an image. On the Cinder side this basically means to get the image, ask
`qemu-img` to recogise its format, and to convert it to raw, and write the
raw bytes to the volume.

With XenServer, this works out of the box with raw images, but if you are using
XenServer type images, you will get unexpected results, when you expect to see
the bytes of your image on the volume. Basically the image file will be written
to the volume, without any conversion, because `qemu-img` recognise the targz
file as `raw`.

`dd` -ing a targz of vhd chains to a disk is hardly usable.

We decided to eliminate this gap, and implement XenServer image to volume
functionality. Having this feature will enable us to run boot from volume
exercise as well.

## About XenServer Images

As a first thing, let's get familiar with XenServer type images in OpenStack.
If you are using XenServer with OpenStack, the images used are vhd chains
inside a targz archive file. You might wonder why the chain is needed, but it
will be clear in a second, once we get to snapshots. For now, let's say that
there could be more than one `vhd` inside the targz, forming a chain.

The above mentioned format could be best learned by looking at the XenAPI
plugins.  [Those plugins live in nova at the moment](https://github.com/openstack/nova/blob/master/plugins/xenserver/xenapi/etc/xapi.d/plugins/utils.py#L272).

The conclusion is that a XenServer image is a tgz with vhd files inside. The
naming convention of those files are:

    0.vhd
    1.vhd
    ...
    n.vhd

And they form a chain, `0.vhd` being the latest difference, and `n.vhd` being
the base image.

## Converting a XenServer Image to raw

To start with something, let's create a simple cirros image for start. This
should be a `tgz` containing one base image, `0.vhd`. See [this blog
entry](http://blogs.citrix.com/2012/10/17/upload-custom-images-to-a-xenserver-powered-openstack-cloud/)
on how to accomplish this. If you don't want to spend time with creating the
initial image, feel free to download it from
[here](https://github.com/downloads/citrix-openstack/warehouse/cirros-0.3.0-x86_64-disk.vhd.tgz).
If you are using devstack to install your OpenStack, you could specify the
above url in your localrc file, and your initial stack will be populated with
the image:

    IMAGE_URLS="https://github.com/downloads/citrix-openstack/warehouse/cirros-0.3.0-x86_64-disk.vhd.tgz"
    DEFAULT_IMAGE_NAME="cirros-0.3.0-x86_64-disk"

`DEFAULT_IMAGE_NAME` is required by various tests to find the image for the
tests.

Enter to your stack:

    $ cd devstack/
    $ . openrc admin

So let's say, we have this image uploaded to our cloud:

    $ glance image-list
    +------+--------------------------+-------------+------------------+---------+--------+
    | ID   | Name                     | Disk Format | Container Format | Size    | Status |
    +------+--------------------------+-------------+------------------+---------+--------+
    | <id> | cirros-0.3.0-x86_64-disk | vhd         | ovf              | 9220018 | active |
    +------+--------------------------+-------------+------------------+---------+--------+

Good stuff. Let's download it:

    $ glance image-download <id> --file origin.tgz

Look into it:

    $ mkdir origin && tar -xzf origin.tgz -C origin
    $ ls origin/
    0.vhd

Now install the `vhd-util` to gather some information on the vhd file:

    $ sudo apt-get install blktap-utils

And take a closer look at `0.vhd`:

    $ vhd-util read -n origin/0.vhd -p
    ...
    Original disk size  : 40 MB (41943040 Bytes)
    Current disk size   : 40 MB (41943040 Bytes)
    ...
    Disk type           : Dynamic hard disk

Now, get back to OpenStack, and launch an instance based on this image with
the `m1.tiny` flavor:

    $ nova boot --flavor=m1.tiny --image=<id> demomachine

After some time, the instance will get an IP address, use `nova list` to get
its IP, and ssh to the instance. This is a standard cirros image, so username
sould be `cirros` and password is `cubswin:)`.

Now, inside the instance, see, that the disk has been resized according to the
requested flavor:

    $ sudo fdisk -l

    Disk /dev/xvda: 1073 MB, 1073741824 bytes
    ...

Now, write some data to the disk with dd:

    $ sudo dd if=/dev/xvda of=somefile bs=1024 count=10000
    $ sudo md5sum somefile > somefile.md5
    $ sync

Now, I am logging out of the instance (back to my devstack), and creating a
backup of this instance to glance:

    $ nova list
    +--------------+-------------+--------+------------+-------------+------------------+
    | ID           | Name        | Status | Task State | Power State | Networks         |
    +--------------+-------------+--------+------------+-------------+------------------+
    | <instanceid> | demomachine | ACTIVE | None       | Running     | private=10.0.0.2 |
    +--------------+-------------+--------+------------+-------------+------------------+
    $ nova backup <instanceid> snap snapshot 1

Some time later, a new image should be in glance:

    $ glance image-list
    +-----------+--------------------------+-------------+------------------+----------+--------+
    | ID        | Name                     | Disk Format | Container Format | Size     | Status |
    +-----------+--------------------------+-------------+------------------+----------+--------+
    | <id>      | cirros-0.3.0-x86_64-disk | vhd         | ovf              | 9220018  | active |
    | <snapid>  | snap                     | vhd         | ovf              | 10117120 | active |
    +-----------+--------------------------+-------------+------------------+----------+--------+

Let's download the new image for some investigation:

    $ glance image-download <snapid> --file snap.tgz
    $ mkdir snap && tar -xzf snap.tgz -C snap
    $ ls snap/
    0.vhd  1.vhd  2.vhd

Oh, that's how we get multiple `vhd` files per image! `vhd-util` can check a vhd,
so let's try that:

    $ vhd-util check -n snap/0.vhd
    parent locator 0 points to missing file ./66083a56-f5e8-4d8a-847a-a1e23526472c.vhd (resolved to (null))
    snap/0.vhd appears invalid; dumping metadata
    ...

Let's look at these vhd files, and see that the snapshots are differencing hard
disks, and that the parent name refers to non-existing vhd files.

    $ vhd-util read -n snap/0.vhd -p
    ...
    Original disk size  : 1024 MB (1073741824 Bytes)
    Current disk size   : 1024 MB (1073741824 Bytes)
    ...
    Disk type           : Differencing hard disk
    ...
    Parent name         : 66083a56-f5e8-4d8a-847a-a1e23526472c.vhd
    ...
    $ vhd-util read -n snap/1.vhd -p
    ...
    Original disk size  : 40 MB (41943040 Bytes)
    Current disk size   : 1024 MB (1073741824 Bytes)
    ...
    Disk type           : Differencing hard disk
    ...
    Parent name         : 50ca4384-f4e3-4b7b-ba79-b175e5da2e4b.vhd
    ...
    $ vhd-util read -n snap/2.vhd -p
    ...
    Original disk size  : 40 MB (41943040 Bytes)
    Current disk size   : 40 MB (41943040 Bytes)
    ...
    Disk type           : Dynamic hard disk
    ...
    Parent name         : 
    ...

It's time to fix the chain:

    $ vhd-util modify -n snap/0.vhd -p snap/1.vhd
    $ vhd-util modify -n snap/1.vhd -p snap/2.vhd

And the check should be fine:

    $ vhd-util check -n snap/0.vhd 
    snap/0.vhd is valid

Now we just need to convert them to a raw disk:

    $ qemu-img convert snap/0.vhd -O raw zerovhd

And look at the partition table:

    $ fdisk -l zerovhd
    ...
    Disk zerovhd doesn't contain a valid partition table

That's bad, we were expecting a partition table. The issue here seems to be,
that `qemu-img` does not look at the whole chain, just this item. So let's
coalesce all the devices back to the base image:

    $ vhd-util coalesce -n snap/0.vhd
    $ vhd-util coalesce -n snap/1.vhd

And convert the coalesced base image:

    $ qemu-img convert snap/2.vhd -O raw coalesced.raw
    $ fdisk -l coalesced.raw
    ...
    Disk coalesced.raw: 41 MB, 41909760 bytes
    ...
            Device Boot      Start         End      Blocks   Id  System
    coalesced.raw1   *       16065     2088449     1036192+  83  Linux

Looks better, although the size does not look good. I would expect it to be a
1G disk. In order to fix this issue, I will include a resize step as well, so
that my conversion looks like this:

    $ mkdir snap && tar -xzf snap.tgz -C snap
    $ vhd-util modify -n snap/0.vhd -p snap/1.vhd
    $ vhd-util resize -n snap/1.vhd -s $(vhd-util query -n snap/0.vhd -v) -j resize1.journal
    $ vhd-util coalesce -n snap/0.vhd
    $ vhd-util modify -n snap/1.vhd -p snap/2.vhd
    $ vhd-util resize -n snap/2.vhd -s $(vhd-util query -n snap/1.vhd -v) -j resize2.journal
    $ vhd-util coalesce -n snap/1.vhd
    $ qemu-img convert snap/2.vhd -O raw rawdisk

Now, as we have `rawdisk`, let's mount it:

    $ sudo kpartx -av rawdisk
    add map loop1p1 (252:0): 0 64260 linear /dev/loop1 16065
    $ sudo mount /dev/mapper/loop1p1 /mnt/

And check, if the checksum of the file is the same

    $ ( cd /mnt/home/cirros/ && sudo md5sum -c somefile.md5 )
    somefile: OK

Also, `fdisk` should give the expected results:

    $ fdisk -l rawdisk 

    Disk rawdisk: 1073 MB, 1073479680 bytes
    ...

So, this is the story on how to convert a XenServer Image manually to a raw
disk with some userspace tools.

## Cinder

The cinder patch, that adds these changes to cinder, could be found (here)[https://review.openstack.org/34336]
here, so if you have any questions or suggestion on it, please comment
on it.

My local devstack installation already has this patch, so I can easily create
an instance from that image:

    $ cinder create --image-id <snapid> 1
    ...
    $ cinder list
    +---------+-----------+--------------+------+-------------+----------+-------------+
    |      ID |   Status  | Display Name | Size | Volume Type | Bootable | Attached to |
    +---------+-----------+--------------+------+-------------+----------+-------------+
    | <volid> | available |     None     |  1   |     None    |   True   |             |
    +---------+-----------+--------------+------+-------------+----------+-------------+

And I can boot up from that as well:

    $ nova boot --flavor m1.tiny --block-device-mapping vda=<volid> fromvol
    ...
    $ nova list
    +--------------+-------------+--------+------------+-------------+------------------+
    | ID           | Name        | Status | Task State | Power State | Networks         |
    +--------------+-------------+--------+------------+-------------+------------------+
    | <instanceid> | demomachine | ACTIVE | None       | Running     | private=10.0.0.2 |
    | <bfvid>      | fromvol     | ACTIVE | None       | Running     | private=10.0.0.3 |
    +--------------+-------------+--------+------------+-------------+------------------+

And check the checksum:

    $ ssh cirros@10.0.0.3 sudo md5sum -c somefile.md5
    cirros@10.0.0.3's password: 
    somefile: OK
