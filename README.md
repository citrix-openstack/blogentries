blogentries
===========
A repository for blogs:

- [XenAPINFS](./xenapinfs.md)
- [Virtual Hypervisor](./virtual_hypervisor.md)
- [Neutron on XenServer](./quantum_on_xenserver.md)
- [XenServer Image to VOlume](./xenserver_image_to_volume.md)

tools
=====
To convert an entry to html:

    cat xenapinfs.md | python remove_newlines.py | markdown_py | xclip    

Preformatted blocks with black background:

    cat quantum_on_xenserver.md | ./formatted_blog_to_clipboard.sh

After this, it could be inserted to wordpress.
