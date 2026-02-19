let
  core = [
    "com.github.tchx84.Flatseal"
    "org.gnome.FileRoller"
    "net.nokyan.Resources"
    "com.bitwarden.desktop"
    "com.google.Chrome"
    "org.mozilla.firefox"
    "org.videolan.VLC"
    "io.mpv.Mpv"
    "com.obsproject.Studio"
    "md.obsidian.Obsidian"
    "org.sqlitebrowser.sqlitebrowser"
    "com.jgraph.drawio.desktop"
    "com.prusa3d.PrusaSlicer"
    "org.blender.Blender"
    "org.freecad.FreeCAD"
    "org.openscad.OpenSCAD"
    "org.kicad.KiCad"
    "org.virt_manager.virt-manager"
    "org.gnome.Boxes"
    "org.prismlauncher.PrismLauncher"
  ];

  aiWorkstation = core ++ [
    "org.jupyter.JupyterLab"
    "com.getpostman.Postman"
    "rest.insomnia.Insomnia"
    "io.dbeaver.DBeaverCommunity"
    "io.github.shiftey.Desktop"
    "com.tradingview.tradingview"
    "com.ultimaker.cura"
  ];

  gaming = core ++ [
    "com.valvesoftware.Steam"
    "net.lutris.Lutris"
    "com.heroicgameslauncher.hgl"
    "com.usebottles.bottles"
    "org.libretro.RetroArch"
    "net.pcsx2.PCSX2"
    "org.DolphinEmu.dolphin-emu"
    "net.rpcs3.RPCS3"
    "io.github.ryubing.Ryujinx"
    "com.discordapp.Discord"
    "page.kramo.Cartridges"
  ];

  minimal = [
    "org.mozilla.firefox"
    "com.google.Chrome"
    "md.obsidian.Obsidian"
    "com.github.tchx84.Flatseal"
    "com.obsproject.Studio"
  ];
in
{
  core = core;
  ai_workstation = aiWorkstation;
  gaming = gaming;
  minimal = minimal;
}
