from typing import Dict, Iterable, List, Optional

import discord


def sanitise(
    string: str, *, limit: int = 2000, escape: bool = True, tag_escape=True
) -> str:
    """Sanitise string.

    Args:
        string: A text string to sanitise.
        limit: How many characters should be processed.
        escape: Whether to escape characters (to prevent unwanted markdown).
        tag_escape: Whether to escape tags (to prevent unwanted tags).

    Returns:
        Sanitised string.
    """
    if escape:
        string = discord.utils.escape_markdown(string)

    if tag_escape:
        return string.replace("@", "@\u200b")[:limit]
    else:
        return string[:limit]


def split(string: str, limit: int = 1990) -> List[str]:
    """Split text into multiple smaller ones.

    :param string: A text string to split.
    :param limit: How long the output strings should be.
    :return: A string split into a list of smaller lines with maximal length of
        ``limit``.
    """
    return list(string[0 + i : limit + i] for i in range(0, len(string), limit))


def smart_split(
    string: str,
    limit: int = 1990,
    min_length: int = 1000,
    mark_continuation: str = "",
) -> List[str]:
    """Split text into multiple smaller ones.

    :param string: A text string to split.
    :param limit: How long the output strings should be.
    :param min_length: Minimal length of the output strings.
    :param mark_continuation: Continuation mark of message.
    :return: List of splitted strings with max length of ``limit``
    """

    parts = [string]

    # sanitize limits
    mark_continuation = "" if mark_continuation is None else mark_continuation
    min_length = min(abs(min_length), 1900, limit - 100)
    min_length = (
        max(len(mark_continuation) + 5, min_length)
        if mark_continuation != ""
        else min_length
    )
    limit = min(1990, abs(limit))

    # split message to chunks of roughly limit chars
    while len(parts[len(parts) - 1]) > limit:

        # determine where to split the message
        split_pos = parts[len(parts) - 1].find(" ", limit - 20)
        if split_pos > limit or split_pos <= 0:
            split_pos = parts[len(parts) - 1].rfind(" ", min_length, limit - 20)
        if split_pos > limit or split_pos <= 0:
            split_pos = limit

        split_pos_old = (
            split_pos  # save found value, it might get useful, if part gets too short
        )

        part = (str)(parts[len(parts) - 1][:split_pos])  # get part

        markdown_sanitization_success = False

        # check if markdown marks aren't split in half
        markdown_marks = ["~~", "***", "**", "*", "__", "_", "```", "`", "||"]
        while not markdown_sanitization_success:
            markdown_sanitization_success = True
            for mark in markdown_marks:
                if part.count(mark) % 2 != 0:
                    split_pos = part.rfind(mark)
                    part = (str)(part[:split_pos])
                    markdown_sanitization_success = False

        # if by trying to keep markdown marks complete part to split became to short, add ends of markdown marks to the end
        marks_to_add_to_start = ""
        if split_pos < min_length or split_pos <= 0:
            split_pos = split_pos_old
            part = (str)(
                parts[len(parts) - 1][:split_pos]
            )  # update part using new split pos
            for mark in markdown_marks:
                if part.count(mark) % 2 != 0:
                    tmp_pos = parts[len(parts) - 1].find(mark, split_pos) + len(mark)
                    # try to move split after end of markdown mark, if part is still shorter than limit use it
                    if 0 < tmp_pos <= limit:
                        split_pos = tmp_pos
                        part = (str)(parts[len(parts) - 1][:split_pos])
                    # if there are odd number of markdown marks, end them and save them to add them to next part
                    if part.count(mark) % 2 != 0:
                        part = (str)(part + mark)
                        marks_to_add_to_start += mark

        # if by adding ends of markdown marks part became too long split it again
        if len(part) > min(2000, limit + 10):
            tmp_parts = smart_split(
                part,
                limit - 20,
                min_length=min_length,
                mark_continuation=mark_continuation,
            )  # make space for potentially adding ends of markdown marks, if it's second pass
            part = (str)(tmp_parts[0])
            split_pos = len(part)

        # check if text is supposed to be bigger, smaller or citation
        marks = ["### ", "## ", "-# ", "# ", ">>> ", "> "]
        for mark in marks:
            tmp = part.split("\n")[-1]
            if tmp.startswith(mark):
                if tmp.startswith(
                    mark + ">>> "
                ):  # bigger or smaller text can also be citation
                    mark += ">>> "
                marks_to_add_to_start = mark + marks_to_add_to_start

        part = (str)(
            part.removesuffix(" ")
        )  # remove space from start of part, it might end up there because of moving split to end of markdown mark

        tmp = parts[len(parts) - 1][split_pos:].removeprefix(
            " "
        )  # save rest of message

        parts.append(
            (
                (
                    # if next part starts with \n remove it from continuation mark
                    (
                        mark_continuation.rstrip()
                        if tmp.startswith("\n")
                        else mark_continuation
                    )
                    if limit > len(mark_continuation) + 20
                    else ""
                )
                + (
                    marks_to_add_to_start if len(tmp.split("\n")[0].strip()) > 0 else ""
                )  # add start of markdown marks if there is some text before new line
                if len(tmp.strip()) > 0
                else ""
            )  # add this part only if there is some non blank spaces string in next part
            + tmp  # add the next part
        )  # mark remaining text as continuation
        parts[(len(parts) - 2)] = (
            part  # update previous part to be roughly limit chars long
        )

    return parts


# consider renaming to merge_lines, makes more sense, since it's merging blocks
def split_lines(lines: List[str], limit: int = 1990) -> List[str]:
    """Split list of lines to bigger blocks.

    :param lines: List of lines to split.
    :param limit: How long the output strings should be.
    :return: A list of strings constructed from ``lines``.

    This works just as :meth:`split()` does; the only difference is that
    this guarantees that the line won't be split at half, instead of calling
    the :meth:`split()` on ``lines`` joined with newline character.
    """
    pages: List[str] = list()
    page: str = ""

    for line in lines:
        if len(page) >= limit:
            pages.append(page.strip("\n"))
            page = ""
        page += line + "\n"
    pages.append(page.strip("\n"))
    return pages


def parse_bool(string: str) -> Optional[bool]:
    """Parse string into a boolean.

    :param string: Text to be parsed.
    :return: Boolean result of the conversion.

    Pass strings ``1``, ``true``, ``yes`` for ``True``.

    Pass strings ``0``, ``false``, ``no`` for ``False``.

    Other keywords return ``None``.
    """
    if string.lower() in ("1", "true", "yes"):
        return True
    if string.lower() in ("0", "false", "no"):
        return False
    return None


def create_table(
    iterable: Iterable, header: Dict[str, str], *, limit: int = 1990, rich: bool = True
) -> List[str]:
    """Create table from any iterable.

    This is useful mainly for '<command> list' situations.

    Args:
        iterable: Any iterable of items to create the table from.
        header: Dictionary of item attributes and their translations.
        limit: Character limit, at which the table is split.
        rich:
            Color rows.
            Defaults to ``False`` until Discord properly supports ANSI
            escape codes on Android.
    """
    matrix: List[List[str]] = []
    pages: List[str] = []

    # Compute column widths, make sure all fields have non-None values
    matrix.append(list(header.values()))
    column_widths: List[int] = [len(v) for v in header.values()]
    for item in iterable:
        line: List[str] = []
        for i, attr in enumerate(header.keys()):
            line.append(str(getattr(item, attr, "")))

            item_width: int = len(line[i])
            if column_widths[i] < item_width:
                column_widths[i] = item_width

        matrix.append(line)

    P: str = ""
    H: str = ""
    A: str = ""
    R: str = ""
    if rich:
        P = "ansi\n"
        H = "\u001b[1;34m"  # bold blue
        A = "\u001b[36m"  # cyan
        R = "\u001b[0m"  # reset

    page: str = P
    for i, matrix_line in enumerate(matrix):
        line: str = ""

        # Color heading & odd lines
        if i == 0:
            line += H
        elif i % 2 == 0:
            line += A

        # Add values
        for column_no, column_width in enumerate(column_widths):
            line += matrix_line[column_no].ljust(column_width + 2)

        # End line
        line = line.rstrip()
        if i % 2 == 0:
            line += R + "\n"
        else:
            line += "\n"

        # Add line
        if len(page) + len(line) > limit:
            pages.append(page)
            page = P
        page += line

    # Add final non-complete page
    pages.append(page)

    return pages


def shorten(text: Optional[str], max_len: int = 1024) -> Optional[str]:
    """Shortens the text based on the given max length.
    This function also sanitizes the code blocks.

    :param text: Text to shorten.
    :param max_len: How long the output strings should be.
    :return: Shortened string with fixed .
    """
    if text is not None and len(text) > 1024:
        text = text[:1024]
        text = text[:-3] + "```" if text.count("```") % 2 != 0 else text

    return text
