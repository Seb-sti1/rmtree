rmtree
===

A command line tool to convert the files in `/home/root/.local/share/remarkable/xochitl/` of
the [reMarkable 2](https://remarkable.com/) to PDFs.

**It is only compatible with `.rm` version 6
and `.content` version 1 and 2.**
See [this section](#how-to-check-compatibility-and-update-my-files-to-v6) to verify compatibility.

It uses [rmc](https://github.com/ricklupton/rmc) (which depends on [rmscene](https://github.com/ricklupton/rmscene)) to
render the remarkable files to svg, converts them to pdf and then merges them together with, if necessary,
the background pdf. _Currently, [Seb-sti1/rmc](https://github.com/Seb-sti1/rmc/tree/dev) is used because it
uses [rmscene](https://github.com/ricklupton/rmscene) v0.5.0 instead of v0.2.0._

_Please before submitting an issue check the [known issues](#major-known-issues) section and the already existing
issues._

## How to install?

Start by installing the dependency:

```sh
apt install libcairo2
```

Then download the `.whl` from the last release.

### Using pipx (recommended)

See the [official pipx documentation](https://pipx.pypa.io/stable/installation/) on how
to install pipx.

```sh
pipx install ./rmtree.whl
```

### Using venv

```sh
python3.11 -m venv .venv  # create a venv 
source .venv/bin/activate  # source the venv
pip install ./rmtree.whl
```

_Note: in the following instead of `rmtree`, you should use `python -m rmtree` to start the package._

## How to use?

After installing, it is intended to be used with the following commands:

```sh
# replace [ip] by the ip of the remarkable. 
rsync -r --delete --progress root@[ip]:/home/root/.local/share/remarkable/xochitl/ rm_folder/
rmtree ./rm_folder ./exported_file_destination
```

_If you have assertion errors, you can ignore them using the `--ignore-assertion` option but
there is a high chance that the output will not be correct.
For more information or compatibility errors see
[the next section](#how-to-check-compatibility-and-update-my-files-to-v6)._

## How to check compatibility and update my files to v6?

You can test the program for compatibility and assertion errors using
`rmtree ./rm_folder --test-compatibility`. It will output the detected compatibility
and assertion errors.

- Compatibility refers to the constraint that I decided to impose (mainly the
  version constraint on .rm and .content files). Any error regarding this is
  considered 'wrong input from the user'/'software limitation' and not a bug.
- Assertion refers to the hypothesis made as there is no official API for
  the reMarkable file structure. Errors regarding these assertions can be
  considered bugs. Please report them on GitHub with as much information as possible.

### Update rm files to v6

Compatibility error regarding the `.rm` files version will be listed as shown below:

```
The following are compatibility errors. This software is explicitly not compatible with those files.
You can look at the README.md to find more information:
https://github.com/Seb-sti1/rmtree?tab=readme-ov-file#how-to-check-compatibility-and-update-my-files-to-v6.
	- Notes (page n°1, 2) (25a92754-ea08-467a-a386-5e169c804c96): This software is only compatible with rm file version 6
	- Notebook (page n°1, 2, 3, 4, 5) (fb90bd3d-62d2-46f6-a7e3-aa098c1938f2): This software is only compatible with rm file version 6
```

This indicates that `Notes` page number 1 and 2 and `Notebook` page number 1, 2, 3, 4 and 5 are not using
`.rm` file v6.
**It appears that going to each page individually and drawing (even if removing afterward) makes the
reMarkable updates the page to v6.**

## Major known issues

- [Background template aren't exactly aligned](https://github.com/Seb-sti1/rmc/issues/4)
- [Missing background templates](https://github.com/Seb-sti1/rmtree/issues/4)
  (`P Lines small`,  `P Grid medium`, `P Grid large`, `P Lines medium`, `P Checklist`)
- `Unknown block type 13` or `Unknown block type 8`: Fixed
  in [rmscene#24](https://github.com/ricklupton/rmscene/pull/24), waiting for the version to be released.
- [`AssertionError` on `next_items` in `toposort_items`](https://github.com/ricklupton/rmscene/issues/32)

## Contributions

All contributions are welcomed :).
