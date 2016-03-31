### Introduction To XenServer Fuel Plugin

As becoming part of the Big Tent, Mirantis Fuel has already made itself one of the leader installers for OpenStack and offers an pluggable architecture that enable you to add new capabilities to your environments. To take advantage of that, XenServer Fuel Plugin is aiming to enables use of the XenServer open source hypervisor (version 6.5. SP1) as a compute provider on Mirantis OpenStack, with commercial support options from Citrix. To be more specific we want to achieve the following major goals:

* Customize user interface
* Configure hypervisor type
* Apply patches
* Reschedule control networks
* Modify guest images

In this blog post, we will have a close look of how XenServer Fuel plugin glues these things together. The outline will also be based on that.

#### Customize user interface

One of the major characteristics that Mirantis really pride themselves is Fuel is highly GUI-based. Fuel UI is a single page application written in JavaScript. User can go through a wizard making choices from a variety of hypervisor, network or storage types and other extra OpenStack services, and then cover the specific settings of the environment in a list of categorized tabs. You can even drag and drop the network interfaces. Generally, in Fuel UI configuration has been redesigned for visual concerns.

![XenServer Fuel plugin wizzard](https://github.com/openstack/fuel-plugin-xenserver/blob/master/doc/source/_static/fmwizard00.png?raw=true)

Moreover, Mirantis Fuel even provides a control plane to let you customize the UI. As long as you follow the schema like [openstack.yaml](https://github.com/openstack/fuel-web/blob/master/nailgun/nailgun/fixtures/openstack.yaml), a brand new OpenStack release can be defined and exercised by Fuel. As shown in the above picture, we create our own release of OpenStack - "Liberty+Citrix XenServer on Ubuntu 14.04" - and upload it to Nailgun service, which contains all the business logic of the system. Interestingly, Mirantis seems to be also in fond of container technology and hosts most of major components inside the docker containers. Here comes the command.

    dockerctl copy xs_release.yaml nailgun:/tmp/xs_release.yaml
    dockerctl shell nailgun manage.py loaddata /tmp/xs_release.yaml
    fuel rel --sync-deployment-tasks --dir /etc/puppet/

The reason to have an own release is we need to filter out incompatible user options. For example, as XenServer is chosen to be the hypervisor of the cluster, vCenter should be disabled. Another example is since VXLAN support hasn't been implemented for XenAPI, so we can only let user select VLAN for network segmentation.

Except a self-defined OpenStack release, Mirantis also provide another approach for Fuel plugin to customize user interface. Within environment_config.yaml we define a bunch of attributes which finally will be rendered as the form shown below.

![XenServer Fuel plugin credential tab](https://github.com/openstack/fuel-plugin-xenserver/blob/master/doc/source/_static/fmsetting00.png?raw=true)

With this form, we can require user to provide the XenServer hosts' credential information in order to ssh into XenServer hosts to apply patches later on.

If you are interested in how Nailgun manages the data gathered by Fuel UI and hand it over to another submodule called Astute for the further provisioning actions, more details from [Fuel- OpenStack Wiki](https://wiki.openstack.org/wiki/Fuel) will be quite useful.

#### Configure hypervisor type

For now in Mirantis Fuel there are only three built-in hypervisor types which are qemu, kvm and vmware and XenServer hasn't been included. Our solution will get started with qemu and change it back to XenServer when all prerequisites have been settled down. Change hypervisor type is quite straightforward, just write below settings to `/etc/nova/nova-compute.conf` and restart Nova services.

    [DEFAULT]
    compute_driver=xenapi.XenAPIDriver
    [xenserver]
    connection_url=http://169.254.0.1
    connection_username="root"
    connection_password="XENSERVER_PASSWORD"

But the timing to do the change might be tricky. Fortunately Mirantis Fuel provides a flexible hook mechanism essentially based on Puppet task dependencies. Once it is done, the new hypervisor type will reflect in Horizon like below.

![XenServer Fuel plugin horizon](https://github.com/openstack/fuel-plugin-xenserver/blob/master/doc/source/_static/fmhorizon00.png?raw=true)

#### Apply patches

However changing the hypervisor type is just the first step. The communication between xapi and Nova services need to be set up like shown in the below diagram. So we need to patch some files.

![xenserver_architecture](http://docs.openstack.org/liberty/config-reference/content/figures/2/a/a/common/figures/xenserver_architecture.png)

Usually the best way to apply patches to XenServer hosts, or more precisely, Dom0, is to pack the changed files into a XenServer supplemental pack and call xe CLI to install it.

    xe-install-supplemental-pack /tmp/novaplugins-liberty.iso

Still, timing is important and we better to take steps. The major steps can be install-pv-tool, install-dpkg-dependencies and install-sup-pack. So the task dependencies probably will be like this:

    - id: 'install-pv-tool'
      role: ['compute']
      required_for: ['compute-post-deployment']
      requires: ['post_deployment_start']
    - id: 'install-dpkg-dependencies'
      role: ['compute']
      required_for: ['compute-post-deployment']
      requires: ['post_deployment_start']
    - id: 'install-sup-pack'
      role: ['compute']
      required_for: ['post_deployment_end']
      requires: ['install-pv-tool', 'install-dpkg-dependencies']

More information about Fuel's hook mechanism can be found in [deployment_tasks.yaml](https://wiki.openstack.org/wiki/Fuel/Plugins#deployment_tasks.yaml).

#### Reschedule control networks

In XenServer, Host Internal Management Network (aka. HIMN) is a special internal network and has the following characteristics:

* It is a built-in network isolated from others.
* It is invisible in XenCenter. So some potential risks will be reduced.
* There is DHCP service already running on this network and the IP address of dom0 is fixed as `169.254.0.1`.

We see HIMN is ideal for internal use and you don't have to spend effort on setting up one. More importantly, Dom0 need to have access to OpenStack control networks as well as Compute nodes do. If we forward control packets via HIMN, that will be easier than setting up additional interfaces for Dom0. And in a sense, Dom0 and Compute node can be regarded as one unity.

Here is the code. We create iptable rules in Compute nodes:

    sed -i s/#net.ipv4.ip_forward/net.ipv4.ip_forward/g /etc/sysctl.conf
    sysctl -p /etc/sysctl.conf
    iptables -t nat -A POSTROUTING -o br-storage -j MASQUERADE
    iptables -A FORWARD -i br-storage -o eth3 -m state --state RELATED,ESTABLISHED -j ACCEPT
    iptables -A FORWARD -i eth3 -o br-storage -j ACCEPT
    iptables -t nat -A POSTROUTING -o br-mgmt -j MASQUERADE
    iptables -A FORWARD -i br-mgmt -o eth3 -m state --state RELATED,ESTABLISHED -j ACCEPT
    iptables -A FORWARD -i eth3 -o br-mgmt -j ACCEPT

`br-storage` and `br-mgmt` refer to OpenStack Storage network and Management networks. They are the OpenStack control networks we talk about. Then we change the default gateway in Dom0.

    route add -net mgmt_ip netmask mgmt_mask gw himn_ip
    route add -net storage_ip netmask mgmt_mask gw himn_ip

#### Modify guest images

One of greatest advantages in Fuel is Health Check. Fuel will go through a list of test cases including booting up some guest VMs and test the functionalities. But we still need to specify appropriate images because specific images are for specific hypervisors.

Please be noted that Fuel will always pick up test images strictly with hard-coded names.

    wget http://ca.downloads.xensource.com/OpenStack/cirros-0.3.4-x86_64-disk.vhd.tgz
    glance image-create --name "TestVM" --container-format ovf --disk-format vhd --property vm_mode="xen" --visibility public --file "cirros-0.3.4-x86_64-disk.vhd.tgz"

    wget http://ca.downloads.xensource.com/OpenStack/F21-x86_64-cfntools.tgz
    glance image-create --name "F17-x86_64-cfntools" --container-format ovf --disk-format vhd --property vm_mode="hvm" --visibility public --file "F17-x86_64-cfntools.tgz"

#### Other misc.

Actually XenServer Fuel plugin will be used to deliver other patches, like:

* novnc proxy patch
* guest logs reformatter patch
* config drive patch
* Validation for necessary hotfix
