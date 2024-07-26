from pathlib import Path
from unittest import mock

import factory
import pygscholar
import pytest
from pygscholar.cli import app
from typer.testing import CliRunner

runner = CliRunner(mix_stderr=False)


def create_args(
    author: pygscholar.AuthorInfo, backend: pygscholar.api.APIBackend, cache_dir: str
) -> tuple[list[str], pygscholar.api.APIBackend]:
    args = [
        "add-author",
        author.name,
        "--scholar-id",
        author.scholar_id,
        "--cache-dir",
        str(cache_dir),
    ]
    if backend == "":
        backend = pygscholar.api.APIBackend.SCRAPER

    args += [
        "--backend",
        str(backend),
    ]

    return args, backend


@pytest.mark.parametrize("backend", ["scholarly", "scraper"])
def test_add_author_simple(tmpdir, backend):
    author = factory.AuthorInfoFactory.build()
    args, backend = create_args(author, backend, tmpdir)

    with mock.patch(f"pygscholar.api.{backend}.search_author") as m:
        m.return_value = [author]

        result = runner.invoke(app, args)
    assert result.exit_code == 0, result.stderr

    assert (
        f"Successfully added author with name {author.name} and scholar id {author.scholar_id}"
        in result.stdout
    )


@pytest.mark.parametrize("backend", ["scholarly", "scraper"])
def test_add_author_with_name_that_already_exist(tmpdir, backend):
    author = factory.AuthorInfoFactory.build()
    args, backend = create_args(author, backend, tmpdir)
    args2, _ = create_args(author, backend, tmpdir)
    args2[3] = "23432refw"  # Change scholar id

    with mock.patch(f"pygscholar.api.{backend}.search_author") as m:
        m.return_value = [author]
        result = runner.invoke(app, args)
        result = runner.invoke(app, args2)

    assert result.exit_code == 101
    assert f"Author with name {author.name} already exist in database" in result.stderr


@pytest.mark.parametrize("backend", ["scholarly", "scraper"])
def test_add_author_with_scholar_id_that_already_exist(tmpdir, backend):
    author = factory.AuthorInfoFactory.build()

    args, backend = create_args(author, backend, tmpdir)

    with mock.patch(f"pygscholar.api.{backend}.search_author") as m:
        m.return_value = [author]

        result = runner.invoke(app, args)
        args[1] = "Another name"
        result = runner.invoke(app, args)

    assert result.exit_code == 102
    assert "There is already an author with the provided scholar id" in result.stderr


@pytest.mark.parametrize("backend", ["scholarly", "scraper"])
def test_list_author(tmpdir, backend):
    author1 = factory.AuthorInfoFactory.build()
    author2 = factory.AuthorInfoFactory.build()
    args1, backend = create_args(author1, backend, tmpdir)
    args2, backend = create_args(author2, backend, tmpdir)
    with mock.patch(f"pygscholar.api.{backend}.search_author") as m:
        m.return_value = [author1, author2]

        result1 = runner.invoke(app, args1)
        result2 = runner.invoke(app, args2)

        result = runner.invoke(app, ["list-authors", "--cache-dir", tmpdir])

    assert result1.exit_code == 0
    assert result2.exit_code == 0
    assert result.exit_code == 0
    assert author1.name in result.stdout
    assert author2.name in result.stdout
    assert author1.scholar_id in result.stdout
    assert author2.scholar_id in result.stdout


@pytest.mark.parametrize("backend", ["scholarly", "scraper"])
def test_list_author_publications_when_no_author_is_added(tmpdir, backend):
    author = factory.AuthorFactory.build()
    with mock.patch(f"pygscholar.api.{backend}.search_author") as m:
        m.return_value = []
        result = runner.invoke(
            app,
            [
                "list-author-publications",
                author.name,
                "--cache-dir",
                tmpdir,
            ],
        )

    assert result.exit_code == 1
    assert f"Unable to find name '{author.name}'. Possible options are \n" == str(
        result.exception,
    )


@pytest.mark.parametrize("backend", ["scholarly", "scraper"])
def test_list_author_publications(tmpdir, backend):
    author = factory.AuthorFactory.build()
    args1, backend = create_args(author.info, backend, tmpdir)

    with mock.patch(f"pygscholar.api.{backend}.search_author") as m:
        m.return_value = [author.info]
        runner.invoke(app, args1)

        with mock.patch("pygscholar.api.search_author_with_publications") as m:
            m.return_value = author
            result = runner.invoke(
                app,
                [
                    "list-author-publications",
                    author.name,
                    "--cache-dir",
                    str(tmpdir),
                ],
            )

    assert result.exit_code == 0
    assert f"Publications for {author.name} (Sorted by citations)" in result.stdout
    for pub in author.publications:
        assert pub.title in result.stdout
        assert str(pub.year) in result.stdout
        assert str(pub.num_citations) in result.stdout


def test_list_dep_new_publications(tmpdir):
    old_author = factory.AuthorFactory.build()

    authors_file = Path(tmpdir).joinpath("authors.json")
    pygscholar.utils.dump_json({old_author.name: old_author.scholar_id}, authors_file)

    dep = pygscholar.Department(authors=(old_author,))
    publications_file = Path(tmpdir).joinpath("publications.json")
    pygscholar.utils.dump_json(dep.dict(), publications_file)

    # Create a new publication
    new_pub = factory.PublicationFactory.build()

    author_dict = old_author.dict()
    author_dict["publications"] = (author_dict["publications"][0], new_pub.dict())
    new_author = pygscholar.Author(**author_dict)

    with mock.patch("pygscholar.api.scholarly.scholarly") as m:
        m.search_author = lambda name: iter([new_author.dict()])
        m.fill = lambda x: x
        result = runner.invoke(
            app,
            [
                "list-new-dep-publications",
                "--no-add-authors",
                "--cache-dir",
                tmpdir,
            ],
        )

    assert result.exit_code == 0
    assert "New publications" in result.stdout
    assert new_pub.title in result.stdout
