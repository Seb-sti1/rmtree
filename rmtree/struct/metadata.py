import json
from pathlib import Path
from typing import Optional

from rmtree.struct.content import Content, FileType


class Metadata:
    def __init__(self, src: Path, uuid: str):
        self.src = src
        self.uuid = uuid
        path = src.joinpath(uuid + ".metadata")

        # read file
        f = open(str(path), "r")
        self.raw = json.load(f)
        f.close()

    def get_parent_uuid(self) -> str:
        return self.raw["parent"]

    def get_name(self) -> str:
        return self.raw["visibleName"]

    def get_file_type(self) -> FileType:
        return self.raw["type"]

    def get_associated_content(self) -> Optional[Content]:
        return Content.from_file(self.src, self.uuid, self.get_file_type())

    def test_assertion(self, uuid_list: list[str]) -> bool:
        # the metadata contains is type, visibleName and parent
        # - type is one of FileType valid type
        # - parent is in uuid
        return all([p in self.raw for p in ["type", "visibleName", "parent"]]) \
            and self.raw["parent"] in uuid_list or self.raw["parent"] in ["", "trash"] \
            and FileType.valid_type(self.raw["type"])
