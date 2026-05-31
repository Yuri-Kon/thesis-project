{
  description = "Development shell for thesis-project.dev";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs =
    { nixpkgs, ... }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
    in
    {
      devShells = forAllSystems (
        system:
        let
          pkgs = import nixpkgs { inherit system; };

          corePackages = with pkgs; [
            bashInteractive
            coreutils
            curl
            git
            jq
            openssh
            pkg-config
            rsync
            tmux

            python312
            uv

            nodejs_24
            typescript

            jdk21_headless
            nextflow

            texlive.combined.scheme-full
            texlab
          ];

          bioCliPackages =
            with pkgs;
            [
              blast-bin
              dssp
              mmseqs2
            ]
            ++ lib.optionals (pkgs ? foldseek) [
              foldseek
            ];
        in
        {
          default = pkgs.mkShell {
            packages = corePackages ++ bioCliPackages;

            env = {
              UV_PROJECT_ENVIRONMENT = ".venv";
              UV_PYTHON = "${pkgs.python312}/bin/python3.12";
              NXF_HOME = ".nextflow";
            };

            shellHook = ''
              echo "thesis-project.dev shell"
              echo "  Python: $(python --version)"
              echo "  uv:     $(uv --version)"
              echo "  Node:   $(node --version)"
              echo ""
              echo "Common commands:"
              echo "  uv sync"
              echo "  uv run pytest"
              echo "  uv run basedpyright"
              echo "  npm install && npm run check:ui"
              echo "  nextflow -version"
            '';
          };
        }
      );
    };
}
