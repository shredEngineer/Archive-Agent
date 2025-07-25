#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

from contextlib import contextmanager
from rich.progress import Progress, SpinnerColumn, TextColumn


@contextmanager
def Informer(description: str):
    """
    Context manager to display a single Rich spinner for the duration of a block.

    :param description: Description text shown next to the spinner.
    """
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True
    ) as progress:
        task = progress.add_task(description=description, total=None)
        try:
            yield
        finally:
            progress.remove_task(task)
