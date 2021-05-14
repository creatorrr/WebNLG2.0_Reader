from enum import Enum

__all__ = ["ALPHA", "OMEGA", "SPLITABLES", "DataSetType"]

ALPHA = chr(2)  # Start of text
OMEGA = chr(3)  # End of text
SPLITABLES = {
    ALPHA,
    OMEGA,
    " ",
    ".",
    ",",
    ":",
    "-",
    "'",
    "(",
    ")",
    "?",
    "!",
    "&",
    ";",
    '"',
}


class DataSetType(Enum):
    TEST = "test"
    TRAIN = "train"
    DEV = "dev"
