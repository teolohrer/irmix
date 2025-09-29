import logging
import os
import sys
from contextlib import contextmanager
from rich.logging import RichHandler
from rich.console import Console

# Create a console instance for rich
console = Console()

# Configure rich logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(name)s - %(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(console=console, show_path=True, show_time=True)]
)

# Create logger for this module
logger = logging.getLogger(__name__)

def get_logger(name: str | None = None) -> logging.Logger:
    """Get a logger instance with the specified name.
    
    Args:
        name: The name for the logger. If None, uses the calling module's name.
    
    Returns:
        A configured logger instance.
    """
    if name is None:
        # Get the calling module's name
        import inspect
        frame = inspect.currentframe()
        if frame and frame.f_back:
            name = frame.f_back.f_globals.get('__name__', 'unknown')
    
    return logging.getLogger(name)

@contextmanager
def suppress_stdout_stderr():
    with open(os.devnull, 'w') as devnull:
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = devnull
        sys.stderr = devnull
        try:
            yield
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr