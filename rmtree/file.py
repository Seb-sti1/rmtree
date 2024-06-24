from __future__ import annotations

import json
import logging
import os
import re
import shutil
import typing as tp
from pathlib import Path

import cairosvg
from pypdf import PdfReader, PdfWriter, Transformation
from rmc.exporters.svg import tree_to_svg, PAGE_WIDTH_PT, PAGE_HEIGHT_PT
from rmscene import read_tree

# id are formatted as 8-4-4-4-12 alphanumerical characters
ID_PATTERN = re.compile(r"([a-z0-9]{8}-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{12})\.?.*")

# svg viewBox
SVG_VIEWBOX_PATTERN = re.compile(r"^<svg .+ viewBox=\"([\-\d.]+) ([\-\d.]+) ([\-\d.]+) ([\-\d.]+)\">$")

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

    def get_path(self, files: tp.Dict[str, File]) -> str:
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

    def get_fullpath(self, files: tp.Dict[str, File]) -> str:
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
        self.template = None
        if not self.isContentVersion1 and "template" in definition:
            self.template = None if definition["template"]["value"] == "Blank" else definition["template"]["value"]

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

    def export(self, dst="/tmp") -> (str, (float, float, float, float)):
        """
        Use rmc to convert a rm binary file to a svg

        :param dst: the destination path where to store the svg
        :return: the path to the svg, and the x,y shift in the svg coordinates
        """
        assert self.get_version() != FileVersion.EMPTY
        input_rm = Path(os.path.join(self.src, self.notebook.uid, self.uid + ".rm"))
        output_svg = os.path.join(dst, f"{self.uid}.svg")

        template = Path(os.path.join(Path(__file__).parent, "templates", self.template + ".svg")) \
            if self.template is not None else None

        if template is not None and not template.exists():
            logger.warning(f"Can't find the specified template file ({template.name})")
            template = None

        with open(input_rm, 'rb') as f:
            with open(output_svg, "w") as fout:
                tree = read_tree(f)
                tree_to_svg(tree, fout, template)

        x_shift, y_shift, w, h = 0, 0, PAGE_WIDTH_PT, PAGE_HEIGHT_PT
        with open(output_svg, "r") as svg:
            found = False
            for line in svg.readlines():
                res = SVG_VIEWBOX_PATTERN.match(line)
                if res is not None:
                    x_shift, y_shift = float(res.group(1)), float(res.group(2))
                    w, h = float(res.group(3)), float(res.group(4))
                    found = True
                    break

            if not found:
                logger.warning(f"Can't find x shift, y shift, width and height for {self.uid}")

        return output_svg, (x_shift, y_shift, w, h)


class Notebook(File):
    """
    A notebook is a file on the reMarkable that is a folder or a deleted file (tombstone/dirty). Currently, it can
    be anything from a pdf to a "drawing" only file.
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

        # create the folder tree (if needed)
        os.makedirs(path, exist_ok=True)

        if os.path.exists(os.path.join(self.src, self.uid + ".pdf")):
            if all([page == FileVersion.EMPTY for page in self.pages]):
                # this is only a pdf
                logger.debug(f"[pdf] {str(self)} -> {fullpath}")
                shutil.copyfile(os.path.join(self.src, self.uid + ".pdf"), fullpath + ".pdf")
            else:
                background = PdfReader(os.path.join(self.src, self.uid + ".pdf"))
                output_pdf = PdfWriter()

                # FIXME deal with "new page" in pdf (then use a with background not the pdf)
                for page, background_page in zip(self.pages, background.pages):
                    if page.get_version() != FileVersion.EMPTY:
                        try:
                            svg, (x_shift, y_shift, w, h) = page.export("/tmp" if not debug else dst)
                            # use dpi=72 so that the pdf has the same size as the svg
                            cairosvg.svg2pdf(url=svg, write_to=svg + ".pdf", dpi=72)
                            # get the background_page
                            svg_pdf = PdfReader(svg + ".pdf")
                            assert len(svg_pdf.pages) == 1
                            svg_pdf_p = svg_pdf.pages[0]
                            # merge page depending on which, between the svg and the background pdf, is bigger
                            # FIXME this doesn't work. the following code should create a page using the biggest width
                            #   and height between svg_pdf_p and background_page
                            if (svg_pdf_p.mediabox.height > background_page.mediabox.height
                                    or svg_pdf_p.mediabox.width > background_page.mediabox.width):
                                # move it at the right place
                                t = Transformation().translate(
                                    - x_shift - background_page.mediabox.width / 2,
                                    svg_pdf_p.mediabox.height - background_page.mediabox.height + y_shift)
                                svg_pdf_p.merge_transformed_page(background_page, t, over=False)
                                output_pdf.add_page(svg_pdf_p)
                            else:
                                # move it at the right place
                                t = Transformation().translate(
                                    background_page.mediabox.width / 2 + x_shift,
                                    background_page.mediabox.height - svg_pdf_p.mediabox.height + y_shift)
                                background_page.merge_transformed_page(svg_pdf_p, t)
                                output_pdf.add_page(background_page)
                        except Exception as e:
                            logger.warning(f"Failed to export {page.uid} of {self.uid}: {e}")
                    else:
                        output_pdf.add_page(background_page)

                # FIXME prevent empty pdf export
                output_pdf.write(fullpath + ".pdf")
                output_pdf.close()
        else:
            merger = PdfWriter()
            for background_page in self.pages:
                try:
                    svg, _ = background_page.export("/tmp" if not debug else dst)
                    cairosvg.svg2pdf(url=svg, write_to=svg + ".pdf")
                    merger.append(svg + ".pdf")
                except Exception as e:
                    logger.warning(f"Failed to export {background_page.uid} of {self.uid}: {e}")
            merger.write(fullpath + ".pdf")
            merger.close()
