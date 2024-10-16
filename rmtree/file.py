from __future__ import annotations

import json
import logging
import os
import re
import shutil
from pathlib import Path
from typing import Dict

import cairosvg
from pypdf import PdfReader, PdfWriter, Transformation
from rmc.cli import convert_rm

# id are formatted as 8-4-4-4-12 alphanumerical characters
ID_PATTERN = re.compile(r"([a-z0-9]{8}-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{12})\.?.*")

# the header of a rm binary file, used to detect the version of the file
RM_VERSION = "reMarkable .lines file, version="

logger = logging.getLogger(__name__)


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
    """
    An abstract class that represents a file
    """

    def __init__(self, src: str, uid: str):
        self.uid = uid
        self.src = src

        # load files
        with open(os.path.join(self.src, uid + ".metadata")) as f:
            self.metadata = json.load(f)
        with open(os.path.join(self.src, uid + ".content")) as f:
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


class Folder(File):
    """
    This a simple folder
    """

    def __init__(self, src: str, uid: str):
        super().__init__(src, uid)


class NotebookPage:
    """
    Represents a page of a notebook
    """

    def __init__(self, src: str, uid: str, notebook: Notebook, isContentVersion1: bool, definition: json):
        self.definition = definition
        self.isContentVersion1 = isContentVersion1
        self.notebook = notebook
        self.uid = uid
        self.src = src

        self.path = os.path.join(self.src, self.notebook.uid, self.uid + ".rm")
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

    def export(self, dst="/tmp") -> None | str:
        """
        Use rmc to convert a rm binary file to a svg

        :param dst: the destination path where to store the svg
        :return:
        """

        if self.get_version() == FileVersion.EMPTY:
            return None

        input_rm = Path(os.path.join(self.src, self.notebook.uid, self.uid + ".rm"))
        output_svg = os.path.join(dst, f"{self.uid}.svg")

        with open(output_svg, "w") as fout:
            convert_rm(input_rm, "svg", fout)

        return output_svg


class Notebook(File):
    """
    A notebook is a file on the reMarkable that is a folder or a deleted file (tombstone/dirty). Currently, it can
    be anything from a pdf to a "drawing" only file.

    TODO: deals with background of the remarkable
    """

    def __init__(self, src: str, uid: str):
        super().__init__(src, uid)
        assert self.content["formatVersion"] in [1, 2]  # this software is only compatible with .content version 2 or 1

        pages = self.content["cPages"]["pages"] if self.content["formatVersion"] == 2 else self.content["pages"]

        self.pages: list[NotebookPage] = []
        for p in pages:
            if "deleted" not in p:
                uid = p if self.content["formatVersion"] == 1 else p["id"]
                p = NotebookPage(self.src, uid, self, self.content["formatVersion"] == 1, p)

                if p.get_version() != FileVersion.EMPTY:
                    assert p.get_version() == FileVersion.V6  # this software is only compatible with .rm version 6

                self.pages.append(p)
            else:
                assert not os.path.exists(os.path.join(self.src, self.uid, p["id"] + ".rm"))

        assert self.content["pageCount"] == len(self.pages)

    def export(self, dst: Path, files: Dict[str, File], debug=False):
        path = os.path.join(dst, self.get_path(files))
        fullpath = os.path.join(dst, self.get_fullpath(files))

        os.makedirs(path, exist_ok=True)

        svgs = []
        for page in self.pages:
            try:
                svg = page.export("/tmp" if not debug else dst)
                svgs.append(svg)
            except Exception as e:
                logger.warning(f"Failed to export {page.uid} of {self.uid}: {e}")

        if os.path.exists(os.path.join(self.src, self.uid + ".pdf")):
            if all([svg is None for svg in svgs]):
                # this is only a pdf
                shutil.copyfile(os.path.join(self.src, self.uid + ".pdf"), fullpath + ".pdf")
            else:
                background = PdfReader(os.path.join(self.src, self.uid + ".pdf"))
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
