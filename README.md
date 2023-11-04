# bale: ZFS Snapshot Browser Based GUI

## Demo
https://github.com/natankeddem/bale/assets/44515217/e1f3ed79-7a63-4560-afdf-f6370b8f1571

## ⚠️ **_WARNING_**

**This utility is currently in early development and may undergo breaking changes in future updates. Your configuration may be lost, and snapshot functionality might be affected. Use with caution; data loss may occur.**

## Features

- **Remote Management**: bale handles all interactions over SSH, eliminating the need for local installation. You can manage your ZFS snapshots from anywhere.
- **Multi-Host Support**: Configure bale to manage multiple hosts within the same installation, making it a versatile choice for system administrators.
- **User-Friendly GUI**: Easily manage your ZFS snapshots with an intuitive web-based interface that simplifies the process.
- **Automation**: bale can automate generic remote and local applications as well as work seamlessly with zfs_autobackup, streamlining your backup and snapshot tasks.
- **Download**: Easily download files directly from your ZFS snapshots through the web interface.

## Installation

### Using Docker

1. Download `docker-compose.yml`.

2. Customize the `docker-compose.yml` file to suit your requirements.

3. Run the application using Docker Compose:

   ```bash
   docker-compose up -d
   ```

### Using Proxmox LXC Container

1. Download `pve-install.yml` and `inv.yml`.

2. Ensure you have a compatible Debian template available and updated `inv.yml` accordingly.

3. Customize the `inv.yml` file to match your specific setup requirements.

4. Execute the Ansible playbook for Proxmox LXC container installation against your Proxmox host:

   ```bash
   ansible-playbook -i inv.yml pve-install.yml
   ```

### Access GUI

Access bale by navigating to `http://host:8080`.

---
