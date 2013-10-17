#!/bin/bash
python remove_newlines.py |
    markdown_py |
    sed -e 's/<pre/<pre style="font-family: monospace; background-color: #F8F8F8;border: 1px solid #DDDDDD;border-radius: 3px 3px 3px 3px;font-size: 13px;line-height: 19px;overflow: auto;padding: 6px 10px;"/g' | xclip
