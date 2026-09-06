---
name: external-disk-rw
description: Safely mount the Cyan_data exFAT external disk read-write for robot capture, filter training, and model artifacts, identified by stable filesystem UUID rather than USB device name.
---

# External disk read-write

For a new machine or before the first persistent setup, install the UUID-based
automount once. It creates the canonical systemd/fstab rule and verifies that
the current user can write to the disk:

```bash
bash scripts/install_cyan_data_automount.sh
```

After that, plugging the disk into any USB port is enough. Accessing
`/media/ilex/Cyan_data` activates the mount at the only permitted target.

Use the bundled recovery script only when that persistent mount is missing,
read-only, or owned by root. It targets Cyan_data filesystem UUID `3E1D-6B65`
by default and performs device, mount, read-write, ownership, and write-test
checks.

```bash
bash skills/external-disk-rw/scripts/mount_cyan_data_rw.sh
```

The recovery operation is temporary by design: it does not edit `/etc/fstab`.
Do not override the UUID for the project disk. Override the mount point only
for a separately verified recovery operation:

```bash
CYAN_DATA_MOUNTPOINT=/media/ilex/Cyan_data \
bash skills/external-disk-rw/scripts/mount_cyan_data_rw.sh
```

If mounting fails, stop capture processes and run `fsck.exfat -a` on the
unmounted partition. Never format the disk or delete data as part of this
skill. A read-only filesystem or failed write test is a hard stop for data
capture.
