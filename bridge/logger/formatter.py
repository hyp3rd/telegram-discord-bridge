"""Logger formatters.""" ""
import logging
import sys
from copy import copy
from typing import Optional

import click

if sys.version_info < (3, 8):  # pragma: py-gte-38
    from typing_extensions import Literal
else:  # pragma: py-lt-38
    from typing import Literal

TRACE_LOG_LEVEL = 5


class ColourizedFormatter(logging.Formatter):
    """
    A custom log formatter class that:

    * Outputs the LOG_LEVEL with an appropriate color.
    * If a log call includes an `extras={"color_message": ...}` it will be used
      for formatting the output, instead of the plain text message.
    """

    level_name_colors = {
        TRACE_LOG_LEVEL: lambda level_name: click.style(str(level_name), fg="blue"),
        logging.DEBUG: lambda level_name: click.style(str(level_name), fg="cyan"),
        logging.INFO: lambda level_name: click.style(str(level_name), fg="green"),
        logging.WARNING: lambda level_name: click.style(str(level_name), fg="yellow"),
        logging.ERROR: lambda level_name: click.style(str(level_name), fg="red"),
        logging.CRITICAL: lambda level_name: click.style(
            str(level_name), fg="bright_red"
        ),
    }

    def __init__(
        self,
        fmt: Optional[str] = None,
        datefmt: Optional[str] = None,
        style: Literal["%", "{", "$"] = "%",
        use_colors: Optional[bool] = None,
    ):
        if use_colors in (True, False):
            self.use_colors = use_colors
        else:
            self.use_colors = sys.stdout.isatty()
        super().__init__(fmt=fmt, datefmt=datefmt, style=style)

    def color_level_name(self, level_name: str, level_no: int) -> str:
        """Colorize the level name."""

        def default(level_name: str) -> str:
            return str(level_name)  # pragma: no cover

        func = self.level_name_colors.get(level_no, default)
        return func(level_name)

    def color_asctime(self, date: str) -> str:
        """Colorize the date."""
        return click.style(date, fg="bright_blue")

    def format_pid(self, pid: int) -> str:
        """Format the pid."""
        return click.style(str(pid), fg="blue", bold=True)

    def should_use_colors(self) -> bool:
        """Whether the formatter should use colors or not."""
        return True  # pragma: no cover

    def formatMessage(self, record: logging.LogRecord) -> str:
        recordcopy = copy(record)
        levelname = recordcopy.levelname
        seperator = " " * (8 - len(recordcopy.levelname))
        asctime = recordcopy.asctime
        process = recordcopy.process if recordcopy.process else 0
        message = recordcopy.getMessage()

        if self.use_colors:
            levelname = self.color_level_name(levelname, recordcopy.levelno)
            asctime = self.color_asctime(recordcopy.asctime)
            process = self.format_pid(process)
            if "color_message" in recordcopy.__dict__:
                recordcopy.msg = recordcopy.__dict__["color_message"]
                recordcopy.__dict__["message"] = message

        recordcopy.__dict__["levelprefix"] = levelname + ":" + seperator
        recordcopy.__dict__["asctime"] = asctime + ":"
        recordcopy.__dict__["message"] = f"{process} - " + message
        return super().formatMessage(recordcopy)


class DefaultFormatter(ColourizedFormatter):
    """The default formatter for the logger."""

    def should_use_colors(self) -> bool:
        return sys.stderr.isatty()  # pragma: no cover
