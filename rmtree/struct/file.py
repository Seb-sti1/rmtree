from __future__ import annotations

import logging
import os
import re
import shutil
import traceback
import typing as tp
from pathlib import Path

from pypdf import PdfReader, PdfWriter, Transformation

from rmtree.struct.content import Content, ContentFile
from rmtree.struct.metadata import Metadata
from rmtree.struct.page import PageEmpty, PageRM

logger = logging.getLogger(__name__)

ID_PATTERN = re.compile(r"([a-z0-9]{8}-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{12})\.?.*")


def replace_invalid_char(string: str) -> str:
    for char in ["/", ":", "*", "?", "\"", "<", ">", "|"]:
        string = string.replace(char, "")
    return string


class File:
    @staticmethod
    def from_metadata(metadata: Metadata) -> File:
        content = metadata.get_associated_content()
        if isinstance(content, ContentFile):
            return Notebook(metadata, content)
        else:
            return Folder(metadata, content)

    def __init__(self, metadata: Metadata, content: Content):
        self.metadata = metadata
        self.content = content

    def get_uuid(self):
        return self.metadata.uuid

    def get_parent_uuid(self) -> str:
        return self.metadata.get_parent_uuid()

    def get_name(self) -> str:
        return self.metadata.get_name()

    def get_path(self, files: tp.Dict[str, File]) -> Path:
        p = ""

        file = self

        while file.get_parent_uuid() not in ["trash", ""]:
            file = files[file.get_parent_uuid()]
            p = os.path.join(file.get_name(), p)

        if file.get_parent_uuid() == "trash":
            p = os.path.join("_trash", p)

        return Path(p)

    def export(self, output_path: Path):
        """
        Export the file to a pdf

        :param output_path: A folder where to save the file
        :return:
        """
        raise NotImplemented("This is an abstract class.")

    def __str__(self):
        return f"{self.metadata.get_name()} ({self.get_uuid()})"

    def __repr__(self):
        return str(self)


class Notebook(File):

    def __init__(self, metadata: Metadata, content: ContentFile):
        super().__init__(metadata, content)
        self.content = content  # fix type hints

    def export(self, output_path: Path):
        fullpath = os.path.join(output_path, replace_invalid_char(self.metadata.get_name()))
        background_pdf_path = os.path.join(self.metadata.src, self.get_uuid() + ".pdf")

        # create the folder tree (if needed)
        os.makedirs(output_path, exist_ok=True)

        # this is only a pdf
        if all([isinstance(page, PageEmpty) for page in self.content.get_pages()]):
            logger.debug(f"[pdf] {str(self)} -> {fullpath}")
            shutil.copyfile(background_pdf_path, fullpath + ".pdf")
        else:
            background_pdf = PdfReader(background_pdf_path) if os.path.exists(background_pdf_path) else None
            output_pdf = PdfWriter()
            for page, background_page in self.content.iterate_pages(background_pdf):
                if isinstance(page, PageRM):
                    try:
                        # get the svg as a pdf
                        svg_pdf_p, (x_shift, y_shift, w_svg, h_svg) = page.export()
                        # get size of the background_page
                        w_bg = 0 if background_page is None else background_page.mediabox.width
                        h_bg = 0 if background_page is None else background_page.mediabox.height
                        # add a blank page that can contains both svg and background pdf
                        width, height = max(w_svg, w_bg), max(h_svg, h_bg)
                        new_page = output_pdf.add_blank_page(width, height)
                        # compute position of svg and background in the new_page
                        x_svg, y_svg = 0, 0
                        x_bg, y_bg = 0, 0
                        if w_svg > w_bg:
                            x_bg = width / 2 - w_bg / 2 - (w_svg / 2 + x_shift)
                        elif w_svg < w_bg:
                            x_svg = width / 2 - w_svg / 2 + (w_svg / 2 + x_shift)
                        if h_svg > h_bg:
                            y_bg = height - h_bg + y_shift
                        elif h_svg < h_bg:
                            y_svg = height - h_svg - y_shift
                        # merge background_page and svg_pdf_p
                        if background_page is not None:
                            new_page.merge_transformed_page(background_page,
                                                            Transformation().translate(x_bg, y_bg))
                        new_page.merge_transformed_page(svg_pdf_p,
                                                        Transformation().translate(x_svg, y_svg))
                    except Exception:
                        logger.warning(f"Failed to export {page.get_page_uuid()} of {self.get_uuid()}:")
                        traceback.print_exc()
                elif background_page is not None:
                    output_pdf.add_page(background_page)

            if len(output_pdf.pages) > 0:
                output_pdf.write(fullpath + ".pdf")
                output_pdf.close()
            else:
                logger.critical(f"{fullpath + '.pdf'} is empty... It will not be exported to disk.")


class Folder(File):
    """
    This a simple folder
    """

    def __init__(self, metadata: Metadata, content: Content):
        super().__init__(metadata, content)

    def export(self, output_path: Path):
        fullpath = os.path.join(output_path, self.metadata.get_name())

        # create the folder tree (if needed)
        os.makedirs(fullpath, exist_ok=True)


def list_files(src: Path) -> tp.Dict[str, File]:
    """
    List the reMarkable file from the src folder.

    :param src: The source folder
    :return: A dict of uuid -> files
    """
    uuid_list = list(set([ID_PATTERN.fullmatch(f).group(1) for f in os.listdir(src)
                          if ID_PATTERN.fullmatch(f) is not None]))

    files = {}
    for uuid in uuid_list:
        if os.path.exists(src.joinpath(uuid + ".metadata")) \
                and os.path.exists(src.joinpath(uuid + ".content")):
            files[uuid] = File.from_metadata(Metadata(src, uuid))
    return files
