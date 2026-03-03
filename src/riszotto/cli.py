import typer

app = typer.Typer()


@app.command()
def search():
    """Search for papers in your Zotero library."""
    typer.echo("search: not implemented")


@app.command()
def info():
    """Show metadata for a paper."""
    typer.echo("info: not implemented")


@app.command()
def show():
    """Convert a paper's PDF to markdown."""
    typer.echo("show: not implemented")
