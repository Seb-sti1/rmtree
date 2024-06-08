reMarkable2pdf
===

__**This project is still in a early stage and have significant short comings.**__

This is repo aims to convert the files in `/home/root/.local/share/remarkable/xochitl/` of
the [reMarkable 2](https://remarkable.com/) to PDFs.

# Constraints

I decided to make this app for `.content` version 2 _(`"formatVersion": 2`)_, and
to use [rmc](https://github.com/ricklupton/rmc) to render `.rm` v6.

Therefore any files older than these versions won't be compatible.

_Currently [EelcovanVeldhuizen/rmc](https://github.com/EelcovanVeldhuizen/rmc@7cb02ef) is used because it
uses [rmscene](https://github.com/ricklupton/rmscene) v0.4.0 instead of v0.2.0_