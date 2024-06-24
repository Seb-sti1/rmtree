reMarkable2pdf
===

__**This project is still in an early stage and have significant shortcomings.**__

Command line tool to convert the files in `/home/root/.local/share/remarkable/xochitl/` of
the [reMarkable 2](https://remarkable.com/) to PDFs.

**It is only compatible with `.rm` v6.**

## Constraints

I decided to make this app for `.content` version 1 and 2
_(`"formatVersion": 2` or `"formatVersion": 1`)_, and
to use [rmc](https://github.com/ricklupton/rmc) to render `.rm` v6.

_Currently [EelcovanVeldhuizen/rmc](https://github.com/EelcovanVeldhuizen/rmc@7cb02ef) is used because it
uses [rmscene](https://github.com/ricklupton/rmscene) v0.4.0 instead of v0.2.0_

### How to check compatibility and update my files to v6?


## Known issues

- `Unknown block type 13` or `Unknown block type 8`: Fix in [rmscene#24](https://github.com/ricklupton/rmscene/pull/24),
  waiting for the version to be released.