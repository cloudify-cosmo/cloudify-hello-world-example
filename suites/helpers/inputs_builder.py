import os
import sys

import requests
import xmltodict


def main():
    username = os.environ['QUICK_BUILD_USER']
    password = os.environ['QUICK_BUILD_PASSWORD']
    build_id = os.environ['QUICK_BUILD_BUILD_ID']
    qb_url = os.environ['QUICK_BUILD_URL']

if __name__ == '__main__':
    main()
