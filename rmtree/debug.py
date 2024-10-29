import os
import typing as tp
from pathlib import Path

from rmtree.struct.content import ContentFile
from rmtree.struct.file import ID_PATTERN
from rmtree.struct.metadata import Metadata
from rmtree.struct.page import PageRM, PageVersion

"""
Here is a list and partial description of the files in the /home/root/.local/share/remarkable/xochitl/ of the 
reMarkable. `[uuid]` represents an uuid v4.

- .tree: TBD
- [uuid].local: TBD
- [uuid].content: Contains information on the actual content (like pages, page count, etc)
- [uuid].metadata: Contains the metadata (like the name, parent file, etc)
- [uuid].pagedata: TBD
- [uuid].pdf: The background PDF (if any)
- [uuid]/: The folder containing the pages
    - [page uuid].rm: reMarkable binary files
    - [page uuid]-metadata.json: TBD
- [uuid].thumbnails/: The folder containing PNG of the pages (probably used for preview)
- [uuid].highlights/: TBD
- [uuid].textconversion/: TBD
"""

know_file_extensions = ["tombstone", "local", "metadata", "content", "pagedata", "pdf", "dirty"]
know_folder_extensions = ["thumbnails", "highlights", "textconversion", "RM_FOLDER"]


def count_extension(src: Path) -> tp.Tuple[tp.Dict[str, int], tp.Dict[str, int]]:
    """
    Count the number of files of each extension in the `src` folder
    :param src: the source folder
    :return: A dictionary with number of files of each extension, A dictionary with number of folder of each extension
    """

    file_extension = {}
    folder_extension = {}

    for filename in [f for f in os.listdir(src) if ID_PATTERN.fullmatch(f) is not None]:
        if os.path.isfile(os.path.join(src, filename)):
            ext = filename.split(".")[-1]

            if ext in file_extension:
                file_extension[ext] += 1
            else:
                file_extension[ext] = 1
        else:
            ext = filename.split(".")[-1] if "." in filename else "RM_FOLDER"

            if ext in folder_extension:
                folder_extension[ext] += 1
            else:
                folder_extension[ext] = 1

    return file_extension, folder_extension


def test_assertion(src: Path, custom_print=print) -> tp.Tuple[int, int]:
    custom_print(f"===== Testing compatibility and assertion on {src} =====")
    custom_print()
    custom_print("Be aware of the following:")
    custom_print("\t- Compatibility refers to the constraint that I decided to impose (mainly the\n"
                 "\t  version constraint on .rm and .content files). Any error regarding this is\n"
                 "\t  considered 'wrong input from the user'/'software limitation' and not a bug.\n"
                 "\t- Assertion refers to the hypothesis made as there is no official API for\n"
                 "\t  the reMarkable file structure. Errors regarding these assertions can be\n"
                 "\t  considered bugs. Please report them on GitHub with as much information as possible.")
    custom_print()

    extensions = count_extension(src)
    custom_print("Extension of detected files:")
    custom_print("\n".join([f"\t- {ext} "
                            f"{'' if ext in know_file_extensions else '(unknown, please consider submitting an issue)'}: {c}"
                            for ext, c in extensions[0].items()]))
    custom_print("Extension of detected folder:")
    custom_print("\n".join([f"\t- {ext} "
                            f"{'' if ext in know_folder_extensions else '(unknown, please consider submitting an issue)'}: {c}"
                            for ext, c in extensions[1].items()]))

    uuid_list = list(set([ID_PATTERN.fullmatch(f).group(1) for f in os.listdir(src)
                          if ID_PATTERN.fullmatch(f) is not None]))

    def exists(name: str):
        return os.path.exists(os.path.join(src, name))

    errors = {}
    for uuid in uuid_list:
        # if it's a tombstone or dirty file then there are no other available files
        if (exists(uuid + ".tombstone") or exists(uuid + ".dirty")) and \
                any([exists(uuid + "." + ext) for ext in know_file_extensions + know_folder_extensions
                     if ext not in ["tombstone", "dirty", "RM_FOLDER"]]
                    + [exists(uuid)]):
            errors[uuid] = {"type": "assert",
                            "reason": "tombstone or dirty is present with useful files."}
            continue

        # otherwise there should be a metadata and a content
        if not (exists(uuid + ".metadata") and exists(uuid + ".content")):
            errors[uuid] = {"type": "assert",
                            "reason": "Either the metadata or content file is missing."}
            continue

        # verify assertion on the metadata file
        metadata = Metadata(src, uuid)
        if not metadata.test_assertion(uuid_list):
            errors[uuid] = {"type": "assert",
                            "reason": "The metadata assertion are not verified."}
            continue

        # verify assertion on the content file
        content = metadata.get_associated_content()
        if isinstance(content, ContentFile) and content.get_version() not in [1, 2]:
            errors[uuid] = {"name": metadata.get_name(), "type": "compatibility",
                            "reason": "This software is only compatible with content version 1 and 2."}
            continue
        elif not content.test_assertion():
            errors[uuid] = {"name": metadata.get_name(), "type": "assert",
                            "reason": "The content assertion are not verified."}
            continue

        # check rm file version
        if isinstance(content, ContentFile):
            not_compatible_pages: list[tp.Tuple[int, str, PageVersion]] = []
            for n, page in enumerate(content.get_pages()):
                if isinstance(page, PageRM) and not page.test_assertion():
                    not_compatible_pages.append((n + 1, page.page_uuid, page.get_version()))

            if len(not_compatible_pages) > 0:
                errors[uuid] = {"name": metadata.get_name(), "pages": not_compatible_pages, "type": "compatibility",
                                "reason": "This software is only compatible with rm file version 6"}

        # [uuid]/ folder only contains rm files
        if exists(uuid):
            for filename in os.listdir(os.path.join(src, uuid)):
                if not (filename.endswith(".rm") or filename.endswith("-metadata.json")):
                    errors[uuid] = {"name": metadata.get_name(), "type": "assert",
                                    "reason": "Unknown files in the [uuid]/ folder"}

    # print compatibilities errors
    compatibility_errors = {uuid: error for uuid, error in errors.items() if error["type"] == "compatibility"}
    if len(compatibility_errors) > 0:
        custom_print()
        custom_print(
            "The following are compatibility errors. This software is explicitly not compatible with those files.\n"
            "You can look at the README.md to find more information:\n"
            "https://github.com/Seb-sti1/rmtree?tab=readme-ov-file#how-to-check-compatibility-and-update-my-files-to-v6.")
        for uuid, error in compatibility_errors.items():
            if "pages" in error:
                custom_print(
                    f"\t- {error['name']} (page n°{', '.join([str(pages[0]) for pages in error['pages']])}) ({uuid}):"
                    f" This software is only compatible with rm file version 6")
            else:
                custom_print(f"\t- {error['name']} ({uuid}): {error['reason']}")

    # print assertion errors
    assertion_errors = {uuid: error for uuid, error in errors.items() if error["type"] == "assert"}
    if len(assertion_errors) > 0:
        custom_print()
        custom_print(
            "The following are assertion errors. You can report them at https://github.com/Seb-sti1/rmtree/issues.")
        for uuid, error in assertion_errors.items():
            custom_print(f"\t- {error['name'] if 'name' in error else 'Unknown name'} ({uuid}): {error['reason']}")

    return len(compatibility_errors), len(assertion_errors)
