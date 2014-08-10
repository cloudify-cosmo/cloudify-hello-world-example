Chef Solo WordPress/MySQL example
=================================

This example needs few additional steps after the blueprints is downloaded and before running it. These steps create the `cookbooks.tar.gz` file needed by Chef Solo. Following are the shell commands for these steps:

```bash
gem install berkshelf  # Berkshelf manages cookbooks' dependencies. It processes `Berksfile`.
cd chef-solo-wordpress
berks install  # Fetch all required cookbooks and all their transitive dependencies.
berks package cookbooks.tar.gz  # Archive all required cookbooks and all their transitive dependencies.
```

After executing the commands above, you proceed as with any other Cloudify blueprint. See http://getcloudify.org/guide/3.0/quickstart.html for instructions regarding blueprints usage.

Tested with `Berkshelf` version `3.1.4`.
