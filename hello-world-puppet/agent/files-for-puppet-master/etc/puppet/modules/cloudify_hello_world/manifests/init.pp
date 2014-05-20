class cloudify_hello_world {

    # Apache
    class{'apache':
        default_vhost => false
    }
    $docroot = "$apache::docroot/cloudify_hello_world"
    apache::vhost{'cloudify_hello_world':
        docroot => $docroot,
        directoryindex => 'index.html',
        port => $cloudify_properties_port,
    }

    # Files
    file { $docroot:
        require => Package['httpd'],
        ensure  => directory,
    }

    file { "${docroot}/index.html":
        require => File[$docroot],
        ensure  => file,
        content => template('cloudify_hello_world/index.html.erb'),
    }
    file { "${docroot}/images/":
        require => File[$docroot],
        ensure  => directory,
        recurse => true,
        source  => "puppet:///modules/cloudify_hello_world/images/",
    }
}

