# Overleaf upload

Create the upload bundle from this directory:

```bash
make overleaf-zip
```

Upload `dist/ICRA2027_overleaf.zip` with **New Project > Upload Project** in
Overleaf. The archive has `main.tex` at its root and contains a regular copy of
the Zotero-generated bibliography rather than the local symbolic link.

Overleaf does not synchronize changes back to this repository. Keep the local
repository as the authoritative source, download any intentional web edits,
and merge them locally before generating the next upload bundle.
