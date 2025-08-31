{ pkgs ? import <nixpkgs> {} }:
(pkgs.buildFHSEnv {
  name = "pydev";
  targetPkgs = pkgs: [
    pkgs.python313
    pkgs.python313.pkgs.virtualenv
    pkgs.nodejs
    pkgs.pnpm
  ];

  profile = ''

    source .venv/bin/activate
  '';

  runScript = ''

    if [ ! -d .venv ]; then
      python -m venv .venv
      source .venv/bin/activate
      pip install -e ".[dev,testing,docs]"
    fi

    exec bash --login
  '';
}).env
