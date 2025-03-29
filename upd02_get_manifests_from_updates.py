from threading import Thread
from pathlib import Path
import subprocess
import requests
import tempfile
import hashlib
import shutil
import json
import time
import os
import re

from delta_patch import unpack_null_differential_file
import config


class UpdateNotFound(Exception):
    pass


class UpdateNotSupported(Exception):
    pass


def get_update_download_urls(download_uuid):
    url = f'https://uupdump.net/json-api/get.php?id={download_uuid}&lang=en-us&edition=professional'
    r = requests.get(url)

    if r.status_code == 500:
        error = r.json()['response']['error']
        if error == 'EMPTY_FILELIST':
            raise UpdateNotFound

    if r.status_code == 400:
        error = r.json()['response']['error']
        if error == 'UNSUPPORTED_COMBINATION':
            raise UpdateNotSupported

    r.raise_for_status()

    files = r.json()['response']['files']

    urls = []
    for file in files:
        # Skip metadata ESD files which contain partial content and can't be
        # extracted with 7z.
        if file.lower() in [
            'professional_en-us.esd',
            'metadataesd_professional_en-us.esd',
        ]:
            continue

        # Skip other unsupported files.
        if file.lower() in [
            'winre.wim',
            'wim_edge.wim',
            'edge.wim',
        ]:
            continue

        extension = Path(file).suffix.lower()
        if extension not in ['.cab', '.esd', '.psf', '.msu', '.wim']:
            raise Exception(f'Unknown file extension: {extension}')

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

        args = ['aria2c', '-x4', '-d', local_dir, '-o', name, '--allow-overwrite=true', url]
        while True:
            result = subprocess.run(args, stdout=None if config.verbose_run else subprocess.DEVNULL)
            if result.returncode == 0:
                break

            # https://aria2.github.io/manual/en/html/aria2c.html#exit-status
            if result.returncode != 1:
                raise Exception(f'Failed to download {name} from {url} (exit code {result.returncode})')

            print(f'[{update_kb}] Retrying download of {name} from {url}...')
            time.sleep(10)

        local_path = local_dir.joinpath(name)

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


# Delta files might be identical except for the checksum and timestamp.
#
# Header file format: [4 bytes checksum] ['PA31'] [8 bytes timestamp]
def delta_files_equal(source_file: Path, destination_file: Path):
    source_file_size = source_file.stat().st_size
    destination_file_size = destination_file.stat().st_size
    if source_file_size <= 16 or source_file_size != destination_file_size:
        return False

    source_data = source_file.read_bytes()
    destination_data = destination_file.read_bytes()

    source_header = source_data[4:8]
    destination_header = destination_data[4:8]
    if source_header != b'PA31' or source_header != destination_header:
        return False

    return source_data[16:] == destination_data[16:]


def extract_update_files(local_dir: Path):
    def cab_extract(from_file: Path, to_dir: Path):
        args = ['tools/expand/expand.exe', '-r', '-f:*']
        stdout = None if config.verbose_run else subprocess.DEVNULL
        to_dir.mkdir()

        from_file_absolute = from_file.resolve(strict=True)
        if len(str(from_file_absolute)) <= 259:
            args += [from_file_absolute, to_dir]
            subprocess.check_call(args, stdout=stdout)
            return

        # Long paths are not supported by expand.exe. Use a temporary directory
        # and a shorter path via a hard link.
        with tempfile.TemporaryDirectory(dir=os.environ.get('WINBINDEX_TEMP')) as tmpdirname:
            tmp_cab = Path(tmpdirname).joinpath('a.cab')
            os.link(from_file_absolute, tmp_cab)
            args += [tmp_cab, to_dir]
            subprocess.check_call(args, stdout=stdout)

    def run_7z_extract(from_file: Path, to_dir: Path, files: list[str] = []):
        args = ['7z.exe', 'x', from_file, f'-o{to_dir}', '-y'] + files
        subprocess.check_call(args, stdout=None if config.verbose_run else subprocess.DEVNULL)

    def psf_extract(from_file: Path, to_dir: Path, delete=False):
        # Extract delta files from the PSF file which can be found in Windows 11
        # updates. References:
        # https://www.betaarchive.com/forum/viewtopic.php?t=43163
        # https://github.com/Secant1006/PSFExtractor
        description_file = from_file.parent.joinpath('express.psf.cix.xml')
        if not description_file.exists():
            cab_file = from_file.with_suffix('.cab')
            wim_file = from_file.with_suffix('.wim')
            if cab_file.exists() and wim_file.exists():
                raise Exception(f'PSF description ambiguity: {from_file}')
            elif cab_file.exists():
                cab_extract(cab_file, to_dir)
                if delete:
                    cab_file.unlink()
            elif wim_file.exists():
                run_7z_extract(wim_file, to_dir)
                if delete:
                    wim_file.unlink()
            else:
                raise Exception(f'PSF description file not found: {from_file}')

            description_file = to_dir.joinpath('express.psf.cix.xml')

        args = ['tools/PSFExtractor.exe', '-v2', from_file, description_file, to_dir]
        subprocess.check_call(args, stdout=None if config.verbose_run else subprocess.DEVNULL)

        if delete:
            from_file.unlink()

    def msu_extract(from_file: Path, to_dir: Path):
        wim_file = from_file.with_suffix('.wim')
        if wim_file.exists():
            raise Exception(f'WIM file already exists: {wim_file}')

        psf_file = from_file.with_suffix('.psf')
        if wim_file.exists():
            raise Exception(f'PSF file already exists: {psf_file}')

        run_7z_extract(from_file, from_file.parent, [wim_file.name, psf_file.name])

        if wim_file.exists() and psf_file.exists():
            run_7z_extract(wim_file, to_dir)
            wim_file.unlink()

            description_file = to_dir.joinpath('express.psf.cix.xml')
            args = ['tools/PSFExtractor.exe', '-v2', psf_file, description_file, to_dir]
            subprocess.check_call(args, stdout=None if config.verbose_run else subprocess.DEVNULL)
            description_file.unlink()
            psf_file.unlink()
            return
        elif wim_file.exists() or psf_file.exists():
            raise Exception(f'Could not extract {from_file}')

        # Try hotpatch.
        cab_file = from_file.with_name(re.sub(r'-(\w+)\.msu$', r'-Hotpatch-\g<1>.cab', from_file.name))
        if cab_file.exists():
            raise Exception(f'cab file already exists: {cab_file}')

        run_7z_extract(from_file, from_file.parent, [cab_file.name])

        if cab_file.exists():
            cab_extract(cab_file, to_dir)
            cab_file.unlink()
            return

        raise Exception(f'Could not extract {from_file}')

    next_extract_dir_num = 1

    # Extract PSF file.
    psf_files = list(local_dir.glob('*.psf'))
    if psf_files:
        # Only one PSF file per update was observed so far.
        assert len(psf_files) == 1, psf_files
        p = psf_files[0]

        extract_dir = local_dir.joinpath(f'_extract_{next_extract_dir_num}')
        print(f'Extracting {p} to {extract_dir}')
        next_extract_dir_num += 1
        psf_extract(p, extract_dir, delete=True)

    # Extract ESD files.
    esd_files = list(local_dir.glob('*.esd'))
    for esd_file in esd_files:
        extract_dir = local_dir.joinpath(f'_extract_{next_extract_dir_num}')
        print(f'Extracting {esd_file} to {extract_dir}')
        next_extract_dir_num += 1

        run_7z_extract(esd_file, extract_dir)
        esd_file.unlink()

    # Extract MSU files.
    msu_files = list(local_dir.glob('*.msu'))
    for msu_file in msu_files:
        extract_dir = local_dir.joinpath(f'_extract_{next_extract_dir_num}')
        print(f'Extracting {msu_file} to {extract_dir}')
        next_extract_dir_num += 1

        msu_extract(msu_file, extract_dir)
        msu_file.unlink()

    # Extract CAB files.
    cab_files = list(local_dir.glob('*.cab'))
    for cab_file in cab_files:
        extract_dir = local_dir.joinpath(f'_extract_{next_extract_dir_num}')
        print(f'Extracting {cab_file} to {extract_dir}')
        next_extract_dir_num += 1

        cab_extract(cab_file, extract_dir)
        cab_file.unlink()

        cab_files_nested = list(extract_dir.glob('*.cab'))
        for cab_file in cab_files_nested:
            extract_dir = local_dir.joinpath(f'_extract_{next_extract_dir_num}')
            print(f'Extracting nested {cab_file} to {extract_dir}')
            next_extract_dir_num += 1

            cab_extract(cab_file, extract_dir)
            cab_file.unlink()

    # Starting with Windows 11, manifest files are compressed with the DCM v1
    # format. Use SXSEXP to de-compress them: https://github.com/hfiref0x/SXSEXP
    #
    # Note: Run this before moving the files to a single folder (below).
    # Otherwise, there could be a file which is sometimes compressed and
    # sometimes isn't, and the equality check will fail.
    args = ['tools/sxsexp64.exe', local_dir, local_dir]
    subprocess.check_call(args, stdout=None if config.verbose_run else subprocess.DEVNULL)

    # Move all extracted files from all folders to the target folder.
    got_duplicates = False
    for extract_dir in local_dir.glob('_extract_*'):
        def ignore_files(path, names):
            source_dir = Path(path)
            relative_dir = source_dir.relative_to(extract_dir)
            destination_dir = local_dir.joinpath(relative_dir)

            ignore = []
            for name in names:
                source_file = source_dir.joinpath(name)
                if source_file.is_file():
                    # Ignore files in root folder which have different non-identical copies with the same name.
                    # Also ignore small cab archives in the root folder.
                    if source_dir == extract_dir:
                        if (name in ['update.mum', '$filehashes$.dat'] or
                            name.endswith('.cat') or
                            (name.endswith('.cab') and source_file.stat().st_size < 1024 * 1024 * 10) or
                            name.endswith('.dll')):
                            ignore.append(name)
                            continue

                    # Ignore files which already exist as long as they're identical.
                    destination_file = destination_dir.joinpath(name)
                    if destination_file.exists():
                        if not destination_file.is_file():
                            raise Exception(f'A destination item already exists and is not a file: {destination_file}')

                        can_ignore = False
                        if sha256sum(source_file) == sha256sum(destination_file):
                            can_ignore = True
                        elif 'f' in relative_dir.parts and delta_files_equal(source_file, destination_file):
                            can_ignore = True

                        if not can_ignore:
                            print(f'A different file copy already exists: {destination_file} (source: {source_file})')
                            nonlocal got_duplicates
                            got_duplicates = True
                            can_ignore = True

                        ignore.append(name)

            return ignore

        # Special cases for duplicate manifests with the same name but different content.
        for manifest_name in [
            # 10.0.26100.3613 x64
            'amd64_dual_tpm.inf_31bf3856ad364e35_10.0.26100.3613_none_bb0d74004378951e',
            'amd64_microsoft-windows-apisetschema-server_31bf3856ad364e35_10.0.26100.3613_none_87680f1423804054',
            'amd64_microsoft-windows-apisetschema-windows_31bf3856ad364e35_10.0.26100.3613_none_c5d98eaf0ac07e10',
            'amd64_microsoft-windows-b..vironment-os-loader_31bf3856ad364e35_10.0.26100.3613_none_f6d3b9591cbd3655',
            'amd64_microsoft-windows-c..egrity-driverpolicy_31bf3856ad364e35_10.0.26100.3613_none_4fe2fc8b9427845c',
            'amd64_microsoft-windows-codeintegrity_31bf3856ad364e35_10.0.26100.3613_none_3c24f064b4d63a53',
            'amd64_microsoft-windows-i..dsetup-rejuvenation_31bf3856ad364e35_10.0.26100.3613_none_ee461ec5c0d1f3e3',
            'amd64_microsoft-windows-lddmcore_31bf3856ad364e35_10.0.26100.3613_none_477597c593a31b89',
            'amd64_microsoft-windows-os-kernel_31bf3856ad364e35_10.0.26100.3613_none_07dd60c764396875',
            'amd64_microsoft-windows-win32k_31bf3856ad364e35_10.0.26100.3613_none_54a078e14a9d1fcd',
            'amd64_microsoft-windows-win32kbase_31bf3856ad364e35_10.0.26100.3613_none_4a2344ef16d3b29c',
            'amd64_microsoft-windows-win32kbasers_31bf3856ad364e35_10.0.26100.3613_none_8c00f390d7be4e6f',
            'amd64_microsoft-windows-winpe_tools_31bf3856ad364e35_10.0.26100.3613_none_96aca207e6f620ac',
            'amd64_microsoft-windows-winre-tools_31bf3856ad364e35_10.0.26100.3613_none_65aa9cdb2028863c',
            'wow64_microsoft-windows-win32k_31bf3856ad364e35_10.0.26100.3613_none_5ef523337efde1c8',

            # 10.0.26100.3613 ARM64
            'arm64_dual_tpm.inf_31bf3856ad364e35_10.0.26100.3613_none_bb0d7c3a437889ba',
            'arm64_microsoft-windows-apisetschema-server_31bf3856ad364e35_10.0.26100.3613_none_8768174e238034f0',
            'arm64_microsoft-windows-apisetschema-windows_31bf3856ad364e35_10.0.26100.3613_none_c5d996e90ac072ac',
            'arm64_microsoft-windows-b..vironment-os-loader_31bf3856ad364e35_10.0.26100.3613_none_f6d3c1931cbd2af1',
            'arm64_microsoft-windows-c..egrity-driverpolicy_31bf3856ad364e35_10.0.26100.3613_none_4fe304c5942778f8',
            'arm64_microsoft-windows-codeintegrity_31bf3856ad364e35_10.0.26100.3613_none_3c24f89eb4d62eef',
            'arm64_microsoft-windows-i..dsetup-rejuvenation_31bf3856ad364e35_10.0.26100.3613_none_ee4626ffc0d1e87f',
            'arm64_microsoft-windows-lddmcore_31bf3856ad364e35_10.0.26100.3613_none_47759fff93a31025',
            'arm64_microsoft-windows-os-kernel_31bf3856ad364e35_10.0.26100.3613_none_07dd690164395d11',
            'arm64_microsoft-windows-win32k_31bf3856ad364e35_10.0.26100.3613_none_54a0811b4a9d1469',
            'arm64_microsoft-windows-win32kbase_31bf3856ad364e35_10.0.26100.3613_none_4a234d2916d3a738',
            'arm64_microsoft-windows-win32kbasers_31bf3856ad364e35_10.0.26100.3613_none_8c00fbcad7be430b',
            'arm64_microsoft-windows-winpe_tools_31bf3856ad364e35_10.0.26100.3613_none_96acaa41e6f61548',
            'arm64_microsoft-windows-winre-tools_31bf3856ad364e35_10.0.26100.3613_none_65aaa51520287ad8',
            'arm64.x86_microsoft-windows-win32k_31bf3856ad364e35_10.0.26100.3613_none_fa357839ceef2191',

            # 10.0.26100.5516 x64
            'amd64_microsoft-windows-b..vironment-os-loader_31bf3856ad364e35_10.0.26100.5516_none_f6de48b91cb56195',
            'amd64_microsoft-windows-i..dsetup-rejuvenation_31bf3856ad364e35_10.0.26100.5516_none_ee50ae25c0ca1f23',
            'amd64_microsoft-windows-lddmcore_31bf3856ad364e35_10.0.26100.5516_none_47802725939b46c9',
            'amd64_microsoft-windows-os-kernel_31bf3856ad364e35_10.0.26100.5516_none_07e7f027643193b5',
            'amd64_microsoft-windows-s..tform-media-onecore_31bf3856ad364e35_10.0.26100.5516_none_a0de9c05919d4924',
            'amd64_microsoft-windows-u..te-orchestratorcore_31bf3856ad364e35_10.0.26100.5516_none_2289e22c34819d64',
            'amd64_microsoft-windows-win32k_31bf3856ad364e35_10.0.26100.5516_none_54ab08414a954b0d',
            'amd64_microsoft-windows-win32kbase_31bf3856ad364e35_10.0.26100.5516_none_4a2dd44f16cbdddc',
            'amd64_microsoft-windows-winre-tools_31bf3856ad364e35_10.0.26100.5516_none_65b52c3b2020b17c',
            'wow64_microsoft-windows-win32k_31bf3856ad364e35_10.0.26100.5516_none_5effb2937ef60d08',
        ]:
            if (
                extract_dir.joinpath(manifest_name).exists() and
                extract_dir.joinpath(f'{manifest_name}.manifest').exists() and
                local_dir.joinpath(manifest_name).exists() and
                local_dir.joinpath(f'{manifest_name}.manifest').exists()
            ):
                manifest_dup_dir = extract_dir.joinpath(f'{manifest_name}_dup1')
                assert not manifest_dup_dir.exists()
                extract_dir.joinpath(manifest_name).rename(manifest_dup_dir)
                
                manifest_dup_file = extract_dir.joinpath(f'{manifest_name}_dup1.manifest')
                assert not manifest_dup_file.exists()
                extract_dir.joinpath(f'{manifest_name}.manifest').rename(manifest_dup_file)

        shutil.copytree(extract_dir, local_dir, copy_function=shutil.move, dirs_exist_ok=True, ignore=ignore_files)
        shutil.rmtree(extract_dir)

    if got_duplicates:
        raise Exception('Duplicate files found')

    # Make sure there are no archive files left.
    archives_left = [p for p in local_dir.glob('*') if p.suffix in {'.cab', '.psf', '.wim', '.msu', '.esd'}]
    if archives_left:
        raise Exception(f'Unexpected archive files left: {archives_left}')

    # Unpack null differential files.
    for file in local_dir.glob('*/n/**/*'):
        if file.is_file():
            unpack_null_differential_file(file, file)

    # Use DeltaDownloader to extract meaningful data from delta files:
    # https://github.com/m417z/DeltaDownloader
    args = ['tools/DeltaDownloader/DeltaDownloader.exe', '/g', local_dir]
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
