import xml.etree.ElementTree as ET
from threading import Thread
from pathlib import Path
import subprocess
import requests
import hashlib
import shutil
import json
import time
import re

from delta_patch import unpack_null_differential_file
import config


class UpdateNotFound(Exception):
    pass


class UpdateNotSupported(Exception):
    pass


def get_update_download_urls(download_uuid):
    while True:
        url = f'https://uup.rg-adguard.net/api/GetFiles?id={download_uuid}&lang=en-us&edition=professional&txt=yes'
        r = requests.get(url)

        r.raise_for_status()

        download_sources = r.text

        if download_sources.startswith('Error!!! We did not find any data on these parameters.'):
            # The server returns the same error message for both unsupported and not
            # found updates.
            raise UpdateNotSupported

        download_source_lines = download_sources.splitlines()

        if len(download_source_lines) <= 1:
            print('Unsupported download source content:')
            print(download_sources)
            print('Retrying in 60 seconds...')
            time.sleep(60)
            continue

        if len(download_source_lines) % 3 != 0:
            raise Exception(f'Unsupported download source content')

        break

    names_lower = set()
    file_links = []
    for i in range(0, len(download_source_lines), 3):
        url = download_source_lines[i]
        name = download_source_lines[i + 1]
        checksum = download_source_lines[i + 2]

        if (not url.startswith('http') or
            not name.startswith('  out=') or
            not checksum.startswith('  checksum=')):
            raise Exception(f'Unsupported download source content')

        name = name.removeprefix('  out=')
        names_lower.add(name.lower())
        file_links.append((url, name))

    urls = []
    for url, name in file_links:
        if not re.fullmatch(r'[^\\/:*?"<>|]+', name):
            raise Exception(f'Invalid file name: {name}')

        name_lower = name.lower()
        stem = Path(name_lower).stem
        extension = Path(name_lower).suffix

        # Skip metadata ESD files which contain partial content and can't be
        # extracted with 7z.
        if name_lower in [
            'professional_en-us.esd',
            'metadataesd_professional_en-us.esd',
        ]:
            continue

        # Skip files which don't have a name. Their id is used in this case.
        if extension == '':
            if not re.fullmatch(r'[0-9a-f]{40}', name):
                raise Exception(f'Unknown file name: {name}')
            continue

        # According to uup-dump: "if equivalent cab files exist, exclude updates
        # msu files (from download only)"
        # https://github.com/uup-dump/api/commit/a46a5628c0841055db0c4563d74216d36dc3e402
        if extension == '.msu' and stem + '.cab' in names_lower:
            continue

        # Skip servicing stack updates (SSU).
        if name_lower.startswith('ssu-') and extension in ['.cab', '.psf']:
            continue

        # Skip apps.
        if extension in ['.msix', '.msixbundle', '.appx', '.appxbundle']:
            continue

        if extension not in ['.cab', '.esd', '.psf', '.msu']:
            raise Exception(f'Unknown file extension: {extension}')

        urls.append({
            'name': name,
            'url': url,
        })

    return urls


def download_update(windows_version, update_kb):
    while True:
        try:
            download_urls = get_update_download_urls(update_kb)
            break
        except requests.exceptions.RequestException as e:
            print(e)

            delay = 10
            print(f'Retrying in {delay} seconds...')
            time.sleep(delay)

    local_dir = config.out_path.joinpath('manifests', windows_version, update_kb)
    local_dir.mkdir(parents=True, exist_ok=True)

    for download_url in download_urls:
        name = download_url['name']
        url = download_url['url']

        local_path = local_dir.joinpath(name)

        args = ['aria2c', '-x4', '-o', local_path, '--allow-overwrite=true', url]
        subprocess.check_call(args, stdout=None if config.verbose_run else subprocess.DEVNULL)

        print(f'[{update_kb}] Downloaded {local_path.stat().st_size} bytes to {name} from {url}')

    return local_dir


# https://stackoverflow.com/a/44873382
def sha256sum(filename):
    h  = hashlib.sha256()
    b  = bytearray(128*1024)
    mv = memoryview(b)
    with open(filename, 'rb', buffering=0) as f:
        while n := f.readinto(mv):
            h.update(mv[:n])
    return h.hexdigest()


def extract_update_files(local_dir: Path):
    def cab_extract(pattern: str, from_file: Path, to_dir: Path):
        to_dir.mkdir()
        args = ['expand', '-r', f'-f:{pattern}', from_file, to_dir]
        subprocess.check_call(args, stdout=None if config.verbose_run else subprocess.DEVNULL)

    def msu_extract(from_file: Path, to_dir: Path):
        wim_file = from_file.with_suffix('.wim')
        if wim_file.exists():
            raise Exception(f'WIM file already exists: {wim_file}')

        psf_file = from_file.with_suffix('.psf')
        if wim_file.exists():
            raise Exception(f'PSF file already exists: {psf_file}')

        args = ['7z.exe', 'x', from_file, f'-o{from_file.parent}', '-y', wim_file.name, psf_file.name]
        subprocess.check_call(args, stdout=None if config.verbose_run else subprocess.DEVNULL)

        args = ['7z.exe', 'x', wim_file, f'-o{to_dir}', '-y']
        subprocess.check_call(args, stdout=None if config.verbose_run else subprocess.DEVNULL)
        wim_file.unlink()

        args = ['tools/PSFExtractor.exe', '-v2', psf_file, to_dir.joinpath('express.psf.cix.xml'), to_dir]
        subprocess.check_call(args, stdout=None if config.verbose_run else subprocess.DEVNULL)
        psf_file.unlink()

    next_extract_dir_num = 1

    # Extract CAB files.
    cab_files = list(local_dir.glob('*.cab'))
    for cab_file in cab_files:
        extract_dir = local_dir.joinpath(f'_extract_{next_extract_dir_num}')
        next_extract_dir_num += 1

        psf_file = cab_file.with_suffix('.psf')
        if psf_file.exists():
            # Extract CAB/PSF files.
            # References:
            # https://www.betaarchive.com/forum/viewtopic.php?t=43163
            # https://github.com/Secant1006/PSFExtractor
            args = ['tools/PSFExtractor.exe', cab_file]
            subprocess.check_call(args, stdout=None if config.verbose_run else subprocess.DEVNULL)
            psf_file.unlink()
            cab_file.with_suffix('').rename(extract_dir)
        else:
            cab_extract('*', cab_file, extract_dir)

        cab_file.unlink()

    # Extract ESD files.
    esd_files = list(local_dir.glob('*.esd'))
    for esd_file in esd_files:
        extract_dir = local_dir.joinpath(f'_extract_{next_extract_dir_num}')
        next_extract_dir_num += 1

        args = ['7z.exe', 'x', esd_file, f'-o{extract_dir}', '-y']
        subprocess.check_call(args, stdout=None if config.verbose_run else subprocess.DEVNULL)
        esd_file.unlink()

    # Extract MSU files.
    msu_files = list(local_dir.glob('*.msu'))
    for msu_file in msu_files:
        extract_dir = local_dir.joinpath(f'_extract_{next_extract_dir_num}')
        next_extract_dir_num += 1

        msu_extract(msu_file, extract_dir)
        msu_file.unlink()

    local_dir_resolved = local_dir.resolve(strict=True)
    local_dir_unc = Rf'\\?\{local_dir_resolved}'

    # Starting with Windows 11, manifest files are compressed with the DCM v1
    # format. Use SYSEXP to de-compress them: https://github.com/hfiref0x/SXSEXP
    # Avoid some path length limitations by using a resolved path (the limit is
    # still MAX_PATH).
    #
    # Note: Run this before moving the files to a single folder (below).
    # Otherwise, there could be a file which is sometimes compressed and
    # sometimes isn't, and the equality check will fail.
    args = ['tools/sxsexp64.exe', local_dir_resolved, local_dir_resolved]
    subprocess.run(args, stdout=None if config.verbose_run else subprocess.DEVNULL)

    # Move all extracted files from all folders to the target folder.
    for extract_dir in local_dir.glob('_extract_*'):
        def ignore_files(path, names):
            source_dir = Path(path)
            destination_dir = local_dir.joinpath(Path(path).relative_to(extract_dir))

            ignore = []
            for name in names:
                source_file = source_dir.joinpath(name)
                if source_file.is_file():
                    # Ignore files in root folder which have different non-identical copies with the same name.
                    # Also ignore cab archives in the root folder.
                    if source_dir == extract_dir:
                        if (name in ['update.mum', '$filehashes$.dat'] or
                            name.endswith('.cat') or
                            name.endswith('.cab') or
                            name.endswith('.dll')):
                           ignore.append(name)
                           continue

                    # Ignore files which already exist as long as they're identical.
                    destination_file = destination_dir.joinpath(name)
                    if destination_file.exists():
                        if not destination_file.is_file():
                            raise Exception(f'A destination item already exists and is not a file: {destination_file}')

                        if sha256sum(source_file) != sha256sum(destination_file):
                            raise Exception(f'A different file copy already exists: {destination_file}')

                        ignore.append(name)

            return ignore

        shutil.copytree(extract_dir, local_dir, copy_function=shutil.move, dirs_exist_ok=True, ignore=ignore_files)
        shutil.rmtree(extract_dir)

    # Unpack null differential files.
    for file in local_dir.glob('*/n/**/*'):
        if file.is_file():
            unpack_null_differential_file(file, file)

    # Use DeltaDownloader to extract meaningful data from delta files:
    # https://github.com/m417z/DeltaDownloader
    # Avoid path length limitations by using a UNC path.
    args = ['tools/DeltaDownloader/DeltaDownloader.exe', '/g', local_dir_unc]
    subprocess.check_call(args, stdout=None if config.verbose_run else subprocess.DEVNULL)


def get_files_from_update(windows_version: str, update_kb: str):
    if update_kb in config.updates_unsupported:
        raise UpdateNotSupported

    print(f'[{update_kb}] Downloading update')

    local_dir = download_update(windows_version, update_kb)
    print(f'[{update_kb}] Downloaded update files')

    def extract_update_files_start():
        print(f'[{update_kb}] Extracting update files')
        try:
            extract_update_files(local_dir)
        except Exception as e:
            print(f'[{update_kb}] ERROR: Failed to process update')
            print(f'[{update_kb}]        {e}')
            if config.exit_on_first_error:
                raise
            return
        print(f'[{update_kb}] Extracted update files')

    if config.extract_in_a_new_thread:
        thread = Thread(target=extract_update_files_start)
        thread.start()
    else:
        extract_update_files_start()


def main():
    with open(config.out_path.joinpath('updates.json')) as f:
        updates = json.load(f)

    for windows_version in updates:
        print(f'Processing Windows version {windows_version}')

        for update_kb in updates[windows_version]:
            try:
                get_files_from_update(windows_version, update_kb)
            except UpdateNotSupported:
                print(f'[{update_kb}] Skipping unsupported update')
            except UpdateNotFound:
                print(f'[{update_kb}] WARNING: Update wasn\'t found, it was probably removed from the update catalog')
            except Exception as e:
                print(f'[{update_kb}] ERROR: Failed to process update')
                print(f'[{update_kb}]        {e}')
                if config.exit_on_first_error:
                    raise

        print()


if __name__ == '__main__':
    main()
