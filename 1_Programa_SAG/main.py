"""
SAG – Sistema Administrativo de Gimnasios

Usuarios de prueba:
    Administrador  →  admin / admin123
    Recepcionista  →  recep / recep123
    Entrenador     →  entrenador / entre123   (o diana / diana123)
"""
import sys

from rich.align import Align
from rich.panel import Panel
from rich.table import Table

from menus import MenuAdministrador, MenuEntrenador, MenuRecepcionista
from repositorio import Repositorio
from vista import ACENTO, GUINDA, Vista

# ---------------------------------------------------------------
# Configuración de la base de datos (ajusta tu usuario y contraseña)
# ---------------------------------------------------------------
DB = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password": "",   # la misma que usas para entrar a MySQL Workbench
    "database": "sag",
}


class SAG:
    """Aplicación principal: menú de inicio y autenticación (RF-01 a RF-03)."""

    MAX_INTENTOS = 3
    ROLES = [
        ("Recepcionista", MenuRecepcionista),
        ("Entrenador", MenuEntrenador),
        ("Administrador", MenuAdministrador),
    ]

    def __init__(self, repo: Repositorio):
        self.repo = repo
        self.v = Vista()

    def ejecutar(self) -> None:
        while True:
            self.v.encabezado("Bienvenido a SAG")
            self.v.consola.print(Align.center(
                "[dim]Selecciona tu tipo de usuario para iniciar sesión[/]\n"))
            opcion = self.v.menu("Menú de inicio", [nombre for nombre, _ in self.ROLES],
                                 salida="Salir del programa")
            if opcion == 0:
                if self.v.confirmar("¿Seguro que quieres salir?"):
                    return self.despedida()
                continue

            nombre_rol, ClaseMenu = self.ROLES[opcion - 1]
            usuario = self.iniciar_sesion(nombre_rol)
            if usuario is None:
                return self.despedida("Se agotaron los 3 intentos. El programa se cerrará.")

            self.repo.actualizar_estados()
            ClaseMenu(self.repo, self.v, usuario).ejecutar()   # polimorfismo

    def iniciar_sesion(self, nombre_rol: str):
        self.v.encabezado(f"Inicio de sesión · {nombre_rol}")
        self.v.consola.print(Align.center(
            "[dim]Bienvenido"))
        for intento in range(1, self.MAX_INTENTOS + 1):
            self.v.consola.print(f"[{ACENTO}]Intento {intento} de {self.MAX_INTENTOS}[/]")
            usuario = self.v.texto("Nombre de usuario")
            contrasena = self.v.contrasena()
            empleado = self.repo.autenticar(usuario, contrasena, nombre_rol)
            if empleado:
                self.v.exito(f"¡Hola, {empleado.nombre_pila}! Acceso como {nombre_rol}.")
                self.v.pausa()
                return empleado
            restantes = self.MAX_INTENTOS - intento
            self.v.error("Usuario o contraseña incorrectos" +
                         (f". Te quedan {restantes} intento(s)." if restantes else "."))
        return None

    def despedida(self, mensaje: str = "") -> None:
        self.v.consola.clear()
        grid = Table.grid()
        if mensaje:
            grid.add_row(Align.center(f"[red]{mensaje}[/]\n"))
        grid.add_row(Align.center(f"[bold {GUINDA}]Gracias por usar SAG 💪[/]"))
        self.v.consola.print(Panel(grid, border_style=GUINDA, padding=(1, 4)))


def conectar(vista: Vista) -> Repositorio:
    """Se conecta a MySQL. Si no se puede, ofrece usar datos de ejemplo en memoria."""
    try:
        from repositorio_mysql import RepositorioMySQL
        with vista.consola.status(f"[{ACENTO}]Conectando con la base de datos «{DB['database']}»..."):
            return RepositorioMySQL(**DB)
    except ImportError:
        error = "Falta el conector. Instálalo con:  pip install mysql-connector-python"
    except Exception as e:                      # mysql.connector.Error o ReglaNegocio
        error = str(e)

    vista.consola.clear()
    vista.error(f"No se pudo conectar a la base de datos.\n  {error}")
    vista.info("Revisa que MySQL esté encendido, que ya ejecutaste sag_bd.sql "
               "y que el usuario y la contraseña de DB en main.py sean correctos.")
    if not vista.si_no("¿Abrir el programa con datos de ejemplo (sin guardar)?", default=False):
        sys.exit(1)
    repo = Repositorio()
    repo.cargar_datos_demo()
    return repo


def main() -> None:
    try:
        vista = Vista()
        repo = conectar(vista)
        SAG(repo).ejecutar()
    except (KeyboardInterrupt, EOFError):
        print("\nPrograma interrumpido.")
        sys.exit(0)


if __name__ == "__main__":
    main()
