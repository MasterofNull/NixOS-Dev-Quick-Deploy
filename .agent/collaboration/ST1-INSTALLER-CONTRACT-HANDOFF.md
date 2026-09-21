# ST-1 installer-contract handoff

Status: WIP implementation; unreviewed and not accepted.

- Source module/import/profile baseline came from `768849ea`; it remains
  default-off and does not change any host configuration.
- Installer catalog and fieldset project exactly one new field:
  `roles.agenticToolchain.enable`.
- The execution-receipt golden MAC was regenerated from the resolved receipt
  after the bound catalog and fieldset bytes changed. The verifier remains
  activation-blocked; no authorization or activation behavior was weakened.
- ST-2 is already independently implemented at `4017e5d9`; ST-1's design text
  now avoids describing it as a future slice.

Excluded: host enablement, rebuild/switch, runtime activation, factory installer
or payload changes, provider calls, staging, final acceptance, and final commit.
