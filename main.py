"""Ponto de entrada do NEXUS BIOMECHANICS."""
import sys

from application.application import run

if __name__ == "__main__":
    sys.exit(run(sys.argv[1:]))
