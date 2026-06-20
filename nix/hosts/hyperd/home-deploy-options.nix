{ lib, ... }:
{
  # Git identity (user.name, user.email) is written directly to ~/.gitconfig
  # by nixos-quick-deploy.sh so it remains mutable after every switch.
  # Only enable git and optionally set the credential helper here.
  programs.git = {
    enable = lib.mkDefault true;
    settings = {
      credential.helper = lib.mkDefault "!gh auth git-credential";
    };
  };

  # Gemini / AI Studio API key — resilience anchor for delegate-to-gemini.
  # The gemini npm CLI caches this in ~/.gemini/gemini-credentials.json after
  # first auth, so the env var is not required day-to-day. Set it here so that
  # if the credential cache is wiped, re-auth works without manual shell steps.
  # Obtain from: https://aistudio.google.com/apikey  (free tier available)
  # Routes through generativelanguage.googleapis.com (NOT sunset cloudcode-pa).
  #
  # Uncomment and fill in your key:
  # home.sessionVariables.GEMINI_API_KEY = "AIza...";
}
