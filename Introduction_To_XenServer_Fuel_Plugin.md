### Introduction To XenServer Fuel Plugin

As becoming part of the Big Tent, Mirantis Fuel has already made itself one of the leader installers for OpenStack and offers an pluggable architecture that enable you to add new capabilities to your environments. To take advantage of that, XenServer Fuel Plugin is aiming to deploy production-level OpenStack clusters rigidly and flexibly upon XenServer hosts. To be more specific we want to achieve the following major goals:

* Customize Fuel UI
* Reconfigure default hypervisor type
* Patch Nova plugins and XenAPI SDK
* Forward Management/Storage traffic over HIMN
* Replace test images

In this blog post, we will have a close look of how XenServer Fuel plugin glues these things together. The outline will also be based on that.

#### Customize Fuel UI

One of the major characteristics that Mirantis really pride themselves is Fuel is highly GUI-based. Fuel UI is a single page application written in JavaScript. User can go through a wizard making choices from a variety of hypervisor, network or storage types and other extra OpenStack services, and then cover the specific settings of the environment in a list of categorized tabs. You can even drag and drop the network interfaces. Generally, in Fuel UI everything has been redesigned for visual concerns.

![XenServer Fuel plugin wizzard](https://github.com/openstack/fuel-plugin-xenserver/blob/master/doc/source/_static/fmwizard00.png?raw=true)

However, to get started, the first step, as shown in above picture, is to select an installable OpenStack release which can be defined like [openstack.yaml](https://github.com/openstack/fuel-web/blob/master/nailgun/nailgun/fixtures/openstack.yaml). We have to create our own version, then upload it to the suitable container hosted inside Fuel Master and finally let nailgun service load it into database. Here comes the code.

	dockerctl copy newrelease.yaml nailgun:/tmp/newrelease.yaml
	dockerctl shell nailgun manage.py loaddata /tmp/newrelease.yaml
	fuel rel --sync-deployment-tasks --dir /etc/puppet/

Of course we cannot let users manually do that. So the process mentioned above is automated using [post_install.sh](https://github.com/openstack/fuel-plugin-xenserver/blob/master/post_install.sh) which will be exercised implicitly when installing XenServer Fuel plugin because its hard-coded name has been registered as a hook. Correspondingly, the release will be deleted with [uninstall.sh](https://github.com/openstack/fuel-plugin-xenserver/blob/master/uninstall.sh) when XenServer Fuel plugin is uninstalled.

The reason we need to make our own release is because

* First we need to customize the wizard as well as some other setting tabs in order to narrow down all options to only of those that fits in XenServer
* Second we have to trigger some additional consequent processes which we will discuss in the following sections to complement the environment
* Last but not the least we need to require user to provide the XenServer hosts' credential information in order to ssh into XenServer hosts to patch something. That is why we need to create our own region in setting tabs as below.

![XenServer Fuel plugin credential tab](https://github.com/openstack/fuel-plugin-xenserver/blob/master/doc/source/_static/fmsetting00.png?raw=true)

if you are interested in how Nailgun manages the data gathered by Fuel UI and hand it over to another submodule called Astute for the further provisioning actions, you will like to read more details from [Fuel- OpenStack Wiki](https://wiki.openstack.org/wiki/Fuel)

#### Reconfigure default hypervisor type

For now XenServer hasn't been included in the Fuel's built-in hypervisor types which are qemu, kvm and vmware. In our solution we start with qemu and change to xen when everything is settled down. The approach to change hypervisor type is quite straightforward, just write below settings to `/etc/nova/nova-compute.conf` and restart Nova services.

    [DEFAULT]
    compute_driver=xenapi.XenAPIDriver
    [xenserver]
    connection_url=http://169.254.0.1
    connection_username="root"
    connection_password="XENSERVER_PASSWORD"

Then it will reflect as below picture shows.

![XenServer Fuel plugin horizon](https://github.com/openstack/fuel-plugin-xenserver/blob/master/doc/source/_static/fmhorizon00.png?raw=true)

#### Patch Nova plugins and XenAPI SDK

However changing the hypervisor type isn't enough. The communication between xapi with Nova plugin on Dom0 and Nova services with XenAPI SDK is key in XenServer OpenStack. It can be explicitly shown in the below diagram.

![xenserver_architecture](http://docs.openstack.org/kilo/config-reference/content/figures/2/a/a/common/figures/xenserver_architecture.png)

We have to inject Nova plugins and XenAPI SDK into Dom0 and compute nodes individually.

Nova plugin is a standard XenServer supplemental pack built from OpenStack Nova code repository. Use xe CLI to install it.

    xe-install-supplemental-pack /tmp/novaplugins-kilo.iso

XenAPI SDK is a single python script which delegates the XMLRPC calling to xapi. We only need to copy it to `/usr/lib/python2.7/dist-packages/` on compute nodes to let it take effect.

#### Forward Management/Storage traffic over HIMN

Host Internal Management Network (aka. HIMN) is special internal network inside XenServer. It has the following characteristics:

* It is invisible via XenCenter. It means it cannot be manually operated with a GUI program. If you want to see it or set it, you have to go with CLI.
* It is a built-in network separated from others with DHCP service running over it. It means you don't have to spend any effort on setting up one.
* The IP address of dom0 on HIMN is fixed as `169.254.0.1`.

Based on that, HIMN is ideal for carrying all XenAPI RPC traffics between compute nodes and Dom0. Moreover, we want it carry management and storage traffics since Nova plugin in some cases will use storage network. And if we do so, we don't need to set up two more interfaces to these two networks for Dom0.

In order to implement it, we need iptable and routing table.

* First of all, we enable ip_forward on Compute nodes


    sed -i s/#net.ipv4.ip_forward/net.ipv4.ip_forward/g /etc/sysctl.conf
    sysctl -p /etc/sysctl.conf

* Suppose HIMN is on eth3, we will forward packets from HIMN to management and storage network


	iptables -t nat -A POSTROUTING -o br-storage -j MASQUERADE
	iptables -A FORWARD -i br-storage -o eth3 -m state --state RELATED,ESTABLISHED -j ACCEPT
	iptables -A FORWARD -i eth3 -o br-storage -j ACCEPT
	iptables -t nat -A POSTROUTING -o br-mgmt -j MASQUERADE
	iptables -A FORWARD -i br-mgmt -o eth3 -m state --state RELATED,ESTABLISHED -j ACCEPT
	iptables -A FORWARD -i eth3 -o br-mgmt -j ACCEPT


* Next we route packets to management and storage network go through HIMN as a gateway. The IP address of management and storage network is set in `/etc/astute.yaml` as well as other orchestration information.


    route add -net mgmt_ip netmask mgmt_mask gw himn_ip
    route add -net storage_ip netmask mgmt_mask gw himn_ip

* Last but not the least, don't forget to persist everything.

#### Replace test images

One of greatest features in Fuel is its Health Check. To let it work, we still need to replace the test images because specific test images are for specific hypervisors. But this time we will do that from controller node by calling glance CLI.

	wget http://ca.downloads.xensource.com/OpenStack/cirros-0.3.4-x86_64-disk.vhd.tgz
	glance image-create --name F17-x86_64-cfntools --container-format ovf --disk-format vhd \
	 --property vm_mode=xen --is-public True --file cirros-0.3.4-x86_64-disk.vhd.tgz

	wget http://ca.downloads.xensource.com/OpenStack/F21-x86_64-cfntools.tgz
	glance image-create --name F17-x86_64-cfntools --container-format ovf --disk-format vhd \
	 --property vm_mode=hvm --is-public True --file cirros-0.3.4-x86_64-disk.vhd.tgz

Please be noted that the image names have to be strictly the same because it is hard coded in Fuel.

#### Other miscs

Actually XenServer fuel plugin will something more, like:

* Patch the nova.conf to fix novnc proxy
* Delivery a script to rotate guest logs as it will meet OpenStack standards
* Turn on config drive for file injection
* Check if necessary XenServer hotfix is installed

But mostly they are trivial functions so we don't have to go too keep into them here.
