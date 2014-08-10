name             'database_for_wordpress'
maintainer       'YOUR_COMPANY_NAME'
maintainer_email 'YOUR_EMAIL'
license          'All rights reserved'
description      'Installs/Configures database_for_wordpress'
long_description IO.read(File.join(File.dirname(__FILE__), 'README.md'))
version          '0.1.0'

# Based on https://github.com/brint/wordpress-cookbook/blob/5d067668dde17101754a75c349ed72646afd04d4/metadata.rb
depends "database", ">= 1.6.0"
depends "mysql", ">= 5.0.0"
depends "mysql-chef_gem", ">= 0.0.2"
depends "openssl"
