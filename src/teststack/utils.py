import contextlib
import sys
import termios
import tty


class read_from_stdin:
    def __enter__(self):
        if sys.stdin.isatty():  # pragma: no cover
            fd = sys.stdin.fileno()
            self.orig_fl = termios.tcgetattr(fd)
            tty.setcbreak(fd)  # use tty.setraw() instead to catch ^C also
            mode = termios.tcgetattr(fd)
            CC = 6
            mode[CC][termios.VMIN] = 0
            mode[CC][termios.VTIME] = 0
            termios.tcsetattr(fd, termios.TCSAFLUSH, mode)

            return fd

        return None

    def __exit__(self, exc_type, exc_val, traceback):
        if getattr(self, 'orig_fl', None) is not None:  # pragma: no cover
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSANOW, self.orig_fl)
