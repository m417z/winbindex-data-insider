from pathlib import Path

out_path_override = Path('.out_path_override')
out_path = Path(out_path_override.read_text().strip() if out_path_override.exists() else '.')
index_of_hashes_title = 'Winbindex Insider Hashes'
index_of_hashes_out_path = out_path / 'hashes'

deploy_save_disk_space = True
deploy_amend_last_commit = True

updates_unsupported = set()

updates_max_age_days = 60
updates_never_removed = False
allow_missing_sha256_hash = True
allow_unknown_non_pe_files = True

verbose_run = False
verbose_progress = True
extract_in_a_new_thread = False
exit_on_first_error = True
high_mem_usage_for_performance = False
compression_level = 3
group_by_filename_processes = 4

delta_machine_type_values_supported = {
    'CLI4_I386',
    'CLI4_AMD64',
    'CLI4_ARM',
    'CLI4_ARM64',
}

delta_data_without_rift_table_names = {
    '*.mui',
    'powershell_ise.exe',
    'stdole32.tlb',
    'microsoft.grouppolicy.interop.dll',
}
delta_data_without_rift_table_manifests = {
    'amd64_microsoft-nxt-boottocloud-windows365-app_*',
    'arm64_microsoft-nxt-boottocloud-windows365-app_*',
}
delta_data_without_rift_table_hashes = set()

# Non-PE files (very rare).
file_hashes_non_pe = {
    'af700c04f4334cdf9fc575727a055a30855e1ab6a8a480ab6335e1b4a7585173',  # tapi.dll
    '3d922f8b608401af4f34f71dbacfa458cef1f7bfffedd7febee0a968e51d6dce',  # twain.dll
    '103035a32e7893d702ced974faa4434828bc03b0cc54d1b2e1205a2f2575e7c9',  # twunk_16.exe

    # Some x86 files.
    'c929c0893bba4c6454632d3408ee4f7661b51cf5c2ce20035dcd4283cd623c85',  # ansi.sys
    '491fc48842186dfca9e217869ee3a502667f7ea107b71bc60ef7052580dba39a',  # append.exe
    'ee589c26791b66742f7b5e183a44c56a13053dc584b0dca3fcc20cd87bdca69e',  # comm.drv
    '0e70bce4b742482c5bfb69b323a3863b43e22211954e82480335c66fa3c03217',  # commdlg.dll
    '3387135a5075439b9238d6c486b047d4dba8d9a6d1dad6bb74050347c70616db',  # ctl3dv2.dll
    'ff1219f444920188d9849d4f975a777c9f24b01284999a94cecc0bba2f2a05d2',  # ddeml.dll
    '9c230aa1caff2ff9d845514017b3e4bbe7b308ad26ad88740967651f7955cd60',  # debug.exe
    '4453ae49089cf3d6ab3f3df606e58b6793ffe19ba09d13846d5ac98f81b101ed',  # dosx.exe
    '38875b94605490ed59e24cb1e7a82bc84a0844d6dcbbe72d9d003d1ffd709a69',  # drwatson.exe
    '9d835a8a46406fcb01f4509550cc86ea2755c3084c95c744cbec79d8d94c0477',  # edlin.exe
    'edf4009a2ab45a30ae3291b0f8c9585de9a15b6a1262288ae6694d4693cb737e',  # exe2bin.exe
    '69dabbdb754b358ac4fe4b22de04c0e4c93076816f14bb0730caa9fd223996fc',  # fastopen.exe
    '8959219d6421f27fd1f345d09105438cdd5a333e1eafb2e9a9ec6bf3ec9914e8',  # gdi.exe
    '08aa2c47d835460ed3067fa7d6f8a3b37edeca524ad102b0588fdd1bf389ce08',  # himem.sys
    '7a5740602ef47292583b3ef7f9cc39cb43d3e430cd7b472a84198c6fe3fdd3d4',  # keyboard.drv
    '8df46d3aa6d9572a02864eb45f4206b4308f7d0057eaf9799e03454221080006',  # krnl386.exe
    '60204f58744d38e9201ba958d45c483ce7989b216b98a67ce5aa355af37dec02',  # lanman.drv
    'faf467ce496dd59655ccd91c26c8ea694551f54fa6bbf5f480f398fc54d12fdd',  # lzexpand.dll
    'a80dbaa332171e734b4c505c4d81f4d2fc9bed538991c20f69ccf308489a893a',  # mem.exe
    '6b6250d91cd8dabb3e070539c33c9796ca1d86d912903290061549669f4b6b03',  # mmsystem.dll
    '2fa5611bb18edd9c0f35e0a6b479b9d9db17549aed811ab692bd79c3e899f890',  # mouse.drv
    'fe0948dea02fd25554ce3e4aa3323c5af3a41936acbea9dff170c8508efd91cb',  # mscdexnt.exe
    '30a8ed7453779195ad196d2e0a024e05619688c6a101e6b5ae8c6647608bbb1a',  # netapi.dll
    'a49e8c6c392f0fd323b52c1fa612420a9fc0258ba59413ccb3d2d19b1f229ee8',  # nlsfunc.exe
    '66cdd0ab42e21058926a946ded7f19e080404dd703f801b4003deafeac93be85',  # ntdos.sys
    '5dae653054d410dbb7de1708d3b0d9504600d52c99d87ff3bb99885030f7d526',  # ntdos404.sys
    'b7b0f5901ba94da08d3402237d542d4824cf22ed61c68c391793967954217f6b',  # ntdos411.sys
    'c542ec3cd20f57f55144d0d8165b7a61ee7809f98de58df8ed5a69aeccd9e83b',  # ntdos412.sys
    '16f545fc02ebb2e560a0188bdb3e0b50b3aca1975de1f1cdc49247f433d79118',  # ntdos804.sys
    '4f4cc60cfa05e36c125c851e63f7e22af25696eed99797e90518eaf0af6242a7',  # ntio404.sys
    '3da5a984ea7196624828c677b68c5836c7e0fca4cd139865f034376b60f28732',  # ntio411.sys
    'a9150876b58ffe232bb65da845c55224b1b701ba747b5e3fcc55c615698fbacc',  # ntio412.sys
    'bdbc36ce5c4bff55d4564df525ac8c4e5fda6919bfb448389a5eddd2422a2756',  # ntio804.sys
    'c4d49a1e05cf3e79a2937393aad24c4f50cd5473590542fe4bb9c6d82c913061',  # olecli.dll
    'e0cc3f3b516537f4d6a2f0cf70e129b7a39e87d1b53705d6d60a1cc69d0b1d4e',  # olesvr.dll
    '6ccfe02dc29219851b11e64be907b8394f9cd0d5c26f319cb1cfb1f42601bf2c',  # pmspl.dll
    'fc0b9cc87342315b1e1e4579577881d463f5fe48063ea4e5c784686562fa134c',  # redir.exe
    '3f31a33a1d3c77906e6fc509d7a1152f122892c02bbf060e541f34dd85258eab',  # setver.exe
    '69dabbdb754b358ac4fe4b22de04c0e4c93076816f14bb0730caa9fd223996fc',  # share.exe
    '988e406ad8dfa8ebafae9ff86c9631cef97045892813fad570f85f9bbeb44f71',  # shell.dll
    '4133e6095cdc2a17bd98dc8a845f3738670dfd1a1dc8fcb9ba900b77d9b18efb',  # sound.drv
    'f614d8dc0d46206a5c90a85e5f1d842a04dbe78cf7e67f1263ea615bf94cdf7a',  # sysedit.exe
    '104b6ba95431995bc808768819926246078c2353b2ef10baff99ab07ecdba1c9',  # system.drv
    '8219968dd335fed31f617ec146d65fbf9d5c10681076d3f762b7d1ec264ebdbf',  # timer.drv
    'b673812fdd612b786e89c9a9c23bb4d9f5838444be6d6bb75bc38eecdd00f32d',  # toolhelp.dll
    '7d15e9290c0d305dcc3b5b2102f7dc561d21fd540f9bd4c1fa36bf716f4da581',  # user.exe
    '6d03cf1e31748149b6d34725e293c5ee4f3bd7ddebe526285fe7ba41a1d1f5b4',  # ver.dll
    '4aa6b6f6598829ba9a02c0abf2de1b622d43b8944824407fc8b03c78b72522e8',  # vga.drv
    '06f5dcb633a958dc229eecb4cdb6c0207a7851428a5ac98792115d00efa2348a',  # wfwnet.drv
    'a53794c50a53e85fd03740e26eb7a76ebad2d290200f2d5907b2085b4d3edc9e',  # wifeman.dll
    'd3a72576176ca90c8a45512ec68f2a19a715ff0b935886531a3954f90a85c43d',  # win87em.dll
    '7ad523a8f7183ddd809f6f3251e0e2e6adfc969fab5484ed13c497d92c7abbc6',  # winhelp.exe
    '16c62199b7bcf93c3fb78c77e0108bc655c0ad5558ef9e476ded5209b8bafaa5',  # winnls.dll
    '2b22a58572bb65f3fa3be137337613531d192759c48bdc4a8e37ba1911962212',  # winsock.dll
    '3dca54cc7d1791cce1f77f653b5289f1a7c993371e392fe2adc2b2c1dea8fce5',  # winspool.exe
    '5dff80711a60dbe51f3a4902b9647e15073eb1536c2f4fb66102ae40f8f985f8',  # wowdeb.exe
    '126a00e34a6516c0d382a221071ab4084031c2a89ccb6144cab960ce1f86ee2c',  # wowexec.exe
    'c20bf3630fb9deee8ae444209b1442652961922e78b4c00e64b9a538a06e2792',  # country.sys
    '49ebbeee6286bd770c8b5af4e4591e4139f0ba9ef31b48daa43b696c64f0d176',  # key01.sys
    '659e4e60a48ba8022740537c2918fcadd935b8b98dcd778bf7a6c1099fe71446',  # keyboard.sys
    'c006ab7abd1d791224f8a4c2cbf98d28e710eb6a3094f3b2c8233f41d4be7ead',  # ntio.sys
}

tcb_launcher_descriptions = ['TCB Launcher', 'TCB Launcher (Prerelease)']
tcb_launcher_large_first_section_virtual_addresses = [0x1000, 0x3000, 0x4000, 0x6000]

file_hashes_unusual_section_alignment = {
    'ede86c8d8c6b9256b926701f4762bd6f71e487f366dfc7db8d74b8af57e79bbb': {'first_section_virtual_address': 0x380, 'section_alignment': 0x80},  # ftdibus.sys
    '5bec55192eaef43b0fade13bbadfdf77eb0d45b4b281ae19d4b0b7a0c2350836': {'first_section_virtual_address': 0x2d0, 'section_alignment': 0x10},  # onnxruntime.dll
    '09ced31cad8547a9ee5dcf739565def2f4359075e56a7b699cc85971e0905864': {'first_section_virtual_address': 0x310, 'section_alignment': 0x10},  # onnxruntime.dll
    '3b0a51e1fc4d5bd3e7ec182799ad712aeeaf1dcd761d7e98bec8a0a67f7334af': {'first_section_virtual_address': 0x380, 'section_alignment': 0x80},  # e1g6032e.sys
    '7ae7316c42b47d29f72ea0618c8f2641b412a74dcc707f91e6fd9e156901fd65': {'first_section_virtual_address': 0x600, 'section_alignment': 0x200},  # e100b325.sys
    '75d5318e35813a6b6a9a17734877e6fb7ce31b415e91914c92d86e3da0a4ffb5': {'first_section_virtual_address': 0x600, 'section_alignment': 0x200},  # e1g60i32.sys
    '2dbfff4b7bc30453830523e1bdc8737dd6101102b2e178d4fabd051ff8d01dd4': {'first_section_virtual_address': 0x300, 'section_alignment': 0x80},  # efe5b32e.sys
    'cbd4667fd69c6d40118ea25cafde663a1fe4ca203fb7135e65f682d77a85a3b9': {'first_section_virtual_address': 0x480, 'section_alignment': 0x80},  # nvm62x32.sys
    '50256eeadbbc5cccf3ebaeb9020d91edb9961e7404bd41067a4290362be6962f': {'first_section_virtual_address': 0x380, 'section_alignment': 0x80},  # nvm62x64.sys
}

file_names_zero_timestamp = {
    'microsoft.ink.dll',
}

file_hashes_zero_timestamp = {
    '18dd945c04ce0fbe882cd3f234c2da2d0faa12b23bd6df7b1edc31faecf51c69',  # brlapi-0.8.dll
    '7a9113d00a274c075c58b22a3ebacf1754e7da7cfb4d3334b90367b602158d78',  # brltty.exe
}

file_hashes_small_non_signature_overlay = {
    '11efef27aea856060bdeb6d2f0d62c68088eb891997d4e99de708a6b51743148',  # brlapi-0.6.dll
    'b175123eff88d1573f451b286cd5370003a0839e53c7ae86bf22b35b7e77bad3',  # brlapi-0.6.dll
    '18dd945c04ce0fbe882cd3f234c2da2d0faa12b23bd6df7b1edc31faecf51c69',  # brlapi-0.8.dll
    '3eaa62334520b41355c5103dcd663744ba26caae3496bd9015bc399fbaf42fce',  # brltty.exe
    '69f83db2fda7545ab0a1c60056aee472bf3c70a0af7454c51e1cd449b5c7f43b',  # brltty.exe
    '7a9113d00a274c075c58b22a3ebacf1754e7da7cfb4d3334b90367b602158d78',  # brltty.exe
    'b4cc93cf4d7c2906c1929c079cd98ef00c7a33832e132ac57adde71857082e36',  # libgcc_s_dw2-1.dll
    'f6f4951f98185ba8ddcdaa43f13b8106b9b667bb7f5ee027dc51b4bca4556adc',  # crtdll.dll
    'e9c61945c0c7b887ec786832af1056334968d890fc042f0c16b8d7f80a2c0c9a',  # expsrv.dll
    '078d2cd98918638f40ce0f1fc0c3c9079ee1a6fbd3b45d6c32ab99fda642efe9',  # vbajet32.dll
    '25681fc405354e54c08e91d2d1cc3212dd17db7cb1fc85c3cb7eee73ab3bbdc8',  # vbajet32.dll
}

file_hashes_unsigned_with_overlay = {
    'cf54a8504f2dbdd7bea3acdcd065608d21f5c06924baf647955cc28b8637ae68',  # libiconv-2.dll
    'ee1df918ca67581f21eac49ae4baffca959f71d1a0676d7c35bc5fb96bea3a48',  # libiconv-2.dll
    '9eec7e5188d1a224325281e4d0e6e1d5f9f034f02bd1fadeb792d3612c72319e',  # libpdcurses.dll
    'f9b385e19b9d57a1d1831e744ed2d1c3bb8396d28f48d10120cecfe72595b222',  # libpdcursesu.dll
    '787d5c07ab0bb782dede7564840e86c468e3728e81266dae23eb8ad614bcee95',  # libpdcursesw.dll
    '6896c1f21cc9a5bc17e2e2fb645669ae708cb378c63e5eef11b3e95527f3da32',  # ctl3d32.dll
    '94ef91b4c7864bd1ecc0db099e58298708bc5d22da40132ebb1c17feb4675964',  # ctl3d32.dll
    'c8aacb7314fe061b16c0d1961f4071e144be9aa44e7e00cd89b9b6581aad6430',  # mfc40.dll
    '3ca65b6f8fca231a266248fe6f67b6a87568ba1dcf810eef355d7699f603aa22',  # mfc40u.dll
    '3b2f5858bc5181506e84f6fa09eb755fb5b5e87f48c838bb125eb01fa13cf17e',  # msvbvm60.dll
}

file_details_unsigned_with_overlay = [
    {'k': 'original name', 'v': 'WofTasks.dll', 'overlay_size': 0x200},
]

# Details: https://gist.github.com/m417z/3248c18efd942f63013b8d3035e2dc79
file_hashes_mismatch = {
    # Temporary workaround for what seems to be an incorrect SHA256 hash in
    # KB5017389 and newer Windows 11 22H2 update manifests for some of the
    # files. The files are language resource files (e.g. resources.en-GB.pri)
    # for some esoteric apps:
    # * holocamera_cw5n1h2txyewy
    # * MixedRealityLearning_cw5n1h2txyewy
    # * RoomAdjustment_cw5n1h2txyewy
    ('f8636d2d93606b0069117cb05bc8d91ecb9a09e72e14695d56a693adf419f4e8', '70db27fdd0fd76305fb1dfcd401e8cde'): {'builds'},
    ('5ca0a43e4be5f7b60cd2170b05eb4627407729c65e7e0b62ed4ef3cdf895f5c5', '6ad932076c6a059db6e9743ae06c62cf'): {'builds'},
    ('b5a73db6c73c788dd62a1e5c0aa7bc2f50a260d52b04fcec4cd0192a25c6658f', 'af8a7f7b812a40bf8a1c151d3f09a98c'): {'builds'},
    ('d52440f126d95e94a86465e78849a72df11f0c22115e5b8cda10174d69167a44', 'afbb5df39d32d142a4cca08f89bbbe8e'): {'builds'},
    ('5a3b750a6dcc984084422d5c28ac99a2f878fdfe26c7261c9bff8de77658e8f8', '7ed0e64f81f63730983913be5b3cce17'): {'builds'},
    ('5292013c895e0f412c98766ba4ed7ba5ecb24bebf00aac5b56c71bcf44891945', '886ee85f216e28ac547fe71ff2823fc4'): {'builds'},
    ('b9297098632fbb1a513f96d6d2462926144d6528c4cc426d6caed5ed234438f0', '19aabb40b6431f411f97c85fbe77d7fe'): {'builds'},
    ('700760afebec6b3d638adac2f1cbb96cb60fbe9a2e2558eb20a63f9ebbd2c74f', '1f91bbe1b8ec8c42f00ffc73cbb72247'): {'builds'},
    ('994274f4494a852c0fe8c968d054fbaf0f6f7489ea586fc84102c6ebcafeeca3', 'a0d4e4256e8d54ab86ac6505f1272219'): {'builds'},
    # wfascim_uninstall.mof in KB5025298 and newer Windows 11 21H2 updates.
    ('cee501be4532071c6fe1df2933d98f8fccba4803de481746808386c3245ad6a7', '9e51833f306f8c5c59bc8f041a9ec1bb'): {'builds'},
}
