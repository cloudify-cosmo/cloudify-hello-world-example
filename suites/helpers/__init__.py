import sys


def sh_bake(command):
    return command.bake(_out=lambda line: sys.stdout.write(line),
                        _err=lambda line: sys.stderr.write(line))
