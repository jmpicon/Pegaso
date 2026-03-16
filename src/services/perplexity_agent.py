"""
Pegaso Personal Agent — powered by Perplexity AI.
Agente con herramientas de control del ordenador: archivos, shell, sistema.
Usa Perplexity sonar-pro con tool calling estilo OpenAI.
"""
import os
import json
import sys
from typing import Optional
from openai import OpenAI

from src.tools.computer_tools import TOOL_FUNCTIONS, TOOL_SCHEMAS

# ──────────────────────────────────────────────
# Cliente Perplexity
# ──────────────────────────────────────────────

def _get_client() -> OpenAI:
    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        raise ValueError(
            "PERPLEXITY_API_KEY no configurada.\n"
            "Añádela a .env: PERPLEXITY_API_KEY=tu-clave"
        )
    return OpenAI(
        api_key=api_key,
        base_url="https://api.perplexity.ai",
    )


MODEL = os.getenv("PERPLEXITY_MODEL", "sonar-pro")

SYSTEM_PROMPT = """Eres Pegaso, el asistente personal de José. Tienes acceso completo a su ordenador Linux.

Tus capacidades:
- Gestionar archivos y carpetas (listar, mover, copiar, eliminar, crear, organizar)
- Ejecutar comandos de terminal
- Leer y escribir archivos
- Obtener información del sistema
- Abrir aplicaciones
- Buscar archivos por nombre o patrón
- Analizar uso de disco
- Buscar información en internet (capacidad nativa de Perplexity)

Principios de operación:
1. SIEMPRE confirma antes de eliminar archivos o ejecutar comandos destructivos
2. Para operaciones grandes usa dry_run=true primero para mostrar el plan
3. Responde en español, de forma concisa y directa
4. Si no estás seguro de una ruta, usa list_directory para explorar primero
5. Proporciona resúmenes claros de lo que has hecho

Eres proactivo: si ves que algo se puede mejorar, lo sugieres. Si hay un error, lo explicas claramente."""


# ──────────────────────────────────────────────
# Motor del agente
# ──────────────────────────────────────────────

class PegasoAgent:
    def __init__(self, max_iterations: int = 10, verbose: bool = True):
        self.client = _get_client()
        self.model = MODEL
        self.max_iterations = max_iterations
        self.verbose = verbose
        self.history: list[dict] = []

    def reset(self):
        """Reinicia el historial de conversación."""
        self.history = []

    def _log(self, msg: str):
        if self.verbose:
            print(msg, flush=True)

    def _execute_tool(self, tool_name: str, tool_args: dict) -> str:
        """Ejecuta una herramienta y devuelve el resultado como JSON string."""
        if tool_name not in TOOL_FUNCTIONS:
            return json.dumps({"error": f"Herramienta desconocida: {tool_name}"})
        try:
            result = TOOL_FUNCTIONS[tool_name](**tool_args)
            return json.dumps(result, ensure_ascii=False, default=str)
        except Exception as e:
            return json.dumps({"error": f"Error ejecutando {tool_name}: {e}"})

    def chat(self, user_message: str) -> str:
        """
        Procesa un mensaje del usuario ejecutando el ciclo agente:
        llm → herramientas → llm → ... → respuesta final
        """
        self.history.append({"role": "user", "content": user_message})

        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + self.history

        for iteration in range(self.max_iterations):
            # Llamada al LLM
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=TOOL_SCHEMAS,
                    tool_choice="auto",
                    temperature=0.2,
                    max_tokens=2048,
                )
            except Exception as e:
                error_msg = f"Error conectando con Perplexity: {e}"
                self.history.append({"role": "assistant", "content": error_msg})
                return error_msg

            choice = response.choices[0]
            finish_reason = choice.finish_reason
            assistant_msg = choice.message

            # Añadir respuesta del asistente al historial
            messages.append({
                "role": "assistant",
                "content": assistant_msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in (assistant_msg.tool_calls or [])
                ] or None,
            })

            # Si no hay tool calls → respuesta final
            if not assistant_msg.tool_calls or finish_reason == "stop":
                final = assistant_msg.content or ""
                self.history.append({"role": "assistant", "content": final})
                return final

            # Ejecutar herramientas
            for tool_call in assistant_msg.tool_calls:
                name = tool_call.function.name
                try:
                    args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    args = {}

                self._log(f"\n  [tool] {name}({json.dumps(args, ensure_ascii=False)[:120]})")
                result = self._execute_tool(name, args)
                self._log(f"  [result] {result[:200]}{'...' if len(result) > 200 else ''}")

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })

        # Si llegamos aquí, demasiadas iteraciones
        return "Demasiadas iteraciones. Intenta reformular la petición."


# ──────────────────────────────────────────────
# Función de conveniencia para uso directo
# ──────────────────────────────────────────────

_default_agent: Optional[PegasoAgent] = None


def get_agent() -> PegasoAgent:
    global _default_agent
    if _default_agent is None:
        _default_agent = PegasoAgent()
    return _default_agent


def ask(message: str) -> str:
    """Envía un mensaje al agente y devuelve la respuesta."""
    return get_agent().chat(message)
