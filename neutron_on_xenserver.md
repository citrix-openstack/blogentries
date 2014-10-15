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

