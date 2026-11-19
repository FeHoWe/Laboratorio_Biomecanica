"""Exceções do NEXUS BIOMECHANICS."""


class NexusError(Exception):
    """Base de todas as exceções do projeto."""


class ProjectError(NexusError):
    """Erro genérico de projeto."""


class ProjectIOError(ProjectError):
    """Falha de leitura/escrita de projeto em disco."""


class ProjectValidationError(ProjectError):
    """Arquivo de projeto inválido ou corrompido."""


class SimulationCancelled(NexusError):
    """Operação cancelada pelo usuário."""
