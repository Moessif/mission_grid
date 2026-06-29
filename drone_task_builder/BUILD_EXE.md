# Build EXE

This project can be packaged as a Windows desktop app with `PyInstaller`.

## One-click build

Run:

```bat
build_exe.bat
```

This script will:

1. Install dependencies from `requirements.txt`
2. Run `PyInstaller`
3. Output the packaged app to:

```text
dist\DroneTaskBuilder
```

## Manual build

```bash
python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm --clean --name DroneTaskBuilder --windowed app.py
```

## Result

After packaging, the main executable will be under:

```text
dist\DroneTaskBuilder\DroneTaskBuilder.exe
```

## Notes

- This build packages the Windows GUI app only.
- The generated drone mission bundles are still exported separately by the app itself.
- The packaged app does not modify the original drone-side files on the desktop.
