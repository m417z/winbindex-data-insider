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
    url = f'https://uup.rg-adguard.net/api/GetFiles?id={download_uuid}&lang=en-us&edition=professional&pack=en-US&default=yes'
    r = requests.get(url)

    r.raise_for_status()

    html = r.text

    if html.startswith('Error!!! We did not find any data on these parameters.'):
        # The server returns the same error message for both unsupported and not
        # found updates.
        raise UpdateNotSupported

    p = r'<tr style="[^"]+"><td><a href="([^"]+)" rel="noreferrer">([^<]*)</a></td>'
    file_links = re.findall(p, html)
    assert len(file_links) > 0

    # Make sure that we got the correct amount of links.
    textarea_start = '<textarea class="textarea2" onfocus="this.select()" readonly="readonly" readonly rows=20 cols=110 id="filerename" name="dl">\n'
    textarea_start_pos = html.find(textarea_start)
    assert textarea_start_pos != -1
    textarea_start_pos += len(textarea_start)
    textarea_end = '</textarea>'
    textarea_end_pos = html.find(textarea_end, textarea_start_pos)
    assert textarea_end_pos != -1
    textarea_content = html[textarea_start_pos:textarea_end_pos]
    textarea_lines = textarea_content.count('\n')
    assert textarea_lines == len(file_links)

    urls = []
    for url, name in file_links:
        if not re.fullmatch(r'[^\\/:*?"<>|]+', name):
            raise Exception(f'Invalid file name: {name}')

        if name.lower() in [
            'professional_en-us.esd',
            'metadataesd_professional_en-us.esd',
        ]:
            continue

        extension = Path(name).suffix.lower()

        if extension == '':
            if not re.fullmatch(r'[0-9a-f]{40}', name):
                raise Exception(f'Unknown file name: {name}')
            continue

        if name.lower().startswith('ssu-') and extension in ['.cab', '.psf']:
            continue

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

    local_dir_resolved = local_dir.resolve(strict=True)
    local_dir_unc = Rf'\\?\{local_dir_resolved}'

    # Use DeltaDownloader to extract meaningful data from delta files:
    # https://github.com/m417z/DeltaDownloader
    # Avoid path length limitations by using a UNC path.
    args = ['tools/DeltaDownloader/DeltaDownloader.exe', '/g', local_dir_unc]
    subprocess.check_call(args, stdout=None if config.verbose_run else subprocess.DEVNULL)

    # Starting with Windows 11, manifest files are compressed with the DCM v1 format.
    # Use SYSEXP to de-compress them: https://github.com/hfiref0x/SXSEXP
    # Avoid some path length limitations by using a resolved path (the limit is
    # still MAX_PATH).
    args = ['tools/sxsexp64.exe', local_dir_resolved, local_dir_resolved]
    subprocess.run(args, stdout=None if config.verbose_run else subprocess.DEVNULL)


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
