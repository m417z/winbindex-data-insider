from threading import Thread
from pathlib import Path
import subprocess
import requests
import hashlib
import shutil
import json
import time

from delta_patch import unpack_null_differential_file
import config


class UpdateNotFound(Exception):
    pass


class UpdateNotSupported(Exception):
    pass


def get_update_download_urls(download_uuid):
    url = f'https://uupdump.net/json-api/get.php?id={download_uuid}'
    r = requests.get(url)
    if r.status_code == 500:
        error = r.json()['response']['error']
        if error == 'EMPTY_FILELIST':
            raise UpdateNotFound(f'Update {download_uuid} not found')

    r.raise_for_status()

    files = r.json()['response']['files']

    names = set()
    urls = []
    for file in files:
        if (file.lower().startswith('microsoft-windows-') and
            file.lower().endswith('.esd') and
            not file.lower().startswith('microsoft-windows-client-languagepack-') and
            not file.lower().startswith('microsoft-windows-server-languagepack-')):
            names.add(file)
            urls.append({
                'name': file,
                'url': files[file]['url'],
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
    next_extract_dir_num = 1

    # Extract delta files from the CAB/PSF files.
    # References:
    # https://www.betaarchive.com/forum/viewtopic.php?t=43163
    # https://github.com/Secant1006/PSFExtractor
    cab_files = list(local_dir.glob('*.cab'))
    for cab_file in cab_files:
        psf_file = cab_file.with_suffix('.psf')
        args = ['tools/PSFExtractor.exe', cab_file]
        subprocess.check_call(args, stdout=None if config.verbose_run else subprocess.DEVNULL)
        cab_file.unlink()
        psf_file.unlink()

        extract_dir = local_dir.joinpath(f'_extract_{next_extract_dir_num}')
        next_extract_dir_num += 1
        cab_file.with_suffix('').rename(extract_dir)

    # Extract delta files from the ESD files.
    esd_files = list(local_dir.glob('*.esd'))
    for esd_file in esd_files:
        extract_dir = local_dir.joinpath(f'_extract_{next_extract_dir_num}')
        next_extract_dir_num += 1

        args = ['7z.exe', 'x', esd_file, f'-o{extract_dir}', '-y']
        subprocess.check_call(args, stdout=None if config.verbose_run else subprocess.DEVNULL)
        esd_file.unlink()

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
    # Avoid path limitations by using a UNC path.
    local_dir_unc = Rf'\\?\{local_dir.absolute()}'
    args = ['tools/DeltaDownloader/DeltaDownloader.exe', '/g', local_dir_unc]
    subprocess.check_call(args, stdout=None if config.verbose_run else subprocess.DEVNULL)

    # Starting with Windows 11, manifest files are compressed with the DCM v1 format.
    # Use SYSEXP to de-compress them: https://github.com/hfiref0x/SXSEXP
    args = ['tools/sxsexp64.exe', local_dir, local_dir]
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
        except (KeyboardInterrupt, SystemExit):
            raise
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
            except (KeyboardInterrupt, SystemExit):
                raise
            except UpdateNotSupported:
                print(f'[{update_kb}] WARNING: Skipping unsupported update')
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
