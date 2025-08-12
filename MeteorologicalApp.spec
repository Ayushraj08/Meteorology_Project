# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# In MeteorologicalApp.spec
a = Analysis(['app.py'],
             pathex=['.'],
             binaries=[],
             datas=[
                 ('templates', 'templates'),
                 ('static', 'static')
             ],
             hiddenimports=['matplotlib.backends.backend_agg', 'waitress'],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)

pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='MeteorologicalApp',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=False, # Set to False for --windowed
          icon='static\drdo_logo.png')