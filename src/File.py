from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Dict

import cairosvg
from pypdf import PdfReader, PdfWriter, Transformation
from rmc.cli import convert_rm

# define where is/go the data
SRC_FOLDER = "./data"
DST_FOLDER = "./export"

# id are formatted as 8-4-4-4-12 alphanumerical characters
ID_PATTERN = re.compile(r"([a-z0-9]{8}-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{12})\.?.*")
RM_VERSION = "reMarkable .lines file, version="


class FileVersion:
    V6 = 6
    V5 = 5
    V3 = 3
    EMPTY = 0
    UNKNOWN = -1

    VALID_VERSIONS = [V6, V5, V3]


class FileType:
    UNKNOWN = -1
    DOCUMENT = 'DocumentType'
    FOLDER = 'CollectionType'

    @staticmethod
    def valid_type(file_type: str) -> bool:
        return file_type in [FileType.DOCUMENT, FileType.FOLDER]


class File:
    def __init__(self, uid: str):
        self.uid = uid

        # load files
        with open(os.path.join(SRC_FOLDER, uid + ".metadata")) as f:
            self.metadata = json.load(f)
        with open(os.path.join(SRC_FOLDER, uid + ".content")) as f:
            self.content = json.load(f)

        self.name = re.sub(r"[^a-zA-Z0-9_\-+*[\] ]", "", self.metadata["visibleName"])  # remove any special char
        self.in_trash = self.metadata["parent"] == "trash"
        self.parent = self.metadata["parent"] if self.metadata["parent"] != "" and not self.in_trash else None
        self.type = self.metadata["type"] if FileType.valid_type(self.metadata["type"]) else FileType.UNKNOWN

    def get_path(self, files: Dict[str, File]) -> str:
        path = ""

        if self.parent is not None:
            f = files[self.parent]
            while True:
                path = os.path.join(f.name, path)
                if f.parent is None:
                    break
                f = files[f.parent]

        if self.in_trash:
            path = os.path.join("_trash", path)

        return path

    def get_fullpath(self, files: Dict[str, File]) -> str:
        return str(os.path.join(self.get_path(files), self.name))

    def __str__(self):
        return f"{self.uid} ({self.name})"


class NotebookPage:

    def __init__(self, uid: str, notebook: Notebook, isContentVersion1: bool, definition: json):
        self.definition = definition
        self.isContentVersion1 = isContentVersion1
        self.notebook = notebook
        self.uid = uid

        self.path = os.path.join(SRC_FOLDER, self.notebook.uid, self.uid + ".rm")
        self.version = FileVersion.UNKNOWN

        if not os.path.exists(self.path):
            self.version = FileVersion.EMPTY
        else:
            headers = {v: RM_VERSION + str(v) for v in FileVersion.VALID_VERSIONS}
            with open(self.path, 'rb') as f:
                file_header = f.read(max([len(headers[v]) for v in headers]))
                for v in headers:
                    h = headers[v]
                    if file_header.startswith(h.encode('ascii')):
                        self.version = v
                        break

    def get_version(self):
        """
        :return: the version of the page
        """
        return self.version

    def export(self, debug) -> None | str:
        if self.get_version() == FileVersion.EMPTY:
            return None

        path = os.path.join("/tmp" if not debug else DST_FOLDER, f"{self.uid}.svg")

        with open(path, "w") as fout:
            convert_rm(Path(os.path.join(SRC_FOLDER, self.notebook.uid, self.uid + ".rm")), "svg", fout)

        return path


class Notebook(File):

    def __init__(self, uid: str):
        super().__init__(uid)
        assert self.content["formatVersion"] in [1, 2]  # this software is only compatible with .content version 2 or 1

        pages = self.content["cPages"]["pages"] if self.content["formatVersion"] == 2 else self.content["pages"]

        self.pages: list[NotebookPage] = []
        for p in pages:
            if "deleted" not in p:
                uid = p if self.content["formatVersion"] == 1 else p["id"]
                p = NotebookPage(uid, self, self.content["formatVersion"] == 1, p)

                if p.get_version() != FileVersion.EMPTY:
                    assert p.get_version() == FileVersion.V6  # this software is only compatible with .rm version 6

                self.pages.append(p)
            else:
                assert not os.path.exists(os.path.join(SRC_FOLDER, self.uid, p["id"] + ".rm"))

        assert self.content["pageCount"] == len(self.pages)

    def export(self, files, debug=False):
        path = os.path.join(DST_FOLDER, self.get_path(files))
        fullpath = os.path.join(DST_FOLDER, self.get_fullpath(files))

        os.makedirs(path, exist_ok=True)

        svgs = []
        for page in self.pages:
            try:
                svg = page.export(debug)
                svgs.append(svg)
            except Exception as e:
                print(f"Failed to export {page.uid} of {self.uid}: {e}")

        if os.path.exists(os.path.join(SRC_FOLDER, self.uid + ".pdf")):
            if all([svg is None for svg in svgs]):
                # this is only a pdf
                shutil.copyfile(os.path.join(SRC_FOLDER, self.uid + ".pdf"), fullpath + ".pdf")
            else:
                background = PdfReader(os.path.join(SRC_FOLDER, self.uid + ".pdf"))
                output_pdf = PdfWriter()

                for page_num, (page, svg) in enumerate(zip(background.pages, svgs)):
                    if svg is not None:
                        # use dpi=72 so that the pdf has the same size as the svg
                        cairosvg.svg2pdf(url=svg, write_to=svg + ".pdf", dpi=72)
                        # get the page
                        svg_pdf = PdfReader(svg + ".pdf")
                        assert len(svg_pdf.pages) == 1
                        svg_pdf_p = svg_pdf.pages[0]
                        # scale the page
                        ratio = 856 / page.mediabox.height
                        page.scale(ratio, ratio)
                        # move it at the right place
                        svg_pdf_p.merge_transformed_page(page,
                                                         Transformation().translate(
                                                             (svg_pdf_p.mediabox.width - page.mediabox.width) / 2,
                                                             svg_pdf_p.mediabox.height - page.mediabox.height),
                                                         over=False)
                        output_pdf.add_page(svg_pdf_p)
                    else:
                        output_pdf.add_page(page)

                output_pdf.write(fullpath + ".pdf")
                output_pdf.close()
        else:
            merger = PdfWriter()
            for svg in svgs:
                if svg is not None:
                    cairosvg.svg2pdf(url=svg, write_to=svg + ".pdf")
                    merger.append(str(svg + ".pdf"))
            merger.write(fullpath + ".pdf")
            merger.close()


class Folder(File):
    """
    This a simple folder
    """

    def __init__(self, uid: str):
        super().__init__(uid)


def get_file_by_id(uid: str) -> File | None:
    """

    :param uid:
    :return:
    """

    """
    $id.local: ??
    $id.content: ??
    $id.metadata: visibleName (string), parent (id)
    $id.pagedata: ??
    $id.pdf: background pdf (if exist)
    $id/: the folder containing the remarkable binary files
    """
    available_files = {
        "folder": os.path.exists(os.path.join(SRC_FOLDER, uid)) and os.path.isdir(os.path.join(SRC_FOLDER, uid)),
        "content": os.path.exists(os.path.join(SRC_FOLDER, uid + ".content")),
        "local": os.path.exists(os.path.join(SRC_FOLDER, uid + ".local")),
        "metadata": os.path.exists(os.path.join(SRC_FOLDER, uid + ".metadata")),
        "pagedata": os.path.exists(os.path.join(SRC_FOLDER, uid + ".pagedata")),
        "tombstone": os.path.exists(os.path.join(SRC_FOLDER, uid + ".tombstone")),
        "dirty": os.path.exists(os.path.join(SRC_FOLDER, uid + ".dirty")),
        "pdf": os.path.exists(os.path.join(SRC_FOLDER, uid + ".pdf")),
    }

    # if it's a tombstone or dirty file then there are no other available files
    if available_files["tombstone"] or available_files["dirty"]:
        assert not any([available_files[f] for f in available_files if f not in ["tombstone", "dirty"]])
        return None

    # otherwise there is a metadata and a content
    assert available_files["metadata"] and available_files["content"]  # files should have metadata and content

    # find the type
    fileType = FileType.UNKNOWN
    with open(os.path.join(SRC_FOLDER, uid + ".metadata")) as f:
        metadata = json.load(f)
        if FileType.valid_type(metadata["type"]):
            fileType = metadata["type"]
    assert fileType != FileType.UNKNOWN  # the type should be defined

    if fileType == FileType.FOLDER:
        # folder only have metadata and content
        assert not any([available_files[f] for f in available_files if f not in ["metadata", "content"]])
        return Folder(uid)
    elif fileType == FileType.DOCUMENT:
        return Notebook(uid)
