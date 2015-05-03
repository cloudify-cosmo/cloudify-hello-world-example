import sys


def _write(stream, s):
    try:
        s = unicode(s)
    except UnicodeDecodeError:
        s = str(s).decode(encoding, 'replace')
    stream.write(s)


def sh_bake(command):
    return command.bake(
        _out=lambda line: _write(sys.stdout, line),
        _err=lambda line: _write(sys.stderr, line))
