blogentries
===========
A repository for blogs:

- [XenAPINFS](./xenapinfs.md)
- [Virtual Hypervisor](./virtual_hypervisor.md)

tools
=====
To convert an entry to html:

    cat xenapinfs.md | python remove_newlines.py | markdown_py | xclip    

Preformatted blocks with black background:

    cat quantum_on_xenserver.md | python remove_newlines.py | markdown_py | sed -e 's/<pre/<pre style="background-color:#000;color:#fff;padding:.5em"/g' | xclip

After this, it could be inserted to wordpress.
