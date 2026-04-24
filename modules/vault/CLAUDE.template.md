# {project_name} — Vault

This project manages encrypted file storage and secrets. The AI helps choose the right
tool for a given threat model, generate encryption and key management scripts, automate
encrypted backups, and advise on key rotation and secure practices.

## Key software

- **VeraCrypt** — encrypted containers and full-disk encryption
  - Create: `veracrypt --create` (interactive) or via GUI
  - Mount: `veracrypt /path/to/container /mnt/vault`
  - Unmount: `veracrypt -d /mnt/vault`
- **GPG** — asymmetric and symmetric encryption, signing, key management
  - Generate key: `gpg --full-generate-key`
  - Encrypt: `gpg -e -r user@example.com file.txt` → `file.txt.gpg`
  - Decrypt: `gpg -d file.txt.gpg > file.txt`
  - Export public key: `gpg --export --armor user@example.com > pubkey.asc`
- **age** — simple, modern file encryption (recommended for scripting)
  - Generate key: `age-keygen -o ~/.age/key.txt`
  - Encrypt: `age -r $(cat ~/.age/key.txt | grep public) -o out.age in.txt`
  - Decrypt: `age -d -i ~/.age/key.txt out.age > in.txt`
- **KeePassXC** — local password manager; KDBX format; has TOTP and SSH agent support
  - CLI: `keepassxc-cli show database.kdbx entry-name`
- **LUKS** — Linux full-disk or partition encryption
  - Format: `cryptsetup luksFormat /dev/sdX`
  - Open: `cryptsetup open /dev/sdX vault_name`
  - Mount: `mount /dev/mapper/vault_name /mnt/vault`
- **YubiKey / Nitrokey** — hardware security key; use with GPG (`gpg --card-status`),
  SSH (`ssh-add -s /usr/lib/opensc-pkcs11.so`), and TOTP

## Key management best practices

- Ed25519 for SSH (preferred over RSA 4096 for new keys): `ssh-keygen -t ed25519 -C "label"`
- Add to agent: `ssh-add ~/.ssh/id_ed25519`; verify: `ssh-add -l`
- GPG key size: RSA 4096 or Ed25519/Cv25519 curve keys
- Set key expiry (1–2 years) and extend when needed — never delete expired keys
- Store the revocation certificate separately from the key
- Backup passphrases in KeePassXC, not in plain text

## Encrypted backup pattern

```bash
#!/bin/bash
# Encrypt with age and sync to cloud
tar czf - ~/sensitive-docs | \
  age -r $(cat ~/.age/key.txt | grep public) -o backup-$(date +%F).tar.gz.age
rclone copy backup-*.age remote:vault-backups/
```

## Typical tasks

- Generate an SSH or GPG key pair with appropriate parameters
- Write a backup script that encrypts before syncing to cloud storage
- Create a VeraCrypt container of a given size
- Advise on tool selection given a threat model
- Write a key rotation procedure for SSH or GPG
- Configure GPG to use a YubiKey or hardware token
- Audit which services use which credentials (from inventory below)

## Security principle

Encrypt first, then sync. Never store unencrypted sensitive files in cloud storage,
version control, or shared folders. Keep encryption keys separate from encrypted data.

---

## Your setup

<!-- Purpose — what are you protecting?
     e.g. personal documents, SSH/GPG keys, password database, seed phrases -->

<!-- Encryption tools in use:
     VeraCrypt / GPG / age / KeePassXC / LUKS / other -->

<!-- Key and credential inventory (no actual secrets — just descriptions):
     e.g.
     - GPG key for email signing (fingerprint: ABCD1234)
     - SSH key for GitHub (~/.ssh/id_ed25519)
     - VeraCrypt container at ~/vault.vc (personal documents)
     - KeePassXC database at ~/passwords.kdbx -->

<!-- Backup and sync strategy:
     e.g. nightly age-encrypted backup to Backblaze B2 via rclone,
     weekly rsync of encrypted container to external drive -->

<!-- Threat model:
     e.g. laptop theft, cloud provider breach, accidental deletion,
     account compromise, physical access by untrusted parties -->

## Notes for the AI

<!-- Key rotation schedule, passphrase policy, hardware token (YubiKey model),
     or any workflows already in place that should not be changed. -->
