import contextlib
import sys
import termios
import tty


@contextlib.contextmanager
def read_from_stdin():
    fd = sys.stdin.fileno()
    orig_fl = termios.tcgetattr(fd)
    tty.setcbreak(fd)  # use tty.setraw() instead to catch ^C also
    mode = termios.tcgetattr(fd)
    CC = 6
    mode[CC][termios.VMIN] = 0
    mode[CC][termios.VTIME] = 0
    termios.tcsetattr(fd, termios.TCSAFLUSH, mode)

    yield fd

    termios.tcsetattr(fd, termios.TCSANOW, orig_fl)
