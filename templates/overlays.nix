[
  (final: prev:
    let
      overlayLib = if prev ? lib then prev.lib else final.lib;
      kernelLib = if overlayLib ? kernel then overlayLib.kernel else builtins.throw "nix overlay: lib.kernel unavailable";
    in {
      linuxPackages = prev.linuxPackages // {
        kernel = prev.linuxPackages.kernel.override {
          structuredExtraConfig = with kernelLib; {
            HZ_1000 = yes;
            HZ = 1000;
            PREEMPT_FULL = yes;
            IOSCHED_BFQ = yes;
            DEFAULT_BFQ = yes;
            DEFAULT_IOSCHED = "bfq";
            V4L2_LOOPBACK = module;
            HID = yes;
          };
        };
      };
    })
]
