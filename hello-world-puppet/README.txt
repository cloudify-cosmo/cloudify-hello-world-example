# Puppet master installation:

wget http://apt.puppetlabs.com/puppetlabs-release-precise.deb

dpkg -i puppetlabs-release-precise.deb

apt-get update

apt-get install -u puppetmaster # 3.5.1-1puppetlabs1

puppet module install puppetlabs-apache

# ... then use the provided files to populate /etc/puppet
