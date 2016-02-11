#! /bin/bash -e

# Expected environment variables:
# JENKINS_MASTER_URL
# JENKINS_USERNAME
# JENKINS_PASSWORD
# JENKINS_EXECUTORS

installed()
{
    command -v $1 > /dev/null 2>&1
}

install_yum_dependencies()
{
    sudo yum update -y
    sudo yum install -y \
        git \
        java-1.7.0-openjdk-devel \
        gcc \
        gcc-c++ \
        python-devel \
        libxml2-devel \
        libxslt-devel \
        curl \
        wget \
        tree \
        vim
}

install_pip_dependencies()
{
    if ! installed pip; then
        wget https://bootstrap.pypa.io/get-pip.py -O get-pip.py
        sudo python get-pip.py
        rm get-pip.py
    fi

    if ! installed virtualenv; then
        sudo pip install virtualenv
        sudo ln -s /usr/bin/virtualenv /usr/bin/virtualenv-2.7
    fi

    if ! installed serv; then
        sudo pip install serv
    fi
}

install_docker()
{
    if ! installed docker; then
        curl -sSL https://get.docker.com/ | sudo sh
        sudo groupadd docker || true
        sudo gpasswd -a ${USER} docker
        sudo systemctl start docker
        sudo systemctl enable docker
    fi
}

install_vagrant()
{
    if ! installed vagrant; then
        sudo yum install -y https://releases.hashicorp.com/vagrant/1.8.0/vagrant_1.8.0_x86_64.rpm
    fi
}

install_gpg_1_4_20()
{
    if [ ! -f gnupg-1.4.20/g10/gpg ]; then
        wget https://www.gnupg.org/ftp/gcrypt/gnupg/gnupg-1.4.20.tar.bz2 -O gnupg.tar.bz2
        tar xvf gnupg.tar.bz2
        rm gnupg.tar.bz2
        pushd gnupg-1.4.20
        ./configure
        make
        sudo rm /usr/bin/gpg || true
        sudo ln -s $PWD/g10/gpg /usr/bin/gpg
        popd
    fi
}


install_pass()
{
    if ! installed pass; then
        wget http://git.zx2c4.com/password-store/snapshot/password-store-1.6.5.tar.xz -O password-store.tar.zx
        tar xvf password-store.tar.zx
        rm password-store.tar.zx
        pushd password-store-1.6.5
        sed -i "s|gpg2|$HOME/gnupg-1.4.20/g10/gpg|" src/completion/pass.bash-completion
        sed -i '/^GPG_OPTS=/a \[\[ -n \$EXTRA_GPG_OPTS \]\] \&\& GPG_OPTS\+=\( \$EXTRA_GPG_OPTS \)' src/password-store.sh
        sed -i "s|^GPG=\"gpg\"|GPG=\"$HOME/gnupg-1.4.20/g10/gpg\"|" src/password-store.sh
        sed -i "s|^which gpg2|#which gpg2|" src/password-store.sh
        sed -i "s|^\[\[ -n \$GPG_AGENT|#\[\[ -n \$GPG_AGENT|" src/password-store.sh
        sudo make install
        popd
        rm -r password-store-1.6.5
    fi
}

install_jenkins_slave()
{
    if [ ! -f jenkins-slave/swarm-client.jar ]; then
        mkdir -p jenkins-slave
        pushd jenkins-slave
        wget http://repo.jenkins-ci.org/releases/org/jenkins-ci/plugins/swarm-client/2.0/swarm-client-2.0-jar-with-dependencies.jar -O swarm-client.jar
        sudo serv generate \
            --name jenkins-slave \
            --deploy \
            --start \
            --overwrite \
            --user $USER \
            --group $(id -gn $USER) \
            --chdir $PWD \
            /usr/bin/java --args "\
                -jar swarm-client.jar \
                -master $JENKINS_MASTER_URL \
                -username $JENKINS_USERNAME \
                -password $JENKINS_PASSWORD \
                -executors $JENKINS_EXECUTORS \
                -mode exclusive \
                -labels system-tests \
                -name stjenkins"
        popd
    fi
}

main()
{
    install_yum_dependencies
    install_pip_dependencies
    install_docker
    install_vagrant
    install_gpg_1_4_20
    install_pass
    install_jenkins_slave
}

main
