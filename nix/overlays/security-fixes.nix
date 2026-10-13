# Declarative security fixes overlay.
# Governed by Rule 19 (Root-Cause Discipline) — zero suppression in .grype.yaml;
# addresses CVEs in the NixOS closure at package definition level.
#
# Fixes:
# - Alert #2916 [HIGH]: CVE-2026-103484 (pgvector 0.8.2 -> 0.8.7)
#   Fixes out-of-bounds write in IVFFlat index build leading to arbitrary code execution.
# - Alert #2917 [LOW]:  CVE-2026-106587 (openssh 10.5p1 -> 10.6p1)
#   Fixes configuration option "none" treated as filename in sshd.
final: prev: let
  newPgvector = prev.postgresql_17.pkgs.pgvector.overrideAttrs (_old: {
    version = "0.8.7";
    src = final.fetchFromGitHub {
      owner = "pgvector";
      repo = "pgvector";
      tag = "v0.8.7";
      hash = "sha256-YYXz8zqiuqYWpJwImAhMry/QTLHKOP5MzuY0Of+aflc=";
    };
  });
in {
  postgresql_17 = prev.postgresql_17 // {
    pkgs = prev.postgresql_17.pkgs // {
      pgvector = newPgvector;
    };
    withPackages = f: prev.postgresql_17.withPackages (ps: f (ps // { pgvector = newPgvector; }));
  };

  postgresql = final.postgresql_17;
  postgresqlPackages = final.postgresql_17.pkgs;

  openssh = prev.openssh.overrideAttrs (_old: rec {
    version = "10.6p1";
    src = final.fetchurl {
      url = "mirror://openbsd/OpenSSH/portable/openssh-${version}.tar.gz";
      hash = "sha256-qdyVZd/+hkD2TYY80poyvEo9vewFZqf8RMXW7nZ9Xzk=";
    };
  });
}
