### Manual of XenServer+RDO+Neutron

This manual gives brief instruction on installing OpenStack 
using RDO under RHEL7/CentOS7.

		Environment:
			XenServer: 6.5
			CentOS: 7.0
			OpenStack: Liberty
			Network: Neutron, ML2 plugin, OVS, VLAN

##### 1. Install XenServer 6.5
Make sure SR is EXT3 (in the installer this is called XenDesktop optimised storage).

##### 2. Install OpenStack VM
OpenStack VM is used for installing OpenStack software. One VM per hypervisor using 
XenServer 6.5 and RHEL7/CentOS7 templates. Please ensure they are HVM guests.

2.1 Create network for OpenStack. In single box environment, we need three networks, 
`Integration network`, `External network`, `VM network`. If you have appropriate networks 
for the above (for example, a network that gives you external access) then rename the 
existing network to have the appropriate name-label .

You can do this via XenCenter or run command manully or upload [rdo_xenserver_helper.sh](https://github.com/Annie-XIE/summary-os/blob/master/rdo_xenserver_helper.sh) 
to Dom0, let the script do it automatically.

		xe network-create name-label=openstack-int-network
		xe network-create name-label=openstack-ext-network
		xe network-create name-label=openstack-vm-network

2.2 Create virtual network interfaces for OpenStack VM

		xe vif-create device=<devid> network-uuid=<vm_net_uuid> vm-uuid=<vm_uuid>
		xe vif-plug uuid=<vif-id-vm-net>
		xe vif-create device=<devid> network-uuid=<ext_net_uuid> vm-uuid=<vm_uuid>
		xe vif-plug uuid=<vif-id-ext-net>

*Note: device-id should be set according to the number of VIFs in your environment, 
or can be the string 'autodetect' to ask XAPI to pick the next device number*

##### 3. Install RDO
3.1 [RDO Quickstart](https://www.rdoproject.org/Quickstart) gives detailed 
installation guide, please follow the instruction step by step. 
This manual has points out the ones that must pay attation during installation.

3.2 `Step 1: Software repositories`. 

*Note: If issues are encountered when updating the yum repositories, check that 
appropriate upstream repositories are being used. You may need to reboot 
the VM after yum update*

3.3 `Step 2: Install Packstack Installer` 

*Note: Packstack is the real one that installs OpenStack service. 
Maybe you will meet packages dependency errors during this step, 
you should fix these errors manually.*

3.4 `Step 3: Run Packstack to install OpenStack`. 

Use `packstack --gen-answer-file=<ANSWER_FILE>` to generate an answer file.

Use `packstack --answer-file=<ANSWER_FILE>` to install OpenStack components.

These items should be changed as below:

    CONFIG_DEBUG_MODE=y
    CONFIG_NEUTRON_ML2_TYPE_DRIVERS=vlan
    CONFIG_NEUTRON_ML2_TENANT_NETWORK_TYPES=vlan

These items should be changed according to your environment:

    CONFIG_DEFAULT_PASSWORD=<your-password>
    CONFIG_NEUTRON_ML2_VLAN_RANGES=<physnet1:1000:1050>
    CONFIG_NEUTRON_OVS_BRIDGE_MAPPINGS=<physnet1:br-eth1,phyext:br-ex>
    CONFIG_NEUTRON_OVS_BRIDGE_IFACES=<br-eth1:eth1,br-ex:eth2>

*Note:*

*CONFIG_NEUTRON_ML2_VLAN_RANGES is physical network names usable for VLAN provider and 
tenant networks, ranges is for VLAN tags on each available for allocation to tenant networks.*
 
*CONFIG_NEUTRON_OVS_BRIDGE_MAPPINGS is the mapping of network name and ovs bridge*

*CONFIG_NEUTRON_OVS_BRIDGE_IFACES the interface is the one that with vm network*

##### 5. Configure Nova and Neutron

5.1 Copy Nova and Neutron plugins to XenServer host.

You can use [rdo_xenserver_helper.sh](https://github.com/Annie-XIE/summary-os/blob/master/rdo_xenserver_helper.sh)
to do this work

		install_dom0_plugins <dom0_ip>

5.2 Edit /etc/nova/nova.conf, switch compute driver to XenServer. 

    [DEFAULT]
    compute_driver=xenapi.XenAPIDriver

    [xenserver]
    connection_url=http://<dom0_ip>
    connection_username=root
    connection_password=<password>
    vif_driver=nova.virt.xenapi.vif.XenAPIOpenVswitchDriver
    ovs_int_bridge=<integration network bridge>

**Note:**
*How to know integration_bridge and bridge_mapping?*

*In Dom0, run `xe network-list`, the network with name-label integration network is integration bridge.*

5.3 Install XenAPI Python XML RPC lightweight bindings.

    yum install -y python-pip
    pip install xenapi

5.4 Configure Neutron

Edit */etc/neutron/rootwrap.conf* to support communication with Dom0.

    [xenapi]
    # XenAPI configuration is only required by the L2 agent if it is to
    # target a XenServer/XCP compute host's dom0.
    xenapi_connection_url=http://<dom0_ip>
    xenapi_connection_username=root
    xenapi_connection_password=<password>
    
5.4 Restart Nova and Neutron Services

    for svc in api cert conductor compute scheduler; do \
	    service openstack-nova-$svc restart; \
    done
    
    service neutron-openvswitch-agent restar

##### 6. Launch another neutron-openvswitch-agent for talking with Dom0

For all-in-one installation, typically there should be only one neutron-openvswitch-agent.
Please refer [Deployment Model](https://github.com/Annie-XIE/summary-os/blob/master/deployment-neutron-1.png)

However, XenServer has a seperation of Dom0 and DomU and all instances' VIFs are actually 
managed by Dom0. Their corresponding OVS ports are created in Dom0. Thus, we should manually
start the other ovs agent which is in charge of these ports and is talking to Dom0, 
refer [xenserver_neutron picture](https://github.com/Annie-XIE/summary-os/blob/master/xs-neutron-deployment.png).

6.1 Create another configuration file

    cp /etc/neutron/plugins/ml2/openvswitch_agent.ini /etc/neutron/plugins/ml2/openvswitch_agent.ini.dom0
    
    [ovs]
    integration_bridge = xapi3
    bridge_mappings = physnet1:xapi2
    
    [agent]
    root_helper = neutron-rootwrap-xen-dom0 /etc/neutron/rootwrap.conf
    root_helper_daemon =
    minimize_polling = False
    
    [securitygroup]
    firewall_driver = neutron.agent.firewall.NoopFirewallDriver

*Note: `bridge_mappings = physnet1:xapi2`, bridge xapi2 can be easily found 
via `xe network-list` with name label `openstack-vm-network`*

6.2 Launch neutron-openvswitch-agent

    /usr/bin/python2 /usr/bin/neutron-openvswitch-agent --config-file /usr/share/neutron/neutron-dist.conf --config-file /etc/neutron/neutron.conf --config-file /etc/neutron/plugins/ml2/openvswitch_agent.ini.dom0 --config-dir /etc/neutron/conf.d/neutron-openvswitch-agent --log-file /var/log/neutron/openvswitch-agent.log.dom0 &

##### 7. Replace cirros guest with one set up to work for XenServer
    nova image-delete cirros
    wget http://ca.downloads.xensource.com/OpenStack/cirros-0.3.4-x86_64-disk.vhd.tgz
    glance image-create --name cirros --container-format ovf --disk-format vhd --property vm_mode=xen --visibility public --file cirros-0.3.4-x86_64-disk.vhd.tgz

