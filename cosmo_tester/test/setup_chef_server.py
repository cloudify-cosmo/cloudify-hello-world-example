""" Assumes fabric environment already set up """
import sys

from fabric.api import run, sudo, env
from fabric import operations
from path import path

KNIFE_PARAMS = '-u admin -k ~/admin.pem'


def use_cookbook(cookbook_name, cookbook_url):
    """ Downloads cookbook from given url and uploads it to the Chef server """
    run('mkdir -p ~/cookbooks/{0}'.format(cookbook_name))
    # Next line was inspired by (sorry, flake8)
    # https://github.com/opscode-cookbooks/chef-server/blame/
    # c588a4c401d3fac14f70d3285fe49eb4dccd9759/README.md#L158
    run('wget -qO- {0} | tar xvzC ~/cookbooks/{1} --strip-components=1'.format(
        cookbook_url, cookbook_name))
    run('knife cookbook upload ' + KNIFE_PARAMS +
        ' --cookbook-path ~/cookbooks ' + cookbook_name)
    run('knife cookbook list ' + KNIFE_PARAMS + ' | grep -F ' + cookbook_name +
        ' ')


def userize_file(original_path):
    """ Places the file under user's home directory and make it
        permissions-wise accessible """
    sudo("cp -a {path} ~{user}/ && chown {user} ~{user}/{basename}".format(
        path=original_path,
        basename=str(path(original_path).basename()),
        user=env['user']))


def setup(local_dir, cookbooks):
    userize_file("/etc/chef-server/admin.pem")
    for cb in cookbooks:
        use_cookbook(*cb)

    userize_file("/etc/chef-server/chef-validator.pem")
    operations.get('~/chef-validator.pem', str(local_dir))

if __name__ == '__main__':
    # XXX: not tested - start
    host, user, key_filename, local_dir, cookbooks = sys.argv[1:]
    local_dir = path(local_dir)
    # Cookbooks: name1:url1,name2:url2
    cookbooks = [v.split(':', 1) for v in cookbooks.split(',')]
    env.update({
        'timeout': 30,
        'user': user,
        'key_filename': key_filename,
        'host_string': host,
    })
    setup(local_dir, cookbooks)
    # XXX: not tested - end
