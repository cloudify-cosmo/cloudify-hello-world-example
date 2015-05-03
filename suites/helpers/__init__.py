import sys


def sh_bake(command):
    return command.bake(
        _out=lambda line: sys.stdout.write(line.decode('utf-8')),
        _err=lambda line: sys.stderr.write(line.decode('utf-8')))
