---
title: Generating Images for XenServer in OpenStack
date: 2016-08-20 16:24:00 Z
---

Although OpenStack XenAPI supports some other disk formats, e.g. ami, raw, iso; vhd is the most commonly used and strongly recommended disk format. This blog will focus on how to create images basing on VHD disk format; how to convert other types of disk format to VHD and finally how to create Windows images for XenServer in OpenStack.

# Generate Images from VHD images

In this section, I will try to demonstrate how we can generate images from VHD images. For XenServer OpenStack, the VHD disks should be contained in gzipped tarball. If the existing image is in this format already, we can import it to glance image directly. Otherwise we need convert it to gzipped tarball firstly.

For example, it's zipped VHD-based images at:

https://cloud-images.ubuntu.com/vivid/current/vivid-server-cloudimg-amd64-disk1.vhd.zip

Let's see how to generate images from it.

* Firstly download image and extract vhd file from it.

  `wget https://cloud-images.ubuntu.com/vivid/current/vivid-server-cloudimg-amd64-disk1.vhd.zip`

  `unzip vivid-server-cloudimg-amd64-disk1.vhd.zip`

Once we get vhd file, we can following the follow 2 steps to create the XenServer OpenStack image. This is a common procedure to create images from VHD files for XenServer OpenStack.

* rename vhd file and create gzipped tarball

  `mv vivid-server-cloudimg-amd64-disk1.vhd 0.vhd tar -czf vivid-server-cloudimg-amd64-disk1.tgz 0.vhd`

* create image and import data to glance

  `glance image-create --name="Ubuntu-vivid-server-cloudimg-amd64" --is-public=true --container-format=ovf --disk-format=vhd --property vm_mode=hvm < vivid-server-cloudimg-amd64-disk1.tgz`

# Converting an existing QCOW2 image

Currently XenServer doesn't support QCOW2 images; but thankfully it's easy to convert QCOW2 to VHD based images by using qemu-img.
We can download QCOW2 images from:

*https://getfedora.org/cloud/download/*

*https://uec-images.ubuntu.com/releases*

For example, we download Fedora qcow2 formatted image. We can use the following steps to generate the OpenStack image for XenServer:

`qemu-img convert -O vpc Fedora-Cloud-Base-23-20151030.x86_64.qcow2 0.vhd tar -czf Fedora-Cloud-Base-23-20151030.x86_64.tgz 0.vhd glance image-create --name="Fedora_23" --is-public=true --container-format=ovf --disk-format=vhd --property vm_mode=hvm < Fedora-Cloud-Base-23-20151030.x86_64.tgz`

At here I only take QCOW2 as the example, logically with the similar procedure we can create XenServer Images from any other images format as long as the images can be converted to VHD.

# Creating from an existing XenServer VM

If we have an existing VM running on XenServer, it's easy to create the image from this VM.

1. shutdown the VM

2. get VM's VDI and export it as VHD file. Usually that’s the first disk of the VM, so at here I use “device=xvda” to ensure only the first VBD is listed. If that’s not the first one, please identify it by yourself and specify the correct device.

   `vbd_uuid=$(xe vbd-list vm-name-label=<vm-name> device=xvda minimal=true) vdi_uuid=$(xe vdi-list vbd-uuids=${vbd_uuid} minimal=true) xe vdi-export format=vhd filename=0.vhd uuid=${vdi_uuid}`

3. Once we exported this VHD file, we can follow the same way described in the first section to generate the image.

   Note: There are also other ways to export the vhd file, e.g. copy vhd files directly from ext SR. But I strongly recommend to use vdi-export. It's a formal supported method by XenServer and it will generate compact VHD file with less file size(removed the zero contents from the VHD file). Even you can use this way to compact the existing parsed VHD file. What you need to do is create a VDI and import the VHD file to this VDI then export VHD file from VDI. Finally we will get a compact VHD file.

# Creating a Windows image

 1. From XenCenter, create a VM and install the OS of Window(e.g. Windows 10 (64-bit))

    ![win10-install-2.png](/uploads/win10-install-2.png)![win10-install-1.png](/uploads/win10-install-1.png)

 2. Use Windows Updates to install the latest updates.

 3. Install PV driver from XenCenter:

    ![PVdriver-1.png](/uploads/PVdriver-1.png)

 4. Usually the above operation will insert the XS tools DVD into the DVD drive and finish the installation automatically; but for windows you may need to manually install the XS tools from the VM.

    ![PVdriver-2.png](/uploads/PVdriver-2.png)

 5. After installing PV driver, XenServer may set a device_id to the VM’s parameter of platform. That requires OpenStack to set the proper device_id in the image's metadata so that after the guest VM booted from this image, the PV driver could bind xenbus driver to the correct platform device. But for different releases of XenServer, the device_id may be different, it's easy to cause device_id miss-matching. In order to avoid potential issues, let’s remove this param so that PV driver will negotiate with hypervisor to get a correct device id.

    `xe vm-param-list uuid=8f151bb3-4c90-3e65-94b3-5a9602380369 | grep device_id`

    `platform (MRW): timeoffset: 0; nx: true; pae: true; apic: true; viridian: false; acpi: true; device_id: 0002`

    `xe vm-param-remove param-name=platform param-key=device_id uuid=8f151bb3-4c90-3e65-94b3-5a9602380369`

 6. After installing XenServer tools, reboot VM to make it taking effective.

 7. Add another Administrators account; as Window 10’s security strategy doesn’t allow the built-in Administrator to run Macrosoft Edge which will be used to download cloud. The built-in Administrator will be hidden per Windows’s security strategy.

 8. After login with the new account(e.g. myadmin). Downloading and install the latest Cloudbase-Init version:https://cloudbase.it/downloads/CloudbaseInitSetup_Stable_x64.msi

    ![cloudbase-init-1.png](/uploads/cloudbase-init-1.png)

    ![cloudbase-init-2.png](/uploads/cloudbase-init-2.png)

 9. After cloudbase-init finished running Sysprep, it will shut down VM.

10. Export VDI on XenServer

    ![exportVDI.png](/uploads/exportVDI.png)

11. Create image and upload to glance:

    `tar -cvzf win10.tgz 0.vhd glance image-create --name="win10" --visibility=public --container-format=ovf --disk-format=vhd --property vm_mode=hvm <win10.tgz`

12. Create a new VM from the new image

    `nova boot --flavor 3 --image win10 --meta admin_pass=testVM1pass --nic net-id=0cb33381-e48b-444a-8709-fde15d4cab4e Win10-testVM1`

13. Login Windows with myadmin by using password as the one specified by “—meta admin_pass=”; check this VM’s hostname is Win10-testVM1 which is the VM name specified in the nova boot command.