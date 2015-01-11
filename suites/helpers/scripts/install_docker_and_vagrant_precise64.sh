#! /bin/bash -e

install_vagrant()
{
    local vagrant_version=1.6.3
    local vagrant_package_url=https://dl.bintray.com/mitchellh/vagrant/vagrant_${vagrant_version}_x86_64.deb
    local vagrant_package_dest=vagrant_${vagrant_version}.deb

    if [[ ! -f $vagrant_package_dest ]]; then
        echo Downloading vagrant package
        wget --no-verbose -O $vagrant_package_dest $vagrant_package_url
    fi

    sudo dpkg -i $vagrant_package_dest
}

install_docker()
{
    sudo apt-get update

    # Docker requires kernel >= 3.8, uncomment if your kernel is of an earlier version
    # sudo apt-get install linux-image-generic-lts-raring linux-headers-generic-lts-raring -y

    [[ -e /usr/lib/apt/methods/https ]] || sudo apt-get install apt-transport-https -y

    sudo apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys 36A1D7869245C8950F966E92D8576A8BA88D21E9

    sudo sh -c "echo deb https://get.docker.io/ubuntu docker main > /etc/apt/sources.list.d/docker.list"
    sudo apt-get update
    sudo apt-get install lxc-docker -y

    sudo groupadd docker || :
    sudo gpasswd -a ${USER} docker
    sudo service docker restart
}

main()
{
    install_vagrant
    install_docker
}

main
