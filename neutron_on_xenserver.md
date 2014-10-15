# Neutron and XenServer - 2014

More than a year ago I wrote a blog entry on how to get XenServer up and
running with neutron. A lot of things have moved since, so we thought it might
be a good idea to re-visit XenServer's neutron support. In this blog entry I
will guide you through the process of getting neutron up and running with
XenServer.

## Infrastructure

I will be using XenServer 6.2 installations for my work. My only requirement
for the environment is to have XenServer's `eth0` connected to a network with a
DHCP server on it.

## Installing an OpenStack cloud with DevStack

DevStack is a quite common tool to install an OpenStack cloud for development
purposes. I will use it to deploy my environment as well. If you wanted to use
bare devstack, you would need to use ssh to log in to your hypervisor, download
devstack somehow, and execute a script from there. I am picking another route:
a script will be used to generate a deployment script. The deployment script
will then be used to deploy my cloud. I don't need to log in to Dom0, I don't
need to copy any files over there, it's all done by the deployment script.

### Generating the deployment script

To generate the deployment script, I will need the qa repository of
`citrix-openstack` user:

    git clone https://github.com/citrix-openstack/qa

I also create a directory to hold the files that I create during the
investigation:

    mkdir neutron-investigation

Now I want to generate a deployment script that will deploy a specific revision
of each component of openstack. For each build that passes internally, we push
a reference to our github repo clones. The last reference at the time of
writing that passed the full nova-network suite is:
`refs/citrix-builds/jenkins-os-ctx-test-2295`, so I will use that as a basis
for my work:

    pushd qa
    ./generate-citrix-job.sh \
        refs/citrix-builds/jenkins-os-ctx-test-2295 \
        -t neutron \
        -u trusty -x > ../neutron-investigation/deploy-0.sh
    popd

This yields an installation script that could be used to deploy an OpenStack
cloud on XenServer for development purposes, with devstack. The one mandatory
parameter represents the remote reference to be used - this fixes the revision
of all the components. The parameter with `-t` tells us that we would like to
deploy `neutron` networking, `-u` tells us that we want to use the `trusty`
version of ubuntu, and `-x` will generate references to an external git
repository - in this case github.

Take a look at the file, and look for the string `DEVSTACK_SRC`. You will see
that this variable is referencing to a `tgz` snapshot of a git repository. This
is the devstack that's gonna be used to deploy the cloud.

Later in the file you will see that each repository's revision is fixed to
`refs/citrix-builds/jenkins-os-ctx-test-2295`. That's how the revisions are
fixed.

### Deploying the Cloud

It's time to deploy the cloud to a XenServer, using the deployment script that
we have just created. My server's name is `hanwavel.eng.hq.xensource.com`. To
deploy my development cloud to that box, I will need to run the generated
script. To learn about what parameters does it take, run the script without
arguments:

    bash neutron-investigation/deploy-0.sh

At the end of the screen you will see a typical example to be used. Let's
follow on that for now:

    ssh-keygen -t rsa -N "" -f devstack_key.priv
    ssh-keyscan hanwavel.eng.hq.xensource.com >> ~/.ssh/known_hosts

Now we have a file `devstack_key.priv` and we can communicate with the host
without being asked. Let's deploy the cloud:

    bash neutron-investigation/deploy-0.sh \
        hanwavel.eng.hq.xensource.com \
        xenroot devstack_key.priv \
        -t smoke

What we are expecting from this instruction is to deploy a cloud with neutron
and run smoke tests on that. After a minute or so, a surprise happened:

    +++ set +o xtrace
    line 41: declare: -A: invalid option
    declare: usage: declare [-afFirtx] [-p] [name[=value] ...]


That's an error message which needs to be fixed. I created a new branch on my
github repository, and fixed the issue with [this fix](https://github.com/matelakat/devstack/commit/1372e3d40fa41a4fa0f9dbb3443b0a93367ce84f).
Now what I need to do is to modify the deployment script to use my own devstach
branch. See `deploy-1.sh` for that.  Let's see if my fix worked:

    bash neutron-investigation/deploy-1.sh \
        hanwavel.eng.hq.xensource.com \
        xenroot devstack_key.priv \
        -t smoke

This script will first install an Ubuntu VM, than an OpenStack cloud, so be
patient. The script failed with the following error:

    | + timeout 60 sh -c 'while ! wget  --no-proxy -q -O- http://10.21...
    | + die 616 'Neutron did not start'
    | + local exitcode=0
    | [Call Trace]
    | ./stack.sh:1251:start_neutron_service_and_check
    | /opt/stack/devstack/lib/neutron:616:die
    | [ERROR] /opt/stack/devstack/lib/neutron:616 Neutron did not start
    | Error on exit

Before investigating this issue, save the xva so it will be quicker to install
OpenStack on another hypervisor:

    bash neutron-investigation/deploy-1.sh \
        hanwavel.eng.hq.xensource.com \
        xenroot devstack_key.priv \
        -e trusty.xva

After it's done, you should have a file called `trusty.xva`. Export that file
through a webserver, and you can re-use that basic operating system next time,
significantly reducing the time required for installation.

Let's get back to neutron, log in to the domU. One of the last log messages was
someting like:

    + ssh_no_check -q stack@10.219.3.97 'test -e /var/run/devstack.succeeded'

That line contains the IP we'll use to reach domU:

    ssh stack@10.219.3.97

The password is `citrix`. See that it's configured within `deploy-1.sh`. The
first thing I want to see is what's on the console, so do the following:

    screen -R

The error message is as follows:

    [-] Unrecoverable error: please check log for details.
    Traceback (most recent call last):
      File "/opt/stack/neutron/neutron/service.py", line 102, in serve_wsgi
        service.start()
      File "/opt/stack/neutron/neutron/service.py", line 73, in start
        self.wsgi_app = _run_wsgi(self.app_name)
      File "/opt/stack/neutron/neutron/service.py", line 168, in _run_wsgi
        app = config.load_paste_app(app_name)
      File "/opt/stack/neutron/neutron/common/config.py", line 192, in load_paste_app
        raise RuntimeError(msg)
    RuntimeError: Unable to load neutron from configuration file /etc/neutron/api-paste.ini.

    ERROR: Unable to load neutron from configuration file
    /etc/neutron/api-paste.ini.
    q-svc failed to start
    stack@DevStackOSDomU:~/devstack$

Let's check if `/etc/neutron/api-paste.ini` exists. It does, and looks fine. I
need to look a bit higher in the stacktrace. The next clue is:

      File "/opt/stack/neutron/neutron/manager.py", line 139, in _get_plugin_instance
        raise ImportError(_("Plugin not found."))
    ImportError: Plugin not found.

That's a bit more useful. What is the plugin that's used? Take a look at
`/etc/neutron/neutron.conf`.

    stack@DevStackOSDomU:~/devstack$ grep plugin /etc/neutron/neutron.conf

reveals that the plugin used is:

    core_plugin = neutron.plugins.openvswitch.ovs_neutron_plugin.OVSNeutronPluginV2

I read the rest of the config file and found a reference to neutron's
setup.cfg, so grepped it:

    grep OVSNeutronPluginV2 /opt/stack/neutron/setup.cfg

And it came back to me with:

    openvswitch = neutron.plugins.openvswitch.ovs_neutron_plugin:OVSNeutronPluginV2

So I edited `/etc/neutron/neutron.conf` and set:

    core_plugin = openvswitch

And re-called the failed instruction from the history with Ctrl+P. The error is
different this time:

    ImportError: No module named ovs_neutron_plugin

Look into the source tree this time, and see that the module referenced by
`openvswitch` actually does not exist:

    ls /opt/stack/neutron/neutron/plugins/openvswitch/

yields:

    README  __init__.py  __init__.pyc  agent  common  ovs_models_v2.py
    ovs_models_v2.pyc

Clearly no sign of `ovs_neutron_plugin`. I will browse the history of the
repository to see when did it disappear:

    commit 205162f58050fcb94db53cd51b674d2093dfe700
    Author: Mark McClain <mmcclain@yahoo-inc.com>
    Date:   Wed Sep 24 04:00:54 2014 +0000

        remove openvswitch plugin

        This changeset removes the openvswitch plugin, but retains the agent for ML2
        The database models were not removed since operators will need to migrate the
        data.

        Change-Id: I8b519cb2bbebcbec2c78bb0ec9325716970736cf
        Closes-Bug: 1323729

That's clearly a sign to switch to ML2. I need to learn how to do that. The
first bit that's obvious is that I'll need to use `ml2` as `Q_PLUGIN`. So I
created the `deploy-2.sh` script. After that, re-ran the deployment:

    bash neutron-investigation/deploy-2.sh \
        hanwavel.eng.hq.xensource.com \
        xenroot \
        devstack_key.priv -t smoke

The error message this time is:

    Error: Service q-agt is not running

I'm logging in to domU again and g the screen session to see what
happened. Looking into the console output of the quantum agent:

    ...Failed to create OVS patch port.
       Cannot have tunneling enabled on this agent,
       since this version of OVS does not support tunnels or patch ports.
    Agent terminated!
    q-agt failed to start

I would definitely want to use vlans, so it's going to be another configuration
issue. Looking at `/etc/neutron/plugins/ml2/ml2_conf.ini`, it seems that under
the `[ovs]` section, the tunneling is enabled. I disable that config to see
it's effect:

    enable_tunneling = False

Looking at devstack, this is controlled by the `OVS_ENABLE_TUNNELING` varaible,
which is controlled by the `ENABLE_TENANT_TUNNELS` variabe. So turning it off
in `deploy-3.sh`, and re-installing the cloud.

    bash neutron-investigation/deploy-3.sh \
        hanwavel.eng.hq.xensource.com \
        xenroot \
        devstack_key.priv -t smoke

The error message is the same:

    Error: Service q-agt is not running

It's still complaining about the same things. After editing
`/etc/neutron/plugins/ml2/ml2_conf.ini` I realised that `tenant_network_types`
is set to `vxlan`. I definitely want that to be `vlan`. Looking at devstack,
the value is controlled by `Q_ML2_TENANT_NETWORK_TYPE`. That leaves me with the
next deployment script, `deploy-4.sh`.

    bash neutron-investigation/deploy-4.sh \
        hanwavel.eng.hq.xensource.com \
        xenroot \
        devstack_key.priv -t smoke

This time the script terminated at a different point - I'm clearly making
progress here:

    Unable to create the network. No tenant network is available for allocation.
    ...
    [ERROR] /opt/stack/devstack/functions-common:515 Failure ...
    ...creating NET_ID for 0712dc0d52e940bdbe5b2eb67d876b18

Again, let's resume the screen session to see some more details. A lot of red
lines on q-agt. The devstack script actually failed after:

    Creating initial neutron network elements

So let's read devstack and figure out what was the intention there. It was
calling the `create_neutron_initial_network` function. That's defined in
`lib/neutron`.

I think what's missing is the listing of available VLAN ranges for tenant
networks. The setting `network_vlan_ranges` should define this value. In
devstack, it is defined by `ML2_VLAN_RANGES`. I'm adding that option to my new
deployment config, and re-deploying my cloud:

    bash neutron-investigation/deploy-5.sh \
        hanwavel.eng.hq.xensource.com \
        xenroot \
        devstack_key.priv -t smoke

This resulted in the following output:

    ======
    Totals
    ======
    Run: 614 in 1484.443647 sec.
     - Passed: 500
     - Skipped: 55
     - Failed: 59

Which means I successfully got to the tests. Now I will need to do some
cleanup, and also re-build the hypervisor to do another run.
