class BrokerSecurity(object):
    def __init__(self, cert_path, key_path):
        self.username = 'securetestuser1'
        self.password = 'securetestpass1'
        with open(cert_path) as cert_handle:
            self.public_cert = cert_handle.read()
        with open(key_path) as key_handle:
            self.private_key = key_handle.read()
