from tqdm import tqdm

from File import *

DEBUG = False


def count_extension():
    extension = {}

    for filename in os.listdir(SRC_FOLDER):
        ext = os.path.splitext(filename)
        ext = ext[-1] if ext[-1].startswith(".") else ext[-2]

        if not ext.startswith("."):
            ext = "folder"

        if ext in extension:
            extension[ext] += 1
        else:
            extension[ext] = 1
    return extension


def list_id():
    ids = set()

    for filename in os.listdir(SRC_FOLDER):
        res = ID_PATTERN.fullmatch(filename)
        if res is not None:
            ids.add(res.group(1))

    return list(ids)


def get_files():
    files = {}

    for uid in list_id():
        f = get_file_by_id(uid)
        if f is not None:
            files[uid] = f

    return files


def main():
    if DEBUG:
        print(count_extension())

    files = get_files()
    i = 0

    progress = tqdm(files)
    for uid in files:
        f = files[uid]
        progress.set_description(uid)
        if isinstance(f, Notebook):
            f.export(files)
            i += 1


if __name__ == "__main__":
    main()
