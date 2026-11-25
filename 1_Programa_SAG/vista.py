"""
vista.py – Todo lo que se dibuja en la terminal (rich) y la captura de datos.

Los menús nunca usan print() ni input() directamente: llaman a esta clase.
Así la presentación queda separada de la lógica.
"""
from __future__ import annotations

from datetime import date, datetime, time
from typing import Callable, Iterable, Optional, Sequence

from rich import box
from rich.align import Align
from rich.columns import Columns
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Prompt
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from modelos import DIAS, Cancelado
from repositorio import coincide_codigo

GUINDA = "#c0396b"
ACENTO = "cyan"

BANNER = r"""
 ███████╗  █████╗   ██████╗
 ██╔════╝ ██╔══██╗ ██╔════╝
 ███████╗ ███████║ ██║  ███╗
 ╚════██║ ██╔══██║ ██║   ██║
 ███████║ ██║  ██║ ╚██████╔╝
 ╚══════╝ ╚═╝  ╚═╝  ╚═════╝
"""

COLORES_ESTADO = {
    "Activa": "green", "Activo": "green", "Sí": "green",
    "Vencida": "yellow", "Sin membresía": "bright_black",
    "Cancelada": "red", "Inactivo": "red", "Cerrada": "red", "No": "red",
}


# --------------------------------------------------------------- formatos
def f_fecha(d: Optional[date]) -> str:
    return d.strftime("%d/%m/%Y") if d else "—"


def f_hora(t: Optional[time]) -> str:
    return t.strftime("%H:%M") if t else "—"


def f_fecha_hora(dt: datetime) -> str:
    return dt.strftime("%d/%m/%Y %H:%M")


def dinero(valor: float) -> str:
    return f"${valor:,.2f}"


def estado(texto: str) -> str:
    return f"[{COLORES_ESTADO.get(texto, 'white')}]● {texto}[/]"


def barra(valor: float, maximo: float, ancho: int = 20) -> str:
    llenos = 0 if maximo <= 0 else round(ancho * min(valor / maximo, 1))
    color = "green" if llenos < ancho * 0.7 else "yellow" if llenos < ancho else "red"
    return f"[{color}]{'█' * llenos}[/][bright_black]{'░' * (ancho - llenos)}[/]"


def t(texto: str) -> str:
    """Escapa texto capturado por el usuario para que rich no lo interprete."""
    return escape(texto or "—")


class Vista:
    """Capa de presentación de SAG."""

    def __init__(self):
        self.consola = Console()

    # ----------------------------------------------------------- pantallas
    def encabezado(self, titulo: str, usuario=None) -> None:
        c = self.consola
        c.clear()
        c.print(Align.center(Text(BANNER, style=f"bold {GUINDA}")))
        c.print(Align.center("[bold]Sistema Administrativo de Gimnasios[/]  [dim]· Plaza Sendero, Tijuana[/]"))
        if usuario:
            c.print(Align.center(
                f"[dim]Sesión:[/] [bold]{usuario.nombre_completo}[/]  "
                f"[dim]·[/] [{ACENTO}]{usuario.rol.nombre_rol}[/]  "
                f"[dim]· {f_fecha(date.today())}[/]"))
        c.print(Rule(f"[bold white] {titulo} [/]", style=GUINDA))
        c.print()

    def menu(self, titulo: str, opciones: Sequence[str], salida: str = "Cerrar sesión") -> int:
        tabla = Table.grid(padding=(0, 2))
        tabla.add_column(justify="right", style=f"bold {ACENTO}")
        tabla.add_column()
        for i, texto in enumerate(opciones, 1):
            tabla.add_row(str(i), texto)
        tabla.add_row("[bold red]0[/]", f"[red]{salida}[/]")
        self.consola.print(Align.center(Panel(tabla, title=f"[bold]{titulo}[/]",
                                              border_style=GUINDA, padding=(1, 4),
                                              box=box.ROUNDED)))
        validas = [str(i) for i in range(len(opciones) + 1)]
        return int(Prompt.ask(f"\n[{ACENTO}]›[/] Elige una opción", choices=validas,
                              show_choices=False))

    def tabla(self, titulo: str, columnas: Sequence[str], filas: Iterable[Sequence],
              derecha: Sequence[str] = (), pie: Optional[str] = None) -> int:
        filas = list(filas)
        if not filas:
            self.aviso("No hay registros para mostrar.")
            return 0
        tabla = Table(title=f"[bold]{titulo}[/]", box=box.ROUNDED, border_style="bright_black",
                      header_style=f"bold white on {GUINDA}", title_justify="left")
        for col in columnas:
            tabla.add_column(col, justify="right" if col in derecha else "left")
        for fila in filas:
            tabla.add_row(*[("—" if v is None or v == "" else str(v)) for v in fila])
        self.consola.print(tabla)
        self.consola.print(f"[dim]{pie or f'{len(filas)} registro(s)'}[/]\n")
        return len(filas)

    def ficha(self, titulo: str, datos: dict, color: str = ACENTO) -> None:
        grid = Table.grid(padding=(0, 2))
        grid.add_column(style="dim", justify="right")
        grid.add_column()
        for k, v in datos.items():
            grid.add_row(k, str(v))
        self.consola.print(Panel(grid, title=f"[bold]{titulo}[/]", border_style=color,
                                 expand=False, padding=(1, 3)))

    def tarjetas(self, datos: dict) -> None:
        """Mini tablero: una tarjeta por indicador."""
        paneles = [Panel(Align.center(f"[bold {ACENTO}]{v}[/]\n[dim]{k}[/]"),
                         border_style="bright_black", width=24) for k, v in datos.items()]
        self.consola.print(Align.center(Columns(paneles)))
        self.consola.print()

    # ----------------------------------------------------------- mensajes
    def exito(self, msg: str) -> None:
        self.consola.print(Panel(f"[bold green]✔ {msg}[/]", border_style="green", expand=False))

    def error(self, msg: str) -> None:
        self.consola.print(Panel(f"[bold red]✖ {msg}[/]", border_style="red", expand=False))

    def aviso(self, msg: str) -> None:
        self.consola.print(Panel(f"[yellow]⚠ {msg}[/]", border_style="yellow", expand=False))

    def info(self, msg: str) -> None:
        self.consola.print(f"[{ACENTO}]ℹ[/] {msg}")

    def seccion(self, titulo: str) -> None:
        self.consola.print(Rule(f"[bold]{titulo}[/]", style="bright_black", align="left"))

    def pausa(self) -> None:
        Prompt.ask("\n[dim]Presiona Enter para continuar[/]", default="", show_default=False)

    # ----------------------------------------------------------- captura
    def texto(self, msg: str, default: Optional[str] = None, obligatorio: bool = True) -> str:
        while True:
            valor = Prompt.ask(msg, default=default if default is not None else "",
                               show_default=bool(default)).strip()
            if valor or not obligatorio:
                return valor
            self.consola.print("[red]  Este dato es obligatorio.[/]")

    def contrasena(self, msg: str = "Contraseña") -> str:
        return Prompt.ask(msg, password=True)

    def entero(self, msg: str, default: Optional[int] = None, minimo: int = 1) -> int:
        while True:
            valor = self.texto(msg, None if default is None else str(default))
            if valor.isdigit() and int(valor) >= minimo:
                return int(valor)
            self.consola.print(f"[red]  Escribe un número entero mayor o igual a {minimo}.[/]")

    def decimal(self, msg: str, default: Optional[float] = None) -> float:
        while True:
            valor = self.texto(msg, None if default is None else f"{default:.2f}")
            try:
                numero = float(valor.replace(",", "").replace("$", ""))
                if numero > 0:
                    return numero
            except ValueError:
                pass
            self.consola.print("[red]  Escribe una cantidad mayor que 0.[/]")

    def fecha(self, msg: str, default: Optional[date] = None) -> date:
        while True:
            valor = self.texto(f"{msg} [dim](dd/mm/aaaa)[/]", f_fecha(default) if default else None)
            try:
                return datetime.strptime(valor, "%d/%m/%Y").date()
            except ValueError:
                self.consola.print("[red]  Fecha no válida. Ejemplo: 25/12/2026[/]")

    def hora(self, msg: str, default: Optional[time] = None) -> time:
        while True:
            valor = self.texto(f"{msg} [dim](HH:MM)[/]", f_hora(default) if default else None)
            try:
                return datetime.strptime(valor, "%H:%M").time()
            except ValueError:
                self.consola.print("[red]  Hora no válida. Ejemplo: 07:30[/]")

    def dia(self, default: Optional[str] = None) -> str:
        self.consola.print("  " + "  ".join(f"[{ACENTO}]{i}[/] {d}" for i, d in enumerate(DIAS, 1)))
        extra = {"default": str(DIAS.index(default) + 1)} if default else {}
        n = Prompt.ask("Día", choices=[str(i) for i in range(1, 8)], show_choices=False, **extra)
        return DIAS[int(n) - 1]

    def dias(self, actuales: Sequence[str] = ()) -> list[str]:
        """Varios días a la vez: «1,3» = Lunes y Miércoles."""
        self.consola.print("  " + "  ".join(f"[{ACENTO}]{i}[/] {d}" for i, d in enumerate(DIAS, 1)))
        defecto = ",".join(str(DIAS.index(d) + 1) for d in actuales) or None
        while True:
            texto = self.texto("Días [dim](números separados por coma, ej. 1,3)[/]", defecto)
            partes = [p.strip() for p in texto.split(",") if p.strip()]
            if partes and all(p.isdigit() and 1 <= int(p) <= 7 for p in partes):
                return sorted({DIAS[int(p) - 1] for p in partes}, key=DIAS.index)
            self.consola.print("[red]  Escribe números del 1 al 7 separados por coma.[/]")

    def celulares(self, actuales: Sequence[str] = ()) -> list[str]:
        lista: list[str] = []
        if actuales:
            self.info(f"Celulares actuales: {', '.join(actuales)} (se reemplazarán)")
        while True:
            etiqueta = "Celular" if not lista else "Otro celular [dim](Enter para terminar)[/]"
            valor = self.texto(etiqueta, obligatorio=not lista)
            if not valor:
                return lista
            if valor.isdigit() and len(valor) == 10:
                lista.append(valor)
            else:
                self.consola.print("[red]  El celular debe tener 10 dígitos.[/]")

    def confirmar(self, msg: str = "¿Confirmas la operación?") -> bool:
        return Prompt.ask(f"[bold yellow]{msg}[/] [dim](S/N)[/]", choices=["S", "N", "s", "n"],
                          show_choices=False).upper() == "S"

    def si_no(self, msg: str, default: bool = True) -> bool:
        return Prompt.ask(f"{msg} [dim](S/N)[/]", choices=["S", "N", "s", "n"],
                          default="S" if default else "N", show_choices=False).upper() == "S"

    def opcion(self, msg: str, opciones: Sequence[str]) -> int:
        """Pregunta en línea entre varias opciones. Regresa el índice (0 = primera)."""
        self.consola.print("  " + "   ".join(f"[{ACENTO}]{i}[/] {o}" for i, o in enumerate(opciones, 1)))
        return int(Prompt.ask(msg, choices=[str(i) for i in range(1, len(opciones) + 1)],
                              show_choices=False)) - 1

    def elegir(self, items: Iterable, titulo: str, columnas: Sequence[str],
               fila: Callable, derecha: Sequence[str] = (), opcional: bool = False,
               pregunta: str = "Código"):
        """Muestra una tabla y pide el código de un elemento.

        Enter vacío cancela la operación (o regresa None si opcional=True)."""
        items = list(items)
        if not items:
            if opcional:
                return None
            raise Cancelado("No hay registros disponibles.")
        self.tabla(titulo, columnas, [fila(x) for x in items], derecha)
        while True:
            texto = Prompt.ask(f"{pregunta} [dim](Enter para {'omitir' if opcional else 'cancelar'})[/]",
                               default="", show_default=False).strip()
            if not texto:
                if opcional:
                    return None
                raise Cancelado()
            elegido = next((x for x in items if coincide_codigo(x.codigo, texto)), None)
            if elegido:
                return elegido
            self.consola.print("[red]  Código no encontrado en la lista.[/]")
