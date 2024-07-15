import datetime
import json
from pathlib import Path
import sys

import orjson
from isal import igzip as gzip

import config


def write_to_gzip_file(file, data):
    with open(file, 'wb') as fd:
        with gzip.GzipFile(fileobj=fd, mode='w', compresslevel=config.compression_level, filename='', mtime=0) as gz:
            gz.write(data)


def delete_old_data_for_file(name: str, path: Path, min_date: int):
    with gzip.open(path, 'rb') as f:
        data = orjson.loads(f.read())

    some_deleted = False
    deleted_file_hashes = set()

    data_new = {}

    for file_hash in data:
        windows_versions = data[file_hash]['windowsVersions']
        windows_versions_new = {}
        for windows_version in windows_versions:
            for update in windows_versions[windows_version]:
                release_date = windows_versions[windows_version][update]['updateInfo']['created']
                if release_date >= min_date:
                    windows_versions_new.setdefault(windows_version, {})[
                        update] = windows_versions[windows_version][update]
                else:
                    some_deleted = True

        if windows_versions_new != {}:
            data_new[file_hash] = data[file_hash]
            data_new[file_hash]['windowsVersions'] = windows_versions_new
        else:
            deleted_file_hashes.add((name, file_hash))

    if some_deleted:
        if data_new == {}:
            path.unlink()
        else:
            write_to_gzip_file(path, orjson.dumps(data_new))
    else:
        assert data_new == data

    return deleted_file_hashes


def update_filenames_json(output_dir: Path):
    all_filenames = sorted(path.with_suffix('').stem for path in output_dir.glob('*.json.gz'))

    with open(config.out_path.joinpath('filenames.json'), 'w') as f:
        json.dump(all_filenames, f, indent=0, sort_keys=True)


def update_info_sources_json(deleted_file_hashes: set):
    info_sources_path = config.out_path.joinpath('info_sources.json')
    with open(info_sources_path, 'r') as f:
        info_sources = json.load(f)

    info_sources_new = {}

    for name in info_sources:
        file_hashes_for_name_new = {}
        for hash in info_sources[name]:
            if (name, hash) in deleted_file_hashes:
                continue

            file_hashes_for_name_new[hash] = info_sources[name][hash]

        if file_hashes_for_name_new != {}:
            info_sources_new[name] = file_hashes_for_name_new

    with open(info_sources_path, 'w') as f:
        json.dump(info_sources_new, f, indent=0, sort_keys=True)


def delete_old_data(min_date: int):
    output_dir = config.out_path.joinpath('by_filename_compressed')

    print('Deleting old items')
    deleted_file_hashes = set()
    for path in output_dir.glob('*.json.gz'):
        name = path.name.removesuffix('.json.gz')
        print(f'Deleting old items in {name}')
        deleted_file_hashes |= delete_old_data_for_file(name, path, min_date)

    print('Updating filenames.json')
    update_filenames_json(output_dir)

    print('Updating info_sources.json')
    update_info_sources_json(deleted_file_hashes)

    print('Done')


def main():
    if len(sys.argv) != 2:
        print(f'Usage: {sys.argv[0]} days_to_keep')
        sys.exit(1)

    days_to_keep = int(sys.argv[1])
    date_min = datetime.datetime.now() - datetime.timedelta(days=days_to_keep)
    delete_old_data(round(date_min.timestamp()))


if __name__ == '__main__':
    main()
