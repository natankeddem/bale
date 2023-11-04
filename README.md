# snapper: ZFS Snapshot GUI

https://github.com/natankeddem/snapper/assets/44515217/e26fef13-4fc4-44c3-96a7-70d846f7344d

## ⚠️ **_WARNING_**
**This utility is currently in early development and may undergo breaking changes in future updates. Your configuration may be lost, and snapshot functionality might be affected. Use with caution; data loss may occur.**

## Features

- **Remote Management**: Snapper handles all interactions over SSH, eliminating the need for local installation. You can manage your ZFS snapshots from anywhere.
- **Multi-Host Support**: Configure Snapper to manage multiple hosts within the same installation, making it a versatile choice for system administrators.
- **User-Friendly GUI**: Easily manage your ZFS snapshots with an intuitive web-based interface that simplifies the process.
- **Automation**: Snapper can automate generic remote and local applications as well as work seamlessly with zfs_autobackup, streamlining your backup and snapshot tasks.

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

Access snapper by navigating to `http://host:8080`.

---
