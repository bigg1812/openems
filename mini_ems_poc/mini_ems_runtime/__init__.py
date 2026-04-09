"""Runtime modules for the Mini EMS proof of concept."""


def main():
    from .app import main as app_main

    return app_main()


__all__ = ["main"]
