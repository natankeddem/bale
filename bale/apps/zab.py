options = {
    "dry-run": {
        "control": "label",
        "required": False,
        "description": "Dry run, dont change anything, just show what would be done (still does all read-only operations)",
    },
    "verbose": {"control": "label", "required": False, "description": "verbose output"},
    "debug": {"control": "label", "required": False, "description": "Show zfs commands that are executed, stops after an exception."},
    "debug-output": {"control": "label", "required": False, "description": "Show zfs commands and their output/exit codes. (noisy)"},
    "progress": {
        "control": "label",
        "required": False,
        "description": "show zfs progress output. Enabled automaticly on ttys. (use --no-progress to disable)",
    },
    "utc": {
        "control": "label",
        "required": False,
        "description": "Use UTC instead of local time when dealing with timestamps for both formatting and parsing. To snapshot in an ISO 8601 compliant time format you may for example specify --snapshot-format '{}-%Y-%m-%dT%H:%M:%SZ'. Changing this parameter after-the-fact (existing snapshots) will cause their timestamps to be interpreted as a different time than before.",
    },
    "version": {"control": "label", "required": False, "description": "Show version."},
    "ssh-config": {"control": "input", "required": True, "description": "Custom ssh client config."},
    "ssh-source": {"control": "input", "required": True, "description": "Source host to pull backup from."},
    "ssh-target": {"control": "input", "required": True, "description": "Target host to push backup to."},
    "property-format": {"control": "input", "required": False, "description": "Dataset selection string format. Default: autobackup:{}"},
    "snapshot-format": {"control": "input", "required": False, "description": "ZFS Snapshot string format. Default: {}-%Y%m%d%H%M%S}"},
    "hold-format": {"control": "input", "required": False, "description": "FORMAT  ZFS hold string format. Default: zfs_autobackup:{}"},
    "strip-path": {"control": "input", "required": False, "description": "Number of directories to strip from target path."},
    "exclude-unchanged": {
        "control": "input",
        "required": False,
        "description": "Exclude datasets that have less than BYTES data changed since any last snapshot. (Use with proxmox HA replication)",
    },
    "exclude-received": {
        "control": "label",
        "required": False,
        "description": "Exclude datasets that have the origin of their autobackup: property as 'received'. This can avoid recursive replication between two backup partners.",
    },
    "no-snapshot": {
        "control": "label",
        "required": False,
        "description": "Don't create new snapshots (useful for finishing uncompleted backups, or cleanups)",
    },
    "pre-snapshot-cmd": {
        "control": "input",
        "required": False,
        "description": "Run COMMAND before snapshotting (can be used multiple times.",
    },
    "post-snapshot-cmd": {
        "control": "input",
        "required": False,
        "description": "Run COMMAND after snapshotting (can be used multiple times.",
    },
    "min-change": {"control": "input", "required": False, "description": "Only create snapshot if enough bytes are changed. (default 1)"},
    "allow-empty": {
        "control": "label",
        "required": False,
        "description": "If nothing has changed, still create empty snapshots. (Same as --min-change=0)",
    },
    "other-snapshots": {
        "control": "label",
        "required": False,
        "description": "Send over other snapshots as well, not just the ones created by this tool.",
    },
    "set-snapshot-properties": {"control": "input", "required": False, "description": "List of properties to set on the snapshot."},
    "no-send": {
        "control": "label",
        "required": False,
        "description": "Don't transfer snapshots (useful for cleanups, or if you want a separate send-cronjob)",
    },
    "no-holds": {
        "control": "label",
        "required": False,
        "description": "Don't hold snapshots. (Faster. Allows you to destroy common snapshot.)",
    },
    "clear-refreservation": {
        "control": "label",
        "required": False,
        "description": "Filter 'refreservation' property. (recommended, saves space. same as --filter-properties refreservation)",
    },
    "clear-mountpoint": {
        "control": "label",
        "required": False,
        "description": "Set property canmount=noauto for new datasets. (recommended, prevents mount conflicts. same as --set-properties canmount=noauto)",
    },
    "filter-properties ": {
        "control": "input",
        "required": False,
        "description": "List of properties to 'filter' when receiving filesystems. (you can still restore them with zfs inherit -S)",
    },
    "set-properties": {
        "control": "input",
        "required": False,
        "description": "List of propererties to override when receiving filesystems. (you can still restore them with zfs inherit -S)",
    },
    "rollback": {
        "control": "label",
        "required": False,
        "description": "Rollback changes to the latest target snapshot before starting. (normally you can prevent changes by setting the readonly property on the target_path to on)",
    },
    "force": {
        "control": "label",
        "required": False,
        "description": "Use zfs -F option to force overwrite/rollback. (Useful with --strip-path=1, but use with care)",
    },
    "destroy-incompatible": {
        "control": "label",
        "required": False,
        "description": "Destroy incompatible snapshots on target. Use with care! (implies --rollback)",
    },
    "ignore-transfer-errors": {
        "control": "label",
        "required": False,
        "description": "Ignore transfer errors (still checks if received filesystem exists. useful for acltype errors)",
    },
    "decrypt": {"control": "label", "required": False, "description": "Decrypt data before sending it over."},
    "encrypt": {"control": "label", "required": False, "description": "Encrypt data after receiving it."},
    "zfs-compressed": {"control": "input", "required": False, "description": "Transfer blocks that already have zfs-compression as-is."},
    "compress": {
        "control": "input",
        "required": False,
        "description": "Use compression during transfer, defaults to zstd-fast if TYPE is not specified. (gzip, pigz-fast, pigz-slow, zstd-fast, zstd-slow, zstd-adapt, xz, lzo, lz4)",
    },
    "rate": {"control": "input", "required": False, "description": "Limit data transfer rate in Bytes/sec (e.g. 128K. requires mbuffer.)"},
    "buffer": {
        "control": "input",
        "required": False,
        "description": "Add zfs send and recv buffers to smooth out IO bursts. (e.g. 128M. requires mbuffer)",
    },
    "send-pipe": {
        "control": "input",
        "required": False,
        "description": "pipe zfs send output through COMMAND (can be used multiple times)",
    },
    "recv-pipe": {"control": "input", "required": False, "description": "pipe zfs recv input through COMMAND (can be used multiple times)"},
    "no-thinning": {"control": "label", "required": False, "description": "Do not destroy any snapshots."},
    "keep-source": {
        "control": "input",
        "required": False,
        "description": "Thinning schedule for old source snapshots. Default: 10,1d1w,1w1m,1m1y",
    },
    "keep-target": {
        "control": "input",
        "required": False,
        "description": "Thinning schedule for old target snapshots. Default: 10,1d1w,1w1m,1m1y",
    },
    "destroy-missing": {
        "control": "input",
        "required": False,
        "description": "Destroy datasets on target that are missing on the source. Specify the time since the last snapshot, e.g: --destroy-missing 30d",
    },
}
