let
  pkgs = import <nixpkgs> {};
in pkgs.mkShell {
  packages = [    
    # Add tkinter support (usually comes with Python but may need explicit inclusion in Nix)
    pkgs.python3Packages.tkinter
    
    # X11 libraries needed for tkinter GUI
    pkgs.xorg.libX11
    pkgs.xorg.libXext
    pkgs.xorg.libXrender
    pkgs.xorg.libXft
  ];
  
  # Set environment variables for GUI applications
  shellHook = ''
    export DISPLAY=''${DISPLAY:-:0}
    echo "Python browser development environment ready!"
  '';
}