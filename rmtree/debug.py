import os
from typing import Dict


def count_extension(src) -> Dict[str, int]:
    """
    Count the number of files of each extension in the `src` folder
    :param src: the source folder
    :return: A dictionary with number of files of each extension
    """

    extension = {}

    for filename in os.listdir(src):
        ext = os.path.splitext(filename)
        ext = ext[-1] if ext[-1].startswith(".") else ext[-2]

        if not ext.startswith("."):
            ext = "folder"

        if ext in extension:
            extension[ext] += 1
        else:
            extension[ext] = 1
    return extension
