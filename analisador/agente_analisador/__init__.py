"""Agente Analisador: executa pytest e devolve erros estruturados em JSON."""

from agente_analisador.agent import AnalisadorAgent
from agente_analisador.schemas import AnalisadorResult, Failure, Summary

__all__ = ["AnalisadorAgent", "AnalisadorResult", "Failure", "Summary"]
__version__ = "0.1.0"
