rmtree
===

A command line tool to convert the files in `/home/root/.local/share/remarkable/xochitl/` of
the [reMarkable 2](https://remarkable.com/) to PDFs.

**It is only compatible with `.rm` version 6
and `.content` version 1 and 2 _(`"formatVersion": 2` or `"formatVersion": 1`)_.**

It uses [rmc](https://github.com/ricklupton/rmc) (which depends on [rmscene](https://github.com/ricklupton/rmscene)) to
render the remarkable files to svg, converts them to pdf and then merges them together with, if necessary,
the background pdf. _Currently, [Seb-sti1/rmc](https://github.com/Seb-sti1/rmc/tree/dev) is used because it
uses [rmscene](https://github.com/ricklupton/rmscene) v0.5.0 instead of v0.2.0_

_Please before submitting an issue check the [Known issues](#known-issues) section and the already existing issues._

## How to use?

After installing the package in the python environment, it is intended to be used with the following commands:

```sh
# replace [ip] by the ip of the remarkable. 
rsync -r --delete --progress root@[ip]:/home/root/.local/share/remarkable/xochitl/ rm_folder/
python -m rmtree ./rm_folder ./exported_file_destination
```

## How to check compatibility and update my files to v6?

[_Hopefully soon_](https://github.com/Seb-sti1/rmtree/issues/3)

## Known issues

- [Background template aren't exactly aligned](https://github.com/Seb-sti1/rmc/issues/4)
- [Missing background templates](https://github.com/Seb-sti1/rmtree/issues/4)
  (`P Lines small`,  `P Grid medium`, `P Grid large`, `P Lines medium`, `P Checklist`)
- `Unknown block type 13` or `Unknown block type 8`: Fixed
  in [rmscene#24](https://github.com/ricklupton/rmscene/pull/24), waiting for the version to be released.
- [`AssertionError` on `next_items` in `toposort_items`](https://github.com/ricklupton/rmscene/issues/32)

## Contributions

All contributions are welcomed :).
