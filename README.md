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

    cat quantum_on_xenserver.md | python remove_newlines.py | markdown_py | sed -e 's/<pre/<pre style="background-color: #F8F8F8;border: 1px solid #DDDDDD;border-radius: 3px 3px 3px 3px;font-size: 13px;line-height: 19px;overflow: auto;padding: 6px 10px;"/g' | xclip

After this, it could be inserted to wordpress.
