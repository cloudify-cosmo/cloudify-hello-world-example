import sys


def _write(stream, s):
    try:
        s = s.encode('utf-8')
    except UnicodeDecodeError:
        pass
    stream.write(s)


def sh_bake(command):
    return command.bake(
        _out=lambda line: _write(sys.stdout, line),
        _err=lambda line: _write(sys.stderr, line))
