import argparse
import json
import logging
import os
import typing as tp
from pathlib import Path

from tqdm import tqdm

from .file import Folder, File, FileType, Notebook, ID_PATTERN

logger = logging.getLogger(__name__)


def get_file_by_id(src: str, uid: str) -> File | None:
    """
    Given a specific id, will find the corresponding file

    :param src: the source folder
    :param uid: the uid of the file to find
    :return: The file if it is not a tombstone or a dirty file (None in this case)
    """
    available_files = {
        "folder": os.path.exists(os.path.join(src, uid)) and os.path.isdir(os.path.join(src, uid)),
        "content": os.path.exists(os.path.join(src, uid + ".content")),
        "local": os.path.exists(os.path.join(src, uid + ".local")),
        "metadata": os.path.exists(os.path.join(src, uid + ".metadata")),
        "pagedata": os.path.exists(os.path.join(src, uid + ".pagedata")),
        "tombstone": os.path.exists(os.path.join(src, uid + ".tombstone")),
        "dirty": os.path.exists(os.path.join(src, uid + ".dirty")),
        "pdf": os.path.exists(os.path.join(src, uid + ".pdf")),
    }

    # if it's a tombstone or dirty file then there are no other available files
    if available_files["tombstone"] or available_files["dirty"]:
        assert not any([available_files[f] for f in available_files if f not in ["tombstone", "dirty"]])
        return None

    # otherwise there is a metadata and a content
    assert available_files["metadata"] and available_files["content"]  # files should have metadata and content

    # find the type
    fileType = FileType.UNKNOWN
    with open(os.path.join(src, uid + ".metadata")) as f:
        metadata = json.load(f)
        if FileType.valid_type(metadata["type"]):
            fileType = metadata["type"]
    assert fileType != FileType.UNKNOWN  # the type should be defined

    if fileType == FileType.FOLDER:
        # folder only have metadata and content
        assert not any([available_files[f] for f in available_files if f not in ["metadata", "content"]])
        return Folder(src, uid)
    elif fileType == FileType.DOCUMENT:
        return Notebook(src, uid)


def list_files(src: str) -> tp.Dict[str, File]:
    """
    List the reMarkable file from the src folder. One reMarkable file can be composed of multiple actual files:

    [id].local: TBD
    [id].content: Contains information on the actual content (like pages, page count...)
    [id].metadata: Contains the metadata (like the name, parent file)
    [id].pagedata: TBD
    [id].pdf: The background PDF (if any)
    [id]/: The folder containing the remarkable binary files

    :param src: The source folder
    :return: The list of files
    """
    files = {}

    for filename in os.listdir(src):
        res = ID_PATTERN.fullmatch(filename)
        if res is not None:
            uid = res.group(1)
            if uid not in files:
                files[uid] = get_file_by_id(src, uid)

    return files


def main(args=None):
    # set up the arg parser
    parser = argparse.ArgumentParser(description='Process the file tree of the reMarkable tablet.')
    parser.add_argument('src', type=Path, help='The source folder')
    parser.add_argument('dst', type=Path, help='The folder used to score the files')
    parser.add_argument('--verbose', '-v', action='count', default=0, help='Increase verbosity')
    parser.add_argument('--debug', '-d', action='store_true', default=False,
                        help='Save svg in the destination folder')

    args = parser.parse_args(args)

    # set up the logging
    level = logging.WARN
    if args.verbose == 1:
        level = logging.INFO
    elif args.verbose >= 2:
        level = logging.DEBUG
    logging.basicConfig(level=level)

    # print debug information on the files
    if level == logging.DEBUG:
        from .debug import count_extension
        logger.debug(count_extension(args.src))

    # export all the files
    files = list_files(args.src)
    progress = tqdm(files)
    for uid in progress:
        f = files[uid]
        progress.set_description(str(f))
        if isinstance(f, Notebook):
            f.export(args.dst, files, args.debug)


if __name__ == "__main__":
    main()
