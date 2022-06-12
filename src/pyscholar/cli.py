import difflib
import os
from pathlib import Path
from typing import List
from typing import Optional
from typing import Protocol

import typer
from pyscholar.publication import Publication
from rich.console import Console
from rich.table import Table
from scholarly import MaxTriesExceededException

from . import scholar_api
from . import utils

# from . import Department
# from . import scholar_api

DEFAULT_CACHE_DIR = os.getenv(
    "PYSCHOLAR_CACHE_DIR",
    Path.home().joinpath(".pyscholar").as_posix(),
)
app = typer.Typer()


def version_callback(show_version: bool):
    """Prints version information."""
    if show_version:
        from . import __version__, __program_name__

        typer.echo(f"{__program_name__} {__version__}")
        raise typer.Exit()


def license_callback(show_license: bool):
    """Prints license information."""
    if show_license:
        from . import __license__

        typer.echo(f"{__license__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show version",
    ),
    license: bool = typer.Option(
        None,
        "--license",
        callback=license_callback,
        is_eager=True,
        help="Show license",
    ),
):
    # Do other global stuff, handle other global options here
    return


@app.command(help="List all authors")
def list_authors(cache_dir: str = DEFAULT_CACHE_DIR):
    authors_file = Path(cache_dir).joinpath("authors.json")
    authors = utils.load_json(authors_file)

    table = Table(title="Authors")

    table.add_column("Name", justify="right", style="cyan", no_wrap=True)
    table.add_column("Scholar ID", style="magenta")

    for name, scholar_id in authors.items():
        print(name)
        table.add_row(name, scholar_id)

    console = Console()
    console.print(table)


@app.command(help="Add new author")
def add_author(name: str, scholar_id: str = "", cache_dir: str = DEFAULT_CACHE_DIR):
    authors_file = Path(cache_dir).joinpath("authors.json")
    authors = utils.load_json(authors_file)

    if name in authors:
        typer.echo(f"Author with name {name} already exist in database", err=True)
        raise typer.Exit(101)
    if scholar_id != "" and scholar_id in authors.values():
        typer.echo("There is already an author with the provided scholar id", err=True)
        raise typer.Exit(102)

    try:
        author = scholar_api.get_author(name, scholar_id=scholar_id, fill=False)
    except MaxTriesExceededException:
        typer.echo("Unable to find author online...")
    else:
        name = author.name

        if scholar_id == "":
            scholar_id = author.scholar_id

    authors[name] = scholar_id
    utils.dump_json(authors, authors_file)
    typer.echo(
        f"Successfully added author with name {name} and scholar id {scholar_id}",
    )


@app.command(help="Remove author")
def remove_author(name: str, cache_dir: str = DEFAULT_CACHE_DIR):
    authors_file = Path(cache_dir).joinpath("authors.json")
    authors = utils.load_json(authors_file)
    if name not in authors:
        closest_name = difflib.get_close_matches(name, authors.keys())[0]
        typer.echo(
            f"Could not find author with name '{name}'. Did you mean '{closest_name}'?",
            err=True,
        )
        raise typer.Exit(103)

    authors.pop(name)
    utils.dump_json(authors, authors_file)
    typer.echo(f"Successfully removed author with name {name}")


def print_publications(publications, sort_by_citations, add_authors, name):
    sort_txt = "(Sorted by "
    if sort_by_citations:
        sort_txt += "citations)"
    else:
        sort_txt += "age)"
    table = Table(title=f"Publications for {name} {sort_txt}")
    table.add_column("Title", style="cyan")
    if add_authors:
        table.add_column("Authors", style="magenta")
    table.add_column("Published year", style="green")
    table.add_column("Number of citations", style="yellow")
    for pub in publications:

        try:
            year = str(pub.year)
        except ValueError:
            year = "Unknown"
        if add_authors:
            full_pub = pub.fill()
            table.add_row(pub.title, full_pub.authors, year, str(pub.num_citations))
        else:
            table.add_row(pub.title, year, str(pub.num_citations))

    console = Console()
    console.print(table)


class PublicationObject(Protocol):
    def topk_cited(self, k: int) -> List[Publication]:
        ...

    def topk_age(self, k: int) -> List[Publication]:
        ...

    def topk_cited_not_older_than(self, k: int, age: int) -> List[Publication]:
        ...

    def topk_age_not_older_than(self, k: int, age: int) -> List[Publication]:
        ...


def extract_correct_publications(
    obj: PublicationObject,
    sort_by_citations: bool,
    max_age: Optional[int],
    n: int,
) -> List[Publication]:
    if sort_by_citations:
        if max_age is None:
            publications = obj.topk_cited(k=n)
        else:
            publications = obj.topk_cited_not_older_than(k=n, age=max_age)
    else:
        if max_age is None:
            publications = obj.topk_age(k=n)
        else:
            publications = obj.topk_age_not_older_than(k=n, age=max_age)

    return publications


@app.command(help="List authors publications")
def list_author_publications(
    name: str,
    n: int = 5,
    sort_by_citations: bool = True,
    add_authors: bool = False,
    max_age: Optional[int] = None,
    cache_dir: str = DEFAULT_CACHE_DIR,
):
    authors_file = Path(cache_dir).joinpath("authors.json")
    authors = utils.load_json(authors_file)
    if name not in authors:
        _name = name
        name = difflib.get_close_matches(_name, authors.keys())[0]
        typer.echo(
            f"Could not find author with name '{_name}'. Will use '{name}' instead",
        )

    author = scholar_api.get_author(name=name, scholar_id=authors[name], fill=True)
    publications = extract_correct_publications(author, sort_by_citations, max_age, n)
    print_publications(publications, sort_by_citations, add_authors, name)


@app.command(help="List department publications")
def list_department_publications(
    n: int = 5,
    sort_by_citations: bool = True,
    add_authors: bool = False,
    max_age: Optional[int] = None,
    cache_dir: str = DEFAULT_CACHE_DIR,
):

    authors_file = Path(cache_dir).joinpath("authors.json")
    authors = utils.load_json(authors_file)
    dep = scholar_api.extract_scholar_publications(authors)

    publications = extract_correct_publications(dep, sort_by_citations, max_age, n)
    print_publications(publications, sort_by_citations, add_authors, "department")
