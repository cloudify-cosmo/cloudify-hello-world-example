Chef Solo WordPress/MySQL example
=================================

Description
-----------

This is a blueprint for simple wordpress installation on two VMs:

1. Apache + wordpress
2. MySQL

Tested on `OpenStack` (HP cloud), `Ubuntu 12.04` and `Berkshelf 3.1.4`.

Wordpress installation is at: http://YOUR_WEB_SERVER_FLOATING_IP/wordpress/

You can use `nova list` and look for `apache_web_vm_XXXXX` named server to discover the floating IP for the URL above.


Running
-------

This example needs few additional steps after the blueprint is downloaded and before running it. These steps create the `cookbooks.tar.gz` file needed by Chef Solo. Following are the shell commands for these steps:

```bash
gem install berkshelf  # Berkshelf manages cookbooks' dependencies. It processes `Berksfile`.
cd chef-solo-wordpress
berks install  # Fetch all required cookbooks and all their transitive dependencies.
berks package cookbooks.tar.gz  # Archive all required cookbooks and all their transitive dependencies.
```

After executing the commands above, you proceed as with any other Cloudify blueprint. See http://getcloudify.org/guide/3.0/quickstart.html for instructions regarding blueprints usage.

