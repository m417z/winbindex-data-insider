# winbindex-data-insider

This repository hosts the indexed data of Windows Insider builds for Winbindex,
and updates it on a regular basis with GitHub Actions.

The data in this repository is indexed with the help of [UUP
dump](https://uupdump.net/), using the [UUP dump
API](https://git.uupdump.net/uup-dump/api). When new builds are released, the
scripts extract and index all supported binaries.

## Winbindex

Winbindex is an index of Windows binaries, including download links for
executables such as exe, dll and sys files. For details please refer to [the
main repository](https://github.com/m417z/winbindex).

## Flow of scripts

![winbindex-scripts-flow.png](winbindex-scripts-flow.png)
