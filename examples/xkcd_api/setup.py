import os
from configparser import ConfigParser
from pathlib import Path
from typing import Iterable

import setuptools

HERE = Path(__file__).parent.absolute()
PACKAGE_PATH = HERE / "xkcd_api"


def get_metadata_lines() -> Iterable[str]:
    IGNORED_METADATA = ("long_description", "long_description_content_type")
    setup_metadata = ConfigParser()
    setup_metadata.read(HERE / "setup.cfg")

    def format_value(value: str):
        value = value.strip()
        return f"'{value}'" if "\n" not in value else f"'''{value}'''"

    yield from (
        f"{key.upper()} = {format_value(value)}"
        for key, value in setup_metadata["metadata"].items()
        if key not in IGNORED_METADATA
    )


METADATA_TEMPLATE = "\n".join(
    (
        "# pylint: skip-file",
        *get_metadata_lines(),
        "",  # final newline
    )
)

with open(PACKAGE_PATH / "__metadata__.py", "w") as metadata_file:
    print(METADATA_TEMPLATE, file=metadata_file)

setuptools.setup()
