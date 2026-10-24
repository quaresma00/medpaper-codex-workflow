"""Lossless author words through Unicode argv, UTF-8 files or validated base64.

Never guess a corrected author statement from mojibake. File/base64 routes preserve
the exact supplied text; approval semantics are still checked by the owning command.
"""
import argparse
import base64
import binascii
from pathlib import Path


def intact(value):
    if any(c in value for c in ("\ufffd", "\x00")):
        raise argparse.ArgumentTypeError("Text contains replacement/NUL characters; supply the actual original via --words-file/--why-file, not a guessed repair")
    return value


def from_file(value):
    try:
        return intact(Path(value).read_bytes().decode("utf-8-sig"))
    except (OSError, UnicodeError) as exc:
        raise argparse.ArgumentTypeError(f"Cannot read exact UTF-8 author text: {exc}") from exc


def from_b64(value):
    try:
        return intact(base64.b64decode(value, validate=True).decode("utf-8-sig"))
    except (UnicodeError, ValueError, binascii.Error) as exc:
        raise argparse.ArgumentTypeError("Expected strict base64 of the actual UTF-8 text") from exc


def add(parser, option, *, required=False, help=None):
    dest=option.removeprefix("--").replace("-","_")
    group=parser.add_mutually_exclusive_group(required=required)
    group.add_argument(option,dest=dest,type=intact,help=help)
    group.add_argument(option+"-file",dest=dest,type=from_file,metavar="UTF8_FILE",help="Read exact text from a UTF-8 file; no encoding repair")
    group.add_argument(option+"-b64",dest=dest,type=from_b64,metavar="BASE64",help="Exact UTF-8 text encoded as base64")
