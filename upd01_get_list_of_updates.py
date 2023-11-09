from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET
import requests
import json
import time
import os
import re

import config


def get_builds():
    url = os.environ.get('UUP_RSS_URL') or 'https://uup.rg-adguard.net/rss'
    r = requests.get(url)
    r.raise_for_status()

    rss_tree = ET.fromstring(r.content)
    rss_items = rss_tree.findall('channel/item')

    # https://stackoverflow.com/a/32229368
    ns = {
        'content': 'http://purl.org/rss/1.0/modules/content/',
    }

    builds = {}
    for item in rss_items:
        title = item.findtext('title')
        assert title

        link = item.findtext('link')
        assert link

        pubDate = item.findtext('pubDate')
        assert pubDate

        category = item.findtext('category')
        assert category == 'Windows Update (UUP)'

        content = item.findtext('content:encoded', namespaces=ns)
        assert content

        uuid = link.removeprefix('https://uup.rg-adguard.net/?id=')

        # To unix timestamp.
        # https://stackoverflow.com/a/1258623
        created = int(parsedate_to_datetime(pubDate).timestamp())

        match = re.search(r'<b>Build:</b> (.*?)<br>', content)
        assert match
        build = match.group(1)

        match = re.search(r'<b>Architecture:</b> (.*?)<br>', content)
        assert match
        arch = match.group(1)

        assert uuid not in builds
        builds[uuid] = {
            'title': title,
            'created': created,
            'build': build,
            'arch': arch,
        }

    return {
        'builds': builds,
    }


def main():
    while True:
        try:
            result = get_builds()
            break
        except requests.exceptions.RequestException as e:
            print(e)

            delay = 10
            print(f'Retrying in {delay} seconds...')
            time.sleep(delay)

    with open(config.out_path.joinpath('updates.json'), 'w') as f:
        json.dump(result, f, indent=4, sort_keys=True)


if __name__ == '__main__':
    main()
