# Tracking initial installer passwords

NixOS installers (both the minimal ISO and the Calamares GUI image) create the
first user by writing one of the *initial* password options into the generated
`/etc/nixos/configuration.nix`. Depending on whether the installer captured a
hashed value or plain text, the user entry ends up with either
`initialHashedPassword` or `initialPassword`, and may optionally set
`forceInitialPassword` to require a password change on first login. The
migration script keeps those directives verbatim if it sees them in the source
configuration so the resulting system matches the installer defaults.【F:lib/config.sh†L1406-L1518】

When neither `initial*` option nor a persistent `hashedPassword` directive is
present, the script copies the current `/etc/shadow` hash into the generated
configuration to avoid locking the account. That behaviour mirrors how NixOS
stores established passwords after the initial activation step has already
moved the hash into `/etc/shadow`. This is the final fallback before emitting a
warning and fabricating a temporary password.【F:lib/config.sh†L1522-L1539】

Therefore, if the installer-generated configuration still contains an
`initialHashedPassword` value, you can rely on the migration helper to carry it
forward safely. If you stripped that directive earlier, make sure the user has
logged in at least once so `/etc/shadow` contains a valid hash prior to running
`nixos-quick-deploy.sh`; otherwise the resulting configuration will trigger the
warning you observed.

## Root user password synchronization

As of v4.1.1+, the deployment script also configures the **root** user account
with the same password hash as the primary user. This is required for emergency
mode access:

- When NixOS drops to emergency/rescue mode (due to boot failures), it uses
  `sulogin` which requires root authentication.
- Without a root password configured, the system enters an unrecoverable
  "root account is locked" state.
- By syncing the root password with the primary user, single-user systems
  maintain easy emergency access while avoiding separate credential management.

If you need a different root password, you can manually edit the generated
`configuration.nix` after deployment to set `users.users.root.hashedPassword`
to a different value. Run `mkpasswd -m sha-512` to generate a new hash.
